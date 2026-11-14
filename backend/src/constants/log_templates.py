"""审计动作 -> 中文标签。"""
from __future__ import annotations

ACTIONS: dict[str, str] = {
    "auth.login": "登录",
    "dataset.create": "登记表",
    "dataset.update": "修改表信息",
    "change.create": "提交变更申请",
    "change.run": "执行兼容检测",
    "change.approve": "放行变更",
    "change.reject": "驳回变更",
    "consumer.create": "登记下游消费方",
    "export.checks": "导出检测清单",
    "export.migration": "导出迁移单",
    "http.mutation": "写请求",
}
