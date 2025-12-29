import type { Page } from '@playwright/test'

type AdminLoginOk = { token: string; admin: { id: string; username: string } }
type AdminLogin2fa = { requires2fa: true; challengeId: string }

export async function setAdminSession(page: Page, opts?: { username?: string; password?: string }) {
  const username = opts?.username ?? 'admin'
  const password = opts?.password ?? '123456'

  // 通过前端同源请求（Vite dev 代理）拿到 token，再直接写 localStorage（避免 UI 交互不稳定）
  const resp = await page.request.post('/api/v1/admin/auth/login', {
    data: { username, password },
  })
  if (!resp.ok()) {
    throw new Error(`admin login failed: http=${resp.status()} body=${await resp.text()}`)
  }

  const payload = (await resp.json()) as { success: boolean; data: AdminLoginOk | AdminLogin2fa }
  if (!payload?.success) {
    throw new Error(`admin login failed: success=false payload=${JSON.stringify(payload)}`)
  }

  const data = payload.data
  if ((data as AdminLogin2fa).requires2fa === true) {
    // CI/E2E 环境通常应关闭 2FA；若启用则提示配置问题
    throw new Error('admin login requires 2FA (requires2fa=true); E2E 环境请关闭 2FA 或提供专用账号')
  }

  const ok = data as AdminLoginOk
  await page.addInitScript(
    ({ token, actorType, actorUsername }) => {
      window.localStorage.setItem('lhmy.admin.token', token)
      window.localStorage.setItem('lhmy.admin.actorType', actorType)
      window.localStorage.setItem('lhmy.admin.actorUsername', actorUsername)
    },
    { token: ok.token, actorType: 'ADMIN', actorUsername: ok.admin.username },
  )
}

