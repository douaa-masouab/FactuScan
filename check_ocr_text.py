import sqlite3
conn = sqlite3.connect('factuscan.db')
cursor = conn.cursor()
cursor.execute("SELECT id, supplier, total_amount, extracted_text FROM invoices ORDER BY id DESC LIMIT 1;")
row = cursor.fetchone()
if row:
    print(f"ID: {row[0]}")
    print(f"Supplier: {row[1]}")
    print(f"Total: {row[2]}")
    print(f"Text snippet: {row[3][:500] if row[3] else 'No text'}")
conn.close()
