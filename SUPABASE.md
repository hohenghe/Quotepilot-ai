# QuotePilot AI — Supabase 云同步部署

零后端部署。只需创建 Supabase 项目，前端直接连接数据库。

---

## 第一步：创建 Supabase 项目

1. 访问 [supabase.com](https://supabase.com)，用 GitHub 登录
2. 点击 **New Project**
3. 填写名称（如 `quotepilot`），设置数据库密码，Region 选离你最近的
4. 等待项目初始化（约 2 分钟）

---

## 第二步：创建数据库表

1. 进入项目 → **SQL Editor** → **New Query**
2. 复制 `F:\QuotePilot AI\supabase-schema.sql` 全部内容并粘贴
3. 点击 **Run**

---

## 第三步：获取 API 密钥

1. 进入 **Project Settings** → **API**
2. 复制以下两个值：

| 变量名 | 来源 |
|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | Project URL（形如 `https://xxx.supabase.co`） |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | `anon public` 密钥 |

---

## 第四步：配置 Vercel

在 [vercel.com](https://vercel.com) 找到你的前端项目：

1. **Settings** → **Environment Variables**
2. 添加上面两个变量
3. 重新部署（**Deployments** → **Redeploy**）

---

## 完成

- 电脑上传 CSV → 数据写入 Supabase → 手机打开自动加载
- 不设环境变量时自动退回 localStorage 本地模式
- 所有产品和询盘数据多设备实时同步

---

## 文件说明

| 文件 | 作用 |
|---|---|
| `src/lib/supabase.ts` | Supabase 客户端（懒加载，SSR 兼容） |
| `src/lib/store.ts` | 双模式存储：Supabase 云端 / localStorage 本地 |
| `supabase-schema.sql` | 数据库建表语句 |
