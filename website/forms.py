from datetime import date

from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms.fields import (SubmitField, StringField, PasswordField,
                            RadioField, TextAreaField, SelectField,
                            DateField, TimeField, DecimalField, IntegerField)
from wtforms.validators import (InputRequired, Email, EqualTo, Length,
                                Regexp, NumberRange, Optional)
from wtforms import ValidationError

from .models import User
from . import db

GENRES = [
    'Rock / Punk', 'Metal / Heavy', 'Electronic',
    'Hip-Hop / R&B', 'Jazz / Blues', 'Folk / Acoustic',
]

AGE_RESTRICTIONS = ['All ages', '15+', '18+']


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
    """US12 - create a gig listing. US13 adds the Acknowledgement section."""

    # --- The gig ------------------------------------------------------
    title = StringField("Gig title", validators=[
        InputRequired('Enter a title for your gig'),
        Length(max=120),
    ])
    description = TextAreaField("Description", validators=[
        InputRequired('Describe the gig'),
    ])
    genre = SelectField("Genre",
                        choices=[('', 'Choose a genre')] + [(g, g) for g in GENRES],
                        validators=[InputRequired('Choose a genre')])
    age_restriction = SelectField(
        "Age restriction",
        choices=[('', 'Choose a restriction')] + [(a, a) for a in AGE_RESTRICTIONS],
        validators=[InputRequired('Choose an age restriction')])

    # --- Lineup -------------------------------------------------------
    # Only the headline act is required; the two support slots are optional,
    # which is why the model allows artist_2 and artist_3 to be null.
    artist_1 = StringField("Headline act", validators=[
        InputRequired('Name the headline act'),
        Length(max=120),
    ])
    artist_1_time = TimeField("Set time", validators=[Optional()])
    artist_2 = StringField("Support act", validators=[Optional(), Length(max=120)])
    artist_2_time = TimeField("Set time", validators=[Optional()])
    artist_3 = StringField("Support act", validators=[Optional(), Length(max=120)])
    artist_3_time = TimeField("Set time", validators=[Optional()])

    # --- When and where -----------------------------------------------
    event_date = DateField("Date", validators=[
        InputRequired('Enter the date of the gig'),
    ])
    doors_time = TimeField("Doors open", validators=[Optional()])
    end_time = TimeField("Finishes", validators=[Optional()])
    venue_name = StringField("Venue", validators=[
        InputRequired('Enter the venue'),
        Length(max=120),
    ])
    venue_address = StringField("Street address", validators=[
        Optional(), Length(max=200),
    ])

    # --- Tickets --------------------------------------------------------
    ticket_price = DecimalField("Ticket price (AUD)", places=2, validators=[
        InputRequired('Enter a ticket price'),
        NumberRange(min=0.01, message='Ticket price must be greater than zero'),
    ])
    tickets_total = IntegerField("Tickets available", validators=[
        InputRequired('Enter how many tickets are available'),
        NumberRange(min=1, message='There must be at least one ticket'),
    ])

    # --- Poster ---------------------------------------------------------
    image = FileField("Gig image", validators=[
        FileRequired('Upload a poster for the gig'),
        FileAllowed(['jpg', 'jpeg', 'png'], 'JPG or PNG images only'),
    ])

    # --- Acknowledgement of Country (US13) -------------------------------
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

    submit = SubmitField("Publish gig")

    def validate_event_date(self, field):
        """US12 - a gig cannot be listed for a date that has already passed.

        Without this the event would be created and immediately read back as
        Inactive, which is confusing rather than useful.
        """
        if field.data and field.data < date.today():
            raise ValidationError('Event date must be in the future')

    def validate_aoc_group(self, field):
        """US13 - an enhanced Acknowledgement is meaningless without a named group."""
        if self.aoc_type.data == 'enhanced' and not (field.data or '').strip():
            raise ValidationError('Name the Traditional Custodians of the land your '
                                  'venue is on, or choose the generic option')

    def validate_aoc_statement(self, field):
        """US13 - block tokenistic wording: the statement must name the
        custodians entered above and the venue, not be boilerplate that
        fits any gig anywhere."""
        if self.aoc_type.data != 'enhanced':
            return
        statement = (field.data or '').strip()
        if not statement:
            raise ValidationError('Write your Acknowledgement of Country statement')
        lowered = statement.lower()
        group = (self.aoc_group.data or '').strip().lower()
        # An empty group is already reported by validate_aoc_group.
        if group and group not in lowered:
            raise ValidationError('Name the Traditional Custodians you entered '
                                  'above in your statement')
        venue = (self.venue_name.data or '').strip().lower()
        if venue and venue not in lowered:
            raise ValidationError('Mention the venue ({}) so the Acknowledgement '
                                  'is specific to where this gig is held'
                                  .format(self.venue_name.data))


class CommentForm(FlaskForm):
    """US7 - post a comment on a gig.

    Only the body is captured; the author and timestamp come from the
    session and the database default rather than from the form, so neither
    can be forged by the submitter.
    """

    body = TextAreaField("Add a comment", validators=[
        InputRequired('Write something before posting'),
        Length(max=1000, message='Keep comments under 1000 characters'),
    ])
    submit = SubmitField("Post comment")