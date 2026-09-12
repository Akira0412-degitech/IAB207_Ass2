from . import db
from datetime import datetime, date
from flask_login import UserMixin


class User(db.Model, UserMixin):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50), nullable=False)
    surname = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    contact_number = db.Column(db.String(20), nullable=False)
    street_address = db.Column(db.String(200), nullable=False)

    events = db.relationship('Event', backref='creator', lazy=True)
    bookings = db.relationship('Booking', backref='user', lazy=True)
    comments = db.relationship('Comment', backref='user', lazy=True)

    def __repr__(self):
        return f'<User {self.email}>'


class Event(db.Model):
    __tablename__ = 'events'

    id = db.Column(db.Integer, primary_key=True)
    creator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=False)
    image_filename = db.Column(db.String(200), nullable=True)
    genre = db.Column(db.String(50), nullable=False)
    age_restriction = db.Column(db.String(20), nullable=False)

    event_date = db.Column(db.Date, nullable=False)
    doors_time = db.Column(db.Time, nullable=True)
    end_time = db.Column(db.Time, nullable=True)

    # Venue kept as plain fields on Event rather than a separate Venue table:
    # no user story needs venues to be browsed or reused independently of an
    # event, so normalising it out would add tables/forms/routes with no
    # functional payoff (see design-report review).
    venue_name = db.Column(db.String(120), nullable=False)
    venue_address = db.Column(db.String(200), nullable=True)

    ticket_price = db.Column(db.Numeric(6, 2), nullable=False)
    tickets_total = db.Column(db.Integer, nullable=False)

    # Lineup: kept as a fixed set of flat fields (matches the existing
    # create.html form: artist1/set1, artist2/set2, artist3/set3). A
    # separate Artist/Lineup many-to-many table was considered but rejected
    # for the same reason as Venue, and because a dynamic "add another
    # artist" UI would normally need JavaScript, which this unit forbids.
    artist_1 = db.Column(db.String(120), nullable=False)
    artist_1_time = db.Column(db.Time, nullable=True)
    artist_2 = db.Column(db.String(120), nullable=True)
    artist_2_time = db.Column(db.Time, nullable=True)
    artist_3 = db.Column(db.String(120), nullable=True)
    artist_3_time = db.Column(db.Time, nullable=True)

    # Acknowledgement of Country: 'none' / 'generic' / 'enhanced'
    aoc_type = db.Column(db.String(20), nullable=False, default='none')
    aoc_group = db.Column(db.String(200), nullable=True)  # named custodians, only used when aoc_type == 'enhanced'

    # Cancelled is the one status change that is a genuine user action, so it
    # is the only part of "status" stored as a column. Open / Inactive /
    # Sold Out are all derivable from event_date and ticket counts, so they
    # are computed on the fly in `status` below instead of being stored
    # (a stored value would risk going stale the moment the event date
    # passes or a booking is made, without saving any real computation).
    is_cancelled = db.Column(db.Boolean, nullable=False, default=False)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    bookings = db.relationship('Booking', backref='event', lazy=True, cascade='all, delete-orphan')
    comments = db.relationship('Comment', backref='event', lazy=True, cascade='all, delete-orphan')

    @property
    def tickets_remaining(self):
        """Derived, never stored: tickets_total minus everything already booked."""
        booked = sum(b.quantity for b in self.bookings)
        return self.tickets_total - booked

    @property
    def status(self):
        """Derived except for the Cancelled flag, which is the only user-triggered state."""
        if self.is_cancelled:
            return 'Cancelled'
        if self.event_date < date.today():
            return 'Inactive'
        if self.tickets_remaining <= 0:
            return 'Sold Out'
        return 'Open'

    def __repr__(self):
        return f'<Event {self.title}>'


class Booking(db.Model):
    __tablename__ = 'bookings'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)

    quantity = db.Column(db.Integer, nullable=False)
    # Snapshot of the per-ticket price at the moment of booking, so a later
    # change to Event.ticket_price never rewrites the price on a past order.
    price_per_ticket = db.Column(db.Numeric(6, 2), nullable=False)
    booked_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    @property
    def total_price(self):
        return self.price_per_ticket * self.quantity

    @property
    def order_id(self):
        """Human-readable order reference derived from the primary key (e.g. AMP-2026-000042)."""
        return f'AMP-{self.booked_at.year}-{self.id:06d}'

    def __repr__(self):
        return f'<Booking {self.order_id}>'


class Comment(db.Model):
    __tablename__ = 'comments'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)

    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f'<Comment {self.id} on Event {self.event_id}>'
