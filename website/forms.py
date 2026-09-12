from flask_wtf import FlaskForm
from wtforms.fields import TextAreaField, SubmitField, StringField, PasswordField
from wtforms.validators import InputRequired, Length, Email, EqualTo


# creates the login information
class LoginForm(FlaskForm):
    email = StringField("Email address", validators=[
        InputRequired('Enter your email address'),
        Email('Enter a valid email address'),
    ])
    password = PasswordField("Password", validators=[InputRequired('Enter your password')])
    submit = SubmitField("Login")


# this is the registration form
class RegisterForm(FlaskForm):
    first_name = StringField("First name", validators=[InputRequired('Enter your first name')])
    surname = StringField("Surname", validators=[InputRequired('Enter your surname')])
    email = StringField("Email address", validators=[
        InputRequired('Enter your email address'),
        Email('Enter a valid email address'),
    ])
    contact_number = StringField("Contact number", validators=[InputRequired('Enter your contact number')])
    street_address = StringField("Street address", validators=[InputRequired('Enter your street address')])

    # linking two fields - password should be equal to data entered in confirm
    password = PasswordField("Password", validators=[
        InputRequired('Enter a password'),
        EqualTo('confirm', message="Passwords should match"),
    ])
    confirm = PasswordField("Confirm password")

    # TODO(#2 Register): add a validate_email(self, field) method here that
    # queries the User table and raises wtforms.ValidationError if the email
    # is already registered (Issue #2 acceptance criteria).

    submit = SubmitField("Register")
