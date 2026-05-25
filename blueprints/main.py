from flask import Blueprint, render_template
from flask_login import login_required
from datetime import datetime
from database import query

bp = Blueprint('main', __name__)

@bp.route("/")
@login_required
def index():
    # Estatísticas para o Dashboard
    total_motos = query("SELECT COUNT(*) FROM motos WHERE vendido=0", one=True)[0]
    
    # Vendas deste mês
    hoje = datetime.now()
    ini = f"{hoje.year}-{hoje.month:02d}-01"
    fim = f"{hoje.year}-{hoje.month:02d}-31"
    vendas_mes = query("SELECT COUNT(*) FROM vendas WHERE data_venda BETWEEN ? AND ?", (ini, fim), one=True)[0]
    
    # Transferências Pendentes (não 'Concluída')
    transf_pend = query("SELECT COUNT(*) FROM transferencias WHERE status != 'Concluída'", one=True)[0]
    
    # Alertas: Transferências sem atualização há 48h (e não concluídas)
    # SQLite 'datetime(..., "-2 days")'
    alertas = query("""
        SELECT t.*, m.modelo, m.placa, v.nome as cliente
        FROM transferencias t
        JOIN vendas v ON v.id=t.venda_id
        JOIN motos m ON m.id=v.produto_id
        WHERE t.status != 'Concluída' 
        AND t.data_atualizacao < datetime('now', '-2 days')
    """)
    
    return render_template("index.html", 
                           total_motos=total_motos,
                           vendas_mes=vendas_mes,
                           transf_pend=transf_pend,
                           alertas=alertas)

