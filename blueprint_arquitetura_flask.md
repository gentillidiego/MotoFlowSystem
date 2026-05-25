# Blueprint de Arquitetura de Software: Sistema Flask Modular

Este documento descreve a arquitetura e as tecnologias utilizadas no projeto **MotoFlowSystem**, estruturado para ser reaproveitado em novos projetos de sistemas de gestão web.

## 🚀 Pilares Tecnológicos

### Core Backend
- **Framework:** [Flask](https://flask.palletsprojects.com/) (Python 3)
- **Servidor WSGI:** [Gunicorn](https://gunicorn.org/) (Configurado com `ProxyFix` para compatibilidade com Nginx).
- **Gerenciamento de Ambiente:** `python-dotenv` para variáveis de ambiente e segredos.

### Banco de Dados
- **Motor:** **SQLite 3**
- **Abstração:** Wrapper customizado em `database.py` facilitando consultas seguras e retornos em formato de dicionário (`sqlite3.Row`).
- **Padrão de Acesso:** Funções `query()` para SELECT e `execute()` para comandos de escrita (INSERT/UPDATE/DELETE).

### Frontend & UI
- **Template Engine:** **Jinja2** (integrado ao Flask).
- **Estilo:** CSS Moderno (Vanilla) com foco em responsividade.
- **Segurança UI:** **Flask-WTF (CSRFProtect)** para proteção contra ataques Cross-Site Request Forgery.

---

## 🏛️ Estrutura e Design Patterns

### 1. Sistema de Blueprints (Modularização)
O sistema é dividido em módulos independentes chamados **Blueprints**, permitindo escalabilidade e organização:
- `auth`: Autenticação e gestão de usuários.
- `main`: Rotas principais e dashboards.
- `api`: Endpoints JSON para integrações ou chamadas assíncronas.
- `inventory/sales/etc`: Módulos específicos de negócio.

### 2. Autenticação e Autorização
- **Biblioteca:** `Flask-Login`.
- **Lógica de Sessão:** `UserMixin` para gerenciamento de estado do usuário.
- **Segurança de Senha:** `werkzeug.security` (usando `pbkdf2:sha256`) para hashing de senhas.
- **Controle de Acesso:** Decorators `@login_required` e verificação de permissões em nível de rota (ex: `current_user.is_admin`).

### 3. Gerenciamento de Dados (Camada de Utilidades)
- **`utils.py`:** Centraliza lógica compartilhada, cálculos de negócio e classes auxiliares (como a classe `User`).
- **`database.py`:** Gerencia a conexão com o banco e a inicialização automática de tabelas (`init_db()`).

---

## 🛠️ Checklist de Reúso (Projeto Zero)

Para iniciar um novo projeto com esta base:

1.  **Estrutura de Pastas:**
    ```text
    projeto/
    ├── app.py              # Entry point e config do app
    ├── database.py         # Abstração do SQLite
    ├── utils.py            # Classes/funções globais
    ├── .env                # Variáveis secretas
    ├── static/             # CSS/JS
    ├── templates/          # Base.html e layouts
    └── blueprints/         # Módulos do sistema
        ├── auth.py
        └── main.py
    ```
2.  **Configuração de Proxy:** Sempre use `ProxyFix` no `app.py` se for rodar atrás de um Nginx para garantir que Redirects e Protocolos (HTTPS) funcionem corretamente.
3.  **Segurança:** Mantenha a `SECRET_KEY` fora do código fonte, usando o arquivo `.env`.

---

> [!TIP]
> **Por que SQLite?** Para sistemas de pequeno e médio porte, o SQLite é extremamente performático, não exige manutenção de servidor de banco separado e facilita backups (é apenas um arquivo `.db`).
