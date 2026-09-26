from flask import Blueprint, render_template, request, redirect, url_for, jsonify, flash, Response
from flask_login import login_required, current_user
from werkzeug.security import check_password_hash
import sqlite3
import logging
import os
from database import query, execute, DB
from utils import (
    to_float,
    list_moto_documents,
    upload_moto_document,
    delete_moto_document,
    stream_gdrive_file,
    create_moto_drive_folder,
    get_gdrive_folder_id,
    ensure_moto_doc_subfolders,
    DOC_CATEGORIES,
    ALLOWED_DOC_EXTENSIONS,
    is_valid_gdrive_id,
    sanitize_filename_header
)

bp = Blueprint('estoque', __name__)

@bp.route("/estoque")
@login_required
def estoque():
    page = request.args.get('page', 1, type=int)
    q = request.args.get('q', '').strip()
    per_page = 20
    offset = (page - 1) * per_page

    where = "WHERE vendido=0"
    params = []
    if q:
        where += " AND (modelo LIKE ? OR placa LIKE ? OR chassi LIKE ?)"
        like = f"%{q}%"
        params += [like, like, like]

    total_count = query(f"SELECT COUNT(*) as total FROM motos {where}", params, one=True)["total"]
    total_pages = (total_count + per_page - 1) // per_page

    motos = query(f"""
        SELECT m.*,
               (m.preco_aquisicao + IFNULL(SUM(mc.valor), 0)) as custo_total
        FROM motos m
        LEFT JOIN moto_custos mc ON mc.moto_id = m.id
        {where}
        GROUP BY m.id
        ORDER BY m.id DESC
        LIMIT ? OFFSET ?
    """, params + [per_page, offset])
    total      = len(motos)
    consignada = sum(1 for m in motos if m["origem"] == "Consignada")
    propria    = sum(1 for m in motos if m["origem"] == "Propria")
    fornecedor = sum(1 for m in motos if m["origem"] == "Fornecedor")
    return render_template("estoque.html",
                           motos=motos,
                           total=total_count,
                           consignada=consignada,
                           propria=propria,
                           fornecedor=fornecedor,
                           page=page,
                           total_pages=total_pages,
                           q=q)

@bp.route("/estoque/origem/<origem>")
@login_required
def estoque_por_origem(origem):
    origem_map = {"consignadas":"Consignada","proprias":"Propria","fornecedor":"Fornecedor"}
    o = origem_map.get(origem.lower())
    page = request.args.get('page', 1, type=int)
    q = request.args.get('q', '').strip()
    per_page = 20
    offset = (page - 1) * per_page

    where = "WHERE vendido=0 AND origem=?"
    params = [o]
    if q:
        where += " AND (modelo LIKE ? OR placa LIKE ? OR chassi LIKE ?)"
        like = f"%{q}%"
        params += [like, like, like]

    total_count = query(f"SELECT COUNT(*) as total FROM motos {where}", params, one=True)["total"]
    total_pages = (total_count + per_page - 1) // per_page

    motos = query(f"""
        SELECT m.*,
               (m.preco_aquisicao + IFNULL(SUM(mc.valor), 0)) as custo_total
        FROM motos m
        LEFT JOIN moto_custos mc ON mc.moto_id = m.id
        {where}
        GROUP BY m.id
        ORDER BY m.id DESC
        LIMIT ? OFFSET ?
    """, params + [per_page, offset])
    return render_template("estoque.html", motos=motos, total=total_count,
                           consignada=0, propria=0, fornecedor=0,
                           page=page, total_pages=total_pages, origem_slug=origem, q=q)

@bp.route("/estoque/novo", methods=["GET","POST"])
@bp.route("/estoque/editar/<int:i>", methods=["GET","POST"])
@login_required
def estoque_form(i=None):
    edit = i is not None
    moto = query("SELECT * FROM motos WHERE id=?", (i,), one=True) if edit else {}
    custos = query("SELECT * FROM moto_custos WHERE moto_id=?", (i,)) if edit else []
    if request.method == "POST":
        d = {k: request.form.get(k) or None for k in (
            "modelo","chassi","placa","cor","ano","origem","fotos_url","descricao")}
        
        # Validação numérica
        d["preco_aquisicao"] = to_float(request.form.get("preco_aquisicao"))
        d["preco_venda"] = to_float(request.form.get("preco_venda"))
        d["km"] = to_float(request.form.get("km"), default=0)

        if d["preco_aquisicao"] is None or d["preco_venda"] is None or d["km"] is None:
            return render_template("estoque_form.html",
                                   editar=edit, moto=d, custos=custos,
                                   erro="Preço e KM devem ser números válidos.")
        if not (d["chassi"] or d["placa"]):
            return render_template("estoque_form.html",
                                   editar=edit, moto=d, custos=custos,
                                   erro="Preencha chassi ou placa.")
        if edit:
            execute("""UPDATE motos SET
                         modelo=:modelo,chassi=:chassi,placa=:placa,cor=:cor,
                         ano=:ano,origem=:origem,
                         preco_aquisicao=:preco_aquisicao,
                         preco_venda=:preco_venda,
                         km=:km,
                         fotos_url=:fotos_url,
                         descricao=:descricao
                       WHERE id=:id""", {**d, "id": i})
            moto_id = i
        else:
            # Criação automática da pasta no Google Drive para novos veículos
            drive_folder_id = None
            try:
                drive_folder_id = create_moto_drive_folder(
                    d["modelo"], d["placa"], d["ano"], d["origem"]
                )
            except Exception as e:
                logging.error("Falha ao criar pasta no Drive para moto nova: %s", e)

            d["drive_doc_folder_id"] = drive_folder_id
            with sqlite3.connect(DB) as c:
                cur = c.execute("""INSERT INTO motos(
                              modelo,chassi,placa,cor,ano,origem,
                              preco_aquisicao,preco_venda,km,fotos_url,descricao,
                              drive_doc_folder_id
                            ) VALUES (
                              :modelo,:chassi,:placa,:cor,:ano,:origem,
                              :preco_aquisicao,:preco_venda,:km,:fotos_url,:descricao,
                              :drive_doc_folder_id
                            )""", d)
                moto_id = cur.lastrowid
        execute("DELETE FROM moto_custos WHERE moto_id=?", (moto_id,))
        for desc, val in zip(request.form.getlist("custo_desc"),
                             request.form.getlist("custo_valor")):
            if val:
                val_f = to_float(val)
                if val_f is not None:
                    execute("INSERT INTO moto_custos(moto_id,descricao,valor) VALUES(?,?,?)",
                            (moto_id, desc, val_f))
        return redirect(url_for("estoque.estoque"))
    return render_template("estoque_form.html",
                           editar=edit, moto=moto, custos=custos, erro=None)

@bp.route("/estoque/excluir/<int:i>", methods=["POST"])
@login_required
def estoque_excluir(i):
    data = request.get_json()
    if not data or "usuario" not in data or "senha" not in data:
        return jsonify({"success": False, "error": "Credenciais são obrigatórias."}), 400
        
    u_row = query("SELECT * FROM usuarios WHERE usuario=?", (data["usuario"],), one=True)
    if u_row and check_password_hash(u_row["senha_hash"], data["senha"]):
        execute("DELETE FROM motos WHERE id=?", (i,))
        return jsonify({"success": True})
    else:
        return jsonify({"success": False, "error": "Usuário ou senha incorretos."}), 403

# ==========================================
# GESTÃO DE DOCUMENTAÇÃO (GOOGLE DRIVE)
# ==========================================

@bp.route("/estoque/documentos/<int:i>")
@login_required
def estoque_documentos(i):
    moto = query("SELECT * FROM motos WHERE id=?", (i,), one=True)
    if not moto:
        flash("Veículo não encontrado.", "error")
        return redirect(url_for("estoque.estoque"))

    folder_id = moto["drive_doc_folder_id"]
    docs_data = list_moto_documents(folder_id) if folder_id else {
        "categories": {}, "geral_files": [], "total_files": 0, "drive_url": None
    }

    return render_template(
        "estoque_docs.html",
        moto=moto,
        docs=docs_data,
        categories=DOC_CATEGORIES
    )

@bp.route("/estoque/documentos/<int:i>/upload", methods=["POST"])
@login_required
def estoque_documentos_upload(i):
    moto = query("SELECT * FROM motos WHERE id=?", (i,), one=True)
    if not moto:
        flash("Veículo não encontrado.", "error")
        return redirect(url_for("estoque.estoque"))

    categoria = request.form.get("categoria")
    valid_keys = [c["key"] for c in DOC_CATEGORIES]
    if categoria not in valid_keys:
        flash("Categoria de documento inválida.", "error")
        return redirect(url_for("estoque.estoque_documentos", i=i))

    # Garante a pasta principal no Google Drive se ainda não tiver
    folder_id = moto["drive_doc_folder_id"]
    if not folder_id:
        folder_id = create_moto_drive_folder(
            moto["modelo"], moto["placa"], moto["ano"], moto["origem"]
        )
        if folder_id:
            execute("UPDATE motos SET drive_doc_folder_id=? WHERE id=?", (folder_id, i))
            moto = query("SELECT * FROM motos WHERE id=?", (i,), one=True)
        else:
            flash("Falha ao inicializar pasta no Google Drive.", "error")
            return redirect(url_for("estoque.estoque_documentos", i=i))

    # Garante as subpastas e obtém o ID da subpasta alvo
    subfolders = ensure_moto_doc_subfolders(folder_id)
    target_info = subfolders.get(categoria)
    if not target_info or not target_info.get("id"):
        flash("Subpasta da categoria não encontrada no Drive.", "error")
        return redirect(url_for("estoque.estoque_documentos", i=i))

    target_subfolder_id = target_info["id"]

    uploaded_files = request.files.getlist("files")
    if not uploaded_files or (len(uploaded_files) == 1 and not uploaded_files[0].filename):
        flash("Nenhum arquivo selecionado para upload.", "warning")
        return redirect(url_for("estoque.estoque_documentos", i=i))

    success_count = 0
    errors = []

    for f in uploaded_files:
        if not f.filename:
            continue

        ext = os.path.splitext(f.filename)[1].lower()
        if ext not in ALLOWED_DOC_EXTENSIONS:
            errors.append(f"{f.filename}: formato '{ext}' não permitido. Use PDF ou imagem (JPG, PNG, WEBP).")
            continue

        # Lê 100% em memória - ZERO bytes gravados no disco da VPS
        file_bytes = f.read()
        if not file_bytes:
            continue
        
        ok, err = upload_moto_document(file_bytes, f.filename, target_subfolder_id, folder_id)
        if ok:
            success_count += 1
        else:
            errors.append(f"{f.filename}: {err}")

    if success_count > 0:
        flash(f"{success_count} arquivo(s) enviado(s) para o Google Drive com sucesso!", "success")
    if errors:
        flash(f"Alguns erros ocorreram: {'; '.join(errors)}", "error")

    return redirect(url_for("estoque.estoque_documentos", i=i))

@bp.route("/estoque/documentos/<int:i>/criar-pasta", methods=["POST"])
@login_required
def estoque_documentos_criar_pasta(i):
    moto = query("SELECT * FROM motos WHERE id=?", (i,), one=True)
    if not moto:
        flash("Veículo não encontrado.", "error")
        return redirect(url_for("estoque.estoque"))

    folder_id = create_moto_drive_folder(
        moto["modelo"], moto["placa"], moto["ano"], moto["origem"]
    )
    if folder_id:
        execute("UPDATE motos SET drive_doc_folder_id=? WHERE id=?", (folder_id, i))
        flash("Estrutura completa de documentação criada no Google Drive com sucesso!", "success")
    else:
        flash("Erro ao criar pastas no Google Drive.", "error")

    return redirect(url_for("estoque.estoque_documentos", i=i))

@bp.route("/estoque/documentos/<int:i>/vincular", methods=["POST"])
@login_required
def estoque_documentos_vincular(i):
    moto = query("SELECT * FROM motos WHERE id=?", (i,), one=True)
    if not moto:
        flash("Veículo não encontrado.", "error")
        return redirect(url_for("estoque.estoque"))

    url_or_id = request.form.get("drive_folder_input", "").strip()
    fid = get_gdrive_folder_id(url_or_id)
    if not fid:
        flash("Link ou ID de pasta do Google Drive inválido.", "error")
        return redirect(url_for("estoque.estoque_documentos", i=i))

    execute("UPDATE motos SET drive_doc_folder_id=? WHERE id=?", (fid, i))
    # Garante as 5 subpastas dentro da pasta vinculada
    ensure_moto_doc_subfolders(fid)
    flash("Pasta do Google Drive vinculada com sucesso!", "success")
    return redirect(url_for("estoque.estoque_documentos", i=i))

@bp.route("/estoque/documentos/<int:i>/excluir/<file_id>", methods=["POST"])
@login_required
def estoque_documentos_excluir(i, file_id):
    if not is_valid_gdrive_id(file_id):
        flash("Identificador de arquivo inválido.", "error")
        return redirect(url_for("estoque.estoque_documentos", i=i))

    moto = query("SELECT * FROM motos WHERE id=?", (i,), one=True)
    if not moto:
        flash("Veículo não encontrado.", "error")
        return redirect(url_for("estoque.estoque"))

    ok, err = delete_moto_document(file_id, moto["drive_doc_folder_id"])
    if ok:
        flash("Documento excluído do Google Drive com sucesso!", "success")
    else:
        flash(f"Erro ao excluir documento: {err}", "error")

    return redirect(url_for("estoque.estoque_documentos", i=i))

@bp.route("/estoque/documentos/download/<file_id>")
@login_required
def estoque_documentos_download(file_id):
    """
    Faz o streaming direto do arquivo original do Google Drive para o usuário
    sem salvar nenhum byte temporário no disco da VPS.
    """
    if not is_valid_gdrive_id(file_id):
        flash("Identificador de arquivo inválido.", "error")
        return redirect(request.referrer or url_for("estoque.estoque"))

    stream_iter, content_type = stream_gdrive_file(file_id)
    if not stream_iter:
        flash("Não foi possível transferir o arquivo do Google Drive.", "error")
        return redirect(request.referrer or url_for("estoque.estoque"))

    filename = request.args.get("name", "documento")
    safe_name = sanitize_filename_header(filename)

    return Response(
        stream_iter,
        content_type=content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}"'
        }
    )
