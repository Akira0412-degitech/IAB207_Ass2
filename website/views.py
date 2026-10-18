from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user

from .models import Event, Comment, Booking
from .forms import EventForm, BookingForm
from . import db

main_bp = Blueprint('main', __name__)

# The six categories offered on the landing page. Kept here rather than in
# the template so the route and the chips can never drift apart.
GENRES = [
    'Rock / Punk',
    'Metal / Heavy',
    'Electronic',
    'Hip-Hop / R&B',
    'Jazz / Blues',
    'Folk / Acoustic',
]


@main_bp.route('/')
def index():
    """US1, US2, US3 - landing page.

    One route handles all three stories: it lists every gig, and narrows
    that list by genre and/or keyword when those query parameters are
    present. Keeping them together is what lets the two filters combine,
    e.g. /?genre=Electronic&q=burleigh
    """
    genre = request.args.get('genre', 'all')
    q = request.args.get('q', '').strip()

    query = db.select(Event)

    # US2 - narrow to one genre. 'all' means no genre filter at all.
    if genre != 'all':
        query = query.where(Event.genre == genre)

    # US3 - case-insensitive keyword match. The lineup is stored as three
    # flat columns rather than a related table, so each is searched in turn.
    if q:
        like = '%{}%'.format(q)
        query = query.where(db.or_(
            Event.title.ilike(like),
            Event.venue_name.ilike(like),
            Event.artist_1.ilike(like),
            Event.artist_2.ilike(like),
            Event.artist_3.ilike(like),
        ))

    events = db.session.scalars(query.order_by(Event.event_date)).all()

    return render_template(
        'index.html',
        events=events,
        genres=GENRES,
        genre=genre,
        q=q,
    )


@main_bp.route('/event/<int:event_id>')
def event_detail(event_id):
    """US5, US6 - full details for one gig, plus the comments left on it.

    Both are open to visitors with no login. get_or_404 turns an unknown id
    into a clean 404 rather than a crash, which US19 will style later.
    """
    event = db.get_or_404(Event, event_id)

    # US6 - newest first. Ordering in the query rather than the template
    # means the page can never show comments out of sequence.
    comments = db.session.scalars(
        db.select(Comment)
        .where(Comment.event_id == event_id)
        .order_by(Comment.created_at.desc())
    ).all()

    return render_template('event.html', event=event, comments=comments)


# US8 - why each non-Open status blocks booking, worded for the flash message.
CLOSED_REASONS = {
    'Sold Out': 'it is Sold Out',
    'Cancelled': 'it has been cancelled',
    'Inactive': 'it has already taken place',
}


def _refuse_if_not_open(event):
    """US8 - the server-side gate for booking.

    Hiding the button on the event page is not enough: anyone can type the
    /book URL or POST to /book/confirm directly. Both booking routes call
    this first and return its redirect when the gig is not Open.
    """
    if event.status == 'Open':
        return None
    flash('Tickets for this gig are no longer available: {}.'.format(
        CLOSED_REASONS.get(event.status, 'it is not open for booking')))
    return redirect(url_for('main.event_detail', event_id=event.id))


def _has_enough_tickets(form, event):
    """US9 - refuse a quantity larger than what is left.

    The message goes into quantity.errors rather than a flash so it sits
    next to the number the user typed, and that number stays in the box
    for them to lower.
    """
    remaining = event.tickets_remaining
    if form.quantity.data <= remaining:
        return True
    if remaining == 1:
        left = 'Only 1 ticket is left'
    else:
        left = 'Only {} tickets are left'.format(remaining)
    form.quantity.errors.append(
        '{} for this gig. Lower the quantity and try again.'.format(left))
    return False


@main_bp.route('/event/<int:event_id>/book', methods=['GET', 'POST'])
@login_required
def book_event(event_id):
    """US8, US9 - step 1 of booking: choose a quantity, then review it.

    No JavaScript is allowed, so the confirmation step is a second server
    round trip: a valid POST here only renders the summary page, and
    nothing is saved until that page is submitted to book_confirm.
    """
    event = db.get_or_404(Event, event_id)
    refused = _refuse_if_not_open(event)
    if refused:
        return refused

    if request.method == 'GET':
        # "Change quantity" on the summary page links back with ?quantity=n.
        # type=int turns junk into None, so a hand-edited URL is ignored.
        requested = request.args.get('quantity', type=int)
        form = BookingForm(quantity=requested if requested and requested > 0 else 1)
        return render_template('booking.html', event=event, form=form)

    form = BookingForm()
    if form.validate_on_submit() and _has_enough_tickets(form, event):
        return render_template(
            'booking_confirm.html',
            event=event,
            form=form,
            quantity=form.quantity.data,
            total=event.ticket_price * form.quantity.data,
        )

    return render_template('booking.html', event=event, form=form)


@main_bp.route('/event/<int:event_id>/book/confirm', methods=['POST'])
@login_required
def book_confirm(event_id):
    """US8, US9 - step 2 of booking: place the order.

    The quantity arrives from a hidden field the user could have edited, so
    it goes back through the same BookingForm (CSRF and validators) and the
    stock is checked again: someone else may have bought the last tickets
    while this user was reading the summary.
    """
    event = db.get_or_404(Event, event_id)
    refused = _refuse_if_not_open(event)
    if refused:
        return refused

    form = BookingForm()
    if not (form.validate_on_submit() and _has_enough_tickets(form, event)):
        return render_template('booking.html', event=event, form=form)

    # The price is snapshotted from the event, never taken from the form, so
    # a later price change or a tampered request cannot alter what was paid.
    booking = Booking(
        user_id=current_user.id,
        event_id=event.id,
        quantity=form.quantity.data,
        price_per_ticket=event.ticket_price,
    )
    db.session.add(booking)
    db.session.commit()

    # Post/Redirect/Get: rendering a page from this POST would let a refresh
    # place the same order twice.
    flash("You're going! {} {} booked for {}. Order ID: {}".format(
        booking.quantity,
        'ticket' if booking.quantity == 1 else 'tickets',
        event.title,
        booking.order_id,
    ))
    return redirect(url_for('main.event_detail', event_id=event.id))


@main_bp.route('/create', methods=['GET'])
@login_required
def create_event():
    """US12 - only a signed-in user may list a gig. @login_required sends
    anonymous visitors to auth.login with ?next=/create so they come back
    here afterwards."""
    # TODO(#14): accept POST - validate the full EventForm and save the Event (incl. aoc_statement).
    form = EventForm()
    return render_template('create.html', form=form)


@main_bp.route('/bookings')
@login_required
def bookings():
    """US11 - a user's own booking history, so it requires a session."""
    return render_template('bookings.html')


@main_bp.route('/aoc')
def aoc():
    """US18 - Acknowledgement of Country page. Static content, open to all visitors."""
    return render_template('aoc.html')