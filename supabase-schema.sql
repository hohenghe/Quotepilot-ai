-- 在 Supabase SQL Editor 中执行以下语句

-- 产品表
CREATE TABLE IF NOT EXISTS products (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  sku TEXT,
  category TEXT DEFAULT 'other',
  description TEXT,
  technical_specs TEXT,
  certifications TEXT,
  moq INTEGER,
  unit_price NUMERIC,
  price_range_low NUMERIC,
  price_range_high NUMERIC,
  pricing TEXT,
  lead_time_days INTEGER,
  image_url TEXT,
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 询盘表
CREATE TABLE IF NOT EXISTS inquiries (
  id BIGSERIAL PRIMARY KEY,
  customer_name TEXT,
  customer_email TEXT,
  customer_company TEXT,
  raw_message TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 询盘分析表
CREATE TABLE IF NOT EXISTS inquiry_analyses (
  id BIGSERIAL PRIMARY KEY,
  inquiry_id BIGINT REFERENCES inquiries(id) ON DELETE CASCADE,
  product_category TEXT,
  quantity INTEGER,
  technical_params JSONB DEFAULT '{}',
  target_price NUMERIC,
  required_certifications TEXT[],
  delivery_location TEXT,
  delivery_country TEXT,
  missing_info TEXT[],
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 报价表
CREATE TABLE IF NOT EXISTS quotes (
  id BIGSERIAL PRIMARY KEY,
  inquiry_id BIGINT REFERENCES inquiries(id) ON DELETE CASCADE,
  subject TEXT,
  email_body TEXT NOT NULL,
  matched_products JSONB,
  total_amount_low NUMERIC,
  total_amount_high NUMERIC,
  currency TEXT DEFAULT 'USD',
  notes TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 启用 RLS 并允许匿名访问（开发阶段）
ALTER TABLE products ENABLE ROW LEVEL SECURITY;
ALTER TABLE inquiries ENABLE ROW LEVEL SECURITY;
ALTER TABLE inquiry_analyses ENABLE ROW LEVEL SECURITY;
ALTER TABLE quotes ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow all on products" ON products FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all on inquiries" ON inquiries FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all on inquiry_analyses" ON inquiry_analyses FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all on quotes" ON quotes FOR ALL USING (true) WITH CHECK (true);
