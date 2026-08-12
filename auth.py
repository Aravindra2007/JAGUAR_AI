"""
Authentication for Jaguar AI.

Thin Flask-Login wrapper around db.py. Every account is stored in
MySQL (users table) with a salted/hashed password - nothing sensitive
is ever kept in memory or in state.py.

Blueprint routes:
    GET/POST /login
    GET/POST /register
    GET      /logout
"""

from __future__ import annotations

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user

import db
import state

auth_bp = Blueprint("auth", __name__)
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Please sign in to use Jaguar AI."
login_manager.login_message_category = "info"


class User(UserMixin):
    """Thin adapter so Flask-Login can work with our MySQL row dict."""

    def __init__(self, row: dict):
        self.id = str(row["id"])
        self.username = row["username"]
        self.email = row["email"]
        self.full_name = row.get("full_name") or row["username"]
        self.role = row.get("role", "student")


@login_manager.user_loader
def load_user(user_id):
    row = db.get_user_by_id(int(user_id))
    if not row:
        return None
    return User(row)


def init_auth(app):
    login_manager.init_app(app)
    app.register_blueprint(auth_bp)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("home"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        full_name = request.form.get("full_name", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if password != confirm:
            flash("Passwords don't match.", "error")
            return render_template("register.html")

        try:
            row = db.create_user(username, email, password, full_name=full_name)
        except db.DBError as e:
            flash(str(e), "error")
            return render_template("register.html")
        except Exception as e:
            flash(f"Could not reach the database: {e}", "error")
            return render_template("register.html")

        login_user(User(row))
        state.set_current_user(row["id"], row["username"])
        flash(f"Welcome to Jaguar AI, {row['username']}!", "success")
        return redirect(url_for("home"))

    return render_template("register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("home"))

    if request.method == "POST":
        identifier = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        try:
            row = db.verify_login(identifier, password)
        except Exception as e:
            flash(f"Could not reach the database: {e}", "error")
            return render_template("login.html")

        if not row:
            flash("Invalid username/email or password.", "error")
            return render_template("login.html")

        login_user(User(row), remember=True)
        state.set_current_user(row["id"], row["username"])
        return redirect(url_for("home"))

    return render_template("login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    state.set_current_user(None, None)
    logout_user()
    session.clear()
    return redirect(url_for("auth.login"))
