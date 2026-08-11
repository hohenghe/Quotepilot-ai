# QuotePilot AI — Vercel 部署完整流程

---

## 第一步：初始化 Git 并推送 GitHub

在项目根目录 `F:\QuotePilot AI` 中执行：

```powershell
# 1. 初始化 Git
git init

# 2. 安装 GitHub CLI（如果没有，从 https://cli.github.com 下载）
winget install --id GitHub.cli

# 3. 登录 GitHub
gh auth login

# 4. 在 GitHub 创建仓库
gh repo create quotepilot-ai --public --source=. --remote=origin --push
```

---

## 第二步：创建 .gitignore 文件

项目根目录新建文件 `.gitignore`，内容如下：

```
node_modules/
.next/
out/
__pycache__/
*.pyc
.env
uploads/
```

然后提交：

```powershell
git add .
git commit -m "Initial commit: QuotePilot AI"
git push
```

---

## 第三步：Vercel 部署

### 3.1 安装 Vercel CLI 并部署

```powershell
# 安装 Vercel CLI
npm install -g vercel

# 登录 Vercel（会自动打开浏览器）
vercel login

# 部署（在 frontend 目录内执行）
cd frontend
vercel
```

按提示操作：
- `Set up and deploy?` → 输入 `Y`
- `Which scope?` → 选择你的账号
- `Link to existing project?` → `N`
- `Project name?` → 回车使用默认
- `In which directory is your code?` → `./`（默认当前目录）
- `Override settings?` → `N`

部署完成后会输出一个地址，例如 `https://quotepilot-ai.vercel.app`。

### 3.2 后续自动部署

首次部署后，Vercel 会自动关联你的 GitHub 仓库。之后每次 `git push`，Vercel 会自动重新构建和部署，无需手动操作。

---

## 第四步：可选配置

### 4.1 自定义域名

```powershell
# 在 frontend 目录下
vercel domains add 你的域名
```

然后去域名 DNS 添加 CNAME 记录指向 `cname.vercel-dns.com`。

### 4.2 手动触发重新部署

```powershell
cd frontend
vercel --prod
```

---

## 常见问题

**Q: 上传的产品数据会丢失吗？**

不会。数据存储在浏览器的 localStorage 中，与部署平台无关。但不同设备/浏览器之间的数据不互通。

**Q: 本地还能继续开发吗？**

可以。`npm run dev` 照常使用，Vercel 部署和本地开发互不影响。

**Q: 后端需要部署吗？**

不需要。当前版所有逻辑在浏览器中运行，只部署前端即可。

---

## 快速命令汇总

```powershell
# 在 F:\QuotePilot AI 目录
git init
git add .
git commit -m "Initial commit"
gh auth login
gh repo create quotepilot-ai --public --source=. --remote=origin --push
cd frontend
npm install -g vercel
vercel login
vercel
```
