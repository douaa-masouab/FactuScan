import sqlite3
try:
    conn = sqlite3.connect('factuscan.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, supplier, total_amount, created_at FROM invoices ORDER BY created_at DESC LIMIT 5;")
    rows = cursor.fetchall()
    for row in rows:
        print(row)
    conn.close()
except Exception as e:
    print(f"Error: {e}")
