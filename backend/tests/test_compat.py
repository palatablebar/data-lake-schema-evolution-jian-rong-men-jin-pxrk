"""算法 B（兼容判定 + 影响传播 + 迁移单）单测。"""
from __future__ import annotations

from src.services import compat_engine, schema_diff

DATASET = {"db_name": "dwd", "table_name": "dwd_order_detail", "format": "iceberg", "format_label": "Iceberg"}
BASE = [
    {"name": "order_id", "type": "bigint", "nullable": False},
    {"name": "pay_channel", "type": "string", "nullable": True},
    {"name": "amount", "type": "decimal(12,2)", "nullable": True},
]
CONSUMERS = [
    {"id": 1, "name": "经营日报", "team": "经营分析", "owner": "李蔓", "columns": ["amount", "pay_channel"], "tasks": ["t_daily_gmv"], "reports": ["r_gmv_daily"]},
    {"id": 2, "name": "渠道对账", "team": "财务对账", "owner": "王戈", "columns": ["pay_channel"], "tasks": ["t_channel_recon"], "reports": ["r_channel_diff"]},
    {"id": 3, "name": "商家结算", "team": "商家侧", "owner": "赵晗", "columns": ["amount"], "tasks": ["t_settlement_calc"], "reports": []},
    {"id": 4, "name": "订单导出", "team": "BI 报表", "owner": "陈昊", "columns": ["order_id"], "tasks": ["t_order_export"], "reports": ["r_dump"]},
]


def run(target_fields, consumers=None):
    diff = schema_diff.diff_fields(BASE, target_fields)
    return compat_engine.evaluate(
        code="CR-TEST-0001",
        dataset=DATASET,
        base_version=3,
        diff=diff,
        consumers=CONSUMERS if consumers is None else consumers,
    )


def test_only_nullable_additions_is_backward_and_pass():
    result = run(BASE + [{"name": "ext_json", "type": "string", "nullable": True}])
    assert result["compat"] == "backward"
    assert result["gate"] == "pass"
    assert result["impact"]["task_count"] == 0
    assert result["risk"] == "low"


def test_drop_and_type_change_is_breaking_and_block():
    target = [
        {"name": "order_id", "type": "bigint", "nullable": False},
        {"name": "amount", "type": "bigint", "nullable": True},
    ]
    result = run(target)
    assert result["compat"] == "breaking"
    assert result["gate"] == "block"
    # pay_channel + amount 都被下游引用：3 个任务 / 2 张报表（order_id 那条不算影响）
    assert result["impact"]["task_count"] == 3
    assert result["impact"]["report_count"] == 2
    assert result["impact"]["consumer_count"] == 3
    assert result["risk"] == "critical"
    assert result["impact"]["affected_fields"] == ["amount", "pay_channel"]


def test_three_tasks_threshold_and_below():
    target = [
        {"name": "order_id", "type": "bigint", "nullable": False},
        {"name": "pay_channel", "type": "string", "nullable": True},
    ]
    # 只有 经营日报 + 渠道对账 引用 pay_channel → 2 个任务，breaking 但未达 ≥3 的 critical 阈值
    result = run(target)
    assert result["compat"] == "breaking"
    assert result["impact"]["task_count"] == 2
    assert result["risk"] == "high"


def test_safe_widening_only_is_backward_without_impact():
    target = [
        {"name": "order_id", "type": "bigint", "nullable": False},
        {"name": "pay_channel", "type": "string", "nullable": True},
        {"name": "amount", "type": "decimal(18,2)", "nullable": True},
    ]
    result = run(target)
    assert result["compat"] == "backward"
    assert result["gate"] == "pass"
    assert result["impact"]["task_count"] == 0


def test_migration_sql_contains_add_column_and_rollback():
    target = BASE + [
        {"name": "discount_rate", "type": "decimal(6,4)", "nullable": True},
        {"name": "currency", "type": "string", "nullable": False, "default": "CNY"},
    ]
    result = run(target)
    sql = result["migration_sql"]
    assert "ADD COLUMN discount_rate decimal(6,4)" in sql
    assert "ADD COLUMN currency string" in sql
    assert "-- 5) 回滚脚本" in sql
    assert "DROP COLUMN IF EXISTS discount_rate" in sql
    assert "CREATE OR REPLACE VIEW dwd.v_dwd_order_detail_compat" not in sql  # 无删列/改名时不需要兼容视图


def test_migration_sql_rollback_restores_dropped_column():
    target = [{"name": "order_id", "type": "bigint", "nullable": False},
              {"name": "amount", "type": "bigint", "nullable": True}]
    result = run(target)
    sql = result["migration_sql"]
    assert "ALTER TABLE dwd.dwd_order_detail ADD COLUMN pay_channel string;" in sql
    assert "ALTER COLUMN amount TYPE decimal(12,2)" in sql
    assert "CREATE OR REPLACE VIEW dwd.v_dwd_order_detail_compat" in sql
    assert "[remove_column] pay_channel" in sql


def test_impact_is_empty_when_no_consumers_registered():
    target = [{"name": "order_id", "type": "bigint", "nullable": False}]
    result = run(target, consumers=[])
    assert result["compat"] == "breaking"
    assert result["impact"]["task_count"] == 0
    assert result["risk"] == "high"  # breaking 但无下游任务
    assert result["gate"] == "block"


def test_evaluation_is_deterministic():
    target = [
        {"name": "order_id", "type": "bigint", "nullable": False},
        {"name": "amount", "type": "bigint", "nullable": True},
    ]
    assert run(target) == run(target)
