-- 核心表结构参考（PostgreSQL 语法，运行时不执行；建表由 SQLAlchemy create_all 完成）

CREATE TABLE users (
    id              SERIAL PRIMARY KEY,
    email           VARCHAR(160) NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,
    display_name    VARCHAR(80)  NOT NULL,
    role            VARCHAR(20)  NOT NULL,
    org             VARCHAR(120),
    created_at      TIMESTAMP    NOT NULL
);

-- 领域实体 1：湖仓表，业务自然键 (db_name, table_name)
CREATE TABLE datasets (
    id              SERIAL PRIMARY KEY,
    db_name         VARCHAR(40)  NOT NULL,
    table_name      VARCHAR(80)  NOT NULL,
    owner           VARCHAR(80)  NOT NULL,
    format          VARCHAR(20)  NOT NULL,          -- iceberg / hudi / delta / parquet
    partition_key   VARCHAR(120),
    current_version INTEGER      NOT NULL DEFAULT 1,
    row_count       INTEGER      NOT NULL DEFAULT 0,
    description     TEXT,
    created_at      TIMESTAMP    NOT NULL,
    updated_at      TIMESTAMP    NOT NULL,
    CONSTRAINT uq_datasets_natural_key UNIQUE (db_name, table_name)
);

-- 领域实体 2：已提交的结构快照，自然键 (dataset_id, version)
CREATE TABLE schema_versions (
    id              SERIAL PRIMARY KEY,
    dataset_id      INTEGER      NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    version         INTEGER      NOT NULL,
    fields          JSON         NOT NULL,          -- [{name,type,nullable,default,comment,position}]
    author          VARCHAR(160) NOT NULL,
    summary         TEXT,
    committed_at    TIMESTAMP    NOT NULL,
    CONSTRAINT uq_schema_versions_dataset_version UNIQUE (dataset_id, version)
);

-- 领域实体 3：变更申请（diff / 兼容 / 风险 / 门禁 / 迁移单）
CREATE TABLE change_requests (
    id              SERIAL PRIMARY KEY,
    code            VARCHAR(40)  NOT NULL UNIQUE,
    dataset_id      INTEGER      NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    base_version    INTEGER      NOT NULL,
    target_fields   JSON         NOT NULL,
    diff            JSON         NOT NULL,          -- 算法 A 输出
    impact          JSON         NOT NULL,          -- 算法 B 影响面
    compat          VARCHAR(20)  NOT NULL,          -- backward / forward / full / breaking
    risk            VARCHAR(20)  NOT NULL,          -- low / medium / high / critical
    gate            VARCHAR(10)  NOT NULL,          -- pass / block
    status          VARCHAR(20)  NOT NULL,          -- submitted / checked / approved / rejected
    migration_sql   TEXT,
    summary         TEXT,
    author          VARCHAR(160) NOT NULL,
    decided_by      VARCHAR(160),
    decision_note   TEXT,
    decided_at      TIMESTAMP,
    checked_at      TIMESTAMP,
    created_at      TIMESTAMP    NOT NULL,
    updated_at      TIMESTAMP    NOT NULL
);

-- 附加实体 1：下游消费方，自然键 (dataset_id, name)
CREATE TABLE consumers (
    id              SERIAL PRIMARY KEY,
    dataset_id      INTEGER      NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    name            VARCHAR(120) NOT NULL,
    team            VARCHAR(80)  NOT NULL,
    owner           VARCHAR(120),
    columns         JSON         NOT NULL,          -- 引用列名列表
    tasks           JSON         NOT NULL,          -- 名下调度任务
    reports         JSON         NOT NULL,          -- 名下报表
    refresh_cron    VARCHAR(40),
    created_at      TIMESTAMP    NOT NULL,
    CONSTRAINT uq_consumers_dataset_name UNIQUE (dataset_id, name)
);

-- 附加实体 2：字段级检测结果，自然键 (request_id, field)
CREATE TABLE compat_checks (
    id              SERIAL PRIMARY KEY,
    request_id      INTEGER      NOT NULL REFERENCES change_requests(id) ON DELETE CASCADE,
    field           VARCHAR(120) NOT NULL,
    change_type     VARCHAR(30)  NOT NULL,
    breaking        BOOLEAN      NOT NULL DEFAULT FALSE,
    detail          TEXT,
    created_at      TIMESTAMP    NOT NULL,
    CONSTRAINT uq_compat_checks_request_field UNIQUE (request_id, field)
);

CREATE TABLE audit_logs (
    id              SERIAL PRIMARY KEY,
    actor_email     VARCHAR(160) NOT NULL,
    actor_role      VARCHAR(20)  NOT NULL,
    action          VARCHAR(64)  NOT NULL,
    entity          VARCHAR(40)  NOT NULL,
    entity_id       VARCHAR(64),
    detail          JSON,
    layer           VARCHAR(16)  NOT NULL DEFAULT 'domain',
    ip              VARCHAR(64),
    seed_key        VARCHAR(120) UNIQUE,
    created_at      TIMESTAMP    NOT NULL
);

CREATE INDEX ix_change_requests_compat ON change_requests (compat);
CREATE INDEX ix_change_requests_gate ON change_requests (gate);
CREATE INDEX ix_compat_checks_request ON compat_checks (request_id);
