from flask import Blueprint, render_template, request, redirect, url_for, jsonify
from flask_login import login_required
from datetime import datetime
import calendar
from database import query, execute
from utils import custo_total_venda, to_float

bp = Blueprint('financeiro', __name__)

def financeiro_periodos():
    anos_v = [int(r[0]) for r in query(
        "SELECT DISTINCT strftime('%Y',data_venda) FROM vendas")]
    anos_c = [r["ano"] for r in query(
        "SELECT DISTINCT ano FROM financeiro_custos")]
    return sorted(set(anos_v + anos_c), reverse=True) or [datetime.now().year]

@bp.route("/financeiro")
@login_required
def financeiro():
    hoje = datetime.now()
    return render_template("financeiro.html",
                           anos=financeiro_periodos(),
                           ano_atual=hoje.year,
                           mes_atual=hoje.month)

@bp.route("/financeiro/<int:ano>/<int:mes>")
@login_required
def financeiro_dados(ano, mes):
    ini = f"{ano}-{mes:02d}-01"
    ultimo_dia = calendar.monthrange(ano, mes)[1]
    fim = f"{ano}-{mes:02d}-{ultimo_dia:02d}"
    vendas = query("""
        SELECT v.id, v.nome, v.data_venda, v.produto_id,
               m.modelo, m.preco_venda, m.preco_aquisicao
        FROM vendas v
        JOIN motos m ON m.id=v.produto_id
        WHERE v.data_venda BETWEEN ? AND ?
    """, (ini, fim))

    total_vendas = sum(v["preco_venda"] for v in vendas)
    custo_total  = sum(custo_total_venda(v) for v in vendas)
    lucro_bruto  = total_vendas - custo_total

    custos_mens  = sum(r["valor"] for r in query(
        "SELECT valor FROM financeiro_custos WHERE ano=? AND mes=?", (ano, mes)))
    comissao = 0
    for v in vendas:
        lucro = (v["preco_venda"] - custo_total_venda(v))
        comissao += max(0.10 * lucro, 100.0)

    lucro_liq    = lucro_bruto - comissao - custos_mens

    detalhes = []
    custos_map = {}
    for v in vendas:
        ct = custo_total_venda(v)
        detalhes.append({**dict(v), "custo_total": ct})
        custos_map[v["id"]] = [dict(r) for r in query(
            "SELECT descricao,valor FROM venda_custos WHERE venda_id=?", (v["id"],))]

    return jsonify({
        "total_vendas":    total_vendas,
        "custo_total":     custo_total,
        "lucro_bruto":     lucro_bruto,
        "custos_mensais":  custos_mens,
        "comissao":        comissao,
        "lucro_liquido":   lucro_liq,
        "detalhes_vendas": detalhes,
        "custos_venda":    custos_map
    })

@bp.route("/financeiro/custos/<int:ano>/<int:mes>")
@login_required
def financeiro_custos_page(ano, mes):
    custos = query(
        "SELECT * FROM financeiro_custos WHERE ano=? AND mes=?", (ano, mes))
    return render_template("financeiro_custos.html",
                           ano=ano, mes=mes, custos=custos)

@bp.route("/financeiro/custos", methods=["POST"])
@login_required
def financeiro_gravar_custos():
    ano, mes = int(request.form["ano"]), int(request.form["mes"])
    execute("DELETE FROM financeiro_custos WHERE ano=? AND mes=?", (ano, mes))
    for desc, val in zip(request.form.getlist("custo_desc"),
                         request.form.getlist("custo_valor")):
        if val:
            val_f = to_float(val)
            if val_f is not None:
                execute("""INSERT INTO financeiro_custos
                           (ano,mes,descricao,valor) VALUES(?,?,?,?)""",
                        (ano, mes, desc, val_f))
    return redirect(url_for("financeiro.financeiro"))
