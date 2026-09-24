"""
analysis.py
Loads the MSME invoicing & inventory data, cleans/validates it,
and computes the KPIs used in the Power BI dashboard:
- Outstanding receivables
- Monthly revenue trend
- Stock turnover ratio
- Restock alerts
- Average days to payment

Run generate_data.py first to create msme_analytics.db.
"""

import sqlite3
import pandas as pd
import matplotlib.pyplot as plt

DB_PATH = "msme_analytics.db"


def load_tables(conn):
    customers = pd.read_sql("SELECT * FROM customers", conn, parse_dates=["onboarded_date"])
    products = pd.read_sql("SELECT * FROM products", conn)
    inventory = pd.read_sql("SELECT * FROM inventory", conn, parse_dates=["last_restock_date"])
    invoices = pd.read_sql("SELECT * FROM invoices", conn, parse_dates=["invoice_date", "due_date"])
    invoice_items = pd.read_sql("SELECT * FROM invoice_items", conn)
    payments = pd.read_sql("SELECT * FROM payments", conn, parse_dates=["payment_date"])
    return customers, products, inventory, invoices, invoice_items, payments


def clean_data(invoices, payments):
    # Drop duplicate invoice rows and any with missing critical fields
    invoices = invoices.drop_duplicates(subset="invoice_id").dropna(subset=["invoice_date", "total_amount"])
    payments = payments.drop_duplicates(subset="payment_id").dropna(subset=["invoice_id", "amount_paid"])
    invoices["total_amount"] = invoices["total_amount"].round(2)
    return invoices, payments


def outstanding_receivables(invoices, payments, customers):
    paid = payments.groupby("invoice_id")["amount_paid"].sum().rename("amount_paid")
    merged = invoices.merge(paid, on="invoice_id", how="left")
    merged["amount_paid"] = merged["amount_paid"].fillna(0)
    merged["outstanding"] = merged["total_amount"] - merged["amount_paid"]

    receivables = (
        merged[merged["status"].isin(["Pending", "Overdue"])]
        .merge(customers[["customer_id", "customer_name"]], on="customer_id")
        .groupby("customer_name")["outstanding"]
        .sum()
        .sort_values(ascending=False)
    )
    return receivables


def monthly_revenue(invoices):
    df = invoices.copy()
    df["month"] = df["invoice_date"].dt.to_period("M").astype(str)
    return df.groupby("month")["total_amount"].sum()


def stock_turnover(invoice_items, products, inventory):
    units_sold = invoice_items.groupby("product_id")["quantity"].sum().rename("units_sold")
    merged = (
        products.merge(units_sold, on="product_id", how="left")
        .merge(inventory[["product_id", "current_stock", "reorder_level"]], on="product_id")
    )
    merged["units_sold"] = merged["units_sold"].fillna(0)
    merged["stock_turnover_ratio"] = (
        merged["units_sold"] / merged["current_stock"].replace(0, pd.NA)
    ).round(2)
    return merged.sort_values("stock_turnover_ratio", ascending=False)


def restock_alerts(products, inventory):
    merged = products.merge(inventory, on="product_id")
    return merged[merged["current_stock"] <= merged["reorder_level"]][
        ["product_name", "current_stock", "reorder_level"]
    ]


def avg_days_to_payment(invoices, payments):
    paid_invoices = invoices[invoices["status"] == "Paid"]
    first_payment = payments.groupby("invoice_id")["payment_date"].min()
    merged = paid_invoices.merge(first_payment, on="invoice_id")
    merged["days_to_payment"] = (merged["payment_date"] - merged["invoice_date"]).dt.days
    return merged["days_to_payment"].mean()


def plot_revenue_trend(monthly_rev):
    plt.figure(figsize=(8, 4))
    monthly_rev.plot(kind="line", marker="o")
    plt.title("Monthly Revenue Trend")
    plt.ylabel("Revenue (₹)")
    plt.xlabel("Month")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig("monthly_revenue_trend.png")
    plt.close()
    print("Saved chart: monthly_revenue_trend.png")


if __name__ == "__main__":
    conn = sqlite3.connect(DB_PATH)
    customers, products, inventory, invoices, invoice_items, payments = load_tables(conn)
    invoices, payments = clean_data(invoices, payments)

    print("\n--- Top 5 Outstanding Receivables ---")
    print(outstanding_receivables(invoices, payments, customers).head())

    monthly_rev = monthly_revenue(invoices)
    print("\n--- Monthly Revenue ---")
    print(monthly_rev)
    plot_revenue_trend(monthly_rev)

    print("\n--- Top 5 Stock Turnover Products ---")
    print(stock_turnover(invoice_items, products, inventory).head())

    print("\n--- Restock Alerts ---")
    print(restock_alerts(products, inventory))

    print(f"\nAverage days to payment: {avg_days_to_payment(invoices, payments):.1f} days")

    conn.close()
