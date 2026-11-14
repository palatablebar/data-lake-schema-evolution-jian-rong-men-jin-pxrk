"""幂等 seed：3 账号 / 36 张湖仓表 / 86 个版本 / 42 个下游消费方 / 8 个变更申请 / 8 条字段级检测。

自然键 upsert（重复执行不新增；已被人审批过的变更单不覆盖结论）：
  users.email
  datasets.(db_name, table_name)
  schema_versions.(dataset_id, version)
  consumers.(dataset_id, name)
  change_requests.code
  compat_checks.(request_id, field)
  audit_logs.seed_key

SEED_SUMMARY 契约（batch-plan §0 固定键名与顺序）：
  SEED_SUMMARY brand=<短名> users=3 sources=<N> runs=<N> findings=<N> pending=<N>
本项目的映射：sources=表目录数、runs=变更申请数、findings=字段级检测数、pending=待处理变更数。
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, select

from src.config.database import session_scope
from src.constants.enums import PENDING_STATUSES, ChangeStatus
from src.models.audit import AuditLog
from src.models.change_request import ChangeRequest
from src.models.compat_check import CompatCheck
from src.models.consumer import Consumer
from src.models.dataset import Dataset
from src.models.schema_version import SchemaVersion
from src.models.user import User
from src.services import auth_service, change_service
from src.utils.security import hash_password
from src.utils.timeutil import utcnow

from scripts.demo_config import (
    CHANGE_REQUEST_SPECS,
    CONSUMERS,
    DATASETS,
    DEMO_PASSWORD,
    DEMO_USERS,
    ORG,
    SEED_AUDIT,
    apply_ops,
    fields_for_version,
)

VERSION_EPOCH = datetime(2026, 6, 1, 9, 0, 0)


def ensure_users(db) -> int:
    for email, display_name, role in DEMO_USERS:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            db.add(
                User(
                    email=email,
                    password_hash=hash_password(DEMO_PASSWORD),
                    display_name=display_name,
                    role=role,
                    org=ORG,
                )
            )
    db.flush()
    return db.scalar(select(func.count()).select_from(User)) or 0


def ensure_datasets(db) -> int:
    for db_name, table_name, family, total_versions, partition_key, row_count, owner, description in DATASETS:
        dataset = db.scalar(
            select(Dataset).where(Dataset.db_name == db_name, Dataset.table_name == table_name)
        )
        if dataset is None:
            dataset = Dataset(db_name=db_name, table_name=table_name)
            db.add(dataset)
            db.flush()
        dataset.owner = owner
        dataset.format = "iceberg" if db_name != "ods" or family != "log" else "hudi"
        dataset.partition_key = partition_key
        dataset.row_count = row_count
        dataset.description = description
        dataset.current_version = total_versions
        for version in range(1, total_versions + 1):
            existing = db.scalar(
                select(SchemaVersion).where(
                    SchemaVersion.dataset_id == dataset.id, SchemaVersion.version == version
                )
            )
            if existing is not None:
                continue
            db.add(
                SchemaVersion(
                    dataset_id=dataset.id,
                    version=version,
                    fields=fields_for_version(family, version, total_versions),
                    author=f"data@{ORG.split(' ')[0]}.io",
                    summary=f"v{version}：{description}（第 {version}/{total_versions} 版）",
                    committed_at=VERSION_EPOCH + timedelta(days=3 * (version - 1) + (dataset.id or 0) % 5),
                )
            )
    db.flush()
    return db.scalar(select(func.count()).select_from(Dataset)) or 0


def ensure_consumers(db) -> int:
    datasets = {dataset.full_name: dataset for dataset in db.scalars(select(Dataset)).all()}
    for table, name, team, owner, columns, tasks, reports in CONSUMERS:
        dataset = datasets.get(table)
        if dataset is None:
            raise RuntimeError(f"seed: consumer {name} 引用了不存在的表 {table}")
        existing = db.scalar(
            select(Consumer).where(Consumer.dataset_id == dataset.id, Consumer.name == name)
        )
        if existing is None:
            db.add(
                Consumer(
                    dataset_id=dataset.id,
                    name=name,
                    team=team,
                    owner=owner,
                    columns=columns,
                    tasks=tasks,
                    reports=reports,
                    refresh_cron="0 3 * * *" if not tasks or "realtime" not in tasks[0] else "*/10 * * * *",
                )
            )
    db.flush()
    return db.scalar(select(func.count()).select_from(Consumer)) or 0


def ensure_change_requests(db) -> tuple[int, int]:
    datasets = {dataset.full_name: dataset for dataset in db.scalars(select(Dataset)).all()}
    created = 0
    for spec in CHANGE_REQUEST_SPECS:
        existing = db.scalar(select(ChangeRequest).where(ChangeRequest.code == spec["code"]))
        if existing is not None:
            continue  # 已存在：保留人工审批过的结论，不覆盖
        dataset = datasets.get(spec["table"])
        if dataset is None:
            raise RuntimeError(f"seed: 变更单 {spec['code']} 引用了不存在的表 {spec['table']}")
        base_version = dataset.current_version
        base = db.scalar(
            select(SchemaVersion).where(
                SchemaVersion.dataset_id == dataset.id, SchemaVersion.version == base_version
            )
        )
        if base is None:
            raise RuntimeError(f"seed: 表 {spec['table']} 缺少 v{base_version} 版本")
        target_fields = apply_ops(base.fields or [], spec["ops"])
        result = change_service.analyze(
            db,
            dataset=dataset,
            base_fields=base.fields or [],
            target_fields=target_fields,
            code=spec["code"],
            base_version=base_version,
        )
        request = ChangeRequest(
            code=spec["code"],
            dataset_id=dataset.id,
            base_version=base_version,
            target_fields=target_fields,
            diff=result["diff"],
            impact=result["impact"],
            compat=result["compat"],
            risk=result["risk"],
            gate=result["gate"],
            status=ChangeStatus.SUBMITTED.value,
            migration_sql=result["migration_sql"],
            summary=spec["summary"],
            author="analyst@schemagate.io",
            created_at=utcnow() - timedelta(days=9 - int(spec["code"][-4:]) % 9),
        )
        db.add(request)
        db.flush()
        created += 1

        if spec.get("detect"):
            change_service.run_checks(db, request)
            request.checked_at = utcnow() - timedelta(days=8 - int(spec["code"][-4:]) % 9)

        status = spec.get("status") or ChangeStatus.SUBMITTED.value
        request.status = status
        if spec.get("decided_by"):
            request.decided_by = spec["decided_by"]
            request.decision_note = spec.get("decision_note")
            request.decided_at = utcnow() - timedelta(days=7 - int(spec["code"][-4:]) % 9)
    db.flush()
    total = db.scalar(select(func.count()).select_from(ChangeRequest)) or 0
    return total, created


def ensure_audit(db) -> None:
    for seed_key, email, role, action, entity, detail in SEED_AUDIT:
        exists = db.scalar(select(AuditLog).where(AuditLog.seed_key == seed_key))
        if exists is None:
            db.add(
                AuditLog(
                    actor_email=email,
                    actor_role=role,
                    action=action,
                    entity=entity,
                    detail=detail,
                    layer="seed",
                    seed_key=seed_key,
                )
            )
    db.flush()


def seed_all() -> dict:
    with session_scope() as db:
        users = ensure_users(db)
        datasets = ensure_datasets(db)
        versions = db.scalar(select(func.count()).select_from(SchemaVersion)) or 0
        consumers = ensure_consumers(db)
        changes, created = ensure_change_requests(db)
        ensure_audit(db)
        checks = db.scalar(select(func.count()).select_from(CompatCheck)) or 0
        pending = db.scalar(
            select(func.count()).select_from(ChangeRequest).where(ChangeRequest.status.in_(PENDING_STATUSES))
        ) or 0
        summary = (
            f"SEED_SUMMARY brand=schemagate users={users} sources={datasets} "
            f"runs={changes} findings={checks} pending={pending}"
        )
        print(summary, flush=True)
        print(
            f"[seed] versions={versions} consumers={consumers} requests={changes} checks={checks}",
            flush=True,
        )
        print(
            f"[seed] new_requests={created}（全部实体按自然键 upsert，重复执行不新增）",
            flush=True,
        )
        return {
            "users": users,
            "datasets": datasets,
            "versions": versions,
            "consumers": consumers,
            "changes": changes,
            "checks": checks,
            "pending": pending,
        }


if __name__ == "__main__":
    seed_all()
