from flask_wtf import FlaskForm
from wtforms.fields import (SubmitField, StringField, PasswordField,
                            RadioField, TextAreaField)
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


class EventForm(FlaskForm):
    """US13 - Acknowledgement of Country section of the gig listing form."""

    aoc_type = RadioField("Acknowledgement of Country", choices=[
        ('none', 'No Acknowledgement of Country'),
        ('generic', 'Generic'),
        ('enhanced', 'Enhanced'),
    ], default='generic', validators=[
        InputRequired('Choose how your listing acknowledges Country'),
    ])
    # US13 - no Optional() on these two: it would stop the chain on an empty
    # value and skip the enhanced-only checks below.
    aoc_group = StringField("Traditional Custodians", validators=[
        Length(max=200),
    ])
    aoc_statement = TextAreaField("Your Acknowledgement of Country")
    # TODO(#14): add remaining event fields (title, description, genre, venue, tickets, lineup, image, etc.) and the full creation logic.

    def validate_aoc_group(self, field):
        """US13 - an enhanced Acknowledgement is meaningless without a named group."""
        if self.aoc_type.data == 'enhanced' and not (field.data or '').strip():
            raise ValidationError('Name the Traditional Custodians of the land your '
                                  'venue is on, or choose the generic option')

    def validate_aoc_statement(self, field):
        """US13 - block tokenistic wording: the statement must name the
        custodians entered above, not be boilerplate that fits any venue."""
        if self.aoc_type.data != 'enhanced':
            return
        statement = (field.data or '').strip()
        if not statement:
            raise ValidationError('Write your Acknowledgement of Country statement')
        group = (self.aoc_group.data or '').strip().lower()
        # An empty group is already reported by validate_aoc_group.
        if group and group not in statement.lower():
            raise ValidationError('Name the Traditional Custodians you entered '
                                  'above in your statement')
        # TODO(#14): also require the venue name/suburb once those fields exist
