CREATE EXTENSION IF NOT EXISTS vector;

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
    seller_id INTEGER,
    lead_time_days INTEGER,
    image_url TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    embedding vector(1536),
    embedding_hash TEXT,
    embedding_model TEXT,
    embedding_status TEXT DEFAULT 'pending',
    embedded_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS inquiries (
    id BIGSERIAL PRIMARY KEY,
    customer_name TEXT,
    customer_email TEXT,
    customer_company TEXT,
    raw_message TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS inquiry_analyses (
    id BIGSERIAL PRIMARY KEY,
    inquiry_id INTEGER NOT NULL REFERENCES inquiries(id) ON DELETE CASCADE,
    product_category TEXT,
    quantity INTEGER,
    technical_params JSONB DEFAULT '{}',
    target_price NUMERIC,
    required_certifications JSONB DEFAULT '[]',
    delivery_location TEXT,
    delivery_country TEXT,
    missing_info JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS quotes (
    id BIGSERIAL PRIMARY KEY,
    inquiry_id INTEGER REFERENCES inquiries(id) ON DELETE CASCADE,
    subject TEXT,
    email_body TEXT NOT NULL,
    matched_products JSONB,
    total_amount_low NUMERIC,
    total_amount_high NUMERIC,
    currency TEXT DEFAULT 'USD',
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS documents (
    id BIGSERIAL PRIMARY KEY,
    filename TEXT NOT NULL,
    file_type TEXT NOT NULL,
    file_path TEXT NOT NULL,
    status TEXT DEFAULT 'processing',
    products_count INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
