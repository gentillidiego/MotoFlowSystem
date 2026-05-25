import sqlite3
from database import DB

def add_km_column():
    print(f"Connecting to database at {DB}...")
    with sqlite3.connect(DB) as conn:
        cursor = conn.cursor()
        
        # Check if column exists
        cursor.execute("PRAGMA table_info(motos)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if 'km' not in columns:
            print("Adding 'km' column to 'motos' table...")
            try:
                cursor.execute("ALTER TABLE motos ADD COLUMN km INTEGER")
                print("Column 'km' added successfully.")
            except sqlite3.Error as e:
                print(f"Error adding column: {e}")
        else:
            print("Column 'km' already exists.")

if __name__ == "__main__":
    add_km_column()
