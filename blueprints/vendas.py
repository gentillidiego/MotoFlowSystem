from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime
from werkzeug.security import check_password_hash
import sqlite3
from database import query, execute, DB
from utils import motos_dropdown

bp = Blueprint('vendas', __name__)

# ... (rest of the file remains same, skipping lines for brevity)


# ──────────── LEADS ────────────
@bp.route("/vendas/leads")
@login_required
def leads():
    page = request.args.get('page', 1, type=int)
    per_page = 20
    offset = (page - 1) * per_page

    total_count = query("SELECT COUNT(*) as total FROM leads", one=True)["total"]
    total_pages = (total_count + per_page - 1) // per_page

    rows = query("""
        SELECT l.id,l.created_at,l.nome,l.telefone,l.cpf,l.data_nasc,
                l.temperatura,m.modelo
        FROM leads l
        LEFT JOIN motos m ON m.id=l.produto_id
        ORDER BY l.created_at DESC
        LIMIT ? OFFSET ?
    """, (per_page, offset))
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
                           page=page, total_pages=total_pages, total=total_count)

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
    per_page = 20
    offset = (page - 1) * per_page

    total_count = query("SELECT COUNT(*) as total FROM vendas", one=True)["total"]
    total_pages = (total_count + per_page - 1) // per_page

    lista = query("""
        SELECT v.id,v.data_venda,v.nome,m.modelo,v.cidade,v.telefone
        FROM vendas v
        LEFT JOIN motos m ON m.id=v.produto_id
        ORDER BY v.data_venda DESC
        LIMIT ? OFFSET ?
    """, (per_page, offset))
    return render_template("vendas.html", vendas=lista,
                           page=page, total_pages=total_pages, total=total_count)

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
