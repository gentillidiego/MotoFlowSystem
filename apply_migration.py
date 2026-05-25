import sqlite3
import os

db_path = "/home/diego/projetos/GestaoClinica/clinica.db"
if not os.path.exists(db_path):
    print(f"Error: {db_path} not found")
    exit(1)

conn = sqlite3.connect(db_path)
cur = conn.cursor()

try:
    cur.execute("ALTER TABLE exam_odontograma ADD COLUMN notas_dentes TEXT")
    conn.commit()
    print("Column notas_dentes added successfully to exam_odontograma.")
except Exception as e:
    print(f"Notice: {str(e)}")

# Verify
cur.execute("PRAGMA table_info(exam_odontograma)")
columns = cur.fetchall()
print("Current columns in exam_odontograma:")
for col in columns:
    print(col)

conn.close()
