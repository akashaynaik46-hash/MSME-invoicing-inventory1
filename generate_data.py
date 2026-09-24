"""
generate_data.py
Generates synthetic invoicing, inventory, and payment data for the
MSME Invoicing & Inventory Analytics Dashboard project, and loads it
into a local SQLite database (msme_analytics.db) using the schema in
schema.sql. Also exports each table to CSV for use in Power BI.
"""

import sqlite3
import random
from datetime import date, timedelta
import csv
import os

random.seed(42)

DB_PATH = "msme_analytics.db"
SCHEMA_PATH = "schema.sql"
OUT_DIR = "csv_exports"

BUSINESS_TYPES = ["Retail", "Wholesale", "Manufacturing", "Services"]
CITIES = ["Bengaluru", "Mumbai", "Delhi", "Pune", "Chennai", "Hyderabad"]
CATEGORIES = ["Stationery", "Electronics", "Packaging", "Textiles", "Hardware"]
STATUSES = ["Paid", "Pending", "Overdue"]


def random_date(start: date, end: date) -> date:
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, delta))


def build_database():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    with open(SCHEMA_PATH, "r") as f:
        schema_sql = f.read()
    # Only run the CREATE TABLE statements (skip the KPI queries section)
    create_statements = schema_sql.split("-- KPI QUERIES")[0]
    cur.executescript(create_statements)

    # --- Customers ---
    customers = []
    for cid in range(1, 41):
        customers.append((
            cid,
            f"Customer {cid:03d}",
            random.choice(BUSINESS_TYPES),
            random.choice(CITIES),
            random_date(date(2024, 1, 1), date(2025, 12, 31)).isoformat(),
        ))
    cur.executemany("INSERT INTO customers VALUES (?, ?, ?, ?, ?)", customers)

    # --- Products ---
    products = []
    for pid in range(1, 26):
        unit_cost = round(random.uniform(20, 500), 2)
        products.append((
            pid,
            f"Product {pid:03d}",
            random.choice(CATEGORIES),
            unit_cost,
            round(unit_cost * random.uniform(1.2, 1.8), 2),
        ))
    cur.executemany("INSERT INTO products VALUES (?, ?, ?, ?, ?)", products)

    # --- Inventory ---
    inventory = []
    for pid in range(1, 26):
        opening_stock = random.randint(100, 1000)
        current_stock = max(0, opening_stock - random.randint(0, opening_stock))
        inventory.append((
            pid,
            opening_stock,
            current_stock,
            random.randint(20, 100),
            random_date(date(2026, 1, 1), date(2026, 8, 31)).isoformat(),
        ))
    cur.executemany("INSERT INTO inventory VALUES (?, ?, ?, ?, ?)", inventory)

    # --- Invoices, invoice_items, payments ---
    invoices, invoice_items, payments = [], [], []
    invoice_item_id = 1
    payment_id = 1

    for invoice_id in range(1, 301):
        customer_id = random.randint(1, 40)
        invoice_date = random_date(date(2025, 9, 1), date(2026, 8, 31))
        due_date = invoice_date + timedelta(days=30)
        status = random.choices(STATUSES, weights=[0.7, 0.2, 0.1])[0]

        # line items for this invoice
        n_items = random.randint(1, 5)
        total_amount = 0
        for _ in range(n_items):
            product_id = random.randint(1, 25)
            quantity = random.randint(1, 20)
            unit_price = next(p[4] for p in products if p[0] == product_id)
            line_total = round(quantity * unit_price, 2)
            total_amount += line_total
            invoice_items.append((invoice_item_id, invoice_id, product_id, quantity, unit_price, line_total))
            invoice_item_id += 1

        invoices.append((invoice_id, customer_id, invoice_date.isoformat(), due_date.isoformat(), status, round(total_amount, 2)))

        if status == "Paid":
            payment_date = invoice_date + timedelta(days=random.randint(1, 28))
            payments.append((payment_id, invoice_id, payment_date.isoformat(), round(total_amount, 2)))
            payment_id += 1
        elif status == "Overdue" and random.random() < 0.3:
            # partial payment on some overdue invoices
            payment_date = invoice_date + timedelta(days=random.randint(1, 45))
            partial = round(total_amount * random.uniform(0.2, 0.6), 2)
            payments.append((payment_id, invoice_id, payment_date.isoformat(), partial))
            payment_id += 1

    cur.executemany("INSERT INTO invoices VALUES (?, ?, ?, ?, ?, ?)", invoices)
    cur.executemany("INSERT INTO invoice_items VALUES (?, ?, ?, ?, ?, ?)", invoice_items)
    cur.executemany("INSERT INTO payments VALUES (?, ?, ?, ?)", payments)

    conn.commit()
    return conn


def export_to_csv(conn):
    os.makedirs(OUT_DIR, exist_ok=True)
    tables = ["customers", "products", "inventory", "invoices", "invoice_items", "payments"]
    cur = conn.cursor()
    for table in tables:
        cur.execute(f"SELECT * FROM {table}")
        rows = cur.fetchall()
        col_names = [d[0] for d in cur.description]
        with open(os.path.join(OUT_DIR, f"{table}.csv"), "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(col_names)
            writer.writerows(rows)
        print(f"Exported {table}.csv ({len(rows)} rows)")


if __name__ == "__main__":
    connection = build_database()
    export_to_csv(connection)
    connection.close()
    print(f"\nDatabase created: {DB_PATH}")
    print(f"CSV exports ready in: {OUT_DIR}/ (import these into Power BI)")
