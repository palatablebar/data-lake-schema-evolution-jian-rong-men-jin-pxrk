"""共享枚举（后端唯一定义处）。前端副本见 frontend/site/js/config.js。

枚举分组：
  1. 表格式 datasetFormat  —— Dataset.format
  2. 兼容级别 compat       —— ChangeRequest.compat
  3. 门禁结论 gate         —— ChangeRequest.gate
  4. 变更状态 changeStatus —— ChangeRequest.status
  5. 字段变更类型 changeType —— diff 条目 / CompatCheck.change_type
  6. 风险等级 risk         —— ChangeRequest.risk

README「共享枚举出现位置」一节列出全部出现点，改动需两侧同步。
"""
from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"


# ---------------------------------------------------------------- 表格式
class DatasetFormat(StrEnum):
    """湖仓表格式。运联科技以 Iceberg 为主，少量 Hudi（近实时）与 Parquet 外表。"""

    ICEBERG = "iceberg"
    HUDI = "hudi"
    DELTA = "delta"
    PARQUET = "parquet"


DATASET_FORMAT_LABELS: dict[str, str] = {
    DatasetFormat.ICEBERG.value: "Iceberg",
    DatasetFormat.HUDI.value: "Hudi",
    DatasetFormat.DELTA.value: "Delta",
    DatasetFormat.PARQUET.value: "Parquet 外表",
}


# ---------------------------------------------------------------- 兼容级别
class Compat(StrEnum):
    """Schema 兼容级别（引用 Avro/Iceberg 口径）。"""

    BACKWARD = "backward"
    FORWARD = "forward"
    FULL = "full"
    BREAKING = "breaking"


COMPAT_LABELS: dict[str, str] = {
    Compat.BACKWARD.value: "向后兼容",
    Compat.FORWARD.value: "向前兼容",
    Compat.FULL.value: "完全兼容",
    Compat.BREAKING.value: "破坏性变更",
}

COMPAT_ORDER: list[str] = [Compat.BREAKING.value, Compat.FULL.value, Compat.FORWARD.value, Compat.BACKWARD.value]


# ---------------------------------------------------------------- 门禁
class Gate(StrEnum):
    PASS = "pass"
    BLOCK = "block"


GATE_LABELS: dict[str, str] = {
    Gate.PASS.value: "放行",
    Gate.BLOCK.value: "阻塞",
}


# ---------------------------------------------------------------- 变更状态
class ChangeStatus(StrEnum):
    SUBMITTED = "submitted"
    CHECKED = "checked"
    APPROVED = "approved"
    REJECTED = "rejected"


CHANGE_STATUS_LABELS: dict[str, str] = {
    ChangeStatus.SUBMITTED.value: "待检测",
    ChangeStatus.CHECKED.value: "已检测待审批",
    ChangeStatus.APPROVED.value: "已放行",
    ChangeStatus.REJECTED.value: "已驳回",
}

CHANGE_STATUS_ORDER: list[str] = [
    ChangeStatus.SUBMITTED.value,
    ChangeStatus.CHECKED.value,
    ChangeStatus.APPROVED.value,
    ChangeStatus.REJECTED.value,
]

# 「待处理」= 还没定论的状态，总览与 pending 统计口径
PENDING_STATUSES: tuple[str, ...] = (ChangeStatus.SUBMITTED.value, ChangeStatus.CHECKED.value)


# ---------------------------------------------------------------- 字段变更类型
class ChangeType(StrEnum):
    ADD_COLUMN = "add_column"
    REMOVE_COLUMN = "remove_column"
    RENAME_COLUMN = "rename_column"
    TYPE_CHANGE = "type_change"


CHANGE_TYPE_LABELS: dict[str, str] = {
    ChangeType.ADD_COLUMN.value: "新增字段",
    ChangeType.REMOVE_COLUMN.value: "删除字段",
    ChangeType.RENAME_COLUMN.value: "重命名字段",
    ChangeType.TYPE_CHANGE.value: "类型变更",
}

CHANGE_TYPE_ORDER: list[str] = [
    ChangeType.REMOVE_COLUMN.value,
    ChangeType.RENAME_COLUMN.value,
    ChangeType.TYPE_CHANGE.value,
    ChangeType.ADD_COLUMN.value,
]


# ---------------------------------------------------------------- 风险等级
class Risk(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


RISK_LABELS: dict[str, str] = {
    Risk.LOW.value: "低",
    Risk.MEDIUM.value: "中",
    Risk.HIGH.value: "高",
    Risk.CRITICAL.value: "严重",
}

RISK_ORDER: list[str] = [Risk.CRITICAL.value, Risk.HIGH.value, Risk.MEDIUM.value, Risk.LOW.value]

# 影响任务数达到该阈值即按 critical 处理（batch-plan 验收口径：≥3 任务 critical）
CRITICAL_TASK_THRESHOLD = 3

# 前端字段类型下拉的可选值（后端校验也用它，避免前后端漂移）
FIELD_TYPE_OPTIONS: list[str] = [
    "bigint",
    "int",
    "string",
    "boolean",
    "double",
    "float",
    "decimal(12,2)",
    "decimal(14,2)",
    "decimal(18,2)",
    "decimal(6,4)",
    "timestamp",
    "date",
]
