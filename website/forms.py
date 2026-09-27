from flask_wtf import FlaskForm
from wtforms.fields import SubmitField, StringField, PasswordField
from wtforms.validators import InputRequired, Email, EqualTo, Length, Regexp
from wtforms import ValidationError
 
from .models import User
from . import db
 
 
class LoginForm(FlaskForm):
    """US16 - existing users sign in with their email address and password."""
 
    email = StringField("Email address", validators=[
        InputRequired('Enter your email address'),
        Email('Enter a valid email address'),
    ])
    password = PasswordField("Password", validators=[
        InputRequired('Enter your password'),
    ])
    submit = SubmitField("Login")
 
 
class RegisterForm(FlaskForm):
    """US15 - new users register with the six details required by the brief."""
 
    first_name = StringField("First name", validators=[
        InputRequired('Enter your first name'),
        Length(max=50),
    ])
    surname = StringField("Surname", validators=[
        InputRequired('Enter your surname'),
        Length(max=50),
    ])
    email = StringField("Email address", validators=[
        InputRequired('Enter your email address'),
        Email('Enter a valid email address'),
        Length(max=120),
    ])
    # US15: contact number must be digits only, 8-15 characters.
    contact_number = StringField("Contact number", validators=[
        InputRequired('Enter your contact number'),
        Regexp(r'^\d{8,15}$',
               message='Enter a contact number of 8 to 15 digits, numbers only'),
    ])
    street_address = StringField("Street address", validators=[
        InputRequired('Enter your street address'),
        Length(max=200),
    ])
 
    # The two password fields are linked so the user must type the same value
    # twice before the form will validate.
    password = PasswordField("Password", validators=[
        InputRequired('Enter a password'),
        Length(min=8, message='Use at least 8 characters'),
        EqualTo('confirm', message='Passwords should match'),
    ])
    confirm = PasswordField("Confirm password")
 
    submit = SubmitField("Register")
 
    def validate_email(self, field):
        """US15 - refuse an email address that is already registered.
 
        WTForms calls any method named validate_<fieldname> automatically
        during validate_on_submit(), so this needs no wiring in the view.
        """
        existing = db.session.scalar(
            db.select(User).where(User.email == field.data)
        )
        if existing is not None:
            raise ValidationError('That email address is already registered')