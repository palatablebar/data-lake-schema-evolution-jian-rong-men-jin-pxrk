import { api } from '../api.js';
import { ENUMS, compatTone, gateTone, riskTone } from '../config.js';
import { barList, emptyState, errorBox, errorMessage, esc, fmtTime, gauge, statStrip, trendChart } from '../ui.js';

function recentLedger(items) {
  if (!items || items.length === 0) return emptyState({ title: '还没有变更申请', hint: '去「变更申请」提交第一条。' });
  return `<div class="ledger" data-testid="recent-changes">${items
    .map(
      (item) => `<div class="ledger-row">
        <span class="mono">${esc(item.code)}</span>
        <span><b>${esc(item.dataset_name || '—')}</b>
          <div class="t">${esc(item.status_label)} · 影响 ${item.affected_tasks} 任务 · ${fmtTime(item.created_at)}</div></span>
        <span class="badge ${compatTone(item.compat)}">${esc(item.compat_label)}</span>
        <span class="badge ${gateTone(item.gate)}">${esc(ENUMS.gate[item.gate] || item.gate)}</span>
      </div>`,
    )
    .join('')}</div>`;
}

export const overviewPage = {
  async render(view, ctx) {
    let data;
    try {
      data = await api.get('/api/overview');
    } catch (err) {
      view.innerHTML = errorBox(errorMessage(err));
      view.querySelector('#retry-btn')?.addEventListener('click', () => overviewPage.render(view, ctx));
      return;
    }
    const riskBars = (data.risk || []).map((item) => ({ ...item, count: item.count }));
    view.innerHTML = `
      <section class="sheet">
        <div class="sheet-head">
          <b>DWG-405 · 兼容门禁总览</b>
          <span>表 ${data.datasets_total} / 版本 ${data.versions_total} / 变更 ${data.changes_total} / 检测 ${data.checks_total}</span>
          <span class="mono">${data.worker_alive ? 'worker 在岗' : 'worker 心跳超时'}</span>
        </div>
        ${statStrip([
          { label: '湖仓表', value: data.datasets_total, hint: `${data.versions_total} 个版本快照` },
          { label: '待审变更', value: data.pending_total, hint: `${data.blocked_total} 条被门禁阻塞` },
          { label: '破坏性占比', value: `${(data.breaking_ratio * 100).toFixed(1)}%`, hint: `${data.breaking_total} / ${data.changes_total} 条变更` },
          { label: '字段级检测', value: data.checks_total, hint: `${data.checks_breaking} 条命中破坏` },
        ])}
        <div class="split-2" style="margin-top:var(--pad)">
          <section class="panel">
            <div class="panel-head"><h2>破坏性变更占比</h2><span class="meta">breaking / all</span></div>
            <div class="panel-body">
              ${gauge({
                ratio: data.breaking_ratio,
                label: 'BREAKING',
                caption: `${data.breaking_total} 条破坏性 · ${data.blocked_total} 条 block`,
              })}
              <div class="annot-note">口径：diff 中出现删列 / 重命名 / 非安全类型变更 / 新增非空无默认值，即判定 breaking 并 block。</div>
              <div class="ruler-bar">
                <span style="width:${Math.round((data.breaking_ratio || 0) * 100)}%;background:var(--annot)"></span>
                <span style="width:${100 - Math.round((data.breaking_ratio || 0) * 100)}%;background:var(--accent-wash)"></span>
              </div>
            </div>
          </section>
          <section class="panel">
            <div class="panel-head"><h2>风险分布</h2><span class="meta">risk</span></div>
            <div class="panel-body">
              ${riskBars.length ? barList(riskBars) : emptyState({ title: '还没有评估结果', hint: '提交变更后自动判定。' })}
            </div>
          </section>
        </div>
        <div class="split-2">
          <section class="panel">
            <div class="panel-head"><h2>最近变更</h2><span class="meta">latest 6</span></div>
            <div class="panel-body">${recentLedger(data.recent_changes)}</div>
          </section>
          <section class="panel">
            <div class="panel-head"><h2>近 7 天提交</h2><span class="meta">changes / day</span></div>
            <div class="panel-body">${trendChart(data.trend.map((p) => ({ date: p.date, runs: p.changes })))}</div>
          </section>
        </div>
        <div class="titleblock">
          <div><b>图纸编号</b>DWG-405-OV</div>
          <div><b>下游团队</b>18 个 · 登记 ${data.consumers_total} 个消费方</div>
          <div><b>门禁口径</b>breaking → block</div>
          <div><b>版本</b>REV 2026-11</div>
        </div>
      </section>`;
  },
};

export default overviewPage;
