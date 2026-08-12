# QuotePilot AI — Project Context

AI 驱动的国际贸易销售助手。三端分离（买家/卖家/管理端），买家询盘 → AI 分析 → 跨卖家商品匹配（pgvector 向量 + 关键词）→ 询盘流转给卖家 → AI 生成回复。

---

## Tech Stack

| Layer | Technology |
|---|---|
| 前端 | Next.js 14 (App Router) + React 18 + TypeScript |
| 样式 | Tailwind CSS 3 |
| 图标 | lucide-react |
| 后端 | FastAPI + SQLAlchemy 2.0 (async) + PostgreSQL + pgvector |
| 认证 | JWT (PyJWT) + HMAC 密码哈希 |
| AI (LLM) | OpenAI 兼容 API（DeepSeek / Qwen 等） |
| AI (Embedding) | DashScope Qwen `text-embedding-v4`（1024 维） |
| 部署 | 前端 Vercel + 后端 Railway |

---

## 三端架构

| 路由 | 角色 | 功能 | 认证 |
|---|---|---|---|
| `/buyer` | 买家 | 注册/登录 → 输入询盘 → AI 匹配 → 发送询盘给卖家 | JWT |
| `/seller` | 卖家 | 注册/登录 → 上传/管理产品（按 seller_id 隔离）→ 接收询盘 → AI 回复 | JWT |
| `/admin` | 管理端 | 登录 → 全局仪表盘/卖家/产品/询盘总览 | JWT |
| `/(dashboard)/*` | 旧页面 | `/`、`/products`、`/inquiry`、`/quote`（保留侧边栏，兼容旧功能） | — |

---

## File Structure

```
F:\QuotePilot AI\
├── frontend/
│   └── src/
│       ├── app/
│       │   ├── layout.tsx              # 根布局（无侧边栏），I18nProvider
│       │   ├── buyer/page.tsx          # 买家端
│       │   ├── seller/page.tsx         # 卖家端（产品管理 + 收到的询盘）
│       │   ├── seller/login/page.tsx   # 卖家登录/注册
│       │   ├── admin/page.tsx          # 管理端仪表盘
│       │   ├── admin/login/page.tsx    # 管理端登录
│       │   └── (dashboard)/            # 旧页面路由组（含 AppLayout 侧边栏）
│       ├── components/
│       │   ├── AuthForm.tsx            # 三端复用登录/注册表单（密码确认+显隐+国家下拉）
│       │   ├── AppLayout.tsx           # 旧页面侧边栏布局
│       │   ├── Sidebar.tsx
│       │   ├── LanguageSwitcher.tsx    # 独立语言切换（向下弹出）
│       │   ├── PageHeader.tsx / LoadingSpinner.tsx / EmptyState.tsx
│       ├── i18n/                       # 5 语言：en, zh-CN, zh-TW, es, fr
│       ├── lib/
│       │   ├── api-client.ts           # ⭐ 后端 REST API 客户端（snake↔camel 适配 + JWT 头）
│       │   ├── auth.ts                 # token/user 存取（localStorage）
│       │   ├── countries.ts            # 国家列表
│       │   ├── store.ts                # 旧本地数据层（localStorage/Supabase fallback）
│       │   ├── supabase.ts             # 旧 Supabase 客户端（遗留）
│       │   └── ai/                     # 旧浏览器端 AI（遗留，新流程走后端）
│       └── types/index.ts
├── backend/
│   ├── app/
│   │   ├── main.py                     # FastAPI 入口 + lifespan（init_db + embedding worker + 自动建 admin）
│   │   ├── api/                        # auth, products, inquiries, quotes, dashboard, seller_inquiries
│   │   ├── core/                       # config, database, auth(JWT依赖), security, retry
│   │   ├── models/                     # user, product, inquiry, quote, document, seller_inquiry
│   │   ├── schemas/                    # Pydantic 请求/响应
│   │   └── services/                   # llm, embedding, rag, file_parser
│   ├── seed_admin.py                   # 自动创建管理员（1951444042@qq.com / admin1234）
│   ├── Procfile                        # Railway 启动：uvicorn app.main:app
│   ├── .python-version                 # Python 3.12
│   └── init-db.sql                     # 建表 SQL
├── CHANGELOG.md                        # 开发记录
├── DEPLOY.md                           # 部署指南
└── AGENTS.md                           # 本文件
```

---

## 数据流

### 买家询盘流程

```
买家 → POST /api/inquiries/analyze
  → analyze_inquiry()：非英文先 LLM 翻译 → LLM 结构化提取
  → search_products_hybrid()：query embedding(1次) → pgvector 余弦 Top N → 关键词 rerank
  → 返回 inquiry + analysis + matched_products
买家点「发送询盘」→ POST /api/seller-inquiries/send（按 product 归属 seller）
卖家 → GET /api/seller-inquiries/received → POST /generate-reply（AI 生成回复）
```

### 商品 Embedding（异步）

```
卖家上传 CSV → 解析 → 写入 DB（embedding_status=pending）→ 立即返回
后台 worker（main.py lifespan 启动）：
  扫描 is_active=true AND embedding_status=pending（仅 pending，不重试 failed）
  → 批量调 Embedding API（batch ≤ 10）
  → 写回 embedding + hash + model + status=completed
  写回前 re-check is_active，已删商品丢弃
```

### 认证

```
POST /api/auth/register → 创建 seller 用户 + JWT
POST /api/auth/login → 校验密码 → 返回 JWT
require_auth / require_seller / require_admin 依赖注入
```

---

## 核心 API

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/auth/register` / `/login` | 注册/登录（country 必填、phone 选填） |
| GET | `/api/products` | 商品列表（登录后按 seller 隔离） |
| POST | `/api/products/upload` | CSV 上传（seller） |
| DELETE | `/api/products/batch` | 批量软删除（body: product_ids，1 请求 + 1 commit） |
| DELETE | `/api/products/all` | 删除全部（seller） |
| POST | `/api/inquiries/analyze` | 买家询盘分析 + 匹配 |
| POST | `/api/seller-inquiries/send` | 买家发询盘给卖家 |
| GET | `/api/seller-inquiries/received` | 卖家收到的询盘 |
| POST | `/api/seller-inquiries/generate-reply` | 卖家生成 AI 回复 |
| GET | `/api/dashboard/admin` | 管理端统计 |
| GET | `/api/debug/embedding-status` | embedding 状态（total/completed/pending/processing/failed） |

---

## Embedding 设计要点

- **持久化到 pgvector**，字段：`embedding`(vector 1024)、`embedding_hash`(SHA256)、`embedding_model`、`embedding_status`、`embedding_retry_count`、`embedding_error`、`embedded_at`
- **hash 去重**：商品内容不变不重新生成；相同内容不同商品可复用
- **状态机**：pending → processing → completed / failed；failed **不自动重试**（需内容/model 变更或管理重置）
- **重试策略**：transient（429/5xx/timeout/connection）最多 6 次 exponential backoff + jitter；permanent（400/401/403/404/维度错误）`FatalEmbeddingError` 立即失败
- **禁止 fake embedding**：API 失败标记 failed，不生成假向量
- **维度统一 1024**：`config.EMBEDDING_DIM`、模型 `Vector(settings.EMBEDDING_DIM)`、DB 迁移自动对齐

---

## 环境变量

**后端（Railway）**
```
DATABASE_URL=postgresql+asyncpg://...
OPENAI_API_KEY          # LLM（DeepSeek 等）
OPENAI_BASE_URL
LLM_MODEL
EMBEDDING_BASE_URL      # https://dashscope.aliyuncs.com/compatible-mode/v1
EMBEDDING_MODEL=text-embedding-v4
EMBEDDING_DIM=1024
EMBEDDING_API_KEY       # 可选，独立 key
EMBEDDING_BATCH_SIZE=10
EMBEDDING_MAX_RETRIES=5
EMBEDDING_TIMEOUT=60
JWT_SECRET_KEY
```

**前端（Vercel）**
```
NEXT_PUBLIC_API_BASE_URL=https://xxx.up.railway.app
```

---

## Commands

```powershell
# 前端本地开发
cd frontend
npm run dev
npm run build

# 后端本地开发
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload

# 部署：git push 后 Vercel + Railway 自动部署
```

---

## Key Design Decisions

1. **前后端分离** — 前端纯页面，后端处理数据 + AI。LLM/Embedding Key 只在后端，不暴露浏览器。
2. **三端多租户** — 卖家产品按 `seller_id` 隔离；买家询盘跨所有卖家匹配；管理员看全量。
3. **商品 embedding 异步化** — 上传立即返回，后台 worker 批量生成，不阻塞询盘。
4. **禁止 fake embedding** — API 失败明确报错，不生成假向量伪装成功。
5. **数据库自迁移** — `_sync_columns` + `_migrate_embedding_dimension` 启动时自动补齐列/对齐维度。
6. **i18n** — 5 语言，locale 存 localStorage，客户端 mount 后同步。
7. **询盘自动翻译** — 非英文询盘先 LLM 翻译成英文再分析。

---

## 管理员

- 自动创建：`1951444042@qq.com` / `admin1234`，登录入口 `/admin`

---

## 遗留/待办

- `frontend/src/lib/ai/`（embedding.ts、llm.ts、rag.ts、api-config.ts）、`lib/api.ts`、`lib/supabase.ts`、`lib/store.ts` 为旧浏览器端 AI/存储逻辑，新流程已走后端，属遗留代码，未清理。
- 旧 `(dashboard)` 路由组页面保留，但非主要入口。
- 未来 100k+ 商品需加 pgvector HNSW/IVFFlat 索引 + 独立任务队列（Celery/Redis）。
