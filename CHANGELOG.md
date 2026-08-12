# QuotePilot AI — 开发记录（2026-08-12）

> 本次开发从单一页面应用演进为「买家端 / 卖家端 / 管理端」三端分离的多租户 SaaS，并完成 LLM + Embedding 双 AI 能力接入、线上部署与多轮稳定性修复。

---

## 一、架构演进：前后端分离

- 前端（Next.js / Vercel）仅负责页面展示
- 后端（FastAPI / Railway）负责数据存储、AI 调用、商品匹配
- LLM API Key 从浏览器端移到后端，不再暴露

**关键改动**
- 新增 `frontend/src/lib/api-client.ts`：统一封装后端 REST API，snake_case ↔ camelCase 适配
- 改造 `store.ts`：AI 操作（分析询盘/生成报价）改为后端优先 + 本地降级
- 后端 `llm.py` 重写：真实 OpenAI 兼容 API + mock 双模式，`generate_no_match_response()` 补齐
- 后端 `rag.py`：由纯关键词 → 混合搜索（向量 + 关键词）

---

## 二、三端分离架构（买家/卖家/管理端）

| 路由 | 角色 | 功能 | 认证 |
|---|---|---|---|
| `/buyer` | 买家 | 注册/登录 → 输入询盘 → AI 匹配 → 发送询盘给卖家 | JWT |
| `/seller` | 卖家 | 注册/登录 → 上传/管理产品（隔离）→ 接收询盘 → AI 回复 | JWT |
| `/admin` | 管理端 | 登录 → 全局仪表盘/卖家/产品/询盘总览 | JWT |

**核心实现**
- 新增 `users` 表 + JWT 认证（`core/security.py`、`core/auth.py`、`api/auth.py`）
- 商品按 `seller_id` 隔离；买家询盘跨所有卖家搜索匹配
- 管理端全量数据 API（`api/dashboard.py`、`api/products.py` 的 admin 端点）
- 旧页面（`/`、`/products`、`/inquiry`、`/quote`）移入 `(dashboard)` 路由组保留侧边栏；三端新页面为无侧边栏全屏布局

---

## 三、买 → 卖询盘流转

- 买家匹配结果每个产品带「发送询盘给卖家」按钮
- 新增 `seller_inquiries` 表 + API（发送/接收/AI 生成回复）
- 卖家端「收到的询盘」标签 +「生成 AI 回复」按钮

---

## 四、多语言 i18n（5 种语言）

- 英 / 简中 / 繁中 / 西 / 法，覆盖全部页面
- 新增独立 `LanguageSwitcher` 组件，三端页头均可切换
- **询盘自动翻译**：非英文（含中文）询盘先经 LLM 翻译成英文再分析

---

## 五、注册/登录增强

- 复用 `AuthForm` 组件（买家/卖家/管理端）
- 密码输入两次 + 显隐切换
- 注册新增：国家（必填，24 国下拉）、手机号（选填），`*` 标注必填
- 买家也需注册登录

---

## 六、商品匹配与 Embedding（核心重构）

### 最终架构
- **商品 embedding 持久化到 PostgreSQL（pgvector）**，非进程内存
- 字段：`embedding`、`embedding_hash`、`embedding_model`、`embedding_status`、`embedding_retry_count`、`embedding_error`、`embedded_at`
- 仅当商品内容（name/category/description/specs/certs 的 SHA256）或 model 变化时重新生成
- 商品 embedding 由**后台 worker** 异步批量生成，不阻塞询盘请求
- 询盘请求仅调用 **1 次 query embedding**，随后 pgvector 余弦距离搜索 Top N + 关键词 rerank

### Embedding API 可靠性
- 批量调用（DashScope `text-embedding-v4`，batch ≤ 10）
- Exponential backoff + jitter + Retry-After 支持
- 区分 transient（429/5xx/timeout/connection，最多 6 次）与 permanent（400/401/403/404/维度错误，0 次重试，`FatalEmbeddingError`）
- **禁止 fake/random embedding**：API 失败明确标记 `failed`，不生成假向量
- worker 只处理 `pending`，`failed` 不自动重试（需内容/model 变更或管理重置）
- 删除竞态保护：写回前 `_recheck_product()` 校验 `is_active`，已删商品丢弃结果、绝不重建

### 维度统一（1024）
| 位置 | 原值 | 现值 |
|---|---|---|
| `config.py` | 1024 | 1024 |
| `models/product.py` | 1536（硬编码） | `Vector(settings.EMBEDDING_DIM)` |
| `database.py` / `init-db.sql` | 1536 | 1024 |

- 新增 `_migrate_embedding_dimension()`：检测 DB 实际维度，不一致时 DROP 重建并重置 `pending`

---

## 七、商品批量删除

- 新增 `DELETE /api/products/batch`（body: `product_ids`）和 `DELETE /api/products/all`
- 单次 HTTP 请求 + 单次 commit（内部按 500 分 chunk 的 bulk UPDATE）
- 删除 2000 商品：旧方案 ≈2000 请求 → 新方案 **1 请求**
- 同时设置 `is_active=false` + `embedding_status=skipped`
- seller 页面全选 + 批量删除按钮，删除后从后端重新加载确认

---

## 八、部署与运维

- **Vercel**（前端） + **Railway**（后端 + PostgreSQL + pgvector）
- 后端 Python 3.12 锁定（`.python-version`）、Procfile 启动命令、CORS 放开
- 数据库 schema 自动迁移（`_sync_columns` + `_migrate_embedding_dimension`）
- 启动时自动重置卡住的 `processing` 状态、自动创建管理员账号
- 调试端点：`/api/debug/llm-status`、`/api/debug/embedding-status`

### 环境变量（Railway）
```
OPENAI_API_KEY          # LLM（DeepSeek 等 OpenAI 兼容）
OPENAI_BASE_URL
LLM_MODEL
EMBEDDING_BASE_URL      # DashScope Qwen
EMBEDDING_MODEL=text-embedding-v4
EMBEDDING_DIM=1024
EMBEDDING_API_KEY       # 可选，独立 key
EMBEDDING_BATCH_SIZE=10
EMBEDDING_MAX_RETRIES=5
EMBEDDING_TIMEOUT=60
```

### 管理员
- 自动创建：`1951444042@qq.com` / `admin1234`
- 登录入口：`/admin`

---

## 九、已知遗留

- `DEPLOY_BACKEND.md`、`GUIDE.md` 等旧文档已删除（内容过时，与三端架构不符）
- `frontend/src/lib/ai/embedding.ts` 的前端 mock embedding 已改为后端驱动，该文件为遗留代码
