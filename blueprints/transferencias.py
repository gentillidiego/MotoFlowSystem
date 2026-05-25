from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import login_required
from datetime import datetime
from database import query, execute

bp = Blueprint('transferencias', __name__)

@bp.route("/transferencias")
@login_required
def transferencias_lista():
    page = request.args.get('page', 1, type=int)
    per_page = 20
    offset = (page - 1) * per_page

    total_count = query("SELECT COUNT(*) as total FROM transferencias", one=True)["total"]
    total_pages = (total_count + per_page - 1) // per_page

    # Lista todas as transferências com dados da venda e da moto
    rows = query("""
        SELECT t.*, v.nome as cliente, m.modelo, m.placa, m.chassi, v.data_venda
        FROM transferencias t
        JOIN vendas v ON v.id = t.venda_id
        JOIN motos m ON m.id = v.produto_id
        ORDER BY t.data_atualizacao DESC
        LIMIT ? OFFSET ?
    """, (per_page, offset))
    
    # Processar dias
    transferencias = []
    hoje = datetime.now().date()
    for r in rows:
        # Converter sqlite3.Row para dict para poder adicionar campos
        item = dict(r)
        if item["data_venda"]:
            dv = datetime.strptime(item["data_venda"], "%Y-%m-%d").date()
            item["dias"] = (hoje - dv).days
        else:
            item["dias"] = 0
        transferencias.append(item)
        
    return render_template("transferencias.html", transferencias=transferencias,
                           page=page, total_pages=total_pages, total=total_count)

@bp.route("/transferencias/<int:tid>")
@login_required
def transferencias_detalhes(tid):
    t = query("""
        SELECT t.*, v.nome as cliente, m.modelo, m.placa, m.chassi, v.data_venda
        FROM transferencias t
        JOIN vendas v ON v.id = t.venda_id
        JOIN motos m ON m.id = v.produto_id
        WHERE t.id=?
    """, (tid,), one=True)
    if not t:
        return redirect(url_for("transferencias.transferencias_lista"))
        
    return render_template("transferencias_detalhes.html", t=t)

@bp.route("/transferencias/nova/<int:venda_id>", methods=["GET", "POST"])
@login_required
def transferencias_nova(venda_id):
    # Verifica se já existe
    existe = query("SELECT id FROM transferencias WHERE venda_id=?", (venda_id,), one=True)
    if existe:
        return redirect(url_for("transferencias.transferencias_lista")) # Or details?

    venda = query("SELECT v.*, m.modelo FROM vendas v LEFT JOIN motos m ON m.id=v.produto_id WHERE v.id=?", (venda_id,), one=True)
    if not venda:
        return redirect(url_for("vendas.vendas_home"))
    
    if request.method == "POST":
        resp = request.form.get("responsavel")
        obs = request.form.get("observacoes")
        status_inicial = "Indicação Realizada"
        
        execute("""
            INSERT INTO transferencias (venda_id, responsavel, status, observacoes)
            VALUES (?, ?, ?, ?)
        """, (venda_id, resp, status_inicial, obs))
        return redirect(url_for("transferencias.transferencias_lista"))
    
    return render_template("transferencias_nova.html", venda=venda, venda_id=venda_id)

@bp.route("/transferencias/editar/<int:tid>", methods=["POST"])
@login_required
def transferencias_editar(tid):
    # Atualizar status
    novo_status = request.form.get("status")
    obs = request.form.get("observacoes")
    
    # Se houver mudança de status ou observação
    if novo_status:
        execute("UPDATE transferencias SET status=?, observacoes=?, data_atualizacao=CURRENT_TIMESTAMP WHERE id=?", (novo_status, obs, tid))
    else:
        execute("UPDATE transferencias SET observacoes=?, data_atualizacao=CURRENT_TIMESTAMP WHERE id=?", (obs, tid))
        
    return redirect(url_for("transferencias.transferencias_lista"))

@bp.route("/transferencias/excluir/<int:tid>", methods=["POST"])
@login_required
def transferencias_excluir(tid):
    execute("DELETE FROM transferencias WHERE id=?", (tid,))
    return redirect(url_for("transferencias.transferencias_lista"))
