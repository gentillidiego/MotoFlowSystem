# 🏍️ Projeto MotoFlowSystem — Documentação de Contexto Técnico

Este documento serve como a "Fonte da Verdade" para o estado atual do sistema, sua arquitetura, decisões técnicas e histórico de melhorias. Ele foi projetado para fornecer contexto imediato a qualquer desenvolvedor ou LLM (Large Language Model) que venha a atuar no projeto.

---

## 1. Visão Geral do Sistema
O **MotoFlowSystem** é um ERP web especializado para lojas de motocicletas. Ele gerencia o ciclo de vida completo de uma venda: desde a captação do Lead, gestão de estoque, fechamento financeiro, até o processo burocrático de transferência de documentos.

---

## 2. Stack Tecnológica
*   **Linguagem:** Python 3.13+
*   **Framework Web:** Flask (Arquitetura baseada em Blueprints).
*   **Banco de Dados:** SQLite3 (Localizado em `/home/diego/projetos/MotoFlowSystem/estoque.db`).
*   **Servidor de Produção:** Gunicorn (Gerenciado via Systemd).
*   **Cache:** Flask-Caching com backend `FileSystemCache` (Compartilhado entre workers).
*   **Segurança:** 
    *   `Flask-WTF` para proteção CSRF.
    *   `Werkzeug.security` para Hashing de senhas (PBKDF2).
    *   `Flask-Login` para gestão de sessões.
*   **Frontend:** HTML5, CSS3 (Vanilla), JavaScript (Vanilla), Jinja2 templates.
*   **Integração Externa:** Google Drive API v3 (via Service Account) para exibição de fotos das motos.

---

## 3. Arquitetura de Pastas e Arquivos
*   `/app.py`: Ponto de entrada da aplicação, configuração do app e registro de Blueprints.
*   `/database.py`: Camada de abstração do banco de dados (funções `query`, `execute`, `insert`).
*   `/utils.py`: Funções utilitárias, lógica de integração com Google Drive e conversão de dados.
*   `/extensions.py`: Centralização de extensões (como o objeto `cache`) para evitar importações circulares.
*   `/blueprints/`:
    *   `auth.py`: Autenticação e gestão de usuários.
    *   `estoque.py`: CRUD de veículos e filtros por origem.
    *   `vendas.py`: Gestão de Leads e Histórico de Vendas.
    *   `financeiro.py`: Relatórios de lucro e custos mensais.
    *   `transferencias.py`: Workflow de documentação pós-venda.
    *   `catalogo.py`: Rota pública para clientes e feed XML para Google Merchant.
*   `/templates/`: Arquivos HTML (estendendo `base.html`).
*   `/tests/`: Suite de testes automatizados com `pytest`.

---

## 4. Histórico de Melhorias (Atuação do Agente AI)
O sistema passou por uma fase intensa de otimização baseada no documento `analise_motoflow.md`. As principais mudanças foram:

### 🔒 Segurança & Estabilidade
- **Proteção de Rotas:** Adicionado `@login_required` em todas as rotas administrativas e de exclusão.
- **Gestão de Chaves:** Remoção de Secret Keys hardcoded e migração do arquivo de chave do GDrive para fora do repositório/variáveis de ambiente.
- **Tratamento de Erros:** Implementadas páginas 404 (Não Encontrado) e 500 (Erro Interno) personalizadas.
- **Logging Estruturado:** Migração de `print()` para o módulo `logging`, permitindo auditoria via `journalctl`.

### 🏗️ Arquitetura & Performance
- **Paginação:** Implementada paginação em blocos de 20 itens em todas as listagens críticas para suportar grandes volumes de dados.
- **Cache Compartilhado:** Implementação do `FileSystemCache` para que múltiplos workers do Gunicorn compartilhem tokens do Drive e metadados de fotos.
- **Precisão Financeira:** Correção do algoritmo de data final (uso de `calendar.monthrange`) para garantir relatórios precisos em meses de 28, 30 e 31 dias.

### 🤖 Qualidade & DevOps
- **Testes Automatizados:** Criação de fixtures e testes de rotas/unidade para garantir que futuras atualizações não gerem regressões.
- **Produção:** Ajuste no `init_db()` para funcionar corretamente com servidores WSGI (Gunicorn).
- **Limpeza:** Remoção de arquivos `.db` residuais e placeholder de código morto.

### 🏷️ Vendas & Catálogo Público
- **Ordenação Inteligente:** Implementação de ordenação via Python garantindo que motos sem fotos válidas sejam deslocadas para o final do site.
- **Isca de Leads:** Implementação do controle `manter_catalogo` que permite ao vendedor ocultar uma moto do estoque após a venda, mas mantê-la visível no site para atrair mais clientes.
- **Filtros e Navegação:** Adição de botões para filtrar o estoque ("0KM" vs "Semi Novas") via query parameters (`?filtro=`) preservando as regras de exibição originais. A logo do catálogo também foi convertida em um botão de reset/retorno rápido.

---

## 5. Status Atual e Mecânicas Chave
*   **Estado:** **Produção/Finalizado**. O sistema está estável, seguro e performante.
*   **Mecânica de Venda:** Leads podem ser convertidos em Vendas, que por sua vez geram processos de Transferência automaticamente.
*   **Gestão de Fotos:** O sistema não armazena imagens localmente; ele gera thumbnails dinâmicos via Google Drive ID, economizando espaço em disco no servidor.
*   **Deploy:** O serviço roda via `systemd` como usuário local (`motoflow.service`).

---

## 6. Guia para Próximos Desenvolvedores/LLMs
Ao continuar este projeto, observe:
1.  **Novas Rotas:** Sempre aplique `@login_required` para áreas administrativas.
2.  **Banco de Dados:** Use sempre as funções do `database.py` para manter a padronização do logging de erros SQL.
3.  **Testes:** Antes de qualquer commit, rode `PYTHONPATH=. venv/bin/pytest tests/`.
4.  **Cache:** Se precisar cachear novos dados pesados, utilize o objeto `cache` importado de `extensions.py`.

---
*Assinado: Antigravity AI Project Context — Março de 2026*
