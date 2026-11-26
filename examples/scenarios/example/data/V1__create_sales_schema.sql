-- Flyway migration V1: fixed synthetic retail schema. No PII.
CREATE TABLE products (
    id BIGINT PRIMARY KEY,
    sku VARCHAR(32) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    category VARCHAR(60) NOT NULL
);
CREATE TABLE stores (
    id BIGINT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    city VARCHAR(60) NOT NULL
);
CREATE TABLE sales (
    id BIGINT PRIMARY KEY,
    product_id BIGINT NOT NULL REFERENCES products(id),
    store_id BIGINT NOT NULL REFERENCES stores(id),
    sold_at DATE NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price_cents INTEGER NOT NULL CHECK (unit_price_cents >= 0)
);
CREATE INDEX idx_sales_period ON sales(sold_at);
CREATE INDEX idx_sales_product ON sales(product_id, sold_at);
CREATE INDEX idx_sales_store ON sales(store_id, sold_at);
