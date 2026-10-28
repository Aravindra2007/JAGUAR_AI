# """
# Authentication for Jaguar AI.

# Thin Flask-Login wrapper around db.py. Every account is stored in
# Firebase with a salted/hashed password - nothing sensitive
# is ever kept in memory or in state.py.

# Blueprint routes:
#     GET/POST /login
#     GET/POST /register
#     POST      /logout
# """

# from __future__ import annotations

# from flask import Blueprint, render_template, request, redirect, url_for, flash, session
# from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user

# import db
# import state
# import random
# import email_utils

# auth_bp = Blueprint("auth", __name__)
# login_manager = LoginManager()
# login_manager.login_view = "auth.login"
# login_manager.login_message = "Please sign in to use Jaguar AI."
# login_manager.login_message_category = "info"


# class User(UserMixin):
#     """Thin adapter so Flask-Login can work with our Firebase user dict."""

#     def __init__(self, row: dict):
#         self.id = str(row["id"])
#         self.username = row["username"]
#         self.email = row["email"]
#         self.full_name = row.get("full_name") or row["username"]
#         self.role = row.get("role", "student")


# @login_manager.user_loader
# def load_user(user_id):
#     row = db.get_user_by_id(user_id)
#     if not row:
#         return None
#     return User(row)




# def init_auth(app):
#     login_manager.init_app(app)
#     app.register_blueprint(auth_bp)


# @auth_bp.route("/register", methods=["GET", "POST"])
# def register():
#     if current_user.is_authenticated:
#         return redirect(url_for("home"))

#     if request.method == "POST":
#         username = request.form.get("username", "").strip()
#         email = request.form.get("email", "").strip()
#         full_name = request.form.get("full_name", "").strip()
#         password = request.form.get("password", "")
#         confirm = request.form.get("confirm_password", "")

#         if password != confirm:
#             flash("Passwords don't match.", "error")
#             return render_template("register.html")

#         try:
#             row = db.create_user(username, email, password, full_name=full_name)

#             # Generate and send OTP
#             otp = f"{random.randint(100000, 999999)}"
#             db.save_otp(row["id"], otp)
#             email_utils.send_otp_email(email, otp)

#             session["verify_user_id"] = row["id"]
#             flash("Account created! Please check your email for a verification code.", "info")
#             return redirect(url_for("auth.verify"))
#         except db.DBError as e:
#             flash(str(e), "error")
#             return render_template("register.html")
#         except Exception as e:
#             flash(f"Could not reach Firebase: {e}", "error")
#             return render_template("register.html")

#         login_user(User(row))
#         state.set_current_user(row["id"], row["username"])
#         flash(f"Welcome to Jaguar AI, {row['username']}!", "success")
#         return redirect(url_for("home"))

#     return render_template("register.html")


# @auth_bp.route("/login", methods=["GET", "POST"])
# def login():
#     if current_user.is_authenticated:
#         return redirect(url_for("home"))

#     if request.method == "POST":
#         identifier = request.form.get("username", "").strip()
#         password = request.form.get("password", "")

#         try:
#             row = db.verify_login(identifier, password)
#         except Exception as e:
#             flash(f"Could not reach Firebase: {e}", "error")
#             return render_template("login.html")

#         if not row:
#             flash("Invalid username/email or password.", "error")
#             return render_template("login.html")

#         if not row.get("verified"):
#             flash("Please verify your email before logging in.", "error")
#             return redirect(url_for("auth.verify"))

#         login_user(User(row), remember=True)
#         state.set_current_user(row["id"], row["username"])
#         return redirect(url_for("home"))

#     return render_template("login.html")


# # ==========================
# # Logout
# # =========================

# @auth_bp.route("/logout", methods=["POST"])
# @login_required
# def logout():
    

#     # Clear Jaguar AI state
#     state.set_current_user(None, None)

#     # Remove Flask-Login authentication
#     logout_user()

#     # Clear session
#     session.clear()

#     response = redirect(url_for("auth.login"))

#     # Explicitly expire the remember-me cookie
#     response.delete_cookie(
#         "remember_token",
#         path="/"
#     )

    

#     return response


# @auth_bp.route("/verify", methods=["GET", "POST"])
# def verify():
#     user_id = session.get("verify_user_id")
#     if not user_id:
#         flash("No verification session found. Please register again.", "error")
#         return redirect(url_for("auth.register"))

#     # Get user for resend logic
#     user = db.get_user_by_id(user_id)
#     if not user:
#         session.pop("verify_user_id", None)
#         flash("Account not found. Please register again.", "error")
#         return redirect(url_for("auth.register"))

#     if request.method == "POST":
#         action = request.form.get("action")

#         if action == "resend":
#             otp = f"{random.randint(100000, 999999)}"
#             db.save_otp(user_id, otp)
#             email_utils.send_otp_email(user["email"], otp)
#             flash("A new verification code has been sent to your email.", "info")
#             return render_template("verify.html")

#         otp = request.form.get("otp", "").strip()
#         if not otp:
#             flash("Please enter the OTP code.", "error")
#             return render_template("verify.html")

#         if db.verify_otp(user_id, otp):
#             flash("Email verified successfully! You can now log in.", "success")
#             session.pop("verify_user_id", None)
#             return redirect(url_for("auth.login"))
#         else:
#             flash("Invalid or expired OTP code.", "error")
#             return render_template("verify.html")

#     return render_template("verify.html")












"""
Authentication and Profile Management for Jaguar AI.

Firebase-backed authentication using Flask-Login.

Existing routes:
    GET/POST /login
    GET/POST /register
    GET/POST /verify
    POST     /logout

Profile routes:
    GET      /profile
    POST     /profile/update
    POST     /profile/photo
    POST     /profile/password

Profile features:
    - View account details
    - Edit full name
    - Upload profile photo
    - Change password securely
    - CSRF protection for profile forms
"""

from __future__ import annotations

import io
import random
import secrets
import uuid

from pathlib import Path

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    current_app,
    abort,
)

from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    logout_user,
    login_required,
    current_user,
)

from PIL import Image, UnidentifiedImageError

import db
import state
import email_utils


# ============================================================
# AUTHENTICATION CONFIGURATION
# ============================================================

auth_bp = Blueprint("auth", __name__)

login_manager = LoginManager()

login_manager.login_view = "auth.login"

login_manager.login_message = (
    "Please sign in to use Jaguar AI."
)

login_manager.login_message_category = "info"


# ============================================================
# USER MODEL
# ============================================================

class User(UserMixin):
    """
    Flask-Login adapter for Firebase user documents.

    Sensitive information such as password hashes is never
    stored inside this object.
    """

    def __init__(self, row: dict):

        self.id = str(row["id"])

        self.username = row["username"]

        self.email = row["email"]

        self.full_name = (
            row.get("full_name") or row["username"]
        )

        self.role = row.get("role", "student")

        self.profile_photo = row.get("profile_photo") or ""

        self.verified = row.get("verified", False)


# ============================================================
# USER LOADER
# ============================================================

@login_manager.user_loader
def load_user(user_id):

    row = db.get_user_by_id(user_id)

    if not row:
        return None

    return User(row)


# ============================================================
# INITIALIZATION
# ============================================================

def init_auth(app):

    login_manager.init_app(app)

    app.register_blueprint(auth_bp)


# ============================================================
# REGISTER
# ============================================================

@auth_bp.route("/register", methods=["GET", "POST"])
def register():

    if current_user.is_authenticated:
        return redirect(url_for("home"))

    if request.method == "POST":

        username = request.form.get(
            "username", ""
        ).strip()

        email = request.form.get(
            "email", ""
        ).strip()

        full_name = request.form.get(
            "full_name", ""
        ).strip()

        password = request.form.get(
            "password", ""
        )

        confirm = request.form.get(
            "confirm_password", ""
        )

        # Password validation
        if password != confirm:

            flash(
                "Passwords don't match.",
                "error"
            )

            return render_template("register.html")

        try:

            # Create Firebase account
            row = db.create_user(
                username,
                email,
                password,
                full_name=full_name
            )

            # Generate six-digit verification OTP
            otp = f"{random.randint(100000, 999999)}"

            # Save OTP in Firebase
            db.save_otp(
                row["id"],
                otp
            )

            # Send OTP email
            email_utils.send_otp_email(
                email,
                otp
            )

            # Store verification session
            session["verify_user_id"] = row["id"]

            flash(
                "Account created! Please check your email "
                "for a verification code.",
                "info"
            )

            return redirect(
                url_for("auth.verify")
            )

        except db.DBError as e:

            flash(str(e), "error")

            return render_template("register.html")

        except Exception:

            current_app.logger.exception(
                "Registration failed"
            )

            flash(
                "Unable to complete registration. "
                "Please try again.",
                "error"
            )

            return render_template("register.html")

    return render_template("register.html")


# ============================================================
# LOGIN
# ============================================================

@auth_bp.route("/login", methods=["GET", "POST"])
def login():

    if current_user.is_authenticated:
        return redirect(url_for("home"))

    if request.method == "POST":

        identifier = request.form.get(
            "username", ""
        ).strip()

        password = request.form.get(
            "password", ""
        )

        try:

            row = db.verify_login(
                identifier,
                password
            )

        except Exception:

            current_app.logger.exception(
                "Firebase login failed"
            )

            flash(
                "Could not reach Firebase. "
                "Please try again.",
                "error"
            )

            return render_template("login.html")

        if not row:

            flash(
                "Invalid username/email or password.",
                "error"
            )

            return render_template("login.html")

        # Email verification required
        if not row.get("verified"):

            session["verify_user_id"] = row["id"]

            flash(
                "Please verify your email before logging in.",
                "error"
            )

            return redirect(
                url_for("auth.verify")
            )

        # Authenticate user
        login_user(
            User(row),
            remember=True
        )

        # Retained for compatibility with existing Jaguar AI code.
        # Account-specific requests should use current_user.id.
        state.set_current_user(
            row["id"],
            row["username"]
        )

        flash(
            f"Welcome back, {row['username']}!",
            "success"
        )

        return redirect(url_for("home"))

    return render_template("login.html")


# ============================================================
# LOGOUT
# ============================================================

@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():

    # Clear existing Jaguar AI state
    state.set_current_user(None, None)

    # Remove Flask-Login authentication
    logout_user()

    # Clear Flask session
    session.clear()

    response = redirect(
        url_for("auth.login")
    )

    # Expire remember-me cookie
    response.delete_cookie(
        current_app.config.get(
            "REMEMBER_COOKIE_NAME",
            "remember_token"
        ),
        path=current_app.config.get(
            "REMEMBER_COOKIE_PATH",
            "/"
        ),
        domain=current_app.config.get(
            "REMEMBER_COOKIE_DOMAIN"
        ),
    )

    return response


# ============================================================
# EMAIL VERIFICATION
# ============================================================

@auth_bp.route("/verify", methods=["GET", "POST"])
def verify():

    user_id = session.get("verify_user_id")

    if not user_id:

        flash(
            "No verification session found. "
            "Please register again.",
            "error"
        )

        return redirect(
            url_for("auth.register")
        )

    # Fetch Firebase user
    user = db.get_user_by_id(user_id)

    if not user:

        session.pop(
            "verify_user_id",
            None
        )

        flash(
            "Account not found. Please register again.",
            "error"
        )

        return redirect(
            url_for("auth.register")
        )

    if request.method == "POST":

        action = request.form.get("action")

        # --------------------------
        # Resend OTP
        # --------------------------

        if action == "resend":

            otp = f"{random.randint(100000, 999999)}"

            db.save_otp(
                user_id,
                otp
            )

            email_utils.send_otp_email(
                user["email"],
                otp
            )

            flash(
                "A new verification code has been "
                "sent to your email.",
                "info"
            )

            return render_template("verify.html")

        # --------------------------
        # Verify OTP
        # --------------------------

        otp = request.form.get(
            "otp", ""
        ).strip()

        if not otp:

            flash(
                "Please enter the OTP code.",
                "error"
            )

            return render_template("verify.html")

        if db.verify_otp(user_id, otp):

            flash(
                "Email verified successfully! "
                "You can now log in.",
                "success"
            )

            session.pop(
                "verify_user_id",
                None
            )

            return redirect(
                url_for("auth.login")
            )

        flash(
            "Invalid or expired OTP code.",
            "error"
        )

        return render_template("verify.html")

    return render_template("verify.html")


# ============================================================
# PROFILE CSRF PROTECTION
# ============================================================

def _profile_csrf_token():
    """
    Generate a session-bound security token for profile forms.
    """

    if "profile_csrf_token" not in session:

        session["profile_csrf_token"] = (
            secrets.token_urlsafe(32)
        )

    return session["profile_csrf_token"]


def _check_profile_csrf():
    """
    Reject profile POST requests with missing or invalid tokens.
    """

    submitted = request.form.get(
        "csrf_token",
        ""
    )

    expected = session.get(
        "profile_csrf_token",
        ""
    )

    if (
        not submitted
        or not expected
        or not secrets.compare_digest(
            submitted,
            expected
        )
    ):

        abort(
            400,
            description="Invalid form security token."
        )


# ============================================================
# VIEW PROFILE
# ============================================================

@auth_bp.route("/profile", methods=["GET"])
@login_required
def profile():

    try:

        user = db.get_user_by_id(
            current_user.id
        )

    except Exception:

        current_app.logger.exception(
            "Unable to load user profile"
        )

        flash(
            "Unable to load your profile.",
            "error"
        )

        return redirect(url_for("home"))

    if not user:

        logout_user()

        session.clear()

        flash(
            "Account not found. Please sign in again.",
            "error"
        )

        return redirect(
            url_for("auth.login")
        )

    return render_template(
        "profile.html",
        user=user,
        csrf_token=_profile_csrf_token()
    )


# ============================================================
# UPDATE PERSONAL INFORMATION
# ============================================================

@auth_bp.route(
    "/profile/update",
    methods=["POST"]
)
@login_required
def update_profile():

    _check_profile_csrf()

    full_name = request.form.get(
        "full_name",
        ""
    ).strip()

    # --------------------------
    # Validate full name
    # --------------------------

    if not full_name:

        flash(
            "Full name cannot be empty.",
            "error"
        )

        return redirect(
            url_for("auth.profile")
        )

    if len(full_name) > 100:

        flash(
            "Full name cannot exceed 100 characters.",
            "error"
        )

        return redirect(
            url_for("auth.profile")
        )

    try:

        db.update_user_profile(
            current_user.id,
            full_name
        )

        flash(
            "Profile updated successfully!",
            "success"
        )

    except db.DBError as e:

        flash(
            str(e),
            "error"
        )

    except Exception:

        current_app.logger.exception(
            "Profile update failed"
        )

        flash(
            "Unable to update your profile.",
            "error"
        )

    return redirect(
        url_for("auth.profile")
    )


# ============================================================
# UPLOAD PROFILE PHOTO
# ============================================================

@auth_bp.route(
    "/profile/photo",
    methods=["POST"]
)
@login_required
def upload_profile_photo():

    _check_profile_csrf()

    photo = request.files.get(
        "profile_photo"
    )

    if not photo or not photo.filename:

        flash(
            "Please select a profile photo.",
            "error"
        )

        return redirect(
            url_for("auth.profile")
        )

    # Maximum file size: 5 MB
    max_size = 5 * 1024 * 1024

    raw = photo.stream.read(max_size + 1)

    if len(raw) > max_size:

        flash(
            "Profile photo must be smaller than 5 MB.",
            "error"
        )

        return redirect(
            url_for("auth.profile")
        )

    destination = None

    try:

        # --------------------------
        # Validate actual image
        # --------------------------

        with Image.open(io.BytesIO(raw)) as source:

            if source.format not in (
                "JPEG",
                "PNG",
                "WEBP"
            ):

                raise ValueError(
                    "Unsupported image format."
                )

            # Reject excessively large image dimensions
            if source.width * source.height > 20_000_000:

                raise ValueError(
                    "Image dimensions are too large."
                )

            source.load()

            image = source.convert("RGB")

        # Resize while preserving aspect ratio
        image.thumbnail(
            (512, 512),
            Image.Resampling.LANCZOS
        )

        # --------------------------
        # Create upload directory
        # --------------------------

        upload_dir = (
            Path(current_app.static_folder)
            / "profile_photos"
        )

        upload_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        # Generate safe random filename
        filename = (
            f"{uuid.uuid4().hex}.jpg"
        )

        destination = (
            upload_dir / filename
        )

        # Convert uploaded photo to JPEG
        image.save(
            destination,
            format="JPEG",
            quality=88,
            optimize=True
        )

        relative_path = (
            f"profile_photos/{filename}"
        )

        # --------------------------
        # Save photo path in Firebase
        # --------------------------

        try:

            db.update_profile_photo(
                current_user.id,
                relative_path
            )

        except Exception:

            destination.unlink(
                missing_ok=True
            )

            raise

        flash(
            "Profile photo updated successfully!",
            "success"
        )

    except (
        UnidentifiedImageError,
        ValueError,
        OSError,
        Image.DecompressionBombError
    ):

        flash(
            "Please upload a valid JPG, PNG, "
            "or WebP image.",
            "error"
        )

    except Exception:

        current_app.logger.exception(
            "Profile photo upload failed"
        )

        flash(
            "Unable to upload your profile photo.",
            "error"
        )

    return redirect(
        url_for("auth.profile")
    )


# ============================================================
# CHANGE PASSWORD
# ============================================================

@auth_bp.route(
    "/profile/password",
    methods=["POST"]
)
@login_required
def update_password():

    _check_profile_csrf()

    current_password = request.form.get(
        "current_password",
        ""
    )

    new_password = request.form.get(
        "new_password",
        ""
    )

    confirm_password = request.form.get(
        "confirm_password",
        ""
    )

    # --------------------------
    # Validate input
    # --------------------------

    if not current_password:

        flash(
            "Please enter your current password.",
            "error"
        )

        return redirect(
            url_for("auth.profile")
        )

    if not new_password:

        flash(
            "Please enter a new password.",
            "error"
        )

        return redirect(
            url_for("auth.profile")
        )

    if new_password != confirm_password:

        flash(
            "New passwords do not match.",
            "error"
        )

        return redirect(
            url_for("auth.profile")
        )

    if len(new_password) < 8:

        flash(
            "New password must contain at least "
            "8 characters.",
            "error"
        )

        return redirect(
            url_for("auth.profile")
        )

    # --------------------------
    # Update Firebase password
    # --------------------------

    try:

        db.change_user_password(
            current_user.id,
            current_password,
            new_password
        )

        # Clear compatibility state
        state.set_current_user(
            None,
            None
        )

        # End current login
        logout_user()

        # Clear session
        session.clear()

        flash(
            "Password updated successfully! "
            "Please sign in again.",
            "success"
        )

        response = redirect(
            url_for("auth.login")
        )

        # Expire remember-me cookie
        response.delete_cookie(
            current_app.config.get(
                "REMEMBER_COOKIE_NAME",
                "remember_token"
            ),
            path=current_app.config.get(
                "REMEMBER_COOKIE_PATH",
                "/"
            ),
            domain=current_app.config.get(
                "REMEMBER_COOKIE_DOMAIN"
            ),
        )

        return response

    except db.DBError as e:

        flash(
            str(e),
            "error"
        )

    except Exception:

        current_app.logger.exception(
            "Password update failed"
        )

        flash(
            "Unable to update your password. "
            "Please try again.",
            "error"
        )

    return redirect(
        url_for("auth.profile")
    )

