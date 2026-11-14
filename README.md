# 数据湖 Schema 演进兼容门禁（`schemagate`）

> 数据工程 · 数仓与数据湖方向。原生 HTML/CSS/JS 前端 + Python FastAPI 后端 + Celery worker + PostgreSQL + Redis，恰好 5 个容器一键起。

## 1. 场景

- **模拟客户**：运联科技（物流平台）数据平台组 9 人，运营 Iceberg 湖仓 **240 张表**、服务 **18 个下游团队**。
- **现有工作流**：数据开发改表结构前在群里喊一声「我要删个字段」，下游靠猜；上线后报表炸了才回溯；
  破坏性变更没有回滚脚本，只能靠重跑历史分区硬扛。
- **三个痛点**：
  1. 破坏性变更无门禁 —— 删列、类型收窄和普通新增走同一条上线路径；
  2. 下游影响靠猜 —— 没有「谁引用了哪些列」的登记，影响面完全靠经验；
  3. 无迁移 / 回滚脚本 —— 变更单里只有一句「已改」，出事没有回退方案。
- **上下游**：数据开发提交变更 → 本系统（Schema diff → 兼容判定 → 影响面 → 迁移单）→ 下游团队确认与发布流程。
- **一天的工作剧本**：
  1. 09:20 周棠（数据开发）在「表目录与版本」确认 `dwd.dwd_order_detail` 当前为 v4、8 个字段、下游 7 个消费方；
  2. 09:31 提交变更：删除 `pay_channel`、`amount` 由 `decimal(12,2)` 改 `bigint`，另补 6 个可空列；
  3. 09:31 后端同步算出 8 条字段级判定、兼容级别 `breaking`、风险 `critical`、门禁 `block`；
  4. 09:34 影响面显示 5 个下游消费方 / 5 个调度任务 / 2 张报表，含「渠道对账」「经营日报 · GMV」；
  5. 09:40 林可（平台管理员）在「变更申请」里填放行理由（下游已切兼容视图、回滚已演练）后放行，状态变 `approved`；
  6. 09:45 「迁移单与导出」导出 `CR-*-0002_migration.sql`（含 `ADD COLUMN`、兼容视图与回滚脚本）与 `checks.csv`；
  7. 10:00 陈默（下游只读）在「下游影响」只读复核，无提交/放行按钮，越权调用返回 403。

## 2. 角色与权限

| 角色 | 账号 | 权限 | 典型动作 |
|---|---|---|---|
| 平台管理员 `admin` | `admin@schemagate.io` | 全部：登记表、审批放行、导出、审计 | 放行破坏性变更（需填写理由）、导出迁移单 |
| 数据开发 `analyst` | `analyst@schemagate.io` | 提交变更、跑检测、登记下游、导出 | 提交 diff、重跑兼容检测 |
| 下游只读 `viewer` | `viewer@schemagate.io` | 只读表结构 / 变更判定 / 影响面 | 复核影响面，不能提交或放行 |

密码统一 `Demo@2026`。低权调用高权接口返回**真实 HTTP 403**（不是前端隐藏按钮）：

| 请求 | viewer | analyst | admin |
|---|---|---|---|
| `GET /api/audit` | 403 | 403 | 200 |
| `POST /api/change-requests` | 403 | 201 | 201 |
| `POST /api/change-requests/{id}/run` | 403 | 200 | 200 |
| `POST /api/change-requests/{id}/decision` | 403 | 403 | 200 |
| `GET /api/exports/checks.csv` | 403 | 200 | 200 |
| `POST /api/datasets` | 403 | 403 | 201 |

## 3. 功能模块

1. **表目录与版本**：36 张湖仓表 + 86 个已提交版本快照（`Dataset` / `SchemaVersion`），抽屉里按版本倒序看字段演进。
2. **变更申请**：字段级编辑目标结构 → 后端算 diff、兼容级别、风险、门禁，左右双栏对照 + 逐字段判定依据。
3. **兼容检测**：`POST /api/change-requests/{id}/run` 重跑判定并把结果落到字段级 `CompatCheck`（可重跑、幂等）。
4. **下游影响**：42 个消费方（10 个团队）登记引用列 / 任务 / 报表，按引用列推演受影响任务数与报表数。
5. **迁移单与导出**：迁移单含正向 SQL、兼容视图、阻塞项与回滚脚本；导出 CSV（UTF-8 BOM）与 `.sql`。
6. **审计**：登录 / 提交变更 / 检测 / 放行 / 驳回 / 导出全量落审计（领域层 + HTTP 层）。

## 4. 快速启动

```bash
cp .env.example .env      # 端口已按题目分配（18204 / 19204 / 17704），不要改
docker compose up -d --build
docker compose ps          # 等 5/5 healthy
open http://localhost:18204
```

首次启动 backend 自动建表并执行一次 seed（`SEED_DEMO=true`）。seed 幂等，可重复执行：

```bash
docker compose exec -T backend python -m scripts.seed_demo   # 打印 SEED_SUMMARY，两次逐字一致
docker compose exec -T backend python -m pytest tests -q
```

## 5. 访问地址

| 服务 | 地址 |
|---|---|
| 前端 | http://localhost:18204 |
| 后端 API 文档 | http://localhost:19204/docs |
| 健康检查 | http://localhost:19204/api/health |
| 数据库映射 | localhost:17704 |

## 6. 技术栈

| 层 | 选型 |
|---|---|
| 前端 | 原生 HTML5 + CSS（oklch 令牌 / 蓝图网格）+ ES Modules；**无框架、无打包器、无 CDN 脚本** |
| 后端 | Python 3.11、FastAPI 0.115、SQLAlchemy 2.0、PyJWT、passlib(bcrypt) |
| 异步 | Celery 5.4 + Redis（worker 心跳 10s、每日重跑待审变更的检测） |
| 数据库 | PostgreSQL 16（`db` 服务，命名卷 `db_data`） |
| 部署 | Docker Compose，恰好 5 服务，全部带 healthcheck |

## 7. 目录

```text
backend/
  src/config/         settings / database / app 装配 / celery
  src/constants/      enums.py（6 组共享枚举）roles.py limits.py log_templates.py
  src/models/         dataset.py schema_version.py change_request.py consumer.py compat_check.py
  src/services/       schema_diff.py（算法 A）compat_engine.py（算法 B）
                      dataset_service.py change_service.py consumer_service.py check_service.py
                      overview_service.py export_service.py audit_service.py auth_service.py
  src/controllers/    dataset / change / consumer / check / export / auth
  src/routes/         datasets changes consumers checks exports overview audit auth health
  src/middlewares/    auth(JWT) rbac audit_logger rate_limit error_handler
  scripts/            seed_demo.py demo_config.py worker_healthcheck.sh
  migrations/         001_core_tables.sql（DDL 参考）
  tests/              test_schema_diff.py test_compat.py test_security.py
frontend/site/
  index.html  css/{tokens,app}.css
  js/{config,api,store,ui,app}.js  js/pages/{login,overview,datasets,changes,consumers,exports,audit}.js
```

## 8. 核心算法与口径

两个算法都在 `backend/src/services/`，是**纯函数**（无 DB、无网络、无随机），由 `backend/tests/` 直接单测；
页面只展示后端返回的结果，前端不重算任何判定。

### 算法 A｜Schema diff 与类型矩阵（`services/schema_diff.py`）

- 输入：基线版本字段列表 + 目标字段列表，每项 `{name, type, nullable, default}`（保序）。
- 输出：逐字段条目 `{field, change_type, breaking, from_type, to_type, new_name, similarity, detail}`，
  按「破坏性优先、再按位置」排序。
- 重命名识别：一个「被删字段」与一个「新增字段」**位置相同 + 规范化类型相同 + 名称相似度
  `difflib.SequenceMatcher.ratio() ≥ 0.7`** 时判为 `rename_column`（多候选取相似度最高者一对一配对）。
- 类型矩阵（`canonical_type` 归一别名 `int32/long/varchar…` 后比较）：
  - 安全提升：`tinyint→int→bigint` 整数加宽、整型→`float/double`、`float→double`、
    `decimal(p,s)→decimal(p',s')` 且 `p'≥p, s'≥s`（扩容）；
  - 破坏性：`string→int`、`double→float`、`decimal→整型`、decimal 缩容等一切非安全提升。
- 新增字段：`nullable=true` 或带 `default` → 安全；非空且无默认值 → breaking（存量分区无法回填）。
- 删除字段：一律 breaking。

### 算法 B｜兼容判定 + 影响传播 + 迁移单（`services/compat_engine.py`）

- 兼容级别 `compat`：
  - `breaking`：diff 中存在任一 breaking 条目；
  - `backward`：只有新增（含安全提升），旧读者读新表不受影响；
  - `forward`：只有删除 / 重命名，新读者读旧表不受影响；
  - `full`：既有新增又有删除且全部安全。
  - 说明：按当前矩阵「删除一律 breaking」，因此线上实际只会产出 `backward` 与 `breaking`；
    `forward/full` 保留为 Avro 口径的完整词表（见第 12 节已知差异）。
- 影响传播：被影响列 = `remove_column / rename_column / type_change` 中 breaking 的字段；
  受影响消费方 = 其引用列与这些列有交集的 `Consumer`；任务 / 报表数 = 命中消费方名下
  `tasks` / `reports` 的**并集去重计数**。
- 风险 `risk`：breaking 且任务 ≥ 3 → `critical`（计划验收口径），breaking 且 < 3 → `high`；
  非 breaking 时任务 ≥ 8 → `critical`、≥ 3 → `high`、≥ 1 → `medium`、否则 `low`。
- 门禁 `gate`：`compat == breaking → block`，其余 `pass`。
- 迁移单 `migration_sql`（五段）：① 前置校验 SELECT；② 正向迁移（`ADD COLUMN` / `RENAME COLUMN` /
  `ALTER COLUMN TYPE`，删列注释为下游切换后独立执行）；③ 兼容视图（旧列名兜底）；
  ④ 阻塞项清单；⑤ **回滚脚本**（逆序还原类型、列名、被删列、新增列与视图）。

## 9. 共享枚举出现位置

| 枚举 | 后端（唯一定义处） | 前端（副本） | 其它出现点 |
|---|---|---|---|
| 角色 `admin/analyst/viewer` | `constants/enums.py::Role`、`constants/roles.py` | `js/config.js::ROLE_LABELS/PERMISSIONS` | `middlewares/rbac.py`、登录页 |
| 表格式 `iceberg/hudi/delta/parquet` | `constants/enums.py::DatasetFormat` | `js/config.js::ENUMS.format` | `schemas/dataset.py`、`pages/datasets.js` |
| 兼容级别 `backward/forward/full/breaking` | `constants/enums.py::Compat` | `js/config.js::ENUMS.compat` | `pages/changes.js`、`services/export_service.py` |
| 门禁 `pass/block` | `constants/enums.py::Gate` | `js/config.js::ENUMS.gate` | `compat_engine.resolve_gate` |
| 变更状态 `submitted/checked/approved/rejected` | `constants/enums.py::ChangeStatus` | `js/config.js::ENUMS.status` | `services/change_service.py`、`pages/exports.js` |
| 字段变更类型 `add/remove/rename/type_change` | `constants/enums.py::ChangeType` | `js/config.js::ENUMS.changeType` | `pages/exports.js`、`pages/changes.js` |
| 风险 `low/medium/high/critical` | `constants/enums.py::Risk` | `js/config.js::ENUMS.risk` | `pages/overview.js`、`pages/changes.js` |

## 10. API

| 方法 | 路径 | 说明 | 最低角色 |
|---|---|---|---|
| POST | `/api/auth/login` | 登录换 JWT | 匿名 |
| GET | `/api/overview` | 总览（表数 / 待审 / 破坏性占比 / 风险分布） | viewer |
| GET | `/api/datasets` | 表目录（`q`/`db_name`/`format`） | viewer |
| GET | `/api/datasets/{id}` | 表详情（当前字段、下游数、阻塞变更数） | viewer |
| GET | `/api/datasets/{id}/versions` | 版本历史 | viewer |
| POST | `/api/datasets` | 登记表（重复自然键 409） | admin |
| GET | `/api/change-requests` | 变更申请列表（`compat`/`gate`/`status`/`dataset_id`/`q`） | viewer |
| GET | `/api/change-requests/{id}` | 详情（diff、影响面、迁移单、字段级检测） | viewer |
| POST | `/api/change-requests` | 提交变更并判定 | analyst |
| POST | `/api/change-requests/{id}/run` | 重跑兼容检测，落 `CompatCheck` | analyst |
| POST | `/api/change-requests/{id}/decision` | 放行 / 驳回（`block` 放行必须填理由，否则 422） | admin |
| GET | `/api/consumers` | 下游消费方（`dataset_id`/`team`/`q`） | viewer |
| POST | `/api/consumers` | 登记消费方（同名 409） | analyst |
| GET | `/api/compat-checks` | 字段级检测（`request_id`/`change_type`/`breaking`） | viewer |
| GET | `/api/exports/checks.csv` | 检测清单 CSV（UTF-8 BOM） | analyst |
| GET | `/api/exports/migrations/{id}.sql` | 迁移单 SQL | analyst |
| GET | `/api/audit` | 审计日志 | admin |

## 11. 环境变量

见 `.env` / `.env.example`：`COMPOSE_PROJECT_NAME`、`FRONTEND_PORT=18204`、`BACKEND_PORT=19204`、`DB_PORT=17704`、
`DB_*`、`JWT_SECRET`、`REDIS_URL`、`SEED_DEMO`、`RATE_LIMIT_PER_MINUTE=300`、`RATE_LIMIT_WRITE_PER_MINUTE=60`、
`APP_TIMEZONE_OFFSET_MINUTES=480`。

## 12. 已知差异（简化与取舍）

1. **兼容词表**：矩阵按计划把「删除 / 重命名」一律记为 breaking，因此线上只产出 `backward` 与 `breaking`；
   `forward / full` 只作为词表与筛选器保留。
2. **重命名的位置约束**：严格按「同位置 + 同类型 + 相似度 ≥0.7」判定；若在同一份变更里先删掉了前面的列，
   后续列下标平移，重命名可能退化为 add + remove（这是计划口径的直接结果，未做偏移补偿）。
3. **下游登记是手工维护**：真实环境应从调度系统 / BI 平台扫描血缘；本项目用 `Consumer` 表模拟，
   影响面只对该表登记的引用列负责，不做 SQL 解析。
4. **迁移单是模板化生成**：不区分 Iceberg 的 `ALTER TABLE ... SET TBLPROPERTIES` 等引擎差异，统一用 PostgreSQL/ANSI 语法。

## License

内部演示项目，仅用于评测与教学。
