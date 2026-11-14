"""角色 -> 权限点映射。README 与前端 site/js/config.js 同步。

角色键固定为 admin / analyst / viewer，本项目的展示名与职责：
  admin   平台管理员：维护表目录、审批与放行变更、导出迁移单、看审计
  analyst 数据开发  ：提交变更申请、跑兼容检测、维护下游消费方登记
  viewer  下游负责人：只读影响面与兼容检测结果
"""
from __future__ import annotations

from src.constants.enums import Role

ROLE_LABELS: dict[str, str] = {
    Role.ADMIN.value: "平台管理员",
    Role.ANALYST.value: "数据开发",
    Role.VIEWER.value: "下游只读",
}

ROLE_DUTIES: dict[str, str] = {
    Role.ADMIN.value: "维护表目录与版本、审批放行变更、导出迁移单、查看审计",
    Role.ANALYST.value: "提交变更申请、执行兼容检测、登记下游消费方",
    Role.VIEWER.value: "只读查看表结构、变更判定与下游影响，不能提交或放行",
}

PERMISSIONS: dict[str, set[str]] = {
    Role.ADMIN.value: {
        "overview:read",
        "dataset:read", "dataset:write",
        "change:read", "change:create", "change:run", "change:approve",
        "consumer:read", "consumer:write",
        "check:read",
        "export:read", "audit:read",
    },
    Role.ANALYST.value: {
        "overview:read",
        "dataset:read",
        "change:read", "change:create", "change:run",
        "consumer:read", "consumer:write",
        "check:read",
        "export:read",
    },
    Role.VIEWER.value: {
        "overview:read",
        "dataset:read",
        "change:read",
        "consumer:read",
        "check:read",
    },
}

DATASET_WRITE_ROLES = (Role.ADMIN.value,)
CHANGE_CREATE_ROLES = (Role.ADMIN.value, Role.ANALYST.value)
CHANGE_RUN_ROLES = (Role.ADMIN.value, Role.ANALYST.value)
CHANGE_APPROVE_ROLES = (Role.ADMIN.value,)
CONSUMER_WRITE_ROLES = (Role.ADMIN.value, Role.ANALYST.value)
EXPORT_ROLES = (Role.ADMIN.value, Role.ANALYST.value)
AUDIT_ROLES = (Role.ADMIN.value,)
READ_ROLES = (Role.ADMIN.value, Role.ANALYST.value, Role.VIEWER.value)


def has_permission(role: str, permission: str) -> bool:
    return permission in PERMISSIONS.get(role, set())
