"""Reset the database and load demo data.

Run from the project root with the virtual environment active:

    python seed_db.py

WARNING: this drops every table first, so any accounts or bookings you
created by hand are destroyed. That is deliberate - it means everyone on
the team can get to an identical, known state before testing.

The data below covers all four event statuses so the landing page,
genre filter, search and booking history can all be demonstrated:
    Open      - Halcyon Drift, Low Tide Club, Fernway
    Sold Out  - Quarry Belt (a seeded booking takes the last ticket)
    Cancelled - Verandah Saints (is_cancelled flag)
    Inactive  - Pilot Light (event date in the past)

Dates are relative to today rather than hard-coded, so the demo data
never goes stale and "Inactive" always means genuinely past.
"""

from datetime import date, time, timedelta, datetime

from flask_bcrypt import generate_password_hash

from website import create_app, db
from website.models import User, Event, Booking, Comment


def seed():
    app = create_app()

    with app.app_context():
        db.drop_all()
        db.create_all()

        today = date.today()

        # ------------------------------------------------------------------
        # Users
        # ------------------------------------------------------------------
        # generate_password_hash returns bytes; the column is a String, so
        # decode before storing or every later login comparison fails.
        def make_user(first, last, email, phone, address):
            return User(
                first_name=first,
                surname=last,
                email=email,
                password_hash=generate_password_hash('password123').decode('utf-8'),
                contact_number=phone,
                street_address=address,
            )

        promoter = make_user('Ruth', 'Okonjo', 'ruth@example.com',
                             '0412345678', '12 Brunswick Street, Fortitude Valley')
        punter = make_user('Dev', 'Ramanathan', 'dev@example.com',
                           '0423456789', '88 Vulture Street, West End')
        marta = make_user('Marta', 'Ilic', 'marta@example.com',
                          '0434567890', '5 Boundary Street, West End')

        db.session.add_all([promoter, punter, marta])
        db.session.commit()

        # ------------------------------------------------------------------
        # Events
        # ------------------------------------------------------------------
        def make_event(title, description, image, genre, age, days_from_now,
                       venue, address, price, total, acts,
                       aoc_type='generic', aoc_group=None, cancelled=False):
            """acts is a list of (name, time) tuples, headliner first."""
            acts = acts + [(None, None)] * (3 - len(acts))
            return Event(
                creator_id=promoter.id,
                title=title,
                description=description,
                image_filename=image,
                genre=genre,
                age_restriction=age,
                event_date=today + timedelta(days=days_from_now),
                doors_time=time(19, 30),
                end_time=time(23, 0),
                venue_name=venue,
                venue_address=address,
                ticket_price=price,
                tickets_total=total,
                artist_1=acts[0][0], artist_1_time=acts[0][1],
                artist_2=acts[1][0], artist_2_time=acts[1][1],
                artist_3=acts[2][0], artist_3_time=acts[2][1],
                aoc_type=aoc_type,
                aoc_group=aoc_group,
                is_cancelled=cancelled,
                created_at=datetime.utcnow(),
            )

        halcyon = make_event(
            'Halcyon Drift', 
            'Halcyon Drift have spent two years playing to eighty people in '
            'rooms with bad ceilings, and this is the last show before they '
            'leave for the east coast run. The new material is louder and '
            'considerably less polite than the EP.',
            'gig-halcyon.jpg', 'Rock / Punk', '18+', 21,
            'The Zoo', '711 Ann Street, Fortitude Valley', 28.00, 220,
            [('Halcyon Drift', time(21, 15)),
             ('Slow Tourist', time(20, 35)),
             ('Paper Ferns', time(20, 0))],
            aoc_type='enhanced', aoc_group='Turrbal and Yuggera peoples',
        )

        quarry = make_event(
            'Quarry Belt',
            'Album launch. Two support acts, one very loud PA, and a merch '
            'desk that takes cash only.',
            'gig-quarry.jpg', 'Metal / Heavy', '18+', 28,
            'Crowbar', '243 Brunswick Street, Fortitude Valley', 35.00, 150,
            [('Quarry Belt', time(21, 30)),
             ('Ironbark', time(20, 45)),
             ('Hollow Coast', time(20, 0))],
        )

        lowtide = make_event(
            'Low Tide Club',
            'Live modular set plus two support DJs. All ages, so bring the '
            'whole share house.',
            'gig-lowtide.jpg', 'Electronic', 'All ages', 35,
            "Mo's Desert Clubhouse", '8 Sixth Avenue, Burleigh Heads', 22.00, 180,
            [('Low Tide Club', time(22, 0)),
             ('Saltbox', time(21, 0))],
        )

        fernway = make_event(
            'Fernway',
            'Six-piece, two sets, no support. Arrive early if you want a seat '
            'anywhere near the front.',
            'gig-fernway.jpg', 'Jazz / Blues', 'All ages', 42,
            'Miami Marketta', '23 Hillcrest Parade, Miami', 18.00, 120,
            [('Fernway', time(20, 30))],
            aoc_type='none',
        )

        verandah = make_event(
            'Verandah Saints',
            'Cancelled by the promoter after the venue double-booked the '
            'room. Refunds have been processed automatically.',
            'gig-verandah.jpg', 'Folk / Acoustic', '18+', 14,
            'The Triffid', '7 Stratton Street, Newstead', 30.00, 300,
            [('Verandah Saints', time(21, 0)),
             ('Quiet Cattle', time(20, 15))],
            cancelled=True,
        )

        pilot = make_event(
            'Pilot Light',
            'This gig has already happened. Comments stay open so people can '
            'argue about the setlist.',
            'gig-pilotlight.jpg', 'Hip-Hop / R&B', '18+', -30,
            'The Bearded Lady', '138 Boundary Street, West End', 25.00, 100,
            [('Pilot Light', time(21, 45)),
             ('Nite Errand', time(21, 0))],
        )

        db.session.add_all([halcyon, quarry, lowtide, fernway, verandah, pilot])
        db.session.commit()

        # ------------------------------------------------------------------
        # Bookings
        # ------------------------------------------------------------------
        # Quarry Belt is seeded with a booking for its entire allocation so
        # that Event.status returns "Sold Out" without any extra flag.
        db.session.add_all([
            Booking(user_id=punter.id, event_id=quarry.id, quantity=150,
                    price_per_ticket=quarry.ticket_price,
                    booked_at=datetime.utcnow() - timedelta(days=9)),
            Booking(user_id=punter.id, event_id=halcyon.id, quantity=2,
                    price_per_ticket=halcyon.ticket_price,
                    booked_at=datetime.utcnow() - timedelta(days=5)),
            Booking(user_id=punter.id, event_id=verandah.id, quantity=3,
                    price_per_ticket=verandah.ticket_price,
                    booked_at=datetime.utcnow() - timedelta(days=12)),
            Booking(user_id=punter.id, event_id=pilot.id, quantity=2,
                    price_per_ticket=pilot.ticket_price,
                    booked_at=datetime.utcnow() - timedelta(days=40)),
            Booking(user_id=marta.id, event_id=lowtide.id, quantity=1,
                    price_per_ticket=lowtide.ticket_price,
                    booked_at=datetime.utcnow() - timedelta(days=2)),
        ])

        # ------------------------------------------------------------------
        # Comments
        # ------------------------------------------------------------------
        db.session.add_all([
            Comment(user_id=marta.id, event_id=halcyon.id,
                    body='Saw them at Crowbar in June and the new songs were '
                         'already excellent. Get there early, Paper Ferns are '
                         'worth the trip on their own.',
                    created_at=datetime.utcnow() - timedelta(days=3)),
            Comment(user_id=punter.id, event_id=halcyon.id,
                    body='Is there parking nearby or is it worth taking the '
                         'train to Fortitude Valley station?',
                    created_at=datetime.utcnow() - timedelta(days=2)),
            Comment(user_id=promoter.id, event_id=halcyon.id,
                    body='Train is easier - the station is a five minute walk '
                         'and street parking around Ann Street fills up by 7pm.',
                    created_at=datetime.utcnow() - timedelta(days=1)),
            Comment(user_id=marta.id, event_id=pilot.id,
                    body='Best set I have seen all year. Please come back.',
                    created_at=datetime.utcnow() - timedelta(days=28)),
        ])

        db.session.commit()

        # ------------------------------------------------------------------
        # Summary
        # ------------------------------------------------------------------
        print('Database reset and seeded.')
        print('  users:    {}'.format(db.session.scalar(
            db.select(db.func.count()).select_from(User))))
        print('  events:   {}'.format(db.session.scalar(
            db.select(db.func.count()).select_from(Event))))
        print('  bookings: {}'.format(db.session.scalar(
            db.select(db.func.count()).select_from(Booking))))
        print('  comments: {}'.format(db.session.scalar(
            db.select(db.func.count()).select_from(Comment))))
        print()
        print('Statuses:')
        for ev in db.session.scalars(db.select(Event).order_by(Event.event_date)):
            print('  {:<18} {:<10} {} of {} tickets left'.format(
                ev.title, ev.status, ev.tickets_remaining, ev.tickets_total))
        print()
        print('Log in as any of these with the password "password123":')
        print('  ruth@example.com   (created every event)')
        print('  dev@example.com    (has four bookings)')
        print('  marta@example.com  (has one booking)')


if __name__ == '__main__':
    seed()
