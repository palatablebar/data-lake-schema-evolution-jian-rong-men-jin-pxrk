import { api } from '../api.js';
import { ENUMS, FIELD_TYPES, can, compatTone, gateTone, riskTone, statusTone } from '../config.js';
import {
  diffColumns,
  diffLedger,
  drawer,
  emptyState,
  errorBox,
  errorMessage,
  esc,
  field,
  fmtTime,
  kv,
  sqlBlock,
  table,
  toast,
} from '../ui.js';

const state = { compat: '', gate: '', status: '', q: '', datasetId: '' };

function fieldRow(item = {}) {
  return `<div class="field-row" style="display:grid;grid-template-columns:1.4fr 1fr 64px 96px 32px;gap:6px;align-items:end">
    <div class="field"><label>字段名</label><input data-k="name" value="${esc(item.name || '')}" placeholder="ext_json" /></div>
    <div class="field"><label>类型</label><select data-k="type">${FIELD_TYPES.map(
      (type) => `<option value="${esc(type)}" ${type === (item.type || 'string') ? 'selected' : ''}>${esc(type)}</option>`,
    ).join('')}</select></div>
    <div class="field"><label>可空</label><select data-k="nullable">
      <option value="1" ${item.nullable === false ? '' : 'selected'}>是</option>
      <option value="0" ${item.nullable === false ? 'selected' : ''}>否</option>
    </select></div>
    <div class="field"><label>默认值</label><input data-k="default" value="${esc(item.default ?? '')}" placeholder="—" /></div>
    <button class="btn sm ghost" type="button" data-drop>×</button>
  </div>`;
}

function readRows(container) {
  return [...container.querySelectorAll('.field-row')]
    .map((row) => {
      const name = row.querySelector('[data-k=name]').value.trim();
      if (!name) return null;
      const rawDefault = row.querySelector('[data-k=default]').value.trim();
      return {
        name,
        type: row.querySelector('[data-k=type]').value,
        nullable: row.querySelector('[data-k=nullable]').value === '1',
        default: rawDefault === '' ? null : rawDefault,
      };
    })
    .filter(Boolean);
}

async function openCreate(view, ctx, preselect) {
  let datasets;
  try {
    datasets = await api.get('/api/datasets', { limit: 200 });
  } catch (err) {
    toast(errorMessage(err), 'err');
    return;
  }
  const { root, close } = drawer({
    title: '提交表结构变更',
    subtitle: '选择基线版本 → 改字段 → 后端现算 diff / 兼容 / 影响面 / 迁移单',
    body: `<form id="change-form" style="display:grid;gap:12px">
      <div style="display:grid;grid-template-columns:1.3fr 0.7fr;gap:10px">
        ${field({
          label: '目标表',
          name: 'dataset_id',
          value: preselect || (datasets.items[0] || {}).id,
          options: datasets.items.map((item) => ({ value: item.id, label: `${item.full_name} · v${item.current_version}` })),
        })}
        <div class="field"><label>基线版本</label><input name="base_version" value="" readonly class="mono" /></div>
      </div>
      ${field({ label: '变更说明', name: 'summary', placeholder: '例如：删除 pay_channel，amount 改 bigint' })}
      <div>
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
          <span class="eyebrow">目标字段（TARGET）</span>
          <button class="btn sm ghost" type="button" id="add-field">+ 新增字段行</button>
        </div>
        <div id="field-rows" style="display:grid;gap:6px;max-height:330px;overflow:auto"></div>
      </div>
      <div class="form-error" id="change-error"></div>
      <button class="btn accent" type="submit">提交并判定</button>
    </form>`,
    footer: '<span class="mono muted">diff、兼容级别、门禁、迁移单均由后端算法生成</span>',
  });

  const form = root.querySelector('#change-form');
  const rows = root.querySelector('#field-rows');
  let baseVersion = 1;

  async function loadDataset(datasetId) {
    const detail = await api.get(`/api/datasets/${datasetId}/versions`);
    const latest = detail.items[0];
    baseVersion = latest ? latest.version : 1;
    form.base_version.value = `v${baseVersion}`;
    rows.innerHTML = (latest ? latest.fields : []).map((item) => fieldRow(item)).join('');
  }

  form.dataset_id.addEventListener('change', async () => {
    try {
      await loadDataset(form.dataset_id.value);
    } catch (err) {
      toast(errorMessage(err), 'err');
    }
  });
  rows.addEventListener('click', (event) => {
    if (event.target.closest('[data-drop]')) event.target.closest('.field-row').remove();
  });
  root.querySelector('#add-field').addEventListener('click', () => {
    rows.insertAdjacentHTML('beforeend', fieldRow({}));
  });

  try {
    await loadDataset(form.dataset_id.value);
  } catch (err) {
    root.querySelector('#change-error').textContent = errorMessage(err);
  }

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const button = form.querySelector('button[type=submit]');
    button.disabled = true;
    button.textContent = '判定中…';
    try {
      const payload = {
        dataset_id: Number(form.dataset_id.value),
        base_version: baseVersion,
        summary: form.summary.value.trim() || null,
        target_fields: readRows(rows),
      };
      const created = await api.post('/api/change-requests', payload);
      toast(`已提交 ${created.code}：${created.compat_label} / 门禁 ${created.gate_label}`);
      close();
      await changesPage.render(view, ctx);
      openDetail(view, ctx, created.id);
    } catch (err) {
      root.querySelector('#change-error').textContent =
        err.code === 'VALIDATION' ? '字段不合法（名称需字母开头，类型必填）' : errorMessage(err);
      button.disabled = false;
      button.textContent = '提交并判定';
    }
  });
}

function impactBlock(detail) {
  const impact = detail.impact || {};
  if (!impact.consumer_count) {
    return `<p class="muted">没有下游消费方引用被影响列（${esc((impact.affected_fields || []).join('、') || '无')}）。</p>`;
  }
  return `<div class="ledger">
    ${(impact.affected_consumers || [])
      .map(
        (item) => `<div class="ledger-row" style="grid-template-columns:1.1fr 1fr 58px 58px">
          <b>${esc(item.name)}<div class="t">${esc(item.team)} · ${esc(item.owner || '—')}</div></b>
          <span class="mono">命中列 ${esc(item.hit_columns.join(', '))}</span>
          <span class="mono">${item.tasks.length} 任务</span>
          <span class="mono">${item.reports.length} 报表</span>
        </div>`,
      )
      .join('')}
  </div>
  <div class="annot-note">影响面：${impact.consumer_count} 个消费方 · ${impact.task_count} 个任务 · ${impact.report_count} 张报表（任务 ≥3 记 critical）</div>`;
}

async function openDetail(view, ctx, requestId) {
  let detail;
  try {
    detail = await api.get(`/api/change-requests/${requestId}`);
  } catch (err) {
    toast(errorMessage(err), 'err');
    return;
  }
  const canRun = can(ctx.user.role, 'change:run');
  const canApprove = can(ctx.user.role, 'change:approve');
  const canExport = can(ctx.user.role, 'export:read');
  const pending = ['submitted', 'checked'].includes(detail.status);

  const actionHtml = canApprove && pending
    ? `<form id="decide-form" style="display:grid;gap:8px">
        ${field({ label: '放行理由（gate=block 时必填）', name: 'note', placeholder: '例如：下游已切兼容视图，回滚脚本已演练' })}
        <div style="display:flex;gap:8px">
          <button class="btn accent" type="submit" value="approve" data-action="approve">批准放行</button>
          <button class="btn annot" type="submit" value="reject" data-action="reject">驳回</button>
        </div>
      </form>`
    : `<span class="mono muted">${pending ? '当前角色只能查看，审批需平台管理员' : `已在 ${fmtTime(detail.decided_at)} 由 ${esc(detail.decided_by || '—')} 处置`}</span>`;

  const { root, close } = drawer({
    title: `${detail.code} · ${detail.dataset_name}`,
    subtitle: `基线 v${detail.base_version} · ${detail.summary || '无说明'} · 提交人 ${detail.author}`,
    body: `
      <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px">
        <span class="badge ${compatTone(detail.compat)}">${esc(detail.compat_label)}</span>
        <span class="badge ${gateTone(detail.gate)}">门禁 ${esc(detail.gate_label)}</span>
        <span class="badge ${riskTone(detail.risk)}">风险 ${esc(detail.risk_label)}</span>
        <span class="badge ${statusTone(detail.status)}">${esc(detail.status_label)}</span>
        <span class="badge">${detail.diff_count} 项变更 / ${detail.breaking_count} 项破坏</span>
      </div>
      ${kv([
        ['影响面', `${detail.affected_consumers} 个下游 · ${detail.affected_tasks} 个任务 · ${detail.affected_reports} 张报表`],
        ['检测时间', fmtTime(detail.checked_at)],
        ['审批结论', detail.decision_note ? esc(detail.decision_note) : '—'],
      ])}
      <h3 style="margin:14px 0 4px;font-size:0.9rem">字段 diff（左：基线 / 右：目标）</h3>
      ${diffColumns({ baseFields: detail.base_fields || [], targetFields: detail.target_fields || [], diff: detail.diff || [] })}
      <h3 style="margin:14px 0 4px;font-size:0.9rem">逐字段判定</h3>
      ${diffLedger(detail.diff || [])}
      <h3 style="margin:14px 0 4px;font-size:0.9rem">下游影响</h3>
      ${impactBlock(detail)}
      <h3 style="margin:14px 0 4px;font-size:0.9rem">迁移单（含回滚）</h3>
      ${sqlBlock(detail.migration_sql)}`,
    footer: `<div style="display:grid;gap:8px">
      <div style="display:flex;gap:8px;flex-wrap:wrap">
        ${canRun && pending ? '<button class="btn accent" data-run>重跑兼容检测</button>' : ''}
        ${canExport ? '<button class="btn ghost" data-export>下载迁移单 .sql</button>' : ''}
      </div>
      ${actionHtml}
    </div>`,
  });

  root.querySelector('[data-run]')?.addEventListener('click', async () => {
    try {
      const updated = await api.post(`/api/change-requests/${detail.id}/run`, {});
      toast(`检测完成：${updated.compat_label}，${updated.diff_count} 项字段级判定`);
      close();
      await changesPage.render(view, ctx);
      openDetail(view, ctx, detail.id);
    } catch (err) {
      toast(errorMessage(err), 'err');
    }
  });
  root.querySelector('[data-export]')?.addEventListener('click', async () => {
    try {
      await api.download(`/api/exports/migrations/${detail.id}.sql`, `${detail.code}_migration.sql`);
      toast('迁移单已开始下载');
    } catch (err) {
      toast(errorMessage(err), 'err');
    }
  });
  root.querySelector('#decide-form')?.addEventListener('submit', async (event) => {
    event.preventDefault();
    const action = event.submitter?.dataset.action || 'approve';
    try {
      const updated = await api.post(`/api/change-requests/${detail.id}/decision`, {
        action,
        note: event.target.note.value.trim() || null,
      });
      toast(action === 'approve' ? `已放行 ${updated.code}` : `已驳回 ${updated.code}`);
      close();
      await changesPage.render(view, ctx);
    } catch (err) {
      toast(
        err.status === 422
          ? '破坏性变更（gate=block）必须填写放行理由'
          : err.code === 'CONFLICT'
            ? '该变更已被处置，请刷新'
            : errorMessage(err),
        'err',
      );
    }
  });
}

export const changesPage = {
  async render(view, ctx) {
    state.datasetId = ctx.query.dataset_id || state.datasetId;
    let data;
    try {
      data = await api.get('/api/change-requests', {
        compat: state.compat,
        gate: state.gate,
        status: state.status,
        q: state.q,
        dataset_id: state.datasetId,
        limit: 50,
      });
    } catch (err) {
      view.innerHTML = errorBox(errorMessage(err));
      view.querySelector('#retry-btn')?.addEventListener('click', () => changesPage.render(view, ctx));
      return;
    }
    view.innerHTML = `
      <section class="sheet">
        <div class="sheet-head">
          <b>变更申请</b>
          <span>${data.total} 条 · 点开看左右对照与门禁结果</span>
          <span class="mono">${state.datasetId ? `按表过滤 #${esc(state.datasetId)}` : '全部表'}</span>
        </div>
        <div class="filter-bar" id="change-filters" style="margin-bottom:12px">
          ${field({ label: '搜索', name: 'q', value: state.q, placeholder: '单号 / 说明' })}
          ${field({ label: '兼容级别', name: 'compat', value: state.compat, options: [{ value: '', label: '全部' }, ...Object.entries(ENUMS.compat).map(([value, label]) => ({ value, label }))] })}
          ${field({ label: '门禁', name: 'gate', value: state.gate, options: [{ value: '', label: '全部' }, { value: 'block', label: '阻塞' }, { value: 'pass', label: '放行' }] })}
          ${field({ label: '状态', name: 'status', value: state.status, options: [{ value: '', label: '全部' }, ...Object.entries(ENUMS.status).map(([value, label]) => ({ value, label }))] })}
          <div class="spacer"></div>
          ${can(ctx.user.role, 'change:create') ? '<button class="btn sm accent" id="new-change">提交变更</button>' : ''}
        </div>
        ${table({
          rows: data.items,
          columns: [
            { key: 'code', label: '单号', className: 'mono' },
            { key: 'dataset_name', label: '表', render: (row) => `<b class="mono">${esc(row.dataset_name)}</b>` },
            {
              key: 'diff_count',
              label: '变更',
              className: 'num',
              render: (row) => `${row.diff_count}<span class="muted"> / ${row.breaking_count} 破坏</span>`,
            },
            { key: 'compat', label: '兼容', render: (row) => `<span class="badge ${compatTone(row.compat)}">${esc(row.compat_label)}</span>` },
            { key: 'gate', label: '门禁', render: (row) => `<span class="badge ${gateTone(row.gate)}">${esc(row.gate_label)}</span>` },
            { key: 'risk', label: '风险', render: (row) => `<span class="badge ${riskTone(row.risk)}">${esc(row.risk_label)}</span>` },
            { key: 'affected_tasks', label: '影响任务', className: 'num' },
            { key: 'affected_reports', label: '报表', className: 'num' },
            { key: 'status', label: '状态', render: (row) => `<span class="badge ${statusTone(row.status)}">${esc(row.status_label)}</span>` },
          ],
          empty: { title: '没有匹配的变更申请', hint: '换个筛选，或点右上「提交变更」。' },
        })}
        <div class="titleblock">
          <div><b>视图</b>变更申请</div>
          <div><b>筛选</b>${esc(ENUMS.compat[state.compat] || '全部兼容级别')}</div>
          <div><b>记录数</b>${data.items.length}</div>
          <div><b>来源</b>/api/change-requests</div>
        </div>
      </section>`;

    const filters = view.querySelector('#change-filters');
    filters?.addEventListener('change', () => {
      state.q = filters.querySelector('[name=q]').value.trim();
      state.compat = filters.querySelector('[name=compat]').value;
      state.gate = filters.querySelector('[name=gate]').value;
      state.status = filters.querySelector('[name=status]').value;
      changesPage.render(view, ctx);
    });
    filters?.querySelector('[name=q]')?.addEventListener('keydown', (event) => {
      if (event.key === 'Enter') {
        state.q = event.target.value.trim();
        changesPage.render(view, ctx);
      }
    });
    view.querySelectorAll('table.data tbody tr').forEach((row) => {
      row.addEventListener('click', () => openDetail(view, ctx, Number(row.dataset.id)));
    });
    view.querySelector('#new-change')?.addEventListener('click', () =>
      openCreate(view, ctx, state.datasetId ? Number(state.datasetId) : null),
    );
  },
};

export default changesPage;
