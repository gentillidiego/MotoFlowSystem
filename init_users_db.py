import sqlite3
from pathlib import Path
from werkzeug.security import generate_password_hash

DB = Path("estoque.db")

def init_users():
    if not DB.exists():
        print("Database not found! Run app.py at least once to create it.")
        return

    with sqlite3.connect(DB) as conn:
        cursor = conn.cursor()
        
        # Determine if we need to reset the table? 
        # Since I had issues, let's try to detect if columns exist or just drop/recreate for safety since it's dev
        try:
             cursor.execute("SELECT usuario FROM usuarios LIMIT 1")
        except sqlite3.OperationalError:
             print("Table or column missing, recreating...")
             cursor.execute("DROP TABLE IF EXISTS usuarios")
        
        # Create table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usuarios(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario TEXT UNIQUE NOT NULL,
                senha_hash TEXT NOT NULL,
                is_admin INTEGER DEFAULT 0
            )
        """)
        
        # Check if admin exists
        cursor.execute("SELECT id FROM usuarios WHERE usuario='Diego'")
        if not cursor.fetchone():
            # Create Admin
            # Password '2809'
            pwhash = generate_password_hash("2809")
            cursor.execute("INSERT INTO usuarios (usuario, senha_hash, is_admin) VALUES (?, ?, 1)", ("Diego", pwhash))
            print("Admin user 'Diego' created successfully.")
        else:
            print("Admin user 'Diego' already exists.")
            
        conn.commit()

if __name__ == "__main__":
    init_users()
