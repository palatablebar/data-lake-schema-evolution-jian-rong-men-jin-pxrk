"""算法 A（Schema diff 与类型矩阵）单测：正常路径 + 边界用例。"""
from __future__ import annotations

from src.constants.enums import ChangeType
from src.services import schema_diff


def types(fields):
    return {item["name"]: item["type"] for item in fields}


def by_field(diff):
    return {item["field"]: item for item in diff}


def test_safe_promotion_matrix():
    # 安全提升：整数加宽 / 整型到浮点 / float→double / decimal 扩容
    assert schema_diff.is_safe_promotion("int", "bigint") is True
    assert schema_diff.is_safe_promotion("tinyint", "bigint") is True
    assert schema_diff.is_safe_promotion("int", "double") is True
    assert schema_diff.is_safe_promotion("float", "double") is True
    assert schema_diff.is_safe_promotion("decimal(12,2)", "decimal(14,2)") is True
    assert schema_diff.is_safe_promotion("decimal(12,2)", "decimal(18,2)") is True
    # 破坏性：缩窄 / string→int / decimal 缩容 / decimal→整型
    assert schema_diff.is_safe_promotion("bigint", "int") is False
    assert schema_diff.is_safe_promotion("string", "int") is False
    assert schema_diff.is_safe_promotion("decimal(12,2)", "decimal(10,2)") is False
    assert schema_diff.is_safe_promotion("decimal(12,2)", "bigint") is False
    assert schema_diff.is_safe_promotion("double", "float") is False


def test_type_aliases_are_canonical():
    assert schema_diff.canonical_type("INT32") == "int"
    assert schema_diff.canonical_type("Long") == "bigint"
    assert schema_diff.canonical_type("decimal( 12 , 2 )") == "decimal(12,2)"
    assert schema_diff.is_safe_promotion("int32", "long") is True


def test_remove_column_is_breaking():
    base = [{"name": "order_id", "type": "bigint"}, {"name": "pay_channel", "type": "string"}]
    target = [{"name": "order_id", "type": "bigint"}]
    diff = by_field(schema_diff.diff_fields(base, target))
    assert diff["pay_channel"]["change_type"] == ChangeType.REMOVE_COLUMN.value
    assert diff["pay_channel"]["breaking"] is True


def test_add_column_safe_when_nullable_or_defaulted():
    base = [{"name": "order_id", "type": "bigint"}]
    target = [
        {"name": "order_id", "type": "bigint"},
        {"name": "ext_json", "type": "string", "nullable": True},
        {"name": "currency", "type": "string", "nullable": False, "default": "CNY"},
        {"name": "region", "type": "string", "nullable": False},
    ]
    diff = by_field(schema_diff.diff_fields(base, target))
    assert diff["ext_json"]["breaking"] is False
    assert diff["currency"]["breaking"] is False
    assert diff["region"]["breaking"] is True  # 非空且无默认值


def test_type_change_decimal_to_bigint_is_breaking():
    base = [{"name": "amount", "type": "decimal(12,2)", "nullable": True}]
    target = [{"name": "amount", "type": "bigint", "nullable": True}]
    diff = schema_diff.diff_fields(base, target)
    assert len(diff) == 1
    assert diff[0]["change_type"] == ChangeType.TYPE_CHANGE.value
    assert diff[0]["breaking"] is True
    assert diff[0]["from_type"] == "decimal(12,2)"
    assert diff[0]["to_type"] == "bigint"


def test_rename_detected_by_position_type_and_similarity():
    base = [
        {"name": "order_id", "type": "bigint"},
        {"name": "buyer_id", "type": "bigint"},
        {"name": "amount", "type": "decimal(12,2)"},
    ]
    target = [
        {"name": "order_id", "type": "bigint"},
        {"name": "buyer_key", "type": "bigint"},
        {"name": "amount", "type": "decimal(12,2)"},
    ]
    diff = schema_diff.diff_fields(base, target)
    assert len(diff) == 1
    entry = diff[0]
    assert entry["change_type"] == ChangeType.RENAME_COLUMN.value
    assert entry["field"] == "buyer_id" and entry["new_name"] == "buyer_key"
    assert entry["similarity"] >= schema_diff.RENAME_SIMILARITY_THRESHOLD
    assert entry["breaking"] is True


def test_rename_not_detected_when_type_or_position_differs():
    # 类型不同：不按重命名处理，拆成 add + remove
    base = [{"name": "user_id", "type": "bigint"}]
    target = [{"name": "user_key", "type": "string"}]
    kinds = {item["change_type"] for item in schema_diff.diff_fields(base, target)}
    assert ChangeType.RENAME_COLUMN.value not in kinds
    assert kinds == {ChangeType.ADD_COLUMN.value, ChangeType.REMOVE_COLUMN.value}

    # 名称毫不相似：同样不按重命名处理
    base = [{"name": "pay_channel", "type": "string"}]
    target = [{"name": "settlement_no", "type": "string"}]
    kinds = {item["change_type"] for item in schema_diff.diff_fields(base, target)}
    assert ChangeType.RENAME_COLUMN.value not in kinds


def test_empty_lists_and_identical_schema():
    assert schema_diff.diff_fields([], []) == []
    base = [{"name": "a", "type": "int", "nullable": True}]
    assert schema_diff.diff_fields(base, base) == []


def test_breaking_entries_sort_first():
    base = [
        {"name": "order_id", "type": "bigint"},
        {"name": "amount", "type": "decimal(12,2)"},
    ]
    target = [
        {"name": "order_id", "type": "bigint"},
        {"name": "amount", "type": "decimal(12,2)"},
        {"name": "ext_json", "type": "string", "nullable": True},
        {"name": "region", "type": "string", "nullable": False},
    ]
    diff = schema_diff.diff_fields(base, target)
    assert diff[0]["breaking"] is True
    assert diff[0]["field"] == "region"
