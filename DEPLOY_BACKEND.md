# QuotePilot AI — 后端部署（云同步）

把后端部署到 Railway（免费额度），前端 Vercel 通过 API 连接后端，实现多设备数据同步。

---

## 第一步：部署 PostgreSQL

1. 访问 [railway.app](https://railway.app)，用 GitHub 登录
2. 点击 **New Project** → **Deploy PostgreSQL**
3. 记下连接信息（Host、Port、User、Password、Database）

---

## 第二步：部署后端

在 Railway 同一项目中：

1. 点击 **New Service** → **Deploy from GitHub Repo**
2. 选择你的 `quotepilot-ai` 仓库
3. **Root Directory** 填 `backend`
4. **Environment Variables** 添加：

| 变量名 | 值 |
|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://用户名:密码@host:5432/数据库名` |
| `DATABASE_URL_SYNC` | `postgresql+psycopg2://用户名:密码@host:5432/数据库名` |

> 用户名/密码/host/数据库名 从上一步的 PostgreSQL 连接信息获取

5. 点击 **Deploy**

部署完成后获得后端地址，如 `https://quotepilot-backend.up.railway.app`。

---

## 第三步：更新后端文件上传支持

后端目前只接受 PDF/Excel/Word。需要加入 CSV 支持。

编辑 `backend/app/api/products.py` 第 68 行：

```python
# 将
allowed_exts = {".pdf", ".xlsx", ".xls", ".docx", ".doc"}
# 改为
allowed_exts = {".pdf", ".xlsx", ".xls", ".docx", ".doc", ".csv"}
```

提交并推送，Railway 自动重新部署。

---

## 第四步：配置前端连接后端

在 [vercel.com](https://vercel.com) 找到你的前端项目：

1. 进入 **Settings** → **Environment Variables**
2. 添加：

| 变量名 | 值 |
|---|---|
| `NEXT_PUBLIC_API_URL` | `https://你的后端地址.railway.app` |

3. 重新部署（**Deployments** → 三点菜单 → **Redeploy**）

---

## 验证

部署完成后：

1. 在电脑端上传 CSV 产品文件
2. 手机浏览器打开 Vercel 地址
3. 产品列表应该自动同步显示

---

## 不部署后端？（本地模式）

不设 `NEXT_PUBLIC_API_URL` 环境变量时，应用自动使用 localStorage 本地存储，完全不需要后端。上传的产品仅限当前设备。
