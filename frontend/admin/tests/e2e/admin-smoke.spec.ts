import { expect, test } from '@playwright/test'

import { setAdminSession } from './auth'

test('admin 关键页面可进入（smoke）', async ({ page }) => {
  await setAdminSession(page)

  await page.goto('/admin/dashboard')
  await expect(page.getByText('仪表盘')).toBeVisible()

  // 订单监管
  await page.goto('/admin/orders')
  await expect(page.getByText('订单监管')).toBeVisible()

  // 商品审核/监管
  await page.goto('/admin/products')
  await expect(page.getByText('商品审核/监管')).toBeVisible()

  // 售后仲裁
  await page.goto('/admin/after-sales')
  await expect(page.getByText('售后仲裁')).toBeVisible()

  // 预约管理（监管只读）
  await page.goto('/admin/bookings')
  await expect(page.getByText('预约管理')).toBeVisible()

  // 权益与核销（监管只读）
  await page.goto('/admin/entitlements')
  await expect(page.getByText('权益与核销')).toBeVisible()

  // 小程序配置中心
  await page.goto('/admin/mini-program')
  await expect(page.getByText('小程序配置中心')).toBeVisible()

  // 健行天下：服务包模板/阶梯价格
  await page.goto('/admin/service-packages')
  await expect(page.getByText('服务包模板')).toBeVisible()

  await page.goto('/admin/service-package-pricing')
  await expect(page.getByText('阶梯价格配置')).toBeVisible()

  // 审计日志
  await page.goto('/admin/audit-logs')
  await expect(page.getByText('审计日志')).toBeVisible()
})

