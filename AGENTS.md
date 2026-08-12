# QuotePilot AI — Project Context

AI-powered sales assistant for international trade. Analyze customer inquiries, match against product catalog, and generate professional quotation emails.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14 (App Router) + React 18 + TypeScript |
| Styling | Tailwind CSS 3 |
| Icons | lucide-react |
| Markdown | react-markdown |
| Cloud DB | Supabase (optional, for multi-device sync) |
| Backend (unused) | FastAPI + PostgreSQL + pgvector (in `backend/`, for future use) |
| AI | OpenAI-compatible API (optional), falls back to rule engine |

---

## File Structure

```
F:\QuotePilot AI\
├── frontend/                  # Main app (all active code is here)
│   ├── .env.example           # Template for API keys
│   ├── vercel.json            # Vercel deploy config
│   ├── next.config.js         # Next.js config
│   ├── tailwind.config.js     # Brand colors: indigo palette
│   ├── src/
│   │   ├── app/
│   │   │   ├── globals.css    # Tailwind base + component classes (.card, .btn-primary, .badge, etc.)
│   │   │   ├── layout.tsx     # Root layout, I18nProvider wrapper, suppressHydrationWarning
│   │   │   ├── page.tsx       # Dashboard: stats cards + category breakdown chart
│   │   │   ├── products/
│   │   │   │   └── page.tsx   # Product catalog: CSV/PDF upload, search, expand/delete
│   │   │   ├── inquiry/
│   │   │   │   └── page.tsx   # Inquiry analysis: paste inquiry → extract info → match products → generate quote/no-match email
│   │   │   └── quote/
│   │   │       └── page.tsx   # Quote history: list past inquiries, view details
│   │   ├── components/
│   │   │   ├── AppLayout.tsx  # Sidebar + hamburger (mobile), mounted gate for hydration
│   │   │   ├── Sidebar.tsx    # Fixed sidebar (lg+), slide-in overlay (mobile), language switcher
│   │   │   ├── LanguageSwitcher.tsx  # Language dropdown (en, zh-CN, zh-TW, es, fr)
│   │   │   ├── PageHeader.tsx # Reusable page title + description + action slot
│   │   │   ├── LoadingSpinner.tsx
│   │   │   └── EmptyState.tsx # Empty state with icon + text + action button
│   │   ├── i18n/
│   │   │   ├── index.ts       # Locale type + getDefaultLocale (reads localStorage)
│   │   │   ├── I18nProvider.tsx # React Context: starts with "en", useEffect syncs localStorage
│   │   │   └── locales/       # en.ts, zh-CN.ts, zh-TW.ts, es.ts, fr.ts
│   │   ├── lib/
│   │   │   ├── store.ts       # ⭐ Core data layer: Supabase-first or localStorage fallback
│   │   │   ├── supabase.ts    # Lazy Supabase client (no SSR crash)
│   │   │   ├── api.ts         # Legacy REST API client (unused after Supabase switch)
│   │   │   └── ai/
│   │   │       ├── api-config.ts   # OpenAI-compatible API client (chatCompletion, getEmbedding)
│   │   │       ├── llm.ts          # ⭐ Inquiry analysis + quote email + no-match email. AI or mock.
│   │   │       ├── embedding.ts    # Text embeddings: real API or hash-based mock
│   │   │       ├── rag.ts          # Hybrid search: vector similarity + keyword matching
│   │   │       └── file-parser.ts  # CSV parser (real) + PDF/Excel/Word (mock)
│   │   └── types/
│   │       └── index.ts       # Product, Inquiry, InquiryAnalysis, MatchedProduct, Quote, DashboardStats
│   └── public/
├── backend/                   # FastAPI backend (written but NOT deployed or used currently)
│   ├── app/api/               # products.py, inquiries.py, quotes.py, dashboard.py
│   ├── app/services/          # llm.py, rag.py, embedding.py, file_parser.py (Python mirrors of TS code)
│   ├── app/models/            # SQLAlchemy models
│   └── app/core/              # config.py, database.py
├── docker-compose.yml         # PostgreSQL + pgvector (for backend development)
├── supabase-schema.sql        # Supabase table definitions
├── GUIDE.md                   # User manual
├── DEPLOY.md                  # Vercel deployment guide
├── DEPLOY_BACKEND.md          # Railway backend deployment (not needed after Supabase switch)
└── SUPABASE.md                # Supabase multi-device sync guide
```

---

## Architecture & Data Flow

### Storage Modes (auto-detected)

```
isSupabaseMode()? → Supabase PostgreSQL (cloud sync)
                  → localStorage (single device)
```

No backend needed. Data persistence strategy in `store.ts`:

| Operation | Supabase Mode | Local Mode |
|---|---|---|
| Upload CSV | Parse locally → INSERT to Supabase | Parse locally → localStorage |
| Get products | SELECT from Supabase → cache in localStorage | Read localStorage |
| Delete product | UPDATE is_active=false in Supabase | Remove from localStorage |
| Analyze inquiry | Run LLM locally → save to Supabase | Run LLM locally → save to localStorage |
| Generate quote | Run LLM locally → save to Supabase | Run LLM locally → save to localStorage |
| Dashboard stats | SELECT from Supabase | Read localStorage |

### AI Modes (auto-detected)

```
isLLMAvailable()? → OpenAI-compatible API (gpt-4o-mini, text-embedding-3-small)
                  → Rule-based mock (regex + templates + hash embeddings)
```

All AI functions have identical signatures regardless of mode. Callers don't need to know which is active.

| Function | AI Mode | Mock Mode |
|---|---|---|
| `analyzeInquiry(text)` | Chat API → JSON extraction | Regex for quantity, voltage, certs, etc. |
| `generateQuoteEmail(...)` | Chat API → structured email | Template with {{variables}} |
| `generateNoMatchResponse(text)` | Chat API → polite email | Hardcoded template |
| `generateEmbedding(text)` | Embeddings API | Seeded PRNG 1536-dim vector |

### Key Files Flow

```
User uploads CSV → products/page.tsx → store.uploadFile()
  → file-parser.ts (parse) → store (save to Supabase/localStorage)
  → refreshProducts() → re-render list

User pastes inquiry → inquiry/page.tsx → store.analyzeAndMatch()
  → llm.ts.analyzeInquiry() → extract productCategory, quantity, specs, etc.
  → rag.ts.searchProducts() → hybrid vector+keyword search → MatchedProduct[]
  → return FullAnalysisResult

User clicks "Generate Quote" → inquiry/page.tsx → store.generateQuote()
  → llm.ts.generateQuoteEmail() → email with product details, pricing, terms
  → display + copy-to-clipboard
```

---

## CSV Upload Format

Column matching is case-insensitive with alias support:

| Column | Aliases |
|---|---|
| `name` (required) | `productname`, `product`, `product_name` |
| `sku` | `productcode`, `product_code` |
| `category` | `productcategory`, `product_category` |
| `description` | — |
| `technical_specs` | `technicalspecs`, `specifications`, `specs` |
| `certifications` | `certs` |
| `moq` | `minimumorderquantity`, `minimum_order_quantity`, `minqty` |
| `pricing` | Free text: cost, retail, wholesale tiers |
| `lead_time_days` | `leadtime`, `lead_time`, `deliverydays` |

---

## Environment Variables

```
# Database (optional — no cloud sync without these)
NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGciOi...

# AI (optional — uses rule engine without these)
NEXT_PUBLIC_LLM_API_KEY=sk-xxx
NEXT_PUBLIC_LLM_BASE_URL=https://api.openai.com/v1
NEXT_PUBLIC_LLM_MODEL=gpt-4o-mini
NEXT_PUBLIC_EMBEDDING_MODEL=text-embedding-3-small
```

---

## Commands

```powershell
# Local dev
cd frontend
npm run dev

# Build
npm run build

# Deploy to Vercel
cd frontend
vercel

# Deploy to Vercel (production)
vercel --prod
```

---

## Key Design Decisions

1. **No backend required** — All logic runs in the browser. localStorage for data, rule engine for AI fallback. Zero dependencies to run.

2. **Hybrid AI** — Real API when key is set, mock when not. Same function signatures. No code branches in callers.

3. **Hybrid storage** — Supabase when URL is set, localStorage when not. Product data syncs across devices automatically.

4. **SSR-safe** — `AppLayout` returns null on server, only renders on client. Supabase client is lazily initialized. No hydration errors.

5. **Mobile responsive** — Sidebar becomes slide-in overlay on mobile (< lg breakpoint). Hamburger button in top bar. Padding scales with screen size.

6. **i18n** — 5 languages. Locale persisted in localStorage. Server always renders "en" for consistency, client syncs after mount.

---

## Backend (Future)

The `backend/` folder contains a fully implemented FastAPI server with PostgreSQL + pgvector. It mirrors the TS AI logic in Python. Currently unused. When needed:
- Deploy via Railway with PostgreSQL
- Use `DEPLOY_BACKEND.md` guide
- Switch frontend from localStorage/Supabase to REST API calls
