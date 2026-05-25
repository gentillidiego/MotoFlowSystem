from jinja2 import Template

template_str = """
{% set steps = ['Indicação Realizada', 'Assinatura Comprador', 'Assinatura Vendedor', 'ATPV-e Emitido', 'Taxas e
Vistoria', 'Concluída'] %}
Steps: {{ steps }}
Item 4: '{{ steps[4] }}'
"""

t = Template(template_str)
print(t.render())
