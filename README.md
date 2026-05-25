# Moto Flow System

Sistema de gestão (ERP) completo para concessionárias de motocicletas. Gerencia o ciclo de vida inteiro: **Estoque → Leads → Vendas → Financeiro → Transferência de documentos**.

> **Para LLMs e desenvolvedores:** antes de qualquer alteração, leia também os arquivos de memória do projeto que registram decisões técnicas, histórico de melhorias e contexto atualizado:
>
> - **Índice:** `/home/diego/.claude/projects/-home-diego-projetos-MotoFlowSystem/memory/MEMORY.md`
> - **Memória principal:** `/home/diego/.claude/projects/-home-diego-projetos-MotoFlowSystem/memory/project_motoflowsystem.md`
>
> Ao finalizar uma sessão de trabalho, atualize esses arquivos com qualquer mudança relevante feita no projeto.

---

## Módulos

| Módulo | Rota base | Descrição |
|---|---|---|
| Dashboard | `/` | KPIs do mês + alertas de transferências paradas há +48h |
| Estoque | `/estoque` | CRUD de motos (Própria / Consignada / Fornecedor) com custos extras |
| Leads | `/vendas/leads` | Prospecção com temperatura (quente/morno/frio) |
| Vendas | `/vendas` | Conversão de lead em venda, custos por venda, proposta e termo |
| Financeiro | `/financeiro` | Relatório mensal de lucro bruto/líquido + custos fixos |
| Transferências | `/transferencias` | Workflow de documentação pós-venda |
| Catálogo público | `/catalogo` | Vitrine pública sem login + feed XML Google Merchant |
| API JSON | `/api/estoque` | Endpoint público com estoque disponível |

---

## Stack

- **Linguagem:** Python 3.11 (container) / 3.13 (dev local)
- **Framework:** Flask com Blueprints
- **Banco:** SQLite3 (`estoque.db` — persistido via volume Docker)
- **Servidor:** Gunicorn (3 workers)
- **Cache:** Flask-Caching `FileSystemCache` em `/tmp/motoflow_cache` — compartilhado entre workers
- **PDF:** WeasyPrint (proposta e termo de venda)
- **Fotos:** Google Drive API v3 via Service Account (thumbnails dinâmicos)
- **Segurança:** Flask-Login + Flask-WTF (CSRF) + Werkzeug PBKDF2

---

## Arquitetura de Cache

O sistema usa dois níveis de cache para minimizar chamadas à API do Google Drive:

1. **Cache por pasta Drive** (`gdrive_list_{folder_id}`) — 1h — evita re-listar fotos de cada moto individualmente.
2. **Cache do Feed XML** (`feed_xml_{host}`) — 1h — o XML completo do Google Merchant é gerado uma única vez e servido direto do cache nas requisições seguintes. Atualiza automaticamente ao expirar.

---

## 🐳 Arquitetura e Deploy (Docker)

O ecossistema do MotoFlow é **100% conteinerizado** via Docker. O app não deve ser executado via `systemd` na VPS, garantindo que o ambiente Python e as bibliotecas pesadas do WeasyPrint (`libpango`/`libffi`) fiquem isoladas dentro do container.

- **Porta em Produção:** `5000`
- **Banco de Dados Persistente:** O arquivo `estoque.db` e as imagens (`/static/images`) são **Volumes**. Você pode recriar o container do zero sem perder nenhum dado.
- **Credenciais do Google Drive:** As chaves da Service Account ficam em `/home/diego/moto-flow-config/` (montada como volume somente-leitura `ro`).

---

## 🧪 Ambiente de Testes (Desenvolvimento Local)

Para desenvolver sem derrubar a produção, use o ambiente virtual com uma porta separada:

```bash
source venv/bin/activate
flask run --port 5005
# Acesse em :5005 para homologar. A produção em :5000 permanece intacta.
```

---

## Assets Estáticos

- **Logo:** `static/images/logo.png` — exibida no catálogo público e páginas de detalhe. Ao trocar o arquivo, basta rodar o rebuild para publicar.
- **CSS interno:** cada template do catálogo é autocontido (sem `base.html`), com toda a estilização inline para máxima portabilidade pública.

---

## 🔄 Como Promover o Código para Produção

Após qualquer alteração em `/templates`, blueprints, `app.py` ou assets estáticos (logo, CSS), rode:

```bash
cd /home/diego/projetos/MotoFlowSystem
docker compose up -d --build
```

O Docker recompila a imagem, descarta o container antigo e sobe o novo de forma transparente.
