"""ORM 模型聚合导出（Base 用于 create_all）。"""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from src.models.user import User  # noqa: E402
from src.models.audit import AuditLog  # noqa: E402
from src.models.dataset import Dataset  # noqa: E402
from src.models.schema_version import SchemaVersion  # noqa: E402
from src.models.change_request import ChangeRequest  # noqa: E402
from src.models.consumer import Consumer  # noqa: E402
from src.models.compat_check import CompatCheck  # noqa: E402

__all__ = [
    "Base",
    "User",
    "AuditLog",
    "Dataset",
    "SchemaVersion",
    "ChangeRequest",
    "Consumer",
    "CompatCheck",
]
