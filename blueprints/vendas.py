from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, Response
from flask_login import login_required, current_user
from datetime import datetime
from werkzeug.security import check_password_hash
import os
import sqlite3
from database import query, execute, DB
from utils import (
    motos_dropdown, DOC_CATEGORIES, get_gdrive_folder_id,
    ensure_moto_doc_subfolders, list_moto_documents,
    upload_moto_document, delete_moto_document,
    stream_gdrive_file, create_venda_drive_folder,
    ALLOWED_DOC_EXTENSIONS, is_valid_gdrive_id, sanitize_filename_header
)

bp = Blueprint('vendas', __name__)

# ... (rest of the file remains same, skipping lines for brevity)


# ──────────── LEADS ────────────
@bp.route("/vendas/leads")
@login_required
def leads():
    page = request.args.get('page', 1, type=int)
    q = request.args.get('q', '').strip()
    per_page = 20
    offset = (page - 1) * per_page

    where = ""
    params = []
    if q:
        where = "WHERE l.nome LIKE ?"
        params.append(f"%{q}%")

    total_count = query(f"SELECT COUNT(*) as total FROM leads l {where}", params, one=True)["total"]
    total_pages = (total_count + per_page - 1) // per_page

    rows = query(f"""
        SELECT l.id,l.created_at,l.nome,l.telefone,l.cpf,l.data_nasc,
                l.temperatura,m.modelo
        FROM leads l
        LEFT JOIN motos m ON m.id=l.produto_id
        {where}
        ORDER BY l.created_at DESC
        LIMIT ? OFFSET ?
    """, params + [per_page, offset])
    leads = []
    for r in rows:
        item = dict(r)
        if item["data_nasc"]:
            try:
                item["data_nasc"] = datetime.strptime(item["data_nasc"], "%Y-%m-%d").strftime("%d/%m/%Y")
            except ValueError:
                pass
        leads.append(item)
    return render_template("leads.html", leads=leads,
                           page=page, total_pages=total_pages, total=total_count, q=q)

@bp.route("/vendas/leads/novo", methods=["GET","POST"])
@bp.route("/vendas/leads/editar/<int:i>", methods=["GET","POST"])
@login_required
def leads_form(i=None):
    edit = i is not None
    lead = query("SELECT * FROM leads WHERE id=?", (i,), one=True) if edit else {}
    motos_dd = motos_dropdown()
    if request.method == "POST":
        d = {k: request.form.get(k) or None for k in (
            "nome","telefone","cpf","data_nasc","produto_id",
            "temperatura","observacoes")}
        if not d["nome"]:
            flash("Nome é obrigatório.", "error")
            return render_template("leads_form.html", edit=edit, lead=d,
                                   motos=motos_dd)
        if edit:
            execute("""UPDATE leads SET
                         nome=:nome,telefone=:telefone,cpf=:cpf,data_nasc=:data_nasc,
                         produto_id=:produto_id,temperatura=:temperatura,
                         observacoes=:observacoes
                       WHERE id=:id""", {**d, "id": i})
        else:
            with sqlite3.connect(DB) as c:
                c.execute("""INSERT INTO leads(
                              nome,telefone,cpf,data_nasc,produto_id,
                              temperatura,observacoes
                            ) VALUES (
                              :nome,:telefone,:cpf,:data_nasc,:produto_id,
                              :temperatura,:observacoes
                            )""", d)
        flash("Lead salvo com sucesso!", "success")
        return redirect(url_for("vendas.leads"))
    return render_template("leads_form.html", edit=edit, lead=lead,
                           motos=motos_dd, erro=None)

@bp.route("/vendas/leads/excluir/<int:i>", methods=["POST"])
@login_required
def leads_excluir(i):
    execute("DELETE FROM leads WHERE id=?", (i,))
    return redirect(url_for("vendas.leads"))

# ──────────── VENDAS ────────────
@bp.route("/vendas")
@login_required
def vendas_home():
    page = request.args.get('page', 1, type=int)
    q = request.args.get('q', '').strip()
    per_page = 20
    offset = (page - 1) * per_page

    where = ""
    params = []
    if q:
        where = "WHERE (v.nome LIKE ? OR v.cpf LIKE ? OR m.modelo LIKE ? OR m.placa LIKE ?)"
        like = f"%{q}%"
        params += [like, like, like, like]

    total_count = query(f"""
        SELECT COUNT(*) as total
        FROM vendas v
        LEFT JOIN motos m ON m.id=v.produto_id
        {where}
    """, params, one=True)["total"]
    total_pages = (total_count + per_page - 1) // per_page

    lista = query(f"""
        SELECT v.id,v.data_venda,v.nome,m.modelo,v.cidade,v.telefone,
               v.drive_doc_folder_id, m.drive_doc_folder_id as moto_folder_id
        FROM vendas v
        LEFT JOIN motos m ON m.id=v.produto_id
        {where}
        ORDER BY v.data_venda DESC
        LIMIT ? OFFSET ?
    """, params + [per_page, offset])
    return render_template("vendas.html", vendas=lista,
                           page=page, total_pages=total_pages, total=total_count, q=q)

@bp.route("/vendas/novo", methods=["GET","POST"])
@login_required
def vendas_novo():
    if request.method == "POST":
        return _salvar_venda(False)
    return render_template("vendas_form.html",
                           edit=False, venda=None,
                           lead=None, motos=motos_dropdown(), cv=[])

@bp.route("/vendas/editar/<int:vid>", methods=["GET","POST"])
@login_required
def vendas_editar(vid):
    venda = query("SELECT * FROM vendas WHERE id=?", (vid,), one=True)
    if not venda:
        return redirect(url_for("vendas.vendas_home"))
    if request.method == "POST":
        return _salvar_venda(True, venda_id=vid, venda_original=venda)
    custos_v = query("SELECT * FROM venda_custos WHERE venda_id=?", (vid,))
    return render_template("vendas_form.html",
                           edit=True, venda=venda,
                           lead=None, motos=motos_dropdown(), cv=custos_v)

@bp.route("/vendas/leads/gerar_venda/<int:lid>", methods=["GET","POST"])
@login_required
def gerar_venda(lid):
    lead = query("SELECT * FROM leads WHERE id=?", (lid,), one=True)
    if request.method == "POST":
        return _salvar_venda(False, lead_id=lid)
    return render_template("vendas_form.html",
                           edit=False, venda=None,
                           lead=lead, motos=motos_dropdown(), cv=[])

def _salvar_venda(editar, venda_id=None, lead_id=None, venda_original=None):
    campos = ("nome","telefone","cpf","data_nasc","endereco","bairro","cidade",
              "cep","email","produto_id","condicao_pagamento")
    d = {k: request.form.get(k) or None for k in campos}
    d["lead_id"]    = lead_id
    d["data_venda"] = datetime.now().strftime("%Y-%m-%d")

    if editar:
        d["id"] = venda_id
        execute("""UPDATE vendas SET
                     nome=:nome,telefone=:telefone,cpf=:cpf,data_nasc=:data_nasc,
                     endereco=:endereco,bairro=:bairro,cidade=:cidade,
                     cep=:cep,email=:email,produto_id=:produto_id,
                     condicao_pagamento=:condicao_pagamento
                   WHERE id=:id""", d)
        if venda_original and venda_original["produto_id"] != int(d["produto_id"]):
            execute("UPDATE motos SET vendido=0 WHERE id=?",
                    (venda_original["produto_id"],))
    else:
        manter_catalogo = int(request.form.get("manter_catalogo", 0))
        with sqlite3.connect(DB) as c:
            cur = c.execute("""INSERT INTO vendas(
                          nome,telefone,cpf,data_nasc,endereco,bairro,cidade,cep,
                          email,produto_id,data_venda,lead_id,condicao_pagamento
                        ) VALUES (
                          :nome,:telefone,:cpf,:data_nasc,:endereco,
                          :bairro,:cidade,:cep,:email,:produto_id,
                          :data_venda,:lead_id,:condicao_pagamento
                        )""", d)
            venda_id = cur.lastrowid
            c.execute("UPDATE motos SET vendido=1, manter_catalogo=? WHERE id=?", (manter_catalogo, d["produto_id"]))
            if d["produto_id"]:
                moto_folder = query("SELECT drive_doc_folder_id FROM motos WHERE id=?", (d["produto_id"],), one=True)
                if moto_folder and moto_folder["drive_doc_folder_id"]:
                    c.execute("UPDATE vendas SET drive_doc_folder_id=? WHERE id=?", (moto_folder["drive_doc_folder_id"], venda_id))

    execute("DELETE FROM venda_custos WHERE venda_id=?", (venda_id,))
    for desc, val in zip(request.form.getlist("cv_desc"),
                         request.form.getlist("cv_valor")):
        if val:
            execute("INSERT INTO venda_custos(venda_id,descricao,valor) VALUES(?,?,?)",
                    (venda_id, desc, float(val)))
    flash("Venda salva com sucesso!", "success")
    return redirect(url_for("vendas.vendas_home"))

@bp.route("/vendas/excluir/<int:vid>", methods=["POST"])
@login_required 
def vendas_excluir(vid):
    data = request.get_json()
    if not data or "usuario" not in data or "senha" not in data:
        return jsonify({"success": False, "error": "Credenciais são obrigatórias."}), 400
        
    u_row = query("SELECT * FROM usuarios WHERE usuario=?", (data["usuario"],), one=True)
    if u_row and check_password_hash(u_row["senha_hash"], data["senha"]):
        v = query("SELECT * FROM vendas WHERE id=?", (vid,), one=True)
        if v:
            execute("UPDATE motos SET vendido=0 WHERE id=?", (v["produto_id"],))
            execute("DELETE FROM vendas WHERE id=?", (vid,))
            return jsonify({"success": True})
        return jsonify({"success": False, "error": "Venda não encontrada."}), 404
    else:
        return jsonify({"success": False, "error": "Usuário ou senha incorretos."}), 403

# ──────────── CUSTOS POR VENDA ────────────
@bp.route("/vendas/<int:vid>/custos", methods=["GET","POST"])
@login_required
def venda_custos(vid):
    venda = query("SELECT * FROM vendas WHERE id=?", (vid,), one=True)
    if not venda:
        return redirect(url_for("vendas.vendas_home"))
    if request.method == "POST":
        desc = request.form.get("descricao")
        val  = request.form.get("valor")
        if desc and val:
            execute("INSERT INTO venda_custos(venda_id,descricao,valor) VALUES(?,?,?)",
                    (vid, desc, float(val)))
        return redirect(url_for("vendas.venda_custos", vid=vid))
    custos = query("SELECT * FROM venda_custos WHERE venda_id=?", (vid,))
    
    # Busca custos de estoque da moto
    moto = None
    custos_origem = []
    if venda["produto_id"]:
        moto = query("SELECT * FROM motos WHERE id=?", (venda["produto_id"],), one=True)
        if moto:
            custos_origem = query("SELECT * FROM moto_custos WHERE moto_id=?", (moto["id"],))

    return render_template("venda_custos.html", venda=venda, custos=custos, moto=moto, custos_origem=custos_origem)

@bp.route("/vendas/<int:vid>/custos/excluir/<int:cid>", methods=["POST"])
@login_required
def venda_custos_excluir(vid, cid):
    execute("DELETE FROM venda_custos WHERE id=?", (cid,))
    return redirect(url_for("vendas.venda_custos", vid=vid))

# ──────────── DOCUMENTOS ────────────
@bp.route("/vendas/<int:i>/proposta")
@login_required
def venda_proposta(i):
    v = query("SELECT * FROM vendas WHERE id=?", (i,), one=True)
    m = query("SELECT * FROM motos WHERE id=?", (v["produto_id"],), one=True)
    return render_template("proposta.html", v=v, m=m)

@bp.route("/vendas/<int:i>/termo")
@login_required
def venda_termo(i):
    v = query("SELECT * FROM vendas WHERE id=?", (i,), one=True)
    m = query("SELECT * FROM motos WHERE id=?", (v["produto_id"],), one=True)
    return render_template("termo.html", v=v, m=m)

# ==========================================
# GESTÃO DE DOCUMENTAÇÃO DE VENDAS (GOOGLE DRIVE)
# ==========================================

@bp.route("/vendas/documentos/<int:vid>")
@login_required
def vendas_documentos(vid):
    venda = query("SELECT * FROM vendas WHERE id=?", (vid,), one=True)
    if not venda:
        flash("Venda não encontrada.", "error")
        return redirect(url_for("vendas.vendas_home"))

    moto = None
    if venda["produto_id"]:
        moto = query("SELECT * FROM motos WHERE id=?", (venda["produto_id"],), one=True)

    folder_id = venda["drive_doc_folder_id"] or (moto["drive_doc_folder_id"] if moto else None)
    docs_data = list_moto_documents(folder_id) if folder_id else {
        "categories": {}, "geral_files": [], "total_files": 0, "drive_url": None
    }

    return render_template(
        "vendas_docs.html",
        venda=venda,
        moto=moto,
        docs=docs_data,
        categories=DOC_CATEGORIES,
        folder_id=folder_id
    )

@bp.route("/vendas/documentos/<int:vid>/upload", methods=["POST"])
@login_required
def vendas_documentos_upload(vid):
    venda = query("SELECT * FROM vendas WHERE id=?", (vid,), one=True)
    if not venda:
        flash("Venda não encontrada.", "error")
        return redirect(url_for("vendas.vendas_home"))

    moto = query("SELECT * FROM motos WHERE id=?", (venda["produto_id"],), one=True) if venda["produto_id"] else None

    categoria = request.form.get("categoria")
    valid_keys = [c["key"] for c in DOC_CATEGORIES]
    if categoria not in valid_keys:
        flash("Categoria de documento inválida.", "error")
        return redirect(url_for("vendas.vendas_documentos", vid=vid))

    folder_id = venda["drive_doc_folder_id"] or (moto["drive_doc_folder_id"] if moto else None)
    if not folder_id:
        folder_id = create_venda_drive_folder(venda, moto)
        if folder_id:
            execute("UPDATE vendas SET drive_doc_folder_id=? WHERE id=?", (folder_id, vid))
            if moto and not moto["drive_doc_folder_id"]:
                execute("UPDATE motos SET drive_doc_folder_id=? WHERE id=?", (folder_id, moto["id"]))
            venda = query("SELECT * FROM vendas WHERE id=?", (vid,), one=True)
        else:
            flash("Falha ao inicializar pasta da venda no Google Drive.", "error")
            return redirect(url_for("vendas.vendas_documentos", vid=vid))

    subfolders = ensure_moto_doc_subfolders(folder_id)
    target_info = subfolders.get(categoria)
    if not target_info or not target_info.get("id"):
        flash("Subpasta da categoria não encontrada no Drive.", "error")
        return redirect(url_for("vendas.vendas_documentos", vid=vid))

    target_subfolder_id = target_info["id"]

    uploaded_files = request.files.getlist("files")
    if not uploaded_files or (len(uploaded_files) == 1 and not uploaded_files[0].filename):
        flash("Nenhum arquivo selecionado para upload.", "warning")
        return redirect(url_for("vendas.vendas_documentos", vid=vid))

    success_count = 0
    errors = []

    for f in uploaded_files:
        if not f.filename:
            continue

        ext = os.path.splitext(f.filename)[1].lower()
        if ext not in ALLOWED_DOC_EXTENSIONS:
            errors.append(f"{f.filename}: formato '{ext}' não permitido. Use PDF ou imagem (JPG, PNG, WEBP).")
            continue

        # ZERO bytes no disco da VPS: leitura e streaming 100% em memória
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

    return redirect(url_for("vendas.vendas_documentos", vid=vid))

@bp.route("/vendas/documentos/<int:vid>/criar-pasta", methods=["POST"])
@login_required
def vendas_documentos_criar_pasta(vid):
    venda = query("SELECT * FROM vendas WHERE id=?", (vid,), one=True)
    if not venda:
        flash("Venda não encontrada.", "error")
        return redirect(url_for("vendas.vendas_home"))

    moto = query("SELECT * FROM motos WHERE id=?", (venda["produto_id"],), one=True) if venda["produto_id"] else None

    folder_id = create_venda_drive_folder(venda, moto)
    if folder_id:
        execute("UPDATE vendas SET drive_doc_folder_id=? WHERE id=?", (folder_id, vid))
        if moto and not moto["drive_doc_folder_id"]:
            execute("UPDATE motos SET drive_doc_folder_id=? WHERE id=?", (folder_id, moto["id"]))
        flash("Estrutura completa de documentação criada no Google Drive com sucesso!", "success")
    else:
        flash("Erro ao criar pastas no Google Drive.", "error")

    return redirect(url_for("vendas.vendas_documentos", vid=vid))

@bp.route("/vendas/documentos/<int:vid>/vincular", methods=["POST"])
@login_required
def vendas_documentos_vincular(vid):
    venda = query("SELECT * FROM vendas WHERE id=?", (vid,), one=True)
    if not venda:
        flash("Venda não encontrada.", "error")
        return redirect(url_for("vendas.vendas_home"))

    url_or_id = request.form.get("drive_folder_input", "").strip()
    fid = get_gdrive_folder_id(url_or_id)
    if not fid:
        flash("Link ou ID de pasta do Google Drive inválido.", "error")
        return redirect(url_for("vendas.vendas_documentos", vid=vid))

    execute("UPDATE vendas SET drive_doc_folder_id=? WHERE id=?", (fid, vid))
    if venda["produto_id"]:
        moto = query("SELECT * FROM motos WHERE id=?", (venda["produto_id"],), one=True)
        if moto and not moto["drive_doc_folder_id"]:
            execute("UPDATE motos SET drive_doc_folder_id=? WHERE id=?", (fid, moto["id"]))

    ensure_moto_doc_subfolders(fid)
    flash("Pasta do Google Drive vinculada com sucesso à venda!", "success")
    return redirect(url_for("vendas.vendas_documentos", vid=vid))

@bp.route("/vendas/documentos/<int:vid>/excluir/<file_id>", methods=["POST"])
@login_required
def vendas_documentos_excluir(vid, file_id):
    if not is_valid_gdrive_id(file_id):
        flash("Identificador de arquivo inválido.", "error")
        return redirect(url_for("vendas.vendas_documentos", vid=vid))

    venda = query("SELECT * FROM vendas WHERE id=?", (vid,), one=True)
    if not venda:
        flash("Venda não encontrada.", "error")
        return redirect(url_for("vendas.vendas_home"))

    moto = query("SELECT * FROM motos WHERE id=?", (venda["produto_id"],), one=True) if venda["produto_id"] else None
    folder_id = venda["drive_doc_folder_id"] or (moto["drive_doc_folder_id"] if moto else None)

    ok, err = delete_moto_document(file_id, folder_id)
    if ok:
        flash("Documento excluído do Google Drive com sucesso!", "success")
    else:
        flash(f"Erro ao excluir documento: {err}", "error")

    return redirect(url_for("vendas.vendas_documentos", vid=vid))

@bp.route("/vendas/documentos/download/<file_id>")
@login_required
def vendas_documentos_download(file_id):
    """
    Faz o streaming direto do arquivo original do Google Drive para o usuário
    sem salvar nenhum byte temporário no disco da VPS.
    """
    if not is_valid_gdrive_id(file_id):
        flash("Identificador de arquivo inválido.", "error")
        return redirect(request.referrer or url_for("vendas.vendas_home"))

    stream_iter, content_type = stream_gdrive_file(file_id)
    if not stream_iter:
        flash("Não foi possível transferir o arquivo do Google Drive.", "error")
        return redirect(request.referrer or url_for("vendas.vendas_home"))

    filename = request.args.get("name", "documento")
    safe_name = sanitize_filename_header(filename)

    return Response(
        stream_iter,
        content_type=content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}"'
        }
    )

