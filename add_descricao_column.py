import sqlite3
from pathlib import Path

DB = Path(__file__).with_name("estoque.db")

def migrate():
    print(f"Migrando {DB}...")
    try:
        with sqlite3.connect(DB) as c:
            c.execute("ALTER TABLE motos ADD COLUMN descricao TEXT")
            print("Coluna 'descricao' adicionada com sucesso!")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("Coluna 'descricao' já existe.")
        else:
            print(f"Erro na migração: {e}")
    except Exception as e:
        print(f"Erro inesperado: {e}")

if __name__ == "__main__":
    migrate()
