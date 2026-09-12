from flask import Blueprint, render_template

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    return render_template('index.html')


@main_bp.route('/event/<int:event_id>')
def event_detail(event_id):
    return render_template('event.html')


@main_bp.route('/create', methods=['GET', 'POST'])
def create_event():
    return render_template('create.html')


@main_bp.route('/bookings')
def bookings():
    return render_template('bookings.html')
