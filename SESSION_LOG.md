# QuotePilot AI — 会话工作记录（2026-08-14）

> 记录 2026-08-14 当天的开发工作，供后续 AI/开发者快速恢复上下文。
> 线上：前端 `https://zhermai.com`（Vercel），后端 `https://api.zhermai.com`（Cloudflare → Railway），数据库 PostgreSQL + pgvector（Railway）。

## 一、最近完成的主要工作

### 1. 卖家评价改造（对商家评价）
- 删除「商品评价」，改为**对商家评价**（`reviews.seller_id`，弃用 `product_id`，启动迁移 DROP 该列）。
- 店铺得分 = 各评价**加权平均**：权重 `1 + min(字数/50, 2) + 有图片 +1`（`services/rating.py`）。
- 匹配结果展示卖家名，可点击进入 `SellerModal` 浏览该卖家全部商品（新增 `GET /api/sellers/{id}/products`）。
- 卖家可自定义**店铺名**（`store_name`，默认公司名）；根路径 `/` 重定向 `/buyer`；买家登录页密码下方「我是卖家」跳 `/seller`；admin 仅能通过 `/admin` 进入。

### 2. 邮箱验证 + 密码找回（Brevo）
- 新增 `auth_tokens` 表（一次性 token，库中只存 SHA-256）+ `users.email_verified_at` + `users.auth_version`。
- 注册不再直接发 JWT，改为发验证邮件；未验证登录返回 403（admin 豁免）。
- 新增端点：`/verify-email`、`/resend-verification`、`/forgot-password`、`/reset-password`。
- 邮件服务 `services/email.py`（Brevo Transactional API，httpx）；token 24h/30min，一次性，改密后旧 JWT 失效（auth_version）；forgot/resend 防邮箱枚举统一返回 + 60s 后端限流。
- 前端新增 `/verify-email`、`/forgot-password`、`/reset-password` 页面 + AuthForm 忘记密码链接/注册后验证提示。

### 3. 商品图片 / 头像 / 营业执照 / 手动新增商品
- `products.images`（最多 10 张）、`users.avatar_url`、`users.business_license_url` 列 + 幂等迁移。
- `POST /api/files/upload` 增加 `kind`（review/product/avatar/license）→ R2 不同前缀目录。
- 新增 `POST /api/products`（手动新增商品，无需文件）+ `ProductFormModal`（新增/编辑 + 10 图上传）。
- 买家/卖家头像上传；卖家营业执照上传（非强制）。

### 4. 收藏界面修复 + 清空收藏
- 修复 `/api/saved-products` 500：`list_saved` 原来在外层同时 select `SavedProduct` + 关联子查询引用同一张表，SQLAlchemy 生成冲突 SQL；改为批量 GROUP BY 统计 favorite_count。
- 新增 `DELETE /api/admin/saved-products`（清空所有收藏）+ 管理端危险区按钮；`request()` 对 401 自动登出；收藏页显示真实错误信息。

### 5. AI 成本优化
- `analyze_inquiry` 合并「翻译 + 结构化提取」为**单次 LLM 请求**（非英文从 2 次降到 1 次，翻译保留在输出）。
- `llm.py` 增加 usage 日志（`model/operation/prompt_tokens/cache_hit/cache_miss/completion/reasoning/cache_hit_rate`）。
- 按任务设 `max_tokens`（inquiry_analysis=1200、quote_generation=2000）。
- `embedding.py` 增加 query embedding 内存缓存（有界 256）。

### 6. 跨语言检索 benchmark（已按需求移除）
- 曾新增 `scripts/benchmark_retrieval.py` + 中文测试商品/查询，验证 `text-embedding-v4` 跨语言检索；后按用户要求连同测试数据一并移除。

## 二、当前架构要点
- 数据库自迁移（`init_db()` 的 `_sync_columns` + ad-hoc ALTER + email_verified_at 一次性回填）在启动时幂等执行。
- LLM/Embedding/Brevo/R2 凭证、JWT secret 只存在于 Railway 环境变量，不落代码。
- 图片全部走 R2（`/api/files/upload`，kind 前缀）；CSV 商品上传仍走本地 `StorageService`。

## 三、待办 / 遗留
- 历史评论图片仍在 `backend/uploads/images/`（本地磁盘），需迁移到 R2。
- R2 公开访问需确认 `img.zhermai.com` 能公开读取对象。
- 集成测试需在有 Docker 的环境运行（本机无 Docker）。
- 未来 100k+ 商品需加 pgvector HNSW/IVFFlat 索引 + 独立任务队列。

## 四、Commit 记录（近期，均已 push 到 main）
```
a4a6ddb perf: reduce DeepSeek cost with merged analysis and usage logging
fab8496 fix: resolve 500 on saved-products from correlated subquery
a87040b fix: surface saved-products errors and add clear-all-favorites admin action
b570913 feat: product image management, avatars, and manual product creation
0f667c7 chore: remove cross-lingual benchmark tooling
47fa8c4 chore: remove benchmark sample data from repo
c49a2cb feat: cross-lingual retrieval benchmark
d6ef51c fix: admin accounts list and reported review visibility
5adc113 feat: email verification and password reset
d75d316 feat: seller-level reviews, seller storefront, and buyer routing
```
