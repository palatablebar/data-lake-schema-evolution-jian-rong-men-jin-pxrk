import { api } from '../api.js';
import { ENUMS, can, changeTypeTone } from '../config.js';
import { barList, emptyState, errorBox, errorMessage, esc, field, fmtTime, sqlBlock, table, toast } from '../ui.js';

const state = { requestId: '', breaking: '' };

export const exportsPage = {
  async render(view, ctx) {
    let checks;
    let requests;
    try {
      requests = await api.get('/api/change-requests', { limit: 50 });
      if (!state.requestId && requests.items.length) {
        // 默认选影响面最大的那条（其字段级检测最完整），避免进页面看到空清单
        const top = [...requests.items].sort((a, b) => b.affected_tasks - a.affected_tasks)[0];
        state.requestId = top.id;
      }
      checks = await api.get('/api/compat-checks', {
        request_id: state.requestId,
        breaking: state.breaking,
        limit: 100,
      });
    } catch (err) {
      view.innerHTML = errorBox(errorMessage(err));
      view.querySelector('#retry-btn')?.addEventListener('click', () => exportsPage.render(view, ctx));
      return;
    }
    const summary = checks.summary || { total: 0, breaking: 0, safe: 0, by_type: [] };
    const current = requests.items.find((item) => item.id === Number(state.requestId));
    const canExport = can(ctx.user.role, 'export:read');

    view.innerHTML = `
      <section class="sheet">
        <div class="sheet-head">
          <b>迁移单与导出</b>
          <span>字段级检测 ${summary.total} 条 · 破坏 ${summary.breaking} 条 · 安全 ${summary.safe} 条</span>
        </div>
        <div class="split-2">
          <section class="panel">
            <div class="panel-head"><h2>字段级检测清单</h2><span class="meta">compat checks</span></div>
            <div class="panel-body">
              <div class="filter-bar" style="margin-bottom:10px">
                ${field({
                  label: '变更单',
                  name: 'request_id',
                  value: state.requestId,
                  options: requests.items.map((item) => ({ value: item.id, label: `${item.code} · ${item.dataset_name}` })),
                })}
                ${field({ label: '破坏性', name: 'breaking', value: state.breaking, options: [{ value: '', label: '全部' }, { value: 'true', label: '仅破坏性' }, { value: 'false', label: '仅安全' }] })}
              </div>
              ${table({
                rows: checks.items,
                columns: [
                  { key: 'field', label: '字段', className: 'mono' },
                  { key: 'change_type', label: '变更类型', render: (row) => `<span class="badge ${changeTypeTone(row.change_type)}">${esc(row.change_type_label)}</span>` },
                  { key: 'breaking', label: '判定', render: (row) => (row.breaking ? '<span class="badge danger">破坏</span>' : '<span class="badge ok">安全</span>') },
                  { key: 'detail', label: '依据', render: (row) => `<span class="muted">${esc(row.detail)}</span>` },
                  { key: 'request_code', label: '单号', className: 'mono' },
                ],
                empty: { title: '该筛选下没有检测记录', hint: '到「变更申请」点开单据执行一次检测。' },
              })}
            </div>
          </section>
          <div style="display:grid;gap:var(--pad);align-content:start">
            <section class="panel">
              <div class="panel-head"><h2>变更类型分布</h2><span class="meta">by change type</span></div>
              <div class="panel-body">
                ${summary.by_type.length ? barList(summary.by_type.filter((item) => item.count > 0)) : emptyState({ title: '还没有检测记录' })}
                <div class="annot-note">破坏性占比 ${summary.total ? ((summary.breaking / summary.total) * 100).toFixed(1) : '0.0'}%，全部由后端算法给出。</div>
              </div>
            </section>
            <section class="panel">
              <div class="panel-head"><h2>迁移单</h2><span class="meta">${esc(current ? current.code : '—')}</span></div>
              <div class="panel-body">
                ${
                  current
                    ? `<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px">
                        <span class="badge ${current.gate === 'block' ? 'danger' : 'ok'}">门禁 ${esc(current.gate_label)}</span>
                        <span class="badge">${esc(current.compat_label)}</span>
                        <span class="badge">${current.diff_count} 项变更</span>
                      </div>
                      ${sqlBlock(current.migration_sql)}
                      <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:10px">
                        <button class="btn accent" id="export-csv" ${canExport ? '' : 'disabled'}>导出检测清单 CSV</button>
                        <button class="btn ghost" id="export-sql" ${canExport ? '' : 'disabled'}>下载迁移单 .sql</button>
                      </div>
                      ${canExport ? '' : '<div class="annot-note">只读角色不能导出（/api/exports 需要 export:read 权限）。</div>'}`
                    : emptyState({ title: '还没有变更单', hint: '先提交一条变更申请。' })
                }
              </div>
            </section>
          </div>
        </div>
        <div class="titleblock">
          <div><b>视图</b>迁移单与导出</div>
          <div><b>当前单据</b>${esc(current ? current.code : '—')}</div>
          <div><b>检测时间</b>${current ? fmtTime(current.checked_at) : '—'}</div>
          <div><b>来源</b>/api/compat-checks · /api/exports</div>
        </div>
      </section>`;

    view.querySelector('#export-csv')?.addEventListener('click', async (event) => {
      try {
        await api.download(`/api/exports/checks.csv${state.requestId ? `?request_id=${state.requestId}` : ''}`, 'checks.csv');
        toast('检测清单已开始下载');
      } catch (err) {
        toast(errorMessage(err), 'err');
        event.target.disabled = true;
      }
    });
    view.querySelector('#export-sql')?.addEventListener('click', async () => {
      try {
        await api.download(`/api/exports/migrations/${state.requestId}.sql`, `${current ? current.code : 'migration'}.sql`);
        toast('迁移单已开始下载');
      } catch (err) {
        toast(errorMessage(err), 'err');
      }
    });
    view.querySelectorAll('.filter-bar select').forEach((select) => {
      select.addEventListener('change', () => {
        state.requestId = Number(view.querySelector('[name=request_id]').value);
        state.breaking = view.querySelector('[name=breaking]').value;
        exportsPage.render(view, ctx);
      });
    });
  },
};

export default exportsPage;
