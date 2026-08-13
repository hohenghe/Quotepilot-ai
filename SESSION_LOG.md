# QuotePilot AI — 会话工作记录（2026-08-13）

> 本文件记录 2026-08-13 当天的开发工作，供后续 AI/开发者快速恢复上下文。
> 当前线上：前端 `https://zhermai.com`（Vercel），后端 `https://api.zhermai.com`（Cloudflare 代理 → Railway），数据库 PostgreSQL + pgvector（Railway）。

## 一、今天完成的主要工作

### 1. 后端基础改造
- **文件解析**：`file_parser.py` 由 mock 数据改为真实解析 CSV/XLSX/DOCX/PDF（`.xls`/`.doc` 明确拒绝）。
- **去掉 mock LLM**：`llm.py` 删除规则引擎，LLM/API 失败直接抛异常，无降级。
- **文件存储抽象**：`services/storage.py` 提供 `StorageService`（LocalStorage / R2Storage）+ `get_storage()`。
- **真实集成测试**：`tests/test_inquiry_integration.py`（需 Docker PostgreSQL 运行）。

### 2. 前端 UI/UX 重构（设计系统）
- 统一 Design System（品牌蓝 `#2563EB`，`globals.css` 组件类）。
- 三端共用 `DashboardShell`（角色侧边栏 + 移动端 drawer + 顶栏）。
- 新增共享组件：`StatCard` / `EmptyState` / `LoadingSkeleton` / `ConfirmDialog` / `Toast` / `StatusBadge` / `PageLoader` / `ReviewModal`。
- Buyer/Seller/Admin 三页重写；i18n 5 语言（en/zh-CN/zh-TW/es/fr）全部补齐。
- 修复 hydration（`authReady` 门控）、LanguageSwitcher 定位问题。

### 3. 账号体系（buyer / seller / admin 三端分离）
- 后端角色：`buyer` / `seller` / `admin`；`require_buyer` / `require_seller` / `require_admin`（admin 为超管可进任意端）。
- 同一邮箱可分别注册 buyer 与 seller（`(email, role)` 组合唯一）。
- 手机号必填（buyer+seller）；公司名 seller 必填、buyer 选填。
- 登录：邮箱 / 手机号 / 唯一 ID（`uid`，注册时自动生成）+ 密码；不用公司名。
- Admin 最高权限：`DELETE /api/admin/reset` 一键清空询盘/商品/账号。
- 测试账号：`test@test.com`(buyer) / `seller@test.com`(seller) / `admin@test.com`(admin)，密码均为 `test1234`。

### 4. 询盘 / 评价 / 数据指标
- Seller 询盘分页（Load more）、Buyer 询盘历史 `GET /api/inquiries/buyer`。
- Admin 商品表带 seller 信息；Admin 端「产品目录/询盘记录/账号」三处批量删除（含全选）。
- **评价系统**：`reviews` 表 + 打分（5 分制，0.1 精度）/ 文字 / 图片。
  - 商品评分 = 该商品评价平均分；店铺得分 = 商品评分按询盘量加权平均（`services/rating.py`）。
  - buyer 可写/删自己的评论；seller 只能看+举报；admin 可删任意评论。
- **收藏量 / 浏览量**：`products.view_count` 列（匹配成功界面出现即 +1）；`favorite_count` 由 `saved_products` 实时统计，三端可见（seller 只见自己商品）。

### 5. 文件存储迁移到 Cloudflare R2
- 评论图片上传由 Railway 本地磁盘改为 **Cloudflare R2**（`quotepilot-files` bucket）。
- `services/storage.py` 新增 `upload_file` / `delete_file` / `get_public_url`（S3 兼容 API，boto3）。
- 对象 key 规范：`reviews/{uuid}.{ext}`（后端生成 UUID，客户端不能指定 key）。
- 环境变量：`R2_ACCOUNT_ID` / `R2_ACCESS_KEY_ID` / `R2_SECRET_ACCESS_KEY` / `R2_BUCKET_NAME` / `R2_PUBLIC_BASE_URL`（endpoint 由 account id 构造）。
- 返回完整公开 URL `https://img.zhermai.com/reviews/<uuid>.jpg`；前端 `uploadImage` API 不变。
- 旧的 `GET /api/files/images/{filename}` 保留作兼容（服务历史本地图片）。
- 图片校验：MIME 白名单（jpeg/png/webp/gif）+ 5MB 上限。

### 6. Bug 修复
- 询价 "Failed to fetch"：`seller_inquiries.inquiry_id` 由 `nullable=False` 改为可空 + 启动自迁移 DROP NOT NULL。
- Buyer 页 `/api/saved-products` 无限请求：effect 依赖由 `[user, ...]`（对象引用每次 render 变化）改为 `[user?.user_id, user?.role, ...]`（原始值）。

## 二、当前架构要点
- 前端 `NEXT_PUBLIC_API_BASE_URL=https://api.zhermai.com`；后端 CORS 放开。
- 数据库自迁移（`init_db()` 的 `_sync_columns` + 各 ad-hoc ALTER）在每次启动时执行。
- LLM/Embedding key、R2 凭证、JWT secret 只存在于 Railway 环境变量，不落代码。
- 文件存储：评论图片走 R2；CSV 商品上传仍走本地 `StorageService`（`STORAGE_BACKEND=local`）。

## 三、待办 / 遗留事项
- **历史评论图片迁移**：旧图仍在 `backend/uploads/images/`（Railway 本地磁盘），review.images 里存的是相对 URL `/api/files/images/<uuid>.ext`。需单独写迁移脚本上传到 R2 并改写 URL；Railway 重新部署会丢本地文件。
- **R2 公开访问**：bucket 为 "Public Access: Disabled"，需确认 `img.zhermai.com` 自定义域名能公开读取对象，否则 `<img>` 会 403。
- **Railway 需重新部署**：设置 R2 环境变量后重新部署。
- 集成测试需在有 Docker 的环境运行（本机无 Docker）。
- `DEPLOY.md` 部分内容已过时（mock 降级描述、旧域名），暂未更新。

## 四、Commit 记录（本会话新增，均已在 main）
```
ad37265 feat: migrate review image upload to Cloudflare R2
375e3ec feat: add product favorite and view counts
7ab5cc3 fix: prevent infinite saved-products request from user object dependency
29e1d80 fix: make seller inquiry inquiry_id nullable and surface network errors
1d18b3b feat: product reviews, ratings, seller score, and admin batch delete
e11433e feat: buyer saved products and seller profile
b0670e7 feat: multi-role accounts per email, required phone, uid login, admin reset-all
b837905 fix: language switcher visibility and admin products pagination/bulk delete
e4e767e test: add inquiry integration test
646cf79 feat: refresh frontend with shared dashboard design system
a4dd044 feat: include seller info in admin product list
79e8c3d feat: add seller inquiry pagination and buyer inquiry history
cbca2ff feat: separate buyer and seller accounts
f395740 feat: seed test accounts (test@test.com and admin@test.com)
cec0ca6 chore: remove legacy browser-side AI and storage code
0f76ee0 refactor: remove mock LLM rule engine, fail on API errors
02f1848 feat: implement real product parsing for xlsx/docx/pdf
ca61d31 fix: update supported upload extensions
ac9e8b9 refactor: abstract file storage
```
