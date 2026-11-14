"""算法 B：兼容性判定 + 影响传播 + 迁移单生成（纯函数，无 DB / 无网络，可单测）。

判定口径（README「核心算法与口径」同步）：

兼容级别 compat
  breaking : diff 中存在任一 breaking 条目（删列 / 重命名 / 非安全类型变更 / 新增非空无默认）
  backward : 只有新增（含安全提升），旧读者读新表不受影响（向后兼容）
  forward  : 只有删除 / 重命名（没有新增），新读者读旧表不受影响（向前兼容）
  full     : 既有新增又有删除，但全部为安全变更

影响传播 impact
  受影响列 = change_type ∈ {remove_column, rename_column, type_change} 且 breaking 的字段
            （安全类型提升不改变读取语义，不计入影响面）
  受影响消费方 = 其 columns 与被影响列名有交集的 Consumer
  受影响任务/报表 = 这些消费方名下 tasks / reports 的并集去重计数

风险 risk
  breaking 且受影响任务 >= 3  → critical（batch-plan 验收口径）
  breaking 且受影响任务  < 3  → high
  非 breaking：任务 >= 8 → critical；>= 3 → high；>= 1 → medium；否则 low

门禁 gate
  compat == breaking → block，其余 pass
"""
from __future__ import annotations

from src.constants.enums import (
    CRITICAL_TASK_THRESHOLD,
    ChangeType,
    Compat,
    Gate,
)

IMPACT_CHANGE_TYPES = {
    ChangeType.REMOVE_COLUMN.value,
    ChangeType.RENAME_COLUMN.value,
    ChangeType.TYPE_CHANGE.value,
}


def affected_field_names(diff: list[dict]) -> list[str]:
    """被影响列 = 破坏性的删列/改名/类型变更，按 diff 顺序去重。"""
    names: list[str] = []
    for item in diff or []:
        if item.get("change_type") in IMPACT_CHANGE_TYPES and item.get("breaking"):
            if item["field"] not in names:
                names.append(item["field"])
    return names


def resolve_compat(diff: list[dict]) -> str:
    if not diff:
        return Compat.FULL.value
    breaking = any(item.get("breaking") for item in diff)
    if breaking:
        return Compat.BREAKING.value
    has_add = any(item.get("change_type") == ChangeType.ADD_COLUMN.value for item in diff)
    has_drop = any(
        item.get("change_type") in (ChangeType.REMOVE_COLUMN.value, ChangeType.RENAME_COLUMN.value)
        for item in diff
    )
    if has_add and has_drop:
        return Compat.FULL.value
    if has_drop:
        return Compat.FORWARD.value
    return Compat.BACKWARD.value


def propagate_impact(diff: list[dict], consumers: list[dict]) -> dict:
    """按 Consumer 引用列算受影响任务 / 报表，返回结构化影响面。"""
    names = set(affected_field_names(diff))
    affected: list[dict] = []
    tasks: list[str] = []
    reports: list[str] = []
    for consumer in consumers or []:
        referenced = [str(column) for column in (consumer.get("columns") or [])]
        hit = [column for column in referenced if column in names]
        if not hit:
            continue
        consumer_tasks = [str(task) for task in (consumer.get("tasks") or [])]
        consumer_reports = [str(report) for report in (consumer.get("reports") or [])]
        for task in consumer_tasks:
            if task not in tasks:
                tasks.append(task)
        for report in consumer_reports:
            if report not in reports:
                reports.append(report)
        affected.append(
            {
                "id": consumer.get("id"),
                "name": consumer.get("name"),
                "team": consumer.get("team"),
                "owner": consumer.get("owner"),
                "hit_columns": hit,
                "tasks": consumer_tasks,
                "reports": consumer_reports,
            }
        )
    affected.sort(key=lambda item: (item["team"] or "", item["name"] or ""))
    return {
        "affected_fields": sorted(names),
        "affected_consumers": affected,
        "consumer_count": len(affected),
        "task_count": len(tasks),
        "report_count": len(reports),
        "tasks": tasks,
        "reports": reports,
    }


def resolve_risk(compat: str, impact: dict) -> str:
    task_count = int(impact.get("task_count") or 0)
    if compat == Compat.BREAKING.value:
        return "critical" if task_count >= CRITICAL_TASK_THRESHOLD else "high"
    if task_count >= 8:
        return "critical"
    if task_count >= CRITICAL_TASK_THRESHOLD:
        return "high"
    if task_count >= 1:
        return "medium"
    return "low"


def resolve_gate(compat: str) -> str:
    return Gate.BLOCK.value if compat == Compat.BREAKING.value else Gate.PASS.value


def _table(db_name: str, table_name: str) -> str:
    return f"{db_name}.{table_name}"


def build_migration_sql(
    *,
    code: str,
    dataset: dict,
    base_version: int,
    diff: list[dict],
    compat: str,
    gate: str,
    impact: dict,
) -> str:
    """生成迁移单 SQL：前置校验 / 正向迁移 / 兼容视图 / 阻塞项 / 回滚脚本。"""
    db_name = dataset.get("db_name") or "dwd"
    table_name = dataset.get("table_name") or "unknown_table"
    table = _table(db_name, table_name)
    lines: list[str] = []
    add = [item for item in diff if item["change_type"] == ChangeType.ADD_COLUMN.value]
    drop = [item for item in diff if item["change_type"] == ChangeType.REMOVE_COLUMN.value]
    rename = [item for item in diff if item["change_type"] == ChangeType.RENAME_COLUMN.value]
    retype = [item for item in diff if item["change_type"] == ChangeType.TYPE_CHANGE.value]

    lines.append(f"-- 迁移单 {code} · {table}（{dataset.get('format_label') or dataset.get('format', 'iceberg')} 表）")
    lines.append(f"-- 基线版本 v{base_version}；兼容判定 {compat}；门禁 {gate}")
    lines.append(f"-- 影响面：{impact.get('consumer_count', 0)} 个下游 / {impact.get('task_count', 0)} 个任务 / "
                 f"{impact.get('report_count', 0)} 张报表")
    lines.append("-- 执行顺序：先建兼容视图 → 再改表 → 下游切换完成后回收旧列")
    lines.append("")
    lines.append("-- 1) 前置校验（有数据则先与下游确认）")
    for item in drop + [entry for entry in retype if entry["breaking"]]:
        lines.append(f"SELECT count(*) AS non_null_{item['field']} FROM {table} WHERE {item['field']} IS NOT NULL;")
    if not (drop or [entry for entry in retype if entry["breaking"]]):
        lines.append(f"SELECT count(*) AS rows_total FROM {table};")
    lines.append("")

    lines.append("-- 2) 正向迁移")
    if add:
        for item in add:
            suffix = "" if item.get("nullable") else " NOT NULL"
            lines.append(f"ALTER TABLE {table} ADD COLUMN {item['field']} {item['to_type']}{suffix};")
    for item in rename:
        lines.append(f"ALTER TABLE {table} RENAME COLUMN {item['field']} TO {item['new_name']};")
    for item in retype:
        lines.append(f"ALTER TABLE {table} ALTER COLUMN {item['field']} TYPE {item['to_type']};")
    for item in drop:
        lines.append(f"-- ALTER TABLE {table} DROP COLUMN {item['field']};  -- 待下游切换完成后单独执行")
    if not diff:
        lines.append(f"-- 无字段变化，仅登记版本：{table}")
    lines.append("")

    lines.append("-- 3) 兼容视图（给未切换的下游读旧列名）")
    projections: list[str] = []
    for item in rename:
        projections.append(f"CAST({item['new_name']} AS {item['to_type']}) AS {item['field']}")
    for item in drop:
        projections.append(f"CAST(NULL AS {item['from_type']}) AS {item['field']}")
    if projections:
        lines.append(f"CREATE OR REPLACE VIEW {db_name}.v_{table_name}_compat AS")
        lines.append("SELECT")
        lines.append("    *,")
        lines.append("    " + ",\n    ".join(projections))
        lines.append(f"FROM {table};")
        lines.append(f"-- 下游临时改读 {db_name}.v_{table_name}_compat")
    else:
        lines.append(f"-- 本次无需兼容视图（{table}）")
    lines.append("")

    lines.append("-- 4) 阻塞项")
    blockers = [item for item in diff if item["breaking"]]
    if blockers:
        for item in blockers:
            lines.append(f"-- [{item['change_type']}] {item['field']}：{item['detail']}")
    else:
        lines.append("-- 无阻塞项，门禁可直接放行")
    lines.append("")

    lines.append("-- 5) 回滚脚本（与正向迁移同一事务；按逆序执行）")
    for item in reversed(retype):
        lines.append(f"ALTER TABLE {table} ALTER COLUMN {item['field']} TYPE {item['from_type']};")
    for item in reversed(rename):
        lines.append(f"ALTER TABLE {table} RENAME COLUMN {item['new_name']} TO {item['field']};")
    for item in reversed(drop):
        lines.append(f"ALTER TABLE {table} ADD COLUMN {item['field']} {item['from_type']};")
    for item in reversed(add):
        lines.append(f"ALTER TABLE {table} DROP COLUMN IF EXISTS {item['field']};")
    if projections:
        lines.append(f"DROP VIEW IF EXISTS {db_name}.v_{table_name}_compat;")
    return "\n".join(lines) + "\n"


def evaluate(
    *,
    code: str,
    dataset: dict,
    base_version: int,
    diff: list[dict],
    consumers: list[dict],
) -> dict:
    """算法 B 总入口：返回 compat / risk / gate / impact / migration_sql。"""
    compat = resolve_compat(diff)
    impact = propagate_impact(diff, consumers)
    risk = resolve_risk(compat, impact)
    gate = resolve_gate(compat)
    sql = build_migration_sql(
        code=code,
        dataset=dataset,
        base_version=base_version,
        diff=diff,
        compat=compat,
        gate=gate,
        impact=impact,
    )
    return {"compat": compat, "risk": risk, "gate": gate, "impact": impact, "migration_sql": sql}
