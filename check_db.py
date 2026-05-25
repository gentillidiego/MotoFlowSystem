import sqlite3
import os

db_path = "/home/diego/projetos/GestaoClinica/clinica.db"
if not os.path.exists(db_path):
    print(f"Error: {db_path} not found")
    exit(1)

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("--- exam_odontograma for exam_id=4 ---")
cur.execute("SELECT * FROM exam_odontograma WHERE exam_id = 4")
row = cur.fetchone()
if row:
    print(dict(row))
else:
    print("No record found in exam_odontograma for exam_id=4")

print("\n--- exams for id=4 ---")
cur.execute("SELECT * FROM exams WHERE id = 4")
row = cur.fetchone()
if row:
    print(dict(row))
else:
    print("No record found in exams for id=4")

print("\n--- Tables in DB ---")
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
print([r[0] for r in cur.fetchall()])

conn.close()
