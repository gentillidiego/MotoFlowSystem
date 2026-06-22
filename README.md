# Moto Flow System

Sistema de gestão (ERP) completo para concessionárias de motocicletas. Gerencia o ciclo de vida inteiro: **Estoque → Leads → Vendas → Financeiro → Transferência de documentos**.

🌐 **Domínio principal:** [motoflowmaceio.com.br](https://motoflowmaceio.com.br)

> **Para LLMs e desenvolvedores:** antes de qualquer alteração, leia também o arquivo de contexto técnico do projeto:
>
> - **Contexto técnico:** `Contexto/projeto_motoflow.md`
>
> Ao finalizar uma sessão de trabalho, atualize esse arquivo com qualquer mudança relevante feita no projeto.
>
> ⚠️ **REBILD OBRIGATÓRIO:** Ao finalizar e validar qualquer alteração no código (`.py`, templates, CSS, etc), você DEVE rodar o comando `docker compose up -d --build` para que as mudanças reflitam em produção. Não espere o usuário pedir.

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
| Catálogo público | `/catalogo` | Vitrine pública + feed XML Google Merchant (com retenção de isca de leads, ordenação inteligente de fotos e filtros por origem) |
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

- **Porta em Produção:** `5000` (interna — exposta pelo Nginx)
- **Banco de Dados Persistente:** O arquivo `estoque.db` e as imagens (`/static/images`) são **Volumes**. Você pode recriar o container do zero sem perder nenhum dado.
- **Credenciais do Google Drive:** As chaves da Service Account ficam em `/home/diego/moto-flow-config/` (montada como volume somente-leitura `ro`).

---

## 🌐 Domínio e Nginx (VPS Hostinger)

**VPS:** `72.60.248.85` (Hostinger KVM 2, Debian 13)

### Domínio principal

| URL | Destino |
|---|---|
| `https://motoflowmaceio.com.br` | App MotoFlow (proxy → porta 5000) |
| `https://www.motoflowmaceio.com.br` | Redirect 301 → apex |
| `http://motoflowmaceio.com.br` | Redirect 301 → HTTPS |
| `https://diegopereira.cloud/MotoFlow/*` | Redirect 301 permanente → `motoflowmaceio.com.br/*` |

### Nginx na VPS

- **Config do MotoFlow:** `/etc/nginx/sites-available/motoflowmaceio.com.br`
- **Config do `diegopereira.cloud`:** `/etc/nginx/sites-available/default` (compartilhada com outros projetos — **não alterar blocos não relacionados ao MotoFlow**)
- **SSL:** Let's Encrypt via Certbot — auto-renovação ativa. Cert em `/etc/letsencrypt/live/motoflowmaceio.com.br/`
- **Backup da config anterior:** `/etc/nginx/sites-available/default.bak.20260622`

### Comandos Nginx úteis (na VPS)

```bash
# Testar sintaxe antes de recarregar
sudo nginx -t

# Recarregar sem downtime
sudo nginx -s reload

# Ver logs de erro
sudo tail -f /var/log/nginx/error.log
```

---

## 🧪 Ambiente de Testes (Desenvolvimento Local)

Para desenvolver sem derrubar a produção, use o ambiente virtual com uma porta separada:

```bash
source venv/bin/activate
flask run --port 5005
# Acesse em :5005 para homologar. A produção em :5000 permanece intacta.
```

---

## 🔄 Git — Sincronização Automática

O projeto possui scripts de automação em `scripts/` para manter o repositório sempre atualizado.

> **Pré-requisito:** `inotify-tools` instalado (`sudo apt install inotify-tools`)

### Commit rápido (manual)

Use após qualquer sessão de desenvolvimento para enviar tudo ao GitHub:

```bash
# Com mensagem personalizada:
./scripts/sync.sh "feat: descrição da mudança"

# Sem mensagem (usa timestamp automático):
./scripts/sync.sh
```

### Watcher automático (background)

Monitora o projeto em tempo real e faz push automaticamente após **10 segundos de inatividade**:

```bash
# Iniciar o watcher em background:
./scripts/watch.sh &

# Acompanhar os logs:
# O watcher exibe notificações direto no terminal quando detecta mudanças.

# Parar o watcher:
kill %1   # ou Ctrl+C se estiver em foreground
```

> **Como funciona:** usa `inotifywait` para monitorar todos os arquivos do projeto (exceto `venv/`, `.git/`, `__pycache__/`). Ao detectar qualquer modificação, aguarda 10 segundos de inatividade (debounce) antes de fazer `git add . && git commit && git push`, evitando commits a cada tecla pressionada.

### Fluxo recomendado

```
Editar arquivos  →  salvar  →  watcher detecta  →  10s inativo  →  push automático
```

Ou, ao final de cada sessão:

```bash
./scripts/sync.sh "feat: o que foi feito"
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
