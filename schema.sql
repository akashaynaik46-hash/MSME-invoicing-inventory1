-- ============================================================
-- MSME Invoicing & Inventory Analytics — Database Schema
-- ============================================================

CREATE TABLE customers (
    customer_id     INTEGER PRIMARY KEY,
    customer_name   TEXT NOT NULL,
    business_type   TEXT,        -- e.g. Retail, Wholesale, Manufacturing
    city            TEXT,
    onboarded_date  DATE
);

CREATE TABLE products (
    product_id      INTEGER PRIMARY KEY,
    product_name    TEXT NOT NULL,
    category        TEXT,
    unit_cost       REAL,
    unit_price      REAL
);

CREATE TABLE inventory (
    product_id          INTEGER PRIMARY KEY REFERENCES products(product_id),
    opening_stock       INTEGER,
    current_stock       INTEGER,
    reorder_level       INTEGER,
    last_restock_date   DATE
);

CREATE TABLE invoices (
    invoice_id      INTEGER PRIMARY KEY,
    customer_id     INTEGER REFERENCES customers(customer_id),
    invoice_date    DATE,
    due_date        DATE,
    status          TEXT,        -- Paid, Pending, Overdue
    total_amount    REAL
);

CREATE TABLE invoice_items (
    invoice_item_id INTEGER PRIMARY KEY,
    invoice_id      INTEGER REFERENCES invoices(invoice_id),
    product_id      INTEGER REFERENCES products(product_id),
    quantity        INTEGER,
    unit_price      REAL,
    line_total      REAL
);

CREATE TABLE payments (
    payment_id      INTEGER PRIMARY KEY,
    invoice_id      INTEGER REFERENCES invoices(invoice_id),
    payment_date    DATE,
    amount_paid     REAL
);

-- ============================================================
-- KPI QUERIES — used to power the Power BI dashboard
-- ============================================================

-- 1. Outstanding receivables by customer
SELECT
    c.customer_name,
    SUM(i.total_amount) - COALESCE(SUM(p.amount_paid), 0) AS outstanding_amount
FROM invoices i
JOIN customers c ON c.customer_id = i.customer_id
LEFT JOIN payments p ON p.invoice_id = i.invoice_id
WHERE i.status IN ('Pending', 'Overdue')
GROUP BY c.customer_name
ORDER BY outstanding_amount DESC;

-- 2. Monthly revenue trend
SELECT
    strftime('%Y-%m', invoice_date) AS month,
    SUM(total_amount) AS revenue
FROM invoices
WHERE status != 'Cancelled'
GROUP BY month
ORDER BY month;

-- 3. Stock turnover ratio per product
-- turnover = units sold in period / average stock held
SELECT
    p.product_name,
    SUM(ii.quantity) AS units_sold,
    inv.current_stock,
    ROUND(SUM(ii.quantity) * 1.0 / NULLIF(inv.current_stock, 0), 2) AS stock_turnover_ratio
FROM invoice_items ii
JOIN products p ON p.product_id = ii.product_id
JOIN inventory inv ON inv.product_id = p.product_id
GROUP BY p.product_name, inv.current_stock
ORDER BY stock_turnover_ratio DESC;

-- 4. Products below reorder level (restock alerts)
SELECT
    p.product_name,
    inv.current_stock,
    inv.reorder_level
FROM inventory inv
JOIN products p ON p.product_id = inv.product_id
WHERE inv.current_stock <= inv.reorder_level;

-- 5. Average days to payment (collection efficiency)
SELECT
    ROUND(AVG(julianday(p.payment_date) - julianday(i.invoice_date)), 1) AS avg_days_to_payment
FROM invoices i
JOIN payments p ON p.invoice_id = i.invoice_id
WHERE i.status = 'Paid';
