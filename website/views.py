import os
import uuid

from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, current_app)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from .models import Event, Comment
from .forms import EventForm, CommentForm, GENRES
from . import db

main_bp = Blueprint('main', __name__)


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

    # US7 - the form is rendered only for signed-in visitors; see event.html.
    return render_template('event.html', event=event,
                           comments=comments, form=CommentForm())


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
        event = Event(
            creator_id=current_user.id,
            title=form.title.data.strip(),
            description=form.description.data.strip(),
            image_filename=_save_poster(form.image.data),
            genre=form.genre.data,
            age_restriction=form.age_restriction.data,
            event_date=form.event_date.data,
            doors_time=form.doors_time.data,
            end_time=form.end_time.data,
            venue_name=form.venue_name.data.strip(),
            venue_address=(form.venue_address.data or '').strip() or None,
            ticket_price=form.ticket_price.data,
            tickets_total=form.tickets_total.data,
            artist_1=form.artist_1.data.strip(),
            artist_1_time=form.artist_1_time.data,
            artist_2=(form.artist_2.data or '').strip() or None,
            artist_2_time=form.artist_2_time.data,
            artist_3=(form.artist_3.data or '').strip() or None,
            artist_3_time=form.artist_3_time.data,
            aoc_type=form.aoc_type.data,
            aoc_group=(form.aoc_group.data or '').strip() or None,
            # US13 - the creator's own wording is stored and shown verbatim.
            aoc_statement=(form.aoc_statement.data or '').strip() or None,
        )
        db.session.add(event)
        db.session.commit()
        flash('Your gig is live.')
        return redirect(url_for('main.event_detail', event_id=event.id))

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