import os
import uuid
from datetime import timedelta

from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, current_app, abort)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from .models import Event, Comment, Booking
from .forms import (EventForm, EventEditForm, CancelForm, CommentForm,
                    BookingForm, GENRES)
from . import db

main_bp = Blueprint('main', __name__)

# Queensland does not observe daylight saving, so Brisbane is UTC+10 all
# year and a fixed offset is exact. zoneinfo is avoided on purpose: on
# Windows it needs the extra tzdata package, which is not in requirements.txt.
BRISBANE_OFFSET = timedelta(hours=10)


@main_bp.app_template_filter('local_time')
def local_time(value):
    """US10, US11 - show a stored UTC time as Brisbane time.

    Booking.booked_at is saved with datetime.utcnow, so printing it raw
    would show a gig-goer a time ten hours behind the one on their phone.
    Returns e.g. '18 Oct 2026, 9:42 pm'.
    """
    if value is None:
        return ''
    local = value + BRISBANE_OFFSET
    # Built by hand because strftime's no-padding flags (%-d, %-I) are not
    # supported on Windows.
    return '{} {}, {}:{:02d} {}'.format(
        local.day, local.strftime('%b %Y'),
        local.hour % 12 or 12, local.minute,
        'am' if local.hour < 12 else 'pm')


@main_bp.app_template_filter('money')
def money(value):
    """US10, US11 - format a price as dollars with thousands separators.

    '%.2f' alone renders a large order as $5250.00; this gives $5,250.00,
    and keeps the history and confirmation pages formatting money the same way.
    """
    if value is None:
        return ''
    return '${:,.2f}'.format(value)


def _save_poster(file_storage):
    """Save an uploaded poster and return its path relative to static/.

    secure_filename strips any directory traversal out of the submitted
    name, and the random prefix stops two creators who both upload
    'poster.jpg' from overwriting one another.
    """
    safe = secure_filename(file_storage.filename)
    unique = '{}_{}'.format(uuid.uuid4().hex[:8], safe)
    file_storage.save(os.path.join(current_app.config['UPLOAD_FOLDER'], unique))
    return 'img/uploads/{}'.format(unique)


def _apply_form_to_event(form, event):
    """Copy the editable fields of an EventForm onto an Event.

    Written out rather than using form.populate_obj so that the fields the
    form must never touch - creator_id, is_cancelled, image_filename - are
    impossible to set by accident. Status is absent for the same reason:
    Event.status derives it.
    """
    event.title = form.title.data.strip()
    event.description = form.description.data.strip()
    event.genre = form.genre.data
    event.age_restriction = form.age_restriction.data
    event.event_date = form.event_date.data
    event.doors_time = form.doors_time.data
    event.end_time = form.end_time.data
    event.venue_name = form.venue_name.data.strip()
    event.venue_address = (form.venue_address.data or '').strip() or None
    event.ticket_price = form.ticket_price.data
    event.tickets_total = form.tickets_total.data
    event.artist_1 = form.artist_1.data.strip()
    event.artist_1_time = form.artist_1_time.data
    event.artist_2 = (form.artist_2.data or '').strip() or None
    event.artist_2_time = form.artist_2_time.data
    event.artist_3 = (form.artist_3.data or '').strip() or None
    event.artist_3_time = form.artist_3_time.data
    event.aoc_type = form.aoc_type.data
    event.aoc_group = (form.aoc_group.data or '').strip() or None
    # US13 - the creator's own wording is stored and shown verbatim.
    event.aoc_statement = (form.aoc_statement.data or '').strip() or None


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
    into a clean 404 rather than a crash, which US19's error pages style.
    """
    event = db.get_or_404(Event, event_id)

    # US6 - newest first. Ordering in the query rather than the template
    # means the page can never show comments out of sequence.
    comments = db.session.scalars(
        db.select(Comment)
        .where(Comment.event_id == event_id)
        .order_by(Comment.created_at.desc())
    ).all()

    # US7 - comment form, shown only to signed-in visitors.
    # US14 - cancel form, shown only to the creator; see event.html.
    return render_template('event.html', event=event, comments=comments,
                           form=CommentForm(), cancel_form=CancelForm())


@main_bp.route('/event/<int:event_id>/comment', methods=['POST'])
@login_required
def post_comment(event_id):
    """US7 - add a comment to a gig.

    Kept separate from event_detail so that page stays a pure read, and so
    the redirect afterwards means refreshing never resubmits the comment.
    """
    event = db.get_or_404(Event, event_id)
    form = CommentForm()

    if form.validate_on_submit():
        db.session.add(Comment(
            user_id=current_user.id,
            event_id=event.id,
            body=form.body.data.strip(),
        ))
        db.session.commit()
    else:
        # An empty or over-long comment: report it rather than failing silently.
        for error in form.body.errors:
            flash(error)

    return redirect(
        url_for('main.event_detail', event_id=event.id) + '#comments-heading'
    )


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


@main_bp.route('/event/<int:event_id>/book/confirm', methods=['GET', 'POST'])
@login_required
def book_confirm(event_id):
    """US8, US9 - step 2 of booking: place the order.

    The quantity arrives from a hidden field the user could have edited, so
    it goes back through the same BookingForm (CSRF and validators) and the
    stock is checked again: someone else may have bought the last tickets
    while this user was reading the summary.
    """
    # If the session expires on the summary page, Flask-Login sends the user
    # to /login?next=<this URL> and then GETs it after login. POST-only would
    # show a raw 405 there; the quantity is gone anyway, so restart step 1.
    if request.method == 'GET':
        return redirect(url_for('main.book_event', event_id=event_id))

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

    # Post/Redirect/Get: rendering the confirmation from this POST would let
    # a refresh place the same order twice. The confirmation page is a plain
    # GET, so refreshing it only re-reads the saved order.
    return redirect(url_for('main.booking_success', booking_id=booking.id))


@main_bp.route('/bookings/<int:booking_id>')
@login_required
def booking_success(booking_id):
    """US8, US10 - order confirmation for one booking.

    Also the permanent page for that order, linked from the booking history,
    so it reads the stored price snapshot rather than the event's current
    price and stays correct if the creator later changes the price.
    """
    booking = db.get_or_404(Booking, booking_id)

    # 404 rather than 403: order ids are sequential and easy to guess, so a
    # stranger must not even learn that an order with this id exists.
    if booking.user_id != current_user.id:
        abort(404)

    return render_template('booking_success.html', booking=booking,
                           event=booking.event)


@main_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_event():
    """US12 - list a new gig.

    @login_required sends anonymous visitors to auth.login with ?next=/create
    so they come back here afterwards. The creator is taken from the session,
    never from the form, so ownership cannot be forged. Status is not set
    here either: Event.status derives it from the date and ticket count.
    """
    form = EventForm()

    if form.validate_on_submit():
        event = Event(creator_id=current_user.id,
                      image_filename=_save_poster(form.image.data))
        _apply_form_to_event(form, event)
        db.session.add(event)
        db.session.commit()
        flash('Your gig is live.')
        return redirect(url_for('main.event_detail', event_id=event.id))

    return render_template('create.html', form=form)


@main_bp.route('/event/<int:event_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_event(event_id):
    """US14 - update a gig you created.

    The Inactive check runs before the ownership check deliberately: a past
    event cannot be edited by anyone, so there is no need to first tell a
    stranger whether or not the event is theirs. Status itself is never
    editable - it is derived - which is the requirement the brief sets.
    """
    event = db.get_or_404(Event, event_id)

    if event.status == 'Inactive':
        flash('This event has already passed and can no longer be edited')
        return redirect(url_for('main.event_detail', event_id=event.id))

    if event.creator_id != current_user.id:
        abort(403)

    # obj=event fills the form from the database on GET and is ignored on
    # POST, so the creator sees their current details rather than a blank form.
    form = EventEditForm(obj=event)

    if form.validate_on_submit():
        _apply_form_to_event(form, event)
        # The poster is handled outside _apply_form_to_event so that leaving
        # the file input empty keeps the existing image rather than clearing it.
        if form.image.data:
            event.image_filename = _save_poster(form.image.data)
        db.session.commit()
        flash('Your gig has been updated.')
        return redirect(url_for('main.event_detail', event_id=event.id))

    return render_template('edit_event.html', form=form, event=event)


@main_bp.route('/event/<int:event_id>/cancel', methods=['POST'])
@login_required
def cancel_event(event_id):
    """US14 - cancel a gig you created.

    POST only and CSRF protected, so a cancellation cannot be triggered by
    following a link. is_cancelled is the single stored piece of status;
    Event.status derives Open, Sold Out and Inactive from the data, and
    Cancelled takes precedence over all of them.
    """
    event = db.get_or_404(Event, event_id)

    if event.creator_id != current_user.id:
        abort(403)

    form = CancelForm()
    if form.validate_on_submit():
        event.is_cancelled = True
        db.session.commit()
        flash('"{}" has been cancelled. Anyone who booked will see this in '
              'their tickets.'.format(event.title))

    return redirect(url_for('main.event_detail', event_id=event.id))


@main_bp.route('/bookings')
@login_required
def bookings():
    """US11 - a user's own booking history, so it requires a session.

    Filtered by the session user, never by an id in the URL, so nobody can
    page through someone else's tickets. Orders are split into gigs still
    to come and gigs that are over or cancelled, so the next night out is
    at the top instead of buried among old orders.
    """
    # Every stub shows the event's title, poster and live status, and status
    # needs that event's bookings to count tickets remaining. selectinload
    # fetches all of them in two extra queries up front, instead of one
    # lazy query per order as the template walks the list.
    orders = db.session.scalars(
        db.select(Booking)
        .where(Booking.user_id == current_user.id)
        .options(db.selectinload(Booking.event).selectinload(Event.bookings))
        .order_by(Booking.booked_at.desc())
    ).all()

    # Status is derived in Python (Event.status), so the split happens here
    # rather than in SQL. Only Open events can be booked, so an order placed
    # a moment ago always lands in upcoming.
    upcoming = [b for b in orders if b.event.status in ('Open', 'Sold Out')]
    finished = [b for b in orders if b.event.status in ('Inactive', 'Cancelled')]

    # sort() is stable and orders already arrive newest-booked first, so a
    # single key keeps booked_at descending as the tie-break.
    upcoming.sort(key=lambda b: b.event.event_date)
    finished.sort(key=lambda b: b.event.event_date, reverse=True)

    return render_template('bookings.html', upcoming=upcoming,
                           finished=finished, order_count=len(orders))


@main_bp.route('/aoc')
def aoc():
    """US18 - Acknowledgement of Country page. Static content, open to all visitors."""
    return render_template('aoc.html')