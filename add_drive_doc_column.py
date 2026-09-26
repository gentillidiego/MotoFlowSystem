import sqlite3
from database import DB

def migrate():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("PRAGMA table_info(motos)")
    columns = [row[1] for row in c.fetchall()]
    
    if "drive_doc_folder_id" not in columns:
        print("Adicionando coluna drive_doc_folder_id na tabela motos...")
        c.execute("ALTER TABLE motos ADD COLUMN drive_doc_folder_id TEXT")
        conn.commit()
        print("Coluna drive_doc_folder_id adicionada com sucesso!")
    else:
        print("Coluna drive_doc_folder_id já existe na tabela motos.")
    
    conn.close()

if __name__ == "__main__":
    migrate()
