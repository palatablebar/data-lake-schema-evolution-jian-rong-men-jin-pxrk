import { api } from '../api.js';
import { session } from '../store.js';
import { BRAND } from '../config.js';
import { errorMessage, esc, toast } from '../ui.js';

export const loginPage = {
  async render(root, ctx) {
    root.className = 'login-host';
    root.innerHTML = `
      <div class="login">
        <section class="login-brief">
          <div class="eyebrow">${esc(BRAND.edition)} · 图纸说明</div>
          <h1>${esc(BRAND.title)}<br /><em>${esc(BRAND.short)}</em></h1>
          <p class="tagline">${esc(BRAND.loginLead)}</p>
          <div class="brief-points">
            ${BRAND.loginPoints
              .map(([no, text]) => `<div class="brief-point"><i>${esc(no)}</i><span>${esc(text)}</span></div>`)
              .join('')}
          </div>
          <dl class="login-spec">
            ${BRAND.spec.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join('')}
          </dl>
          <div class="login-annot">批注：门禁不是审批流程的装饰。判定结果、影响任务数与回滚脚本缺一不可，否则视为未完成变更。</div>
        </section>
        <section class="login-form-wrap">
          <form class="login-card" id="login-form" novalidate>
            <div>
              <div class="brand">${esc(BRAND.title)}</div>
              <div class="sub mono" style="font-size:0.72rem">使用内部账号登录；三个演示账号权限不同，页面与按钮随角色变化。</div>
            </div>
            <div class="field">
              <label for="email">邮箱</label>
              <input id="email" name="email" type="email" autocomplete="username" value="admin@${esc(BRAND.short)}.io" required />
            </div>
            <div class="field">
              <label for="password">密码</label>
              <input id="password" name="password" type="password" autocomplete="current-password" value="Demo@2026" required />
            </div>
            <div class="form-error" id="login-error" role="alert"></div>
            <button class="btn accent" id="login-submit" type="submit">进入门禁台</button>
            <div class="login-hint">
              演示账号（密码 <code>Demo@2026</code>）：<br />
              <code>admin@${esc(BRAND.short)}.io</code> 管理员 · <code>analyst@${esc(BRAND.short)}.io</code> 数据开发 ·
              <code>viewer@${esc(BRAND.short)}.io</code> 下游只读
            </div>
          </form>
        </section>
        <div class="login-titleblock">
          <div><b>图号</b>DWG-405</div>
          <div><b>比例</b>1 : 240 表</div>
          <div><b>版本</b>REV 2026-11</div>
          <div><b>绘制 / 审核</b>${esc(BRAND.org)}</div>
        </div>
      </div>`;

    const form = root.querySelector('#login-form');
    const errorNode = root.querySelector('#login-error');
    const submit = root.querySelector('#login-submit');
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      errorNode.textContent = '';
      submit.disabled = true;
      submit.textContent = '正在校验…';
      try {
        const result = await api.post('/api/auth/login', {
          email: form.email.value.trim(),
          password: form.password.value,
        });
        session.set(result.access_token, result.user);
        toast(`欢迎回来，${result.user.display_name}`);
        location.hash = '#/overview';
        await ctx.reload();
      } catch (err) {
        errorNode.textContent = err.code === 'AUTH_INVALID' ? '账号或密码不正确' : errorMessage(err);
      } finally {
        submit.disabled = false;
        submit.textContent = '进入门禁台';
      }
    });
  },
};

export default loginPage;
