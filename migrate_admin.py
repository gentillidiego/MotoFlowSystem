import sqlite3
from pathlib import Path

DB = Path("estoque.db")

def migrate():
    if not DB.exists():
        print("Database not found!")
        return

    with sqlite3.connect(DB) as conn:
        cursor = conn.cursor()
        
        # Check if column exists
        try:
            cursor.execute("SELECT is_admin FROM usuarios LIMIT 1")
            print("Column 'is_admin' already exists.")
        except sqlite3.OperationalError:
            print("Adding 'is_admin' column...")
            cursor.execute("ALTER TABLE usuarios ADD COLUMN is_admin INTEGER DEFAULT 0")
            print("Column added.")

        # Promote Diego to admin
        print("Promoting 'Diego' to admin...")
        cursor.execute("UPDATE usuarios SET is_admin = 1 WHERE usuario = 'Diego'")
        
        # Check changes
        cursor.execute("SELECT usuario, is_admin FROM usuarios")
        users = cursor.fetchall()
        print("Current Users Status:")
        for u in users:
            print(f"User: {u[0]} | Admin: {u[1]}")
            
        conn.commit()
        print("Migration complete.")

if __name__ == "__main__":
    migrate()
