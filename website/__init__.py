# import flask - from 'package' import 'Class'
from flask import Flask, render_template
from flask_bootstrap import Bootstrap5
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
import sqlalchemy.exc

db = SQLAlchemy()

# create a function that creates a web application
# a web server will run this web application
def create_app():

    app = Flask(__name__)  # this is the name of the module/package that is calling this app
    # Should be set to false in a production environment
    app.debug = True
    app.secret_key = 'somesecretkey'
    # set the app configuration data
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sitedata.sqlite'
    # initialise db with flask app
    db.init_app(app)

    Bootstrap5(app)

    # initialise the login manager
    login_manager = LoginManager()

    # set the name of the login function that lets user login
    # in our case it is auth.login (blueprintname.viewfunction name)
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)

    # create a user loader function takes userid and returns User
    # Importing inside the create_app function avoids circular references
    from .models import User

    @login_manager.user_loader
    def load_user(user_id):
        """US19 - load the session user safely.

        When the database is unavailable (e.g. the marker is testing the 500
        page by removing the SQLite file), the normal query raises
        SQLAlchemyError, which would cause a second crash inside the 500 error
        handler while it tries to render base.html with current_user. Catching
        that error and returning None lets Flask-Login treat the visitor as
        anonymous, so the navbar renders in its logged-out state and the error
        page is still fully styled.
        """
        try:
            return db.session.scalar(db.select(User).where(User.id == user_id))
        except sqlalchemy.exc.SQLAlchemyError:
            # Roll back so the broken transaction does not linger on the
            # session that the error-page render will reuse.
            db.session.rollback()
            return None

    from . import views
    app.register_blueprint(views.main_bp)

    from . import auth
    app.register_blueprint(auth.auth_bp)

    # create any missing tables so a fresh clone runs without seed_db.py
    with app.app_context():
        db.create_all()

    # --- US19: custom error handlers ---
    # Registered after blueprints so get_or_404() calls in views also route
    # here rather than showing Flask's default HTML error pages.

    @app.errorhandler(404)
    def page_not_found(e):
        """US19 - return the custom 404 template with the correct status code.

        The explicit ', 404' is required: without it Flask would return 200,
        which breaks any client or test that checks the status code.
        This handler also catches abort(404) and db.get_or_404() raised
        anywhere in the app, so those call sites do not need to change.
        """
        return render_template('404.html'), 404

    @app.errorhandler(500)
    def internal_error(e):
        """US19 - return the custom 500 template with the correct status code.

        Roll back the database session first. If a view raised an exception
        mid-transaction, the session may be in a broken state; rendering the
        error page would then fail with a second exception. The rollback is
        wrapped in its own try/except because the database itself may be the
        thing that is broken (e.g. the file has been removed).

        A final fallback returns bare HTML so the visitor always sees a plain
        human-readable message rather than a raw Flask/Werkzeug error page,
        even when the template render itself fails.
        """
        try:
            db.session.rollback()
        except Exception:
            # Database is completely unavailable; swallow so we can still
            # attempt to render the styled error template.
            pass

        try:
            return render_template('500.html'), 500
        except Exception:
            # Last resort: template rendering failed (e.g. DB still broken and
            # base.html has a query). Return a minimal page — no stack trace,
            # no exception detail, ever.
            return (
                '<!doctype html><html lang="en-AU"><head><meta charset="utf-8">'
                '<title>Something went wrong \u2014 Amplifi</title></head><body>'
                '<h1>Something went wrong on our end.</h1>'
                '<p>We\u2019re looking into it. '
                '<a href="/">Back to Amplifi</a>.</p>'
                '</body></html>'
            ), 500

    return app
