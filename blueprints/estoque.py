from flask import Blueprint, render_template, request, redirect, url_for, jsonify
from flask_login import login_required, current_user
from werkzeug.security import check_password_hash
import sqlite3
from database import query, execute, DB
from utils import to_float

bp = Blueprint('estoque', __name__)

@bp.route("/estoque")
@login_required
def estoque():
    page = request.args.get('page', 1, type=int)
    per_page = 20
    offset = (page - 1) * per_page

    total_count = query("SELECT COUNT(*) as total FROM motos WHERE vendido=0", one=True)["total"]
    total_pages = (total_count + per_page - 1) // per_page

    motos = query("""
        SELECT m.*, 
               (m.preco_aquisicao + IFNULL(SUM(mc.valor), 0)) as custo_total
        FROM motos m
        LEFT JOIN moto_custos mc ON mc.moto_id = m.id
        WHERE m.vendido=0
        GROUP BY m.id
        ORDER BY m.id DESC
        LIMIT ? OFFSET ?
    """, (per_page, offset))
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
                           total_pages=total_pages)

@bp.route("/estoque/origem/<origem>")
def estoque_por_origem(origem):
    origem_map = {"consignadas":"Consignada","proprias":"Propria","fornecedor":"Fornecedor"}
    o = origem_map.get(origem.lower())
    page = request.args.get('page', 1, type=int)
    per_page = 20
    offset = (page - 1) * per_page

    total_count = query("SELECT COUNT(*) as total FROM motos WHERE vendido=0 AND origem=?", (o,), one=True)["total"]
    total_pages = (total_count + per_page - 1) // per_page

    motos = query("""
        SELECT m.*, 
               (m.preco_aquisicao + IFNULL(SUM(mc.valor), 0)) as custo_total
        FROM motos m
        LEFT JOIN moto_custos mc ON mc.moto_id = m.id
        WHERE m.vendido=0 AND m.origem=?
        GROUP BY m.id
        ORDER BY m.id DESC
        LIMIT ? OFFSET ?
    """, (o, per_page, offset))
    return render_template("estoque.html", motos=motos, total=total_count, 
                           consignada=0, propria=0, fornecedor=0,
                           page=page, total_pages=total_pages, origem_slug=origem)

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
            with sqlite3.connect(DB) as c:
                cur = c.execute("""INSERT INTO motos(
                              modelo,chassi,placa,cor,ano,origem,
                              preco_aquisicao,preco_venda,km,fotos_url,descricao
                            ) VALUES (
                              :modelo,:chassi,:placa,:cor,:ano,:origem,
                              :preco_aquisicao,:preco_venda,:km,:fotos_url,:descricao
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
