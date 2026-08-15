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
| 认证 | JWT (PyJWT) + HMAC 密码哈希 + 邮箱验证/密码找回 |
| AI (LLM) | OpenAI 兼容 API（DeepSeek V4 Flash） |
| AI (Embedding) | DashScope Qwen `text-embedding-v4`（1024 维） |
| 邮件 | Brevo Transactional Email API |
| 文件存储 | Cloudflare R2（评论/商品图/头像/营业执照） |
| 部署 | 前端 Vercel + 后端 Railway |

---

## 三端架构

| 路由 | 角色 | 功能 | 认证 |
|---|---|---|---|
| `/buyer` | 买家 | 注册/登录 → 输入询盘 → AI 匹配 → 发送询盘给卖家 → 收藏/评价/头像 | JWT |
| `/seller` | 卖家 | 注册/登录 → 上传/管理产品（按 seller_id 隔离）→ 接收询盘 → AI 回复 → 店铺名/营业执照 | JWT |
| `/admin` | 管理端 | 登录 → 全局仪表盘/卖家/产品/询盘/账号/评价总览 + 批量删除/清空收藏 | JWT |
| `/verify-email` `/forgot-password` `/reset-password` | 公共 | 邮箱验证 / 找回密码 / 重置密码 | — |
| `/(dashboard)/*` | 旧页面 | `/` 已重定向到 `/buyer`；`/products`、`/inquiry`、`/quote` 保留（非主要入口） | — |

---

## File Structure

```
F:\QuotePilot AI\
├── frontend/
│   └── src/
│       ├── app/
│       │   ├── layout.tsx              # 根布局（无侧边栏），I18nProvider + ToastProvider
│       │   ├── buyer/page.tsx          # 买家端（发现/询盘/收藏/个人资料+头像）
│       │   ├── seller/page.tsx         # 卖家端（概览/商品/询盘/评价/资料）
│       │   ├── seller/login/page.tsx   # 卖家登录/注册
│       │   ├── admin/page.tsx          # 管理端仪表盘
│       │   ├── admin/login/page.tsx    # 管理端登录
│       │   ├── verify-email/page.tsx   # 邮箱验证
│       │   ├── forgot-password/page.tsx# 忘记密码
│       │   ├── reset-password/page.tsx # 重置密码
│       │   └── (dashboard)/            # 旧页面路由组（/ 已重定向 /buyer）
│       ├── components/
│       │   ├── AuthForm.tsx            # 三端复用登录/注册（忘记密码 + 注册后验证提示 + 重发）
│       │   ├── DashboardShell.tsx      # 三端共用侧边栏/顶栏布局
│       │   ├── ProductFormModal.tsx    # 手动新增/编辑商品 + 最多 10 张图片上传
│       │   ├── SellerModal.tsx         # 浏览某卖家全部商品
│       │   ├── ReviewModal.tsx         # 对卖家评价（打分/文字/图片）
│       │   └── ConfirmDialog / Toast / StatCard / EmptyState / StatusBadge / LoadingSkeleton / PageLoader / LanguageSwitcher
│       ├── i18n/                       # 5 语言：en, zh-CN, zh-TW, es, fr
│       ├── lib/
│       │   ├── api-client.ts           # ⭐ REST API 客户端（snake↔camel + JWT 头 + 401 自动登出）
│       │   ├── auth.ts                 # token/user 存取（localStorage）
│       │   ├── countries.ts            # 国家列表
│       │   └── store.ts / supabase.ts / ai/  # 旧遗留代码（新流程走后端）
│       └── types/index.ts
├── backend/
│   ├── app/
│   │   ├── main.py                     # FastAPI 入口 + lifespan（init_db + embedding worker + 自动建 admin/测试账号）
│   │   ├── api/                        # auth, products, inquiries, quotes, dashboard, seller_inquiries,
│   │   │                               #   reviews, saved_products, sellers, admin, files
│   │   ├── core/                       # config, database, auth(JWT依赖), security, retry
│   │   ├── models/                     # user, product, inquiry, quote, document, seller_inquiry,
│   │   │                               #   review, saved_product, auth_token
│   │   ├── schemas/                    # inquiry, product, quote
│   │   └── services/                   # llm, embedding, rag, file_parser, rating, storage, email
│   ├── seed_admin.py                   # 自动创建管理员 + 测试账号
│   ├── Procfile                        # Railway 启动：uvicorn app.main:app
│   ├── .python-version                 # Python 3.12
│   └── init-db.sql                     # 建表 SQL
├── SESSION_LOG.md                      # 会话工作记录
└── AGENTS.md                           # 本文件
```

---

## 数据流

### 买家询盘流程

```
买家 → POST /api/inquiries/analyze
  → analyze_inquiry()：单次 LLM 请求（翻译 + 结构化提取合并；英文免翻译）
  → search_products_hybrid()：query embedding(原文, 1次, 有内存缓存) → pgvector 余弦 Top N → 关键词 rerank
  → 返回 inquiry + analysis + matched_products
买家点「发送询盘」→ POST /api/seller-inquiries/send（按 product 归属 seller）
卖家 → GET /api/seller-inquiries/received → POST /generate-reply（AI 生成回复）
```

### 商品 Embedding（异步）

```
卖家上传 CSV 或手动新增商品 → 写入 DB（embedding_status=pending）→ 立即返回
后台 worker（main.py lifespan 启动）：
  扫描 is_active=true AND embedding_status=pending（仅 pending，不重试 failed）
  → 批量调 Embedding API（batch ≤ 10）
  → 按 embedding_hash（商品内容 SHA-256）去重，内容不变不重新生成
  → 写回 embedding + hash + model + status=completed
  写回前 re-check is_active，已删商品丢弃
```

### 认证

```
POST /api/auth/register → 创建用户（email_verified_at=NULL）→ 发送验证邮件（不直接发 JWT）
POST /api/auth/login → 校验密码 + 邮箱已验证（admin 豁免）→ 返回 JWT
邮箱验证：POST /api/auth/verify-email（24h 一次性 token，库中只存 SHA-256）
密码找回：POST /api/auth/forgot-password → /api/auth/reset-password（30min token；
          改密后 auth_version+1，使该用户旧 JWT 立即失效）
重发验证邮件：POST /api/auth/resend-verification（60s 限流，防邮箱枚举统一返回）
require_auth / require_buyer / require_seller / require_admin 依赖注入
```

---

## 核心 API

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/auth/register` / `/login` | 注册（发验证邮件，不返 JWT）/ 登录（邮箱已验） |
| POST | `/api/auth/verify-email` | 邮箱验证 |
| POST | `/api/auth/resend-verification` | 重发验证邮件（60s 限流） |
| POST | `/api/auth/forgot-password` / `/reset-password` | 找回/重置密码 |
| PUT | `/api/auth/me` | 更新个人资料（含 store_name / avatar_url / business_license_url） |
| GET | `/api/products` | 商品列表（登录后按 seller 隔离） |
| POST | `/api/products` | 手动新增商品（无需文件，含最多 10 张图片） |
| POST | `/api/products/upload` | CSV/XLSX/DOCX/PDF 上传（seller） |
| PUT | `/api/products/{id}` | 编辑商品（含图片） |
| DELETE | `/api/products/batch` / `/all` | 批量/全部软删除 |
| POST | `/api/inquiries/analyze` | 买家询盘分析 + 匹配 |
| POST | `/api/seller-inquiries/send` | 买家发询盘给卖家 |
| GET | `/api/seller-inquiries/received` | 卖家收到的询盘 |
| POST | `/api/seller-inquiries/generate-reply` | 卖家生成 AI 回复 |
| GET/POST/DELETE | `/api/reviews` | 对卖家评价（写/列表/删除/举报） |
| GET | `/api/sellers/{id}/products` | 浏览某卖家全部商品 + 店铺得分 |
| GET/POST/DELETE | `/api/saved-products` | 收藏 / 取消收藏 |
| POST | `/api/files/upload` | 图片上传到 R2（kind: review/product/avatar/license） |
| GET | `/api/dashboard/admin` | 管理端统计 |
| DELETE | `/api/admin/reset` / `/api/admin/saved-products` | 清空全部 / 清空所有收藏 |
| GET | `/api/debug/embedding-status` | embedding 状态 |

---

## Embedding 设计要点

- **持久化到 pgvector**，字段：`embedding`(vector 1024)、`embedding_hash`(SHA256)、`embedding_model`、`embedding_status`、`embedding_retry_count`、`embedding_error`、`embedded_at`
- **hash 去重**：商品内容不变不重新生成；相同内容不同商品可复用
- **query embedding 缓存**：内存缓存（有界 256，key=`model|dim|text`），相同 query 不重复调 API
- **状态机**：pending → processing → completed / failed；failed **不自动重试**（需内容/model 变更或管理重置）
- **重试策略**：transient（429/5xx/timeout/connection）最多 6 次 exponential backoff + jitter；permanent（400/401/403/404/维度错误）`FatalEmbeddingError` 立即失败
- **禁止 fake embedding**：API 失败标记 failed，不生成假向量
- **维度统一 1024**：`config.EMBEDDING_DIM`、模型 `Vector(settings.EMBEDDING_DIM)`、DB 迁移自动对齐

---

## LLM 成本优化要点

- **单次请求合并翻译 + 结构化提取**：`analyze_inquiry` 用一次 DeepSeek 请求同时产出 `translation` 和结构化字段（非英文询盘不再翻译+分析两次）。
- **usage 日志**：`llm.py` 记录 `model/operation/prompt_tokens/cache_hit/cache_miss/completion/reasoning/cache_hit_rate`（只记元数据，不记 prompt 内容）。
- **按任务设 max_tokens**：`inquiry_analysis=1200`、`quote_generation=2000`。
- **稳定 prefix**：system prompt 固定且位于 messages 首位，利于 DeepSeek input cache hit。
- 未设置 thinking 模式（V4 Flash 默认；参数格式不明确，未贸然加参）。

---

## 环境变量

**后端（Railway）**
```
DATABASE_URL=postgresql+asyncpg://...
OPENAI_API_KEY          # LLM（DeepSeek V4 Flash）
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
BREVO_API_KEY           # 邮件
MAIL_FROM_EMAIL / MAIL_FROM_NAME
FRONTEND_URL            # 邮件链接回跳，如 https://zhermai.com
R2_ACCOUNT_ID / R2_ACCESS_KEY_ID / R2_SECRET_ACCESS_KEY / R2_BUCKET_NAME / R2_PUBLIC_BASE_URL
```

**前端（Vercel）**
```
NEXT_PUBLIC_API_BASE_URL=https://api.zhermai.com
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

1. **前后端分离** — 前端纯页面，后端处理数据 + AI。LLM/Embedding/Brevo/R2 Key 只在后端，不暴露浏览器。
2. **三端多租户** — 卖家产品按 `seller_id` 隔离；买家询盘跨所有卖家匹配；管理员看全量（超管可进任意端）。
3. **商品 embedding 异步化** — 上传立即返回，后台 worker 批量生成，不阻塞询盘；内容 hash 去重。
4. **禁止 fake embedding** — API 失败明确报错，不生成假向量伪装成功。
5. **数据库自迁移** — `_sync_columns` + `_migrate_embedding_dimension` + 各 ad-hoc ALTER 在启动时执行（幂等）。
6. **i18n** — 5 语言，locale 存 localStorage，客户端 mount 后同步。
7. **询盘翻译合并** — 非英文询盘在单次 LLM 请求内完成翻译 + 结构化提取（翻译保留在输出，供复用）。
8. **邮箱验证 + 密码找回** — 一次性 token 只存 SHA-256；auth_version 使改密后旧 JWT 失效；forgot/resend 防邮箱枚举统一返回。
9. **卖家评价 + 店铺分** — 评价针对卖家（非商品）；店铺分 = 评价加权平均（字数/图片权重更高）。
10. **店铺名 / 头像 / 营业执照** — 卖家可设店铺名（默认公司名）、头像、营业执照；商品最多 10 张图片，全部存 R2。

---

## 管理员

- 自动创建：`1951444042@qq.com` / `admin1234`，登录入口 `/admin`（admin 豁免邮箱验证）。
- 测试账号：`test@test.com`(buyer) / `seller@test.com`(seller) / `admin@test.com`(admin)，密码 `test1234`。

---

## 遗留/待办

- `frontend/src/lib/ai/`、`lib/api.ts`、`lib/supabase.ts`、`lib/store.ts` 为旧浏览器端 AI/存储逻辑，新流程已走后端，属遗留代码，未清理。
- 旧 `(dashboard)` 路由组页面保留，但非主要入口。
- 历史评论图片仍在 `backend/uploads/images/`（Railway 本地磁盘），需迁移到 R2（部署会丢本地文件）。
- R2 公开访问需确认 `img.zhermai.com` 能公开读取对象。
- 未来 100k+ 商品需加 pgvector HNSW/IVFFlat 索引 + 独立任务队列（Celery/Redis）。
