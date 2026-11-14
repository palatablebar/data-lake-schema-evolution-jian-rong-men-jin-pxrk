/**
 * 项目品牌、导航、角色权限与枚举文案（前端唯一定义处）。
 * 后端对应：backend/src/constants/{roles,enums}.py；README 列出全部出现位置。
 * 依约定：前端只做展示与表单，diff / 兼容判定 / 影响面 / 迁移单全部来自后端算法。
 */
export const BRAND = {
  short: 'schemagate',
  title: '数据湖 Schema 演进兼容门禁',
  org: '运联科技 · 数据平台组',
  edition: 'BLUEPRINT · DWG-405',
  subtitle: '改表结构先过门禁：diff → 兼容判定 → 下游影响 → 迁移单',
  loginLead:
    'Iceberg 湖仓 240 张表、18 个下游团队。每一次字段变更都要留下判定依据与可回滚的迁移脚本，而不是在群里喊一声。',
  loginPoints: [
    ['01', '提交变更时后端现算 diff：新增 / 删除 / 重命名 / 类型矩阵逐条给出依据。'],
    ['02', '兼容级别与门禁自动判定：删列、非安全类型变更一律 block，不允许静默上线。'],
    ['03', '按下游登记的引用列推影响任务与报表，≥3 个任务直接 critical。'],
    ['04', '迁移单包含正向 SQL、兼容视图与回滚脚本，随变更单一起归档。'],
  ],
  spec: [
    ['接入表', '36 / 240 张核心表已登记'],
    ['版本快照', '86 个已提交版本'],
    ['下游登记', '42 个消费方 / 10 个团队'],
    ['门禁口径', 'breaking → block，其余放行'],
  ],
};

export const NAV = [
  { to: '#/overview', no: '00', label: '总览', permission: 'overview:read' },
  { to: '#/datasets', no: '01', label: '表目录与版本', permission: 'dataset:read' },
  { to: '#/changes', no: '02', label: '变更申请', permission: 'change:read' },
  { to: '#/consumers', no: '03', label: '下游影响', permission: 'consumer:read' },
  { to: '#/exports', no: '04', label: '迁移单与导出', permission: 'check:read' },
  { to: '#/audit', no: '05', label: '审计日志', permission: 'audit:read' },
];

export const ROLE_LABELS = {
  admin: '平台管理员',
  analyst: '数据开发',
  viewer: '下游只读',
};

export const PERMISSIONS = {
  admin: [
    'overview:read', 'dataset:read', 'dataset:write',
    'change:read', 'change:create', 'change:run', 'change:approve',
    'consumer:read', 'consumer:write', 'check:read',
    'export:read', 'audit:read',
  ],
  analyst: [
    'overview:read', 'dataset:read',
    'change:read', 'change:create', 'change:run',
    'consumer:read', 'consumer:write', 'check:read',
    'export:read',
  ],
  viewer: ['overview:read', 'dataset:read', 'change:read', 'consumer:read', 'check:read'],
};

export const ENUMS = {
  format: { iceberg: 'Iceberg', hudi: 'Hudi', delta: 'Delta', parquet: 'Parquet 外表' },
  compat: { backward: '向后兼容', forward: '向前兼容', full: '完全兼容', breaking: '破坏性变更' },
  gate: { pass: '放行', block: '阻塞' },
  status: { submitted: '待检测', checked: '已检测待审批', approved: '已放行', rejected: '已驳回' },
  changeType: { add_column: '新增字段', remove_column: '删除字段', rename_column: '重命名字段', type_change: '类型变更' },
  risk: { low: '低', medium: '中', high: '高', critical: '严重' },
};

export const FIELD_TYPES = [
  'bigint',
  'int',
  'string',
  'boolean',
  'double',
  'float',
  'decimal(12,2)',
  'decimal(14,2)',
  'decimal(18,2)',
  'decimal(6,4)',
  'timestamp',
  'date',
];

export const COMPAT_ORDER = ['breaking', 'full', 'forward', 'backward'];

export function can(role, permission) {
  return (PERMISSIONS[role] || []).includes(permission);
}

export function compatTone(compat) {
  return { breaking: 'danger', full: 'warn', forward: 'info', backward: 'ok' }[compat] || 'info';
}

export function gateTone(gate) {
  return { block: 'danger', pass: 'ok' }[gate] || 'info';
}

export function riskTone(risk) {
  return { critical: 'danger', high: 'warn', medium: 'info', low: 'ok' }[risk] || 'info';
}

export function statusTone(status) {
  return { submitted: 'warn', checked: 'info', approved: 'ok', rejected: 'danger' }[status] || 'info';
}

export function changeTypeTone(changeType) {
  return { remove_column: 'danger', rename_column: 'warn', type_change: 'warn', add_column: 'ok' }[changeType] || 'info';
}
