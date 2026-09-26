import sqlite3
import re
import requests
from database import DB
from app import app
from utils import get_gdrive_access_token

def sync():
    with app.app_context():
        token = get_gdrive_access_token()
        if not token:
            print("Erro ao obter token do Google Drive.")
            return

        headers = {'Authorization': f'Bearer {token}'}
        
        # Pastas a inspecionar
        parent_ids = {
            'Usadas': '1K9XyE8_N1p0LJ298q9aLfDvy3PXOPW1b',
            'Novas Shineray': '1kBsqbdouRGjOnIo364Afz4eMjYy8wP9c',
            'USADAS - Vendidas': '1jQF7FsksJyShY27zsOQyC4yhpsaKHqRi'
        }
        
        drive_folders = []
        for cat_name, pid in parent_ids.items():
            res = requests.get('https://www.googleapis.com/drive/v3/files',
                               params={'q': f"'{pid}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
                                       'fields': 'files(id, name)',
                                       'pageSize': 100},
                               headers=headers)
            for f in res.json().get('files', []):
                drive_folders.append({'cat': cat_name, 'name': f['name'], 'id': f['id']})
                
        print(f"Total de pastas lidas no Google Drive: {len(drive_folders)}")
        
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        c.execute("SELECT id, modelo, placa FROM motos")
        motos = c.fetchall()
        
        updated = 0
        for m in motos:
            m_id, modelo, placa = m
            if not placa:
                continue
            placa_clean = re.sub(r'[^A-Za-z0-9]', '', placa).upper()
            if len(placa_clean) < 6:
                continue
                
            match = None
            for df in drive_folders:
                df_clean = re.sub(r'[^A-Za-z0-9]', '', df['name']).upper()
                if placa_clean in df_clean:
                    match = df
                    break
                    
            if match:
                c.execute("UPDATE motos SET drive_doc_folder_id = ? WHERE id = ?", (match['id'], m_id))
                updated += 1
                print(f"✅ Moto ID {m_id} ({modelo} - {placa}) -> Vinculada a '{match['name']}' [ID: {match['id']}]")
                
        conn.commit()
        conn.close()
        print(f"\n🎉 Total de motos vinculadas com sucesso: {updated}")

if __name__ == "__main__":
    sync()
