# QuotePilot AI — 线上部署（前后端分离）

前端 Vercel + 后端 Railway + 数据库 Railway PostgreSQL。

---

## 第一步：部署 PostgreSQL 数据库

1. 访问 [railway.app](https://railway.app)，用 GitHub 登录
2. 点击 **New Project**
3. 选择 **Deploy PostgreSQL**
4. 等数据库创建完成后，点进去 → **Connect** 标签
5. 记下 **Postgres Connection URL**（类似 `postgresql://postgres:xxx@host:5432/railway`）

---

## 第二步：部署后端

1. Railway 同一项目中，点 **+ New Service** → **GitHub Repo**
2. 选择你的 `quotepilot-ai` 仓库
3. **Root Directory** 填 `backend`
4. **Variables** 中添加以下环境变量：

| 变量 | 值 |
|---|---|
| `DATABASE_URL` | 把第一步的 URL 改为 `postgresql+asyncpg://postgres:密码@host:5432/railway` |
| `OPENAI_API_KEY` | `sk-你的LLM密钥` |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` |
| `LLM_MODEL` | `gpt-4o-mini` |

> 注意：`DATABASE_URL` 将 `postgresql://` 替换为 `postgresql+asyncpg://`

5. 点击 **Deploy**，等待构建完成
6. 部署成功后，在 **Settings** → **Networking** 里找到你的后端域名，例如 `https://quotepilot-backend.up.railway.app`

---

## 第三步：部署前端到 Vercel

如果还没部署前端：

```powershell
cd "F:\QuotePilot AI\frontend"
npm install -g vercel
vercel login
vercel
```

如果已经部署过，进入 [vercel.com](https://vercel.com) 项目：

1. **Settings** → **Environment Variables**
2. 添加：

| Key | Value |
|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | `https://你的后端域名.up.railway.app` |

3. **Deployments** → 三点菜单 → **Redeploy**（或直接 `git push` 触发）

---

## 验证

1. 打开 Vercel 给你的域名（如 `https://quotepilot.vercel.app`）
2. 上传 CSV 产品，粘贴询盘测试
3. 手机浏览器打开同一地址，数据同步

---

## 故障排查

**后端启动失败？**
- 检查 Railway 构建日志，确认 `requirements.txt` 安装成功
- Railway 默认用 `uvicorn app.main:app --host 0.0.0.0 --port $PORT`，无需额外配置

**前端连不上后端？**
- 确认 `NEXT_PUBLIC_API_BASE_URL` 填的是后端完整域名（含 `https://`，不含尾部 `/`）
- 确认后端已部署成功（Railway 状态为 Active）
- 浏览器 F12 → Console 查看错误信息

**后端不可用时会怎样？**
- 前端自动降级到本地 mock 模式，不会白屏
- Key 未设置时分析/报价使用规则引擎，功能仍可用
