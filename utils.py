from flask_login import UserMixin
from database import query
import os
import requests
import re
import time
from google.oauth2 import service_account
import google.auth.transport.requests
import logging

from extensions import cache

# A expiração agora é controlada pelo cache.init_app e cache.set

class User(UserMixin):
    def __init__(self, id, usuario, senha_hash, is_admin=0):
        self.id = id
        self.usuario = usuario
        self.senha_hash = senha_hash
        self.is_admin = bool(is_admin)

def custo_total_aquisicao(v):
    base = v["preco_aquisicao"]
    extras = sum(r["valor"] for r in query(
        "SELECT valor FROM moto_custos WHERE moto_id=?", (v["produto_id"],)))
    return base + extras

def custo_total_venda(v):
    aq = custo_total_aquisicao(v)
    cv = sum(r["valor"] for r in query(
        "SELECT valor FROM venda_custos WHERE venda_id=?", (v["id"],)))
    return aq + cv

def motos_dropdown():
    rows = query("""
        SELECT id, modelo, placa, chassi, preco_venda
        FROM motos WHERE vendido=0 ORDER BY modelo
    """)
    result = []
    for r in rows:
        label = f"{r['modelo']}"
        if r['placa']: label += f" ({r['placa']})"
        elif r['chassi']: label += f" (Chassi: {r['chassi'][:6]}...)"
        else: label += " (Sem ID)"
        
        result.append({
            "id": r["id"],
            "label": label,
            "preco_venda": r["preco_venda"] or 0
        })
    return result

def get_gdrive_access_token():
    """Gera um token de acesso usando o arquivo JSON da conta de serviço."""
    token_cached = cache.get("gdrive_token")
    if token_cached:
        return token_cached

    json_path = os.getenv("GDRIVE_KEY_PATH")
    if not json_path:
        logging.error("Variável GDRIVE_KEY_PATH não definida.")
        return None
    if not os.path.exists(json_path):
        logging.error("Arquivo de chave do GDrive não encontrado: %s", json_path)
        return None

    try:
        scopes = ['https://www.googleapis.com/auth/drive.readonly']
        creds = service_account.Credentials.from_service_account_file(json_path, scopes=scopes)
        auth_req = google.auth.transport.requests.Request()
        creds.refresh(auth_req)
        
        # Tokens do Google expiram em 1 hora (3600s). Cacheamos por 3500s.
        cache.set("gdrive_token", creds.token, timeout=3500)
        return creds.token
    except Exception as e:
        logging.error("Erro ao gerar token GDrive: %s", e)
        return None

def get_gdrive_folder_id(url):
    """Extrai o ID da pasta do Google Drive a partir de uma URL."""
    if not url: return None
    # Formatos comuns: 
    # drive.google.com/drive/folders/ID
    # drive.google.com/open?id=ID
    match = re.search(r'folders/([a-zA-Z0-9_-]+)', url)
    if match: return match.group(1)
    match = re.search(r'id=([a-zA-Z0-9_-]+)', url)
    if match: return match.group(1)
    return None

def list_gdrive_images(folder_id):
    """Lista IDs de arquivos de imagem em uma pasta do GDrive via API v3 usando Service Account."""
    if not folder_id: return []
    
    # Verificar cache de arquivos compartilhado
    cache_key = f"gdrive_list_{folder_id}"
    cached_files = cache.get(cache_key)
    if cached_files:
        return cached_files

    token = get_gdrive_access_token()
    if not token:
        return []

    try:
        url = "https://www.googleapis.com/drive/v3/files"
        params = {
            "q": f"'{folder_id}' in parents and mimeType contains 'image/' and trashed = false",
            "fields": "files(id, name)",
            "pageSize": 50
        }
        headers = {"Authorization": f"Bearer {token}"}
        res = requests.get(url, params=params, headers=headers, timeout=5)
        
        if res.status_code == 200:
            files = res.json().get("files", [])
            # Ordenar arquivos pelo nome
            files.sort(key=lambda x: x.get('name', '').lower())
            
            # Priorizar arquivos que começam com '01'
            main_files = [f for f in files if f.get('name', '').startswith('01')]
            other_files = [f for f in files if not f.get('name', '').startswith('01')]
            sorted_files = main_files + other_files
            
            # Usar o endpoint de thumbnail com tamanho definido. 
            photo_links = [f"https://drive.google.com/thumbnail?id={f['id']}&sz=w1000" for f in sorted_files]
            
            # Salvar no cache compartilhado por 1 hora
            cache.set(cache_key, photo_links, timeout=3600)
            return photo_links
        else:
            logging.error("Erro API GDrive (%s): %s", res.status_code, res.text)
    except Exception as e:
        logging.error("Erro ao listar GDrive: %s", e)
    
    return []

def to_float(val, default=0.0):
    try:
        if not val: return default
        s = str(val).strip().replace('R$', '').replace(' ', '')
        if ',' in s and '.' in s:
            s = s.replace('.', '').replace(',', '.')
        elif ',' in s:
            s = s.replace(',', '.')
        return float(s)
    except (ValueError, TypeError):
        return None
