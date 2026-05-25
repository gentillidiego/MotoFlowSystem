import sqlite3
from app import load_user, User
from pathlib import Path

# Mock app context if needed or just use load_user directly if it depends on DB only
# app.py's load_user uses the global 'query' function which uses 'DB'.
# Let's ensure 'DB' is correct. app.py sets DB relative to __file__.
# Since we are importing from app, it should work.

print("--- Verifying Admin Logic ---")

# 1. Check Database
conn = sqlite3.connect("estoque.db")
c = conn.cursor()
c.row_factory = sqlite3.Row
u_db = c.execute("SELECT * FROM usuarios WHERE usuario='Diego'").fetchone()
print(f"DB User 'Diego': is_admin={u_db['is_admin']}")

# 2. Check Application Logic
user_obj = load_user(u_db["id"])
print(f"Loaded User Object: {user_obj.usuario}")
print(f"User.is_admin property: {user_obj.is_admin}")

if user_obj.is_admin:
    print("SUCCESS: Diego is recognized as Admin by the app logic.")
else:
    print("FAILURE: Diego is NOT recognized as Admin.")
