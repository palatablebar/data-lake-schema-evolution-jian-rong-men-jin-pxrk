import { api } from '../api.js';
import { ENUMS, can } from '../config.js';
import { drawer, errorBox, errorMessage, esc, field, fmtTime, kv, table, toast } from '../ui.js';

const state = { q: '', dbName: '', format: '' };

function fieldsTable(fields) {
  if (!fields || fields.length === 0) return '<p class="muted">该版本没有字段记录。</p>';
  return `<div class="table-wrap"><table class="data" style="min-width:0">
    <thead><tr><th>#</th><th>字段</th><th>类型</th><th>可空</th><th>默认</th><th>注释</th></tr></thead>
    <tbody>${fields
      .map(
        (item, index) => `<tr>
          <td class="mono">${index + 1}</td>
          <td class="mono">${esc(item.name)}</td>
          <td><span class="type-chip">${esc(item.type)}</span></td>
          <td>${item.nullable ? '是' : '否'}</td>
          <td class="mono">${esc(item.default ?? '—')}</td>
          <td class="muted">${esc(item.comment || '')}</td>
        </tr>`,
      )
      .join('')}</tbody></table></div>`;
}

async function openDataset(view, ctx, dataset) {
  let versions;
  try {
    versions = await api.get(`/api/datasets/${dataset.id}/versions`);
  } catch (err) {
    toast(errorMessage(err), 'err');
    return;
  }
  const latest = versions.items[0];
  const history = versions.items
    .map(
      (item) => `<div class="ledger-row">
        <b class="mono">v${item.version}</b>
        <span>${esc(item.summary || '—')}<div class="t">${esc(item.author)} · ${fmtTime(item.committed_at)}</div></span>
        <span class="mono">${item.field_count} 列</span>
        <span>${item.version === dataset.current_version ? '<span class="badge ok">当前</span>' : ''}</span>
      </div>`,
    )
    .join('');
  const { root, close } = drawer({
    title: dataset.full_name,
    subtitle: `${dataset.format_label} · ${dataset.owner} · 分区 ${dataset.partition_key || '无'}`,
    body: `${kv([
      ['当前版本', `<span class="mono">v${dataset.current_version}</span>`],
      ['字段数', `${dataset.field_count}`],
      ['下游消费方', `${dataset.consumer_count} 个`],
      ['行数', dataset.row_count.toLocaleString('zh-CN')],
      ['说明', esc(dataset.description || '—')],
    ])}
    <h3 style="margin:14px 0 6px;font-size:0.9rem">版本历史（${versions.total}）</h3>
    <div class="ledger">${history}</div>
    <h3 style="margin:14px 0 6px;font-size:0.9rem">当前字段（v${dataset.current_version}）</h3>
    ${fieldsTable(latest ? latest.fields : [])}`,
    footer: can(ctx.user.role, 'change:create')
      ? `<button class="btn accent" data-change>基于当前版本提交变更</button>`
      : '<span class="mono muted">只读角色仅可查看结构</span>',
  });
  root.querySelector('[data-change]')?.addEventListener('click', () => {
    close();
    location.hash = `#/changes?dataset_id=${dataset.id}`;
  });
}

function openCreate(view, ctx) {
  const { root, close } = drawer({
    title: '登记湖仓表',
    subtitle: '登记后即可在「变更申请」里基于它做 diff',
    body: `<form id="dataset-form" class="form-grid" style="display:grid;gap:12px">
      ${field({ label: '库名（如 dwd）', name: 'db_name', placeholder: 'dwd' })}
      ${field({ label: '表名（如 dwd_order_detail）', name: 'table_name', placeholder: 'dwd_order_detail' })}
      ${field({
        label: '表格式',
        name: 'format',
        value: 'iceberg',
        options: Object.entries(ENUMS.format).map(([value, label]) => ({ value, label })),
      })}
      ${field({ label: '分区键', name: 'partition_key', placeholder: 'dt' })}
      ${field({ label: '负责人', name: 'owner', placeholder: '周棠' })}
      ${field({ label: '说明', name: 'description' })}
      <div class="form-error" id="dataset-error"></div>
      <button class="btn accent" type="submit">保存</button>
    </form>`,
  });
  root.querySelector('#dataset-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    const form = event.target;
    try {
      await api.post('/api/datasets', {
        db_name: form.db_name.value.trim(),
        table_name: form.table_name.value.trim(),
        format: form.format.value,
        partition_key: form.partition_key.value.trim() || null,
        owner: form.owner.value.trim() || null,
        description: form.description.value.trim() || null,
      });
      toast('表已登记（v1 空结构，可在变更申请里补字段）');
      close();
      await datasetsPage.render(view, ctx);
    } catch (err) {
      root.querySelector('#dataset-error').textContent =
        err.code === 'CONFLICT' ? '同名表已存在' : errorMessage(err);
    }
  });
}

export const datasetsPage = {
  async render(view, ctx) {
    let data;
    try {
      data = await api.get('/api/datasets', {
        q: state.q,
        db_name: state.dbName,
        format: state.format,
        limit: 60,
      });
    } catch (err) {
      view.innerHTML = errorBox(errorMessage(err));
      view.querySelector('#retry-btn')?.addEventListener('click', () => datasetsPage.render(view, ctx));
      return;
    }
    const dbs = [...new Set(data.items.map((item) => item.db_name))];
    view.innerHTML = `
      <section class="sheet">
        <div class="sheet-head">
          <b>表目录与版本</b>
          <span>共 ${data.total} 张表 · 版本快照在抽屉里按 v 倒序</span>
        </div>
        <div class="filter-bar" id="dataset-filters" style="margin-bottom:12px">
          ${field({ label: '搜索', name: 'q', value: state.q, placeholder: '表名 / 负责人 / 说明' })}
          ${field({ label: '库', name: 'db_name', value: state.dbName, options: [{ value: '', label: '全部' }, ...dbs.map((db) => ({ value: db, label: db }))] })}
          ${field({ label: '表格式', name: 'format', value: state.format, options: [{ value: '', label: '全部' }, ...Object.entries(ENUMS.format).map(([value, label]) => ({ value, label }))] })}
          <div class="spacer"></div>
          ${can(ctx.user.role, 'dataset:write') ? '<button class="btn sm annot" id="new-dataset">登记表</button>' : ''}
        </div>
        ${table({
          rows: data.items,
          columns: [
            { key: 'db_name', label: '库', className: 'mono' },
            { key: 'table_name', label: '表', render: (row) => `<b class="mono">${esc(row.table_name)}</b>` },
            { key: 'format_label', label: '格式', render: (row) => `<span class="type-chip">${esc(row.format_label)}</span>` },
            { key: 'current_version', label: '当前版本', className: 'num', render: (row) => `v${row.current_version}` },
            { key: 'version_count', label: '版本数', className: 'num' },
            { key: 'field_count', label: '字段', className: 'num' },
            { key: 'consumer_count', label: '下游', className: 'num' },
            { key: 'partition_key', label: '分区', render: (row) => esc(row.partition_key || '—') },
            { key: 'owner', label: '负责人' },
          ],
          empty: { title: '没有匹配的表', hint: '调整筛选，或由管理员登记新表。' },
        })}
        <div class="titleblock">
          <div><b>视图</b>表目录</div>
          <div><b>当前筛选</b>${esc(state.dbName || '全部库')} / ${esc(ENUMS.format[state.format] || '全部格式')}</div>
          <div><b>记录数</b>${data.items.length}</div>
          <div><b>来源</b>/api/datasets</div>
        </div>
      </section>`;

    const filters = view.querySelector('#dataset-filters');
    filters?.addEventListener('change', () => {
      state.q = filters.querySelector('[name=q]').value.trim();
      state.dbName = filters.querySelector('[name=db_name]').value;
      state.format = filters.querySelector('[name=format]').value;
      datasetsPage.render(view, ctx);
    });
    filters?.querySelector('[name=q]')?.addEventListener('keydown', (event) => {
      if (event.key === 'Enter') {
        state.q = event.target.value.trim();
        datasetsPage.render(view, ctx);
      }
    });
    view.querySelectorAll('table.data tbody tr').forEach((row) => {
      row.addEventListener('click', () => {
        const item = data.items.find((entry) => String(entry.id) === row.dataset.id);
        if (item) openDataset(view, ctx, item);
      });
    });
    view.querySelector('#new-dataset')?.addEventListener('click', () => openCreate(view, ctx));
  },
};

export default datasetsPage;
