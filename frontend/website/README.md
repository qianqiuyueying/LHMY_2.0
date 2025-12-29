# 企业官网（阶段13）

技术栈：Vue 3 + TypeScript + Vite + Naive UI + Vue Router。

## 本地开发

```bash
npm install
npm run dev
```

默认通过 Vite 代理访问后端：`/api -> http://localhost:8000`（见 `vite.config.ts`）。

## 环境变量（可选）

- `VITE_API_BASE`：API 前缀，默认 `/api`
- `VITE_CONTACT_EMAIL`：联系邮箱
- `VITE_CONTACT_PHONE`：联系电话

## 导流外链（运行时配置）

官网“进入小程序 / H5购买高端服务卡”不再使用构建时环境变量写死；改为运行时从后端读取：

- `GET /api/v1/website/external-links`
- 配置承载：`SystemConfig.key="WEBSITE_EXTERNAL_LINKS"`

