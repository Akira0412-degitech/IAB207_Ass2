from flask import Blueprint, flash, render_template, request, url_for, redirect
from flask_bcrypt import generate_password_hash, check_password_hash
from flask_login import login_user, login_required, logout_user
 
from .models import User
from .forms import LoginForm, RegisterForm
from . import db
 
# Create a blueprint - make sure all BPs have unique names
auth_bp = Blueprint('auth', __name__)
 
 
def _safe_next(target):
    """Return `target` only if it is a relative path on this site.
 
    Without this check an attacker could send a victim to
    /login?next=https://evil.example and have our own login page
    redirect them off-site after a successful login (an open redirect).
    """
    if target and target.startswith('/') and not target.startswith('//'):
        return target
    return None
 
 
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """US16 - sign an existing user in."""
    login_form = LoginForm()
 
    if login_form.validate_on_submit():
        email = login_form.email.data
        password = login_form.password.data
        user = db.session.scalar(db.select(User).where(User.email == email))
 
        # US16: the same message is shown whether the email is unknown or the
        # password is wrong, so the form cannot be used to discover which
        # email addresses have accounts.
        if user is None or not check_password_hash(user.password_hash, password):
            flash('Incorrect email or password')
        else:
            login_user(user)
            # US8 depends on this: a visitor sent here by @login_required is
            # returned to the page they originally asked for.
            nextp = _safe_next(request.args.get('next'))
            return redirect(nextp or url_for('main.index'))
 
    return render_template('user.html', form=login_form, heading='Login')
 
 
@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """US15 - create an account and sign the new user straight in."""
    register_form = RegisterForm()
 
    if register_form.validate_on_submit():
        # flask_bcrypt returns bytes; the password_hash column is a String,
        # so decode before storing or the stored value keeps its b'...'
        # wrapper and every later login comparison fails.
        password_hash = generate_password_hash(
            register_form.password.data
        ).decode('utf-8')
 
        user = User(
            first_name=register_form.first_name.data,
            surname=register_form.surname.data,
            email=register_form.email.data,
            password_hash=password_hash,
            contact_number=register_form.contact_number.data,
            street_address=register_form.street_address.data,
        )
        db.session.add(user)
        db.session.commit()
 
        # US15: on success the user is logged in rather than sent to /login.
        login_user(user)
        flash('Welcome to Amplifi, {}'.format(user.first_name))
 
        nextp = _safe_next(request.args.get('next'))
        return redirect(nextp or url_for('main.index'))
 
    return render_template('user.html', form=register_form, heading='Register')
 
 
@auth_bp.route('/logout')
@login_required
def logout():
    """US16 - end the session and return to the landing page."""
    logout_user()
    flash('You have been logged out')
    return redirect(url_for('main.index'))