from flask import Blueprint, jsonify
from database import query

bp = Blueprint('api', __name__)

@bp.route("/estoque", methods=["GET"])
def estoque_json():
    # Consulta motos não vendidas (vendido=0)
    motos = query("""
        SELECT id, modelo, ano, cor, preco_venda, origem, km, fotos_url
        FROM motos
        WHERE vendido=0
        ORDER BY id DESC
    """)
    
    # Converte rows (sqlite3.Row) para lista de dicionários
    lista_motos = []
    for m in motos:
        lista_motos.append({
            "id": m["id"],
            "modelo": m["modelo"],
            "ano": m["ano"],
            "cor": m["cor"],
            "preco": m["preco_venda"],
            "origem": m["origem"],
            "km": m["km"],
            "fotos": m["fotos_url"]
        })
        
    return jsonify(lista_motos)
