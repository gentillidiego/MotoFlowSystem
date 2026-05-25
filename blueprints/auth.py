from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from flask_login import login_user, logout_user, login_required
from werkzeug.security import check_password_hash
from database import query
from utils import User

bp = Blueprint('auth', __name__)

@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form.get("usuario")
        senha = request.form.get("senha")
        u = query("SELECT * FROM usuarios WHERE usuario=?", (usuario,), one=True)
        
        if u and check_password_hash(u["senha_hash"], senha):
            user = User(u["id"], u["usuario"], u["senha_hash"], u["is_admin"])
            login_user(user)
            session.permanent = True
            flash(f"Bem-vindo, {user.usuario}!", "success")
            return redirect(url_for("main.index"))
        else:
            flash("Usuário ou senha inválidos.", "error")
            
    return render_template("login.html")

@bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))

# ──────────── USUÁRIOS (ADMIN) ────────────
from flask_login import current_user
from werkzeug.security import generate_password_hash
from database import execute

@bp.route("/admin/usuarios")
@login_required
def usuarios_lista():
    if not current_user.is_admin:
        return redirect(url_for("main.index"))
    users = query("SELECT * FROM usuarios")
    return render_template("usuarios_lista.html", usuarios=users)

@bp.route("/admin/usuarios/novo", methods=["GET", "POST"])
@login_required
def usuarios_novo():
    if not current_user.is_admin:
        return redirect(url_for("main.index"))

    if request.method == "POST":
        usuario = request.form.get("usuario")
        senha = request.form.get("senha")
        
        existe = query("SELECT id FROM usuarios WHERE usuario=?", (usuario,), one=True)
        if existe:
             return render_template("usuarios_form.html", erro="Usuário já existe.")
             
        pwhash = generate_password_hash(senha)
        is_admin = 1 if request.form.get("is_admin") else 0
        execute("INSERT INTO usuarios (usuario, senha_hash, is_admin) VALUES (?, ?, ?)", (usuario, pwhash, is_admin))
        return redirect(url_for("auth.usuarios_lista"))
        
    return render_template("usuarios_form.html")

@bp.route("/admin/usuarios/excluir/<int:uid>", methods=["POST"])
@login_required
def usuarios_excluir(uid):
    if not current_user.is_admin:
        return redirect(url_for("main.index"))

    # Protect Admin 'Diego' (id usually 1, but check name too) or self
    if uid == current_user.id:
        return redirect(url_for("auth.usuarios_lista"))
        
    u = query("SELECT usuario FROM usuarios WHERE id=?", (uid,), one=True)
    if u and u["usuario"] == "Diego":
         return redirect(url_for("auth.usuarios_lista"))

    execute("DELETE FROM usuarios WHERE id=?", (uid,))
    return redirect(url_for("auth.usuarios_lista"))

