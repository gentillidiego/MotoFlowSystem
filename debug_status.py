import sqlite3
from pathlib import Path

DB = Path("estoque.db")

def debug_status():
    if not DB.exists():
        print("Database not found!")
        return

    with sqlite3.connect(DB) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        print("--- Checking Transferencias ---")
        cursor.execute("SELECT id, status FROM transferencias")
        rows = cursor.fetchall()
        
        for row in rows:
            tid = row["id"]
            status = row["status"]
            print(f"ID: {tid} | Status: {repr(status)} | Hex: {status.encode('utf-8').hex()}")
            
        print("\n--- Defined Steps in Code (Simulated) ---")
        # Simulating the list from the template to see if Python strings match
        steps = ['Indicação Realizada', 'Assinatura Comprador', 'Assinatura Vendedor', 'ATPV-e Emitido', 'Taxas e Vistoria', 'Concluída']
        for s in steps:
             print(f"Step: {repr(s)} | Hex: {s.encode('utf-8').hex()}")

if __name__ == "__main__":
    debug_status()
