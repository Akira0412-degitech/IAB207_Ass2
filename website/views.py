from flask import Blueprint, render_template, request
from flask_login import login_required

from .models import Event
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
    """US5 - full details for one gig. Open to visitors, no login needed.
    get_or_404 turns an unknown id into a clean 404 rather than a crash,
    which US19's error handling will style later."""
    event = db.get_or_404(Event, event_id)
    return render_template('event.html', event=event)


@main_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_event():
    """US12 - only a signed-in user may list a gig. @login_required sends
    anonymous visitors to auth.login with ?next=/create so they come back
    here afterwards."""
    return render_template('create.html')


@main_bp.route('/bookings')
@login_required
def bookings():
    """US11 - a user's own booking history, so it requires a session."""
    return render_template('bookings.html')