# QuotePilot AI — 问题和任务

## P0 (关键)

### 1. PDF/Excel/Word 解析全是假数据
- **文件**: `frontend/src/lib/ai/file-parser.ts`
- **现象**: 上传 PDF、Excel、Word 文件后返回写死的 LED 灯具 mock 数据，不做真实解析
- **代码注释**: 第 2-4 行明确写了 `Swap in: pdf.js / xlsx / mammoth.js for real client-side parsing.`
- **影响**: 用户上传真实产品目录会得到错误的产品数据
- **建议**: 集成 pdf.js、xlsx.js、mammoth.js 做客户端文件解析

### 2. 仪表盘不自动刷新
- **文件**: `frontend/src/app/page.tsx`
- **现象**: 统计数据在页面首次挂载时计算一次，上传产品或分析询盘后数据不变
- **影响**: 用户需要手动刷新页面才能看到最新数据

---

## P1 (重要)

### 3. 报价历史页面只是一个空壳
- **文件**: `frontend/src/app/quote/page.tsx`
- **现象**: 只展示询盘列表和详情，没有"生成报价"按钮，不能查看/浏览已保存的报价
- **影响**: 报价页面没有发挥实际作用，用户只能从 `/inquiry` 页面生成报价

### 4. 删除产品缺少 await（竞态条件）
- **文件**: `frontend/src/app/products/page.tsx:56`
- **现象**: `deleteProduct(id)` 是异步函数但没有 `await`，`refresh()` 立即执行
- **影响**: Supabase 模式下删除操作可能未完成就刷新了列表，导致产品仍然显示

### 5. 仪表盘 Supabase 模式不完整
- **文件**: `frontend/src/lib/store.ts:456-480`
- **现象**: `getDashboardStatsAsync()` 中式统计产品数，询盘数和报价数永远返回 0
- **影响**: 使用 Supabase 时仪表盘数据不准确

---

## P2 (次要)

### 6. 混合存储模式 ID 计数器不同步
- **文件**: `frontend/src/lib/store.ts`
- **现象**: 本地 `nextProductId` 自增与 Supabase 自动生成的 ID 不一致
- **影响**: 在本地模式和 Supabase 模式之间切换时可能出现 ID 冲突

### 7. 混合模式下询盘数据重复保存
- **文件**: `frontend/src/lib/store.ts` `analyzeAndMatch()`
- **现象**: Supabase 模式下同时调用了 Supabase insert 和 `doLocalAnalyze()`，导致询盘在本地和云端重复存储
- **影响**: 数据冗余，本地查询结果和云端不一致

### 8. 产品搜索没有 embedding 缓存
- **文件**: `frontend/src/lib/ai/rag.ts`, `frontend/src/lib/ai/embedding.ts`
- **现象**: 每次搜索都重新计算所有产品的 embedding，没有预计算或内存缓存
- **影响**: AI API 模式下每次搜索可能需要数十上百次 API 调用

---

## P3 (优化)

### 9. 移除人工延迟
- **文件**: `frontend/src/app/inquiry/page.tsx`
- **现象**: 分析询盘延迟 1.2s、生成报价延迟 0.8s、生成无匹配回复延迟 0.6s
- **建议**: 移除 `setTimeout` 包装，或仅保留最小必要延迟

### 10. 使用 Next.js Link 替代 `<a>` 标签
- **文件**: `frontend/src/app/quote/page.tsx:29,103`
- **现象**: 使用 `<a href="/inquiry">` 造成整页刷新，而非客户端 SPA 导航
- **建议**: 替换为 `<Link>`

### 11. 复制成功缺少视觉反馈
- **文件**: `frontend/src/app/inquiry/page.tsx`
- **现象**: 点击复制按钮后没有 toast/notification
- **建议**: 添加 toast 提示"已复制"

---

## P4 (可忽略)

### 12. 死代码 lib/api.ts
- **文件**: `frontend/src/lib/api.ts`
- **现象**: REST API 客户端已写但从未被调用
- **建议**: 删除或在文件头标注"保留用于未来后端集成"
