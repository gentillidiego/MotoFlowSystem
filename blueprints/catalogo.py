from flask import Blueprint, render_template, request, redirect, url_for, Response
from database import query
from utils import get_gdrive_folder_id, list_gdrive_images
from extensions import cache

bp = Blueprint('catalogo', __name__)

@bp.route("/catalogo")
def catalogo_lista():
    filtro = request.args.get('filtro')
    
    # Apenas motos não vendidas ou que o usuário optou por manter
    base_sql = "SELECT * FROM motos WHERE (vendido=0 OR manter_catalogo=1)"
    
    if filtro == '0km':
        sql = base_sql + " AND origem = 'Fornecedor'"
    elif filtro == 'seminovas':
        sql = base_sql + " AND origem IN ('Propria', 'Consignada')"
    else:
        sql = base_sql
        
    rows = query(sql)
    motos = []
    
    for row in rows:
        moto = dict(row)
        url = moto.get('fotos_url')
        if not url:
            motos.append(moto)
            continue
            
        fid = get_gdrive_folder_id(url)
        if fid:
            # Tentar carregar a primeira foto do drive como thumbnail
            drive_photos = list_gdrive_images(fid)
            if drive_photos:
                moto['fotos_url'] = drive_photos[0]
            else:
                moto['fotos_url'] = None
        motos.append(moto)
        
    # Ordena conforme a regra:
    # 1. Qualquer moto sem foto vai para o final.
    # 2. Se tiver foto, prioriza origem 'Propria'.
    # 3. Empates ordenados por ID decrescente.
    motos.sort(key=lambda m: (
        0 if m.get('fotos_url') else 1,
        0 if m.get('origem') == 'Propria' else 1,
        -m['id']
    ))
        
    return render_template("catalogo.html", motos=motos, filtro_atual=filtro)

@bp.route("/catalogo/detalhes/<int:id>")
def catalogo_detalhes(id):
    moto_row = query("SELECT * FROM motos WHERE id=?", (id,), one=True)
    if not moto_row:
        return redirect(url_for('catalogo.catalogo_lista'))
    
    moto = dict(moto_row)
    fotos = []
    fid = get_gdrive_folder_id(moto['fotos_url'])
    
    if fid:
        fotos = list_gdrive_images(fid)
    elif moto['fotos_url']:
        # Se for uma lista separada por vírgula
        fotos = [f.strip() for f in moto['fotos_url'].split(',')]
    
    return render_template("catalogo_detalhes.html", moto=moto, fotos=fotos)

@bp.route("/catalogo/feed.xml")
def catalogo_feed():
    cache_key = f"feed_xml_{request.host}"
    cached = cache.get(cache_key)
    if cached:
        return Response(cached, mimetype='application/xml')

    sql = "SELECT * FROM motos WHERE vendido=0 OR manter_catalogo=1 ORDER BY id DESC"
    rows = query(sql)
    base_url = request.url_root.rstrip('/')

    xml = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0" xmlns:g="http://base.google.com/ns/1.0">',
        '<channel>',
        '<title>MotoFlow System - Estoque</title>',
        f'<link>{base_url}/catalogo</link>',
        '<description>Feed automático de motos em estoque da MotoFlow</description>'
    ]

    for row in rows:
        moto = dict(row)
        fid = get_gdrive_folder_id(moto.get('fotos_url'))
        main_photo = ""
        if fid:
            drive_photos = list_gdrive_images(fid)
            if drive_photos:
                main_photo = drive_photos[0]

        if not main_photo and moto.get('fotos_url'):
            main_photo = moto['fotos_url'].split(',')[0].strip()

        link = f"{base_url}/catalogo/detalhes/{moto['id']}"
        price = f"{moto['preco_venda'] or 0:.2f} BRL"
        title = str(moto['modelo']).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        desc = str(moto['descricao'] or f"{title} em excelente estado.").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        xml.append('<item>')
        xml.append(f'<g:id>moto_{moto["id"]}</g:id>')
        xml.append(f'<g:title>{title}</g:title>')
        xml.append(f'<g:description>{desc}</g:description>')
        xml.append(f'<g:link>{link}</g:link>')
        xml.append(f'<g:image_link>{main_photo}</g:image_link>')
        xml.append(f'<g:condition>used</g:condition>')
        xml.append(f'<g:price>{price}</g:price>')
        xml.append(f'<g:availability>in stock</g:availability>')
        xml.append(f'<g:brand>MotoFlow</g:brand>')
        xml.append(f'<g:google_product_category>6104</g:google_product_category>')
        xml.append(f'<g:custom_label_0>{moto.get("ano", "N/A")}</g:custom_label_0>')
        xml.append(f'<g:custom_label_1>{moto.get("cor", "N/A")}</g:custom_label_1>')
        xml.append(f'<g:custom_label_2>{moto.get("km", "0")} KM</g:custom_label_2>')
        xml.append('</item>')

    xml.append('</channel>')
    xml.append('</rss>')

    xml_str = "\n".join(xml)
    cache.set(cache_key, xml_str, timeout=3600)
    return Response(xml_str, mimetype='application/xml')
