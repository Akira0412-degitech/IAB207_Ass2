from flask import Blueprint, render_template
from flask_login import login_required

from .models import Event
from . import db

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    """US1 - landing page. Lists every gig held in the database, soonest
    first, and is open to visitors who are not logged in."""
    events = db.session.scalars(
        db.select(Event).order_by(Event.event_date)
    ).all()
    return render_template('index.html', events=events)


@main_bp.route('/event/<int:event_id>')
def event_detail(event_id):
    """US5 - event details. Open to visitors, no login needed.
    The lookup by event_id lands with issue #5."""
    return render_template('event.html')


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