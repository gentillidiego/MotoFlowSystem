from flask import Flask, session
from datetime import timedelta
from flask_login import LoginManager
from database import init_db, query
from utils import User
import os
from dotenv import load_dotenv
from flask_wtf.csrf import CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix
import logging

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
)

load_dotenv()

# Blueprints
from blueprints.auth import bp as auth_bp
from blueprints.main import bp as main_bp
from blueprints.estoque import bp as estoque_bp
from blueprints.vendas import bp as vendas_bp
from blueprints.financeiro import bp as financeiro_bp
from blueprints.transferencias import bp as transferencias_bp
from blueprints.catalogo import bp as catalogo_bp

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Initialize Cache (Shared FileSystem)
from extensions import cache
cache.init_app(app, config={
    'CACHE_TYPE': 'FileSystemCache',
    'CACHE_DIR': '/tmp/motoflow_cache',
    'CACHE_DEFAULT_TIMEOUT': 3600
})

# Secret key - must be defined in environment
app.secret_key = os.environ["FLASK_SECRET_KEY"]

# Initialize CSRF Protection
csrf = CSRFProtect(app)
app.permanent_session_lifetime = timedelta(hours=1)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "auth.login"

@login_manager.user_loader
def load_user(user_id):
    u = query("SELECT * FROM usuarios WHERE id=?", (user_id,), one=True)
    if u:
        return User(u["id"], u["usuario"], u["senha_hash"], u["is_admin"])
    return None

@app.before_request
def make_session_permanent():
    session.permanent = True
    session.modified = True

# Register Blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(main_bp)
app.register_blueprint(estoque_bp)
app.register_blueprint(vendas_bp)
app.register_blueprint(financeiro_bp)

app.register_blueprint(transferencias_bp)
app.register_blueprint(catalogo_bp)

from blueprints.api import bp as api_bp
app.register_blueprint(api_bp, url_prefix="/api")

with app.app_context():
    init_db()

if __name__ == "__main__":
    # Debug mode from environment variable
    debug_mode = os.getenv("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=5000, debug=debug_mode)
