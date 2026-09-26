#!/usr/bin/env python3
"""
Sincroniza automaticamente as vendas existentes no banco de dados com suas
respectivas pastas no Google Drive (em 'USADAS - Vendidas' e 'Novas Shineray').
"""
import re
import logging
from app import app
from database import query, execute
from utils import get_gdrive_access_token, ensure_moto_doc_subfolders
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def normalize_text(text):
    if not text:
        return ""
    return re.sub(r'[^A-Z0-9]', '', str(text).upper())

def find_all_drive_folders(token):
    headers = {"Authorization": f"Bearer {token}"}
    drive_folders = {}

    # 1. Pastas de USADAS - Vendidas: 2026 e 2024 - 2025
    year_folders = [
        ("2026", "1QOD-xIZ3RN7f7IBc7zRMLh4Q-jgVo0v4"),
        ("2024 - 2025", "1SvVUEg-plJWaVfbbYw36cZvnOIaq242P")
    ]
    for yname, yid in year_folders:
        try:
            r = requests.get('https://www.googleapis.com/drive/v3/files',
                params={'q': f"'{yid}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
                        'fields': 'files(id, name)', 'pageSize': 150},
                headers=headers, timeout=15).json()
            for f in r.get('files', []):
                drive_folders[f['name']] = {
                    'id': f['id'],
                    'name': f['name'],
                    'parent': f"USADAS - Vendidas/{yname}"
                }
        except Exception as e:
            logging.error("Erro ao listar pasta %s: %s", yname, e)

    # 2. Novas Shineray (raiz e subpastas de categorias de cilindrada)
    novas_id = "1kBsqbdouRGjOnIo364Afz4eMjYy8wP9c"
    try:
        r_novas = requests.get('https://www.googleapis.com/drive/v3/files',
            params={'q': f"'{novas_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
                    'fields': 'files(id, name)', 'pageSize': 100},
            headers=headers, timeout=15).json()
        
        for sf in r_novas.get('files', []):
            drive_folders[sf['name']] = {'id': sf['id'], 'name': sf['name'], 'parent': 'Novas Shineray'}
            # List sub-subfolders (ex: 175_s -> cliente)
            try:
                r_sub = requests.get('https://www.googleapis.com/drive/v3/files',
                    params={'q': f"'{sf['id']}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
                            'fields': 'files(id, name)', 'pageSize': 100},
                    headers=headers, timeout=15).json()
                for ssf in r_sub.get('files', []):
                    drive_folders[ssf['name']] = {'id': ssf['id'], 'name': ssf['name'], 'parent': f"Novas Shineray/{sf['name']}"}
            except Exception:
                pass
    except Exception as e:
        logging.error("Erro ao listar Novas Shineray: %s", e)

    return drive_folders

def sync_vendas():
    with app.app_context():
        token = get_gdrive_access_token()
        if not token:
            print("❌ Falha ao obter token do Google Drive.")
            return

        print("🔍 Buscando pastas de vendas no Google Drive...")
        drive_folders = find_all_drive_folders(token)
        print(f"📁 Total de {len(drive_folders)} pastas encontradas em USADAS - Vendidas e Novas Shineray.")

        sales = query("""
            SELECT v.id, v.data_venda, v.nome, v.produto_id, v.drive_doc_folder_id,
                   m.modelo, m.placa, m.ano, m.drive_doc_folder_id as moto_folder_id
            FROM vendas v
            LEFT JOIN motos m ON m.id = v.produto_id
            ORDER BY v.id DESC
        """)
        print(f"📊 Total de vendas no banco de dados: {len(sales)}")

        matched_count = 0
        already_linked_count = 0
        updated_sales = 0

        for s in sales:
            venda_id = s["id"]
            cliente = (s["nome"] or "").strip()
            placa = (s["placa"] or "").strip().upper()
            modelo = (s["modelo"] or "").strip()
            clean_placa = normalize_text(placa)
            clean_cliente = normalize_text(cliente)
            first_name = cliente.split()[0].upper() if cliente else ""

            # Se já tem pasta vinculada na venda
            if s["drive_doc_folder_id"]:
                already_linked_count += 1
                continue

            # Se a moto já tem pasta vinculada, herda para a venda
            if s["moto_folder_id"]:
                execute("UPDATE vendas SET drive_doc_folder_id=? WHERE id=?",
                        (s["moto_folder_id"], venda_id))
                updated_sales += 1
                print(f"🔗 Venda #{venda_id} ({cliente}) -> herdou pasta da moto: {s['moto_folder_id']}")
                continue

            matched_folder = None
            # 1. Tentar por placa (se placa com 7 chars)
            if clean_placa and len(clean_placa) >= 7:
                for fname, finfo in drive_folders.items():
                    f_clean = normalize_text(fname)
                    if clean_placa in f_clean:
                        matched_folder = finfo
                        break

            # 2. Tentar por nome do cliente na pasta
            if not matched_folder and clean_cliente and len(first_name) >= 4:
                for fname, finfo in drive_folders.items():
                    f_clean = normalize_text(fname)
                    if len(clean_cliente) >= 8 and clean_cliente in f_clean:
                        matched_folder = finfo
                        break
                    elif first_name and first_name in f_clean and normalize_text(modelo)[:4] in f_clean:
                        matched_folder = finfo
                        break

            if matched_folder:
                fid = matched_folder["id"]
                execute("UPDATE vendas SET drive_doc_folder_id=? WHERE id=?", (fid, venda_id))
                if s["produto_id"]:
                    execute("UPDATE motos SET drive_doc_folder_id=? WHERE id=? AND drive_doc_folder_id IS NULL",
                            (fid, s["produto_id"]))
                matched_count += 1
                updated_sales += 1
                print(f"✅ MATCH Venda #{venda_id} ({cliente} | {modelo} {placa}) -> '{matched_folder['name']}' em {matched_folder['parent']} (ID: {fid})")

        print("\n================ RESUMO DA SINCRONIZAÇÃO ================")
        print(f"Total de vendas analisadas: {len(sales)}")
        print(f"Vendas já vinculadas anteriormente: {already_linked_count}")
        print(f"Vendas recém-vinculadas nesta execução: {updated_sales}")
        print("=========================================================")

if __name__ == "__main__":
    sync_vendas()
