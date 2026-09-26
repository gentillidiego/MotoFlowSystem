from flask_login import UserMixin
from database import query
import os
import requests
import re
import time
import io
import subprocess
import logging
from werkzeug.utils import secure_filename
from google.oauth2 import service_account
import google.auth.transport.requests

from extensions import cache

# Categorias oficiais de documentação solicitadas pelo cliente
DOC_CATEGORIES = [
    {
        "key": "veiculo",
        "name": "01_Documento_Veiculo",
        "label": "Documento do Veículo",
        "icon": "📄",
        "badge": "CRLV / DUT"
    },
    {
        "key": "codigo_seguranca",
        "name": "02_Codigo_Seguranca",
        "label": "Código de Segurança do Veículo",
        "icon": "🔐",
        "badge": "CRV / ATPV"
    },
    {
        "key": "comprador",
        "name": "03_Documento_Comprador",
        "label": "Documento do Comprador",
        "icon": "👤",
        "badge": "CNH / RG / Comprovante"
    },
    {
        "key": "vendedor",
        "name": "04_Documento_Vendedor",
        "label": "Documento do Vendedor",
        "icon": "🤝",
        "badge": "Identificação Vendedor"
    },
    {
        "key": "vistoria",
        "name": "05_Fotos_Vistoria",
        "label": "Fotos para Vistoria",
        "icon": "📸",
        "badge": "Chassi / Motor / Detalhes"
    }
]

GDRIVE_PARENT_FOLDERS = {
    "Usadas": "1K9XyE8_N1p0LJ298q9aLfDvy3PXOPW1b",
    "Novas": "1kBsqbdouRGjOnIo364Afz4eMjYy8wP9c",
    "Vendidas": "1jQF7FsksJyShY27zsOQyC4yhpsaKHqRi",
    "Vendidas_2026": "1QOD-xIZ3RN7f7IBc7zRMLh4Q-jgVo0v4",
    "Vendidas_2024_2025": "1SvVUEg-plJWaVfbbYw36cZvnOIaq242P"
}

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
    """Gera um token de acesso usando o arquivo JSON da conta de serviço (escopo completo do Drive)."""
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
        scopes = ['https://www.googleapis.com/auth/drive']
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
    match = re.search(r'folders/([a-zA-Z0-9_-]+)', url)
    if match: return match.group(1)
    match = re.search(r'id=([a-zA-Z0-9_-]+)', url)
    if match: return match.group(1)
    # Se já for o próprio ID sem URL
    if re.match(r'^[a-zA-Z0-9_-]{20,}$', url.strip()):
        return url.strip()
    return None

def list_gdrive_images(folder_id):
    """Lista IDs de arquivos de imagem em uma pasta do GDrive via API v3 usando Service Account."""
    if not folder_id: return []
    
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
            files.sort(key=lambda x: x.get('name', '').lower())
            
            main_files = [f for f in files if f.get('name', '').startswith('01')]
            other_files = [f for f in files if not f.get('name', '').startswith('01')]
            sorted_files = main_files + other_files
            
            photo_links = [f"https://drive.google.com/thumbnail?id={f['id']}&sz=w1000" for f in sorted_files]
            cache.set(cache_key, photo_links, timeout=3600)
            return photo_links
        else:
            logging.error("Erro API GDrive (%s): %s", res.status_code, res.text)
    except Exception as e:
        logging.error("Erro ao listar GDrive: %s", e)
    
    return []

def optimize_image_bytes(image_bytes, max_dim=1600, quality=80):
    """
    Otimiza imagem 100% em memória via Pillow sem escrever nenhum arquivo no disco da VPS.
    Reduz imagens gigantes (de smartphones) para ~250KB preservando excelente nitidez.
    """
    try:
        from PIL import Image, ImageOps
        img = Image.open(io.BytesIO(image_bytes))
        try:
            img = ImageOps.exif_transpose(img)
        except Exception:
            pass
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        return buf.getvalue(), "image/jpeg"
    except Exception as e:
        logging.warning("Erro ao otimizar imagem em memória: %s. Mantendo bytes originais.", e)
        return image_bytes, None

def ensure_moto_doc_subfolders(moto_folder_id):
    """Garante que as 5 subpastas padronizadas existam dentro da pasta da moto no Google Drive."""
    token = get_gdrive_access_token()
    if not token or not moto_folder_id:
        return {}

    headers = {"Authorization": f"Bearer {token}"}
    try:
        # Busca pastas filhas existentes
        q = f"'{moto_folder_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        res = requests.get('https://www.googleapis.com/drive/v3/files',
                           params={'q': q, 'fields': 'files(id, name)'},
                           headers=headers, timeout=10)
        existing = {}
        if res.status_code == 200:
            existing = {f['name']: f['id'] for f in res.json().get('files', [])}
            
        result = {}
        for cat in DOC_CATEGORIES:
            folder_name = cat["name"]
            if folder_name in existing:
                result[cat["key"]] = {"id": existing[folder_name], "name": folder_name}
            else:
                # Criar subpasta sob demanda via API
                meta = {
                    'name': folder_name,
                    'mimeType': 'application/vnd.google-apps.folder',
                    'parents': [moto_folder_id]
                }
                cr = requests.post('https://www.googleapis.com/drive/v3/files',
                                   json=meta, headers=headers, timeout=10)
                if cr.status_code == 200:
                    created_id = cr.json()['id']
                    result[cat["key"]] = {"id": created_id, "name": folder_name}
                else:
                    logging.error("Falha ao criar subpasta %s no Drive: %s", folder_name, cr.text)
        return result
    except Exception as e:
        logging.error("Erro em ensure_moto_doc_subfolders: %s", e)
        return {}

def create_moto_drive_folder(modelo, placa, ano=None, origem="Usadas"):
    """
    Cria a pasta raiz de uma nova moto no Google Drive da Confiance Motos
    e já inicializa as 5 subpastas. Retorna o ID da pasta criada.
    """
    token = get_gdrive_access_token()
    if not token:
        return None

    headers = {"Authorization": f"Bearer {token}"}
    parent_id = GDRIVE_PARENT_FOLDERS.get("Novas" if origem == "Novas" else "Usadas", GDRIVE_PARENT_FOLDERS["Usadas"])

    parts = [modelo.strip() if modelo else "MOTO"]
    if ano:
        parts.append(str(ano).strip())
    if placa:
        parts.append(f"- {placa.strip().upper()}")
    else:
        parts.append("- SEM PLACA")
    folder_name = " ".join(parts)

    meta = {
        'name': folder_name,
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': [parent_id]
    }
    try:
        r = requests.post('https://www.googleapis.com/drive/v3/files', json=meta, headers=headers, timeout=10)
        if r.status_code == 200:
            new_folder_id = r.json()['id']
            # Cria as 5 subpastas imediatamente
            ensure_moto_doc_subfolders(new_folder_id)
            return new_folder_id
        else:
            logging.error("Erro ao criar pasta da moto no Drive: %s", r.text)
            return None
    except Exception as e:
        logging.error("Exceção ao criar pasta no Drive: %s", e)
        return None

def create_venda_drive_folder(venda, moto=None):
    """
    Cria a pasta raiz de documentação de uma venda no Google Drive:
    - Se a moto for Nova/Shineray -> cria dentro de 'Novas Shineray' (1kBsqbdouRGjOnIo364Afz4eMjYy8wP9c)
    - Se for Usada -> cria dentro de 'USADAS - Vendidas/2026' (1QOD-xIZ3RN7f7IBc7zRMLh4Q-jgVo0v4)
    E inicializa imediatamente as 5 subpastas padronizadas.
    """
    token = get_gdrive_access_token()
    if not token:
        return None

    headers = {"Authorization": f"Bearer {token}"}

    origem = (moto.get("origem") if moto else "") or ""
    modelo = ((moto.get("modelo") if moto else "") or "MOTO").strip()
    is_nova = "nova" in origem.lower() or "shineray" in modelo.lower()

    if is_nova:
        parent_id = GDRIVE_PARENT_FOLDERS["Novas"]
    else:
        data_venda = (venda.get("data_venda") if venda else "") or ""
        if data_venda and data_venda.startswith(("2024", "2025")):
            parent_id = GDRIVE_PARENT_FOLDERS["Vendidas_2024_2025"]
        else:
            parent_id = GDRIVE_PARENT_FOLDERS["Vendidas_2026"]

    ano = (moto.get("ano") if moto else "") or ""
    placa = (moto.get("placa") if moto else "") or ""
    cliente = (venda.get("nome") if venda else "") or ""

    parts = [modelo]
    if ano:
        parts.append(str(ano).strip())
    if placa:
        parts.append(f"- {placa.strip().upper()}")
    elif cliente:
        parts.append(f"- {cliente.strip()}")
    else:
        parts.append("- SEM PLACA")

    folder_name = " ".join(parts)

    meta = {
        'name': folder_name,
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': [parent_id]
    }
    try:
        r = requests.post('https://www.googleapis.com/drive/v3/files', json=meta, headers=headers, timeout=10)
        if r.status_code == 200:
            new_folder_id = r.json()['id']
            ensure_moto_doc_subfolders(new_folder_id)
            return new_folder_id
        else:
            logging.error("Erro ao criar pasta da venda no Drive: %s", r.text)
            return None
    except Exception as e:
        logging.error("Exceção ao criar pasta de venda no Drive: %s", e)
        return None

def format_doc_item(f, cat_key):
    """Formata um item retornado da API do Drive para exibição rica no frontend."""
    mime = f.get('mimeType', '')
    is_img = mime.startswith('image/')
    is_pdf = (mime == 'application/pdf')
    size_bytes = int(f.get('size') or 0)
    fid = f['id']
    name = f.get('name', 'Documento')

    if size_bytes < 1024:
        size_fmt = f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        size_fmt = f"{size_bytes / 1024:.1f} KB"
    else:
        size_fmt = f"{size_bytes / (1024 * 1024):.1f} MB"

    raw_date = f.get('createdTime', '')
    date_fmt = ""
    if raw_date and len(raw_date) >= 10:
        parts = raw_date[:10].split("-")
        if len(parts) == 3:
            date_fmt = f"{parts[2]}/{parts[1]}/{parts[0]}"

    # Miniatura compacta servida diretamente do CDN de alta performance do Google
    thumb_url = f"https://drive.google.com/thumbnail?id={fid}&sz=w800"
    
    # Preview no Google Docs viewer
    view_url = f"https://drive.google.com/file/d/{fid}/preview"
    
    # Link de download direto sem salvar no disco da VPS
    download_url = f"/estoque/documentos/download/{fid}?name={requests.utils.quote(name)}"

    return {
        "id": fid,
        "name": name,
        "mimeType": mime,
        "is_image": is_img,
        "is_pdf": is_pdf,
        "size_fmt": size_fmt,
        "created_date": date_fmt,
        "thumbnail_url": thumb_url,
        "view_url": view_url,
        "download_url": download_url,
        "category_key": cat_key
    }

def list_moto_documents(moto_folder_id):
    """
    Lista todos os documentos de uma moto no Google Drive categorizados nas 5 subpastas,
    mais qualquer arquivo avulso pré-existente na pasta raiz da moto.
    Cache de 2 minutos para velocidade instantânea.
    """
    if not moto_folder_id:
        return {"categories": {}, "geral_files": [], "total_files": 0, "drive_url": None}

    cache_key = f"docs_{moto_folder_id}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    token = get_gdrive_access_token()
    if not token:
        return {"categories": {}, "geral_files": [], "total_files": 0, "drive_url": f"https://drive.google.com/drive/folders/{moto_folder_id}"}

    headers = {"Authorization": f"Bearer {token}"}
    subfolders_map = ensure_moto_doc_subfolders(moto_folder_id)

    categories_data = {}
    total_count = 0

    for cat in DOC_CATEGORIES:
        sub_info = subfolders_map.get(cat["key"])
        files_list = []
        sub_id = sub_info["id"] if sub_info else None
        
        if sub_id:
            q = f"'{sub_id}' in parents and mimeType != 'application/vnd.google-apps.folder' and trashed = false"
            try:
                res = requests.get('https://www.googleapis.com/drive/v3/files',
                                   params={
                                       'q': q,
                                       'fields': 'files(id, name, mimeType, size, createdTime, webViewLink, thumbnailLink)',
                                       'pageSize': 50
                                   },
                                   headers=headers, timeout=8)
                if res.status_code == 200:
                    for f in res.json().get('files', []):
                        f_item = format_doc_item(f, cat["key"])
                        files_list.append(f_item)
                        total_count += 1
            except Exception as e:
                logging.error("Erro ao listar arquivos da subpasta %s: %s", cat['key'], e)

        categories_data[cat["key"]] = {
            "key": cat["key"],
            "label": cat["label"],
            "icon": cat["icon"],
            "badge": cat["badge"],
            "subfolder_name": cat["name"],
            "subfolder_id": sub_id,
            "files": files_list
        }

    # Arquivos legados/avulsos na raiz da pasta da moto
    geral_files = []
    try:
        q_root = f"'{moto_folder_id}' in parents and mimeType != 'application/vnd.google-apps.folder' and trashed = false"
        res_root = requests.get('https://www.googleapis.com/drive/v3/files',
                                params={
                                    'q': q_root,
                                    'fields': 'files(id, name, mimeType, size, createdTime, webViewLink, thumbnailLink)',
                                    'pageSize': 50
                                },
                                headers=headers, timeout=8)
        if res_root.status_code == 200:
            for f in res_root.json().get('files', []):
                geral_files.append(format_doc_item(f, "geral"))
                total_count += 1
    except Exception as e:
        logging.error("Erro ao listar arquivos da raiz da pasta da moto: %s", e)

    result = {
        "categories": categories_data,
        "geral_files": geral_files,
        "total_files": total_count,
        "drive_url": f"https://drive.google.com/drive/folders/{moto_folder_id}"
    }
    cache.set(cache_key, result, timeout=120)
    return result

def upload_moto_document(file_bytes, filename, target_folder_id, moto_folder_id=None):
    """
    Faz upload de arquivo para a subpasta do Drive 100% em memória via streaming pipe (rclone rcat).
    Nenhum arquivo ou byte temporário é gravado no disco da VPS.
    Imagens são comprimidas com Pillow antes do envio.
    """
    clean_filename = secure_filename(filename) or "documento"
    # Se o nome não tiver extensão, tentar inferir ou manter
    is_img = any(clean_filename.lower().endswith(ext) for ext in ('.jpg', '.jpeg', '.png', '.webp', '.bmp'))
    if is_img:
        file_bytes, _ = optimize_image_bytes(file_bytes)

    remote = f"motoflow.drive,root_folder_id={target_folder_id}:{clean_filename}"
    try:
        p = subprocess.Popen(['rclone', 'rcat', remote],
                             stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        stdout, stderr = p.communicate(input=file_bytes, timeout=40)
        if p.returncode == 0:
            if moto_folder_id:
                cache.delete(f"docs_{moto_folder_id}")
            return True, None
        else:
            err_msg = stderr.decode(errors="replace")
            logging.error("Erro no rclone rcat: %s", err_msg)
            return False, err_msg
    except Exception as e:
        logging.error("Exceção no upload para Drive: %s", e)
        return False, str(e)

def delete_moto_document(file_id, moto_folder_id=None):
    """Exclui arquivo do Google Drive e invalida cache."""
    token = get_gdrive_access_token()
    if not token:
        return False, "Token indisponível"
    try:
        headers = {"Authorization": f"Bearer {token}"}
        r = requests.delete(f"https://www.googleapis.com/drive/v3/files/{file_id}", headers=headers, timeout=10)
        if r.status_code in (200, 204):
            if moto_folder_id:
                cache.delete(f"docs_{moto_folder_id}")
            return True, None
        else:
            return False, r.text
    except Exception as e:
        logging.error("Erro ao deletar arquivo do Drive: %s", e)
        return False, str(e)

def stream_gdrive_file(file_id):
    """
    Gera chunks de 16KB diretamente do Google Drive para o navegador via streaming HTTP.
    Zero consumo de disco na VPS.
    """
    token = get_gdrive_access_token()
    if not token:
        return None, None
    url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        res = requests.get(url, headers=headers, stream=True, timeout=30)
        if res.status_code == 200:
            content_type = res.headers.get("Content-Type", "application/octet-stream")
            return res.iter_content(chunk_size=16384), content_type
    except Exception as e:
        logging.error("Erro ao fazer stream de arquivo do Drive: %s", e)
    return None, None

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
