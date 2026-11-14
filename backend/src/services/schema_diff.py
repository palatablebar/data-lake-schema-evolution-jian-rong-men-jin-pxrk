"""算法 A：Schema diff 与类型矩阵（纯函数，无 DB / 无网络，可单测）。

输入两个有序字段列表（`[{name, type, nullable, default}]`），输出逐字段的变更条目：
    {field, change_type, breaking, from_type, to_type, new_name, similarity, detail}

判定口径（README「核心算法与口径」同步）：

1. 重命名识别：一个「被删字段」与一个「新增字段」同时满足
     - 位置相同（在各自列表中的下标一致）
     - 规范化类型完全相同
     - 名称相似度 difflib.SequenceMatcher.ratio() >= 0.7
   则判定为 rename_column（不拆成 remove + add）。多候选取相似度最高者，一对一配对。
2. 类型矩阵（canonical 归一后比较）：
   安全提升：tinyint→int→bigint 的整数加宽；int 族→float/double；float→double；
             decimal(p,s)→decimal(p',s') 且 p'>=p、s'>=s（扩容）。
   其余类型变更（string→int、double→float、decimal→int、decimal 缩容等）一律 breaking。
3. 新增字段：nullable=True 或带 default → 安全；非空且无默认值 → breaking（存量行无法回填）。
4. 删除字段：一律 breaking（旧读者的 SELECT 会直接失败）。
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher

from src.constants.enums import ChangeType

RENAME_SIMILARITY_THRESHOLD = 0.7

# 整数族加宽阶梯：rank 越大表示表达范围越宽
INT_RANK: dict[str, int] = {"tinyint": 1, "smallint": 2, "int": 3, "bigint": 4}
FLOAT_RANK: dict[str, int] = {"float": 1, "double": 2}

_DECIMAL_RE = re.compile(r"^decimal\(\s*(\d+)\s*,\s*(\d+)\s*\)$")
_INT_ALIASES: dict[str, str] = {
    "int32": "int",
    "integer": "int",
    "long": "bigint",
    "int64": "bigint",
    "byte": "tinyint",
    "short": "smallint",
    "real": "float",
    "varchar": "string",
    "text": "string",
    "char": "string",
}


def canonical_type(text: str | None) -> str:
    """把类型写法归一：小写、去空格、别名折叠、decimal 参数紧凑化。"""
    if not text:
        return "string"
    raw = str(text).strip().lower().replace(" ", "")
    match = _DECIMAL_RE.match(raw)
    if match:
        return f"decimal({int(match.group(1))},{int(match.group(2))})"
    if raw.startswith("decimal"):
        # decimal 没带精度时按 10,0 处理，避免误判成安全提升
        return "decimal(10,0)"
    return _INT_ALIASES.get(raw, raw)


def parse_type(text: str | None) -> tuple[str, tuple[int, ...]]:
    canon = canonical_type(text)
    match = _DECIMAL_RE.match(canon)
    if match:
        return "decimal", (int(match.group(1)), int(match.group(2)))
    return canon, ()


def is_safe_promotion(from_type: str | None, to_type: str | None) -> bool:
    """类型变更是否属于安全提升（不丢精度、旧数据可被新读者读完）。"""
    src_kind, src_args = parse_type(from_type)
    dst_kind, dst_args = parse_type(to_type)
    if src_kind == dst_kind:
        if src_kind != "decimal":
            return True  # 同名类型，等价
        src_p, src_s = src_args
        dst_p, dst_s = dst_args
        return dst_p >= src_p and dst_s >= src_s  # decimal 扩容；缩容 breaking
    if src_kind in INT_RANK and dst_kind in INT_RANK:
        return INT_RANK[dst_kind] >= INT_RANK[src_kind]
    if src_kind in INT_RANK and dst_kind in FLOAT_RANK:
        return True
    if src_kind in FLOAT_RANK and dst_kind in FLOAT_RANK:
        return FLOAT_RANK[dst_kind] >= FLOAT_RANK[src_kind]
    return False


def name_similarity(left: str, right: str) -> float:
    return round(SequenceMatcher(None, (left or "").lower(), (right or "").lower()).ratio(), 4)


def _normalize(fields: list[dict]) -> list[dict]:
    normalized: list[dict] = []
    for index, item in enumerate(fields or []):
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        normalized.append(
            {
                "name": name,
                "type": canonical_type(item.get("type")),
                "nullable": bool(item.get("nullable", True)),
                "default": item.get("default"),
                "comment": item.get("comment") or "",
                "position": index,
            }
        )
    return normalized


def _add_is_breaking(field: dict) -> bool:
    return (not field["nullable"]) and field.get("default") in (None, "")


def diff_fields(base_fields: list[dict], target_fields: list[dict]) -> list[dict]:
    """比较两份字段列表，返回按「破坏性优先、再按位置」排序的 diff 列表。"""
    base = _normalize(base_fields)
    target = _normalize(target_fields)
    base_index = {item["name"]: item for item in base}
    target_index = {item["name"]: item for item in target}

    removed = [item for item in base if item["name"] not in target_index]
    added = [item for item in target if item["name"] not in base_index]

    # 1) 先做重命名配对（位置 + 同类型 + 名称相似度）
    renames: list[dict] = []
    used_removed: set[str] = set()
    used_added: set[str] = set()
    candidates: list[tuple[float, dict, dict]] = []
    for old in removed:
        for new in added:
            if old["position"] != new["position"]:
                continue
            if old["type"] != new["type"]:
                continue
            score = name_similarity(old["name"], new["name"])
            if score >= RENAME_SIMILARITY_THRESHOLD:
                candidates.append((score, old, new))
    candidates.sort(key=lambda entry: (-entry[0], entry[1]["position"], entry[1]["name"]))
    for score, old, new in candidates:
        if old["name"] in used_removed or new["name"] in used_added:
            continue
        used_removed.add(old["name"])
        used_added.add(new["name"])
        renames.append(
            {
                "field": old["name"],
                "change_type": ChangeType.RENAME_COLUMN.value,
                "breaking": True,
                "from_type": old["type"],
                "to_type": new["type"],
                "new_name": new["name"],
                "similarity": score,
                "position": old["position"],
                "detail": (
                    f"{old['name']} → {new['name']}：同位置同类型，名称相似度 {score:.2f} "
                    f"≥ {RENAME_SIMILARITY_THRESHOLD}，按重命名处理；引用旧列名的下游会读不到列"
                ),
            }
        )

    diffs: list[dict] = list(renames)

    # 2) 删除字段（未被重命名配对吃掉的）
    for item in removed:
        if item["name"] in used_removed:
            continue
        diffs.append(
            {
                "field": item["name"],
                "change_type": ChangeType.REMOVE_COLUMN.value,
                "breaking": True,
                "from_type": item["type"],
                "to_type": None,
                "new_name": None,
                "similarity": None,
                "position": item["position"],
                "detail": f"删除 {item['name']}（{item['type']}）：引用该列的查询与报表会直接报列不存在",
            }
        )

    # 3) 新增字段（未被重命名配对吃掉的）
    for item in added:
        if item["name"] in used_added:
            continue
        breaking = _add_is_breaking(item)
        default_text = "" if item.get("default") in (None, "") else f"，默认值 {item['default']}"
        if breaking:
            why = "非空且无默认值：存量分区无法回填，写入会失败"
        else:
            why = f"可空或带默认值{default_text}：旧数据读取不受影响"
        diffs.append(
            {
                "field": item["name"],
                "change_type": ChangeType.ADD_COLUMN.value,
                "breaking": breaking,
                "from_type": None,
                "to_type": item["type"],
                "new_name": None,
                "similarity": None,
                "position": item["position"],
                "detail": f"新增 {item['name']}（{item['type']}）：{why}",
            }
        )

    # 4) 同名但类型变化
    for item in target:
        previous = base_index.get(item["name"])
        if previous is None:
            continue
        if previous["type"] == item["type"]:
            continue
        safe = is_safe_promotion(previous["type"], item["type"])
        diffs.append(
            {
                "field": item["name"],
                "change_type": ChangeType.TYPE_CHANGE.value,
                "breaking": not safe,
                "from_type": previous["type"],
                "to_type": item["type"],
                "new_name": None,
                "similarity": None,
                "position": item["position"],
                "detail": (
                    f"{item['name']} 类型 {previous['type']} → {item['type']}："
                    + ("安全提升，旧分区可隐式读取" if safe else "非安全提升，历史分区读取会失败或丢精度")
                ),
            }
        )

    diffs.sort(key=lambda entry: (0 if entry["breaking"] else 1, entry["position"], entry["field"]))
    return diffs
