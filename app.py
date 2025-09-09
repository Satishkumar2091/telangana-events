import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash, g
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import uuid

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET', 'dev-secret-change-me')
DATABASE = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'events.db')

# ---------- DB helpers ----------

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv

def init_db():
    db = get_db()
    with app.open_resource('schema.sql', mode='r') as f:
        db.executescript(f.read())
    db.commit()

# small seed of example events across Telangana (you can edit/extend)

def seed_events():
    db = get_db()
    cur = db.cursor()
    events = [
        ("Wedding Celebration", "Hyderabad", "2025-11-01", 1000, "Full-day wedding services"),
        ("Cultural Concert", "Warangal", "2025-10-15", 800, "Evening concert featuring local artists"),
        ("Food Festival", "Karimnagar", "2025-12-05", 400, "Street food & local specialities"),
        ("Corporate Meet", "Nizamabad", "2025-09-28", 700, "Conference halls and arrangements"),
    ]
    for e in events:
        cur.execute("INSERT INTO events (title, district, date_text, base_price, description) VALUES (?,?,?,?,?)", e)
    db.commit()

# ---------- context / user loader ----------

@app.before_request
def load_logged_in_user():
    user_id = session.get('user_id')
    if user_id is None:
        g.user = None
    else:
        g.user = query_db('SELECT * FROM users WHERE id = ?', [user_id], one=True)

@app.context_processor
def inject_user():
    return dict(current_user=g.get('user', None))

# ---------- routes ----------

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/signup', methods=['GET','POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        error = None
        if not username or not password:
            error = 'Username and password are required.'
        elif query_db('SELECT id FROM users WHERE username = ?', [username], one=True):
            error = 'Username already taken.'
        if error:
            flash(error)
        else:
            pw_hash = generate_password_hash(password)
            db = get_db()
            db.execute('INSERT INTO users (username,email,password_hash) VALUES (?,?,?)', (username,email,pw_hash))
            db.commit()
            flash('Account created — please sign in')
            return redirect(url_for('signin'))
    return render_template('signup.html')

@app.route('/signin', methods=['GET','POST'])
def signin():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = query_db('SELECT * FROM users WHERE username = ?', [username], one=True)
        if user and check_password_hash(user['password_hash'], password):
            session.clear()
            session['user_id'] = user['id']
            flash('Signed in successfully')
            return redirect(url_for('events'))
        flash('Incorrect username or password')
    return render_template('signin.html')

@app.route('/signout')
def signout():
    session.clear()
    flash('Signed out')
    return redirect(url_for('index'))

@app.route('/events')
def events():
    district = request.args.get('district', '')
    if district:
        ev = query_db('SELECT * FROM events WHERE district LIKE ?', [f'%{district}%'])
    else:
        ev = query_db('SELECT * FROM events')
    districts = query_db('SELECT DISTINCT district FROM events')
    return render_template('events.html', events=ev, districts=districts)

@app.route('/event/<int:event_id>')
def event_detail(event_id):
    ev = query_db('SELECT * FROM events WHERE id = ?', [event_id], one=True)
    if not ev:
        flash('Event not found')
        return redirect(url_for('events'))
    return render_template('event_detail.html', event=ev)

@app.route('/quote/<int:event_id>', methods=['GET','POST'])
def quote(event_id):
    ev = query_db('SELECT * FROM events WHERE id = ?', [event_id], one=True)
    if not ev:
        flash('Event not found')
        return redirect(url_for('events'))
    if request.method == 'POST':
        try:
            guests = int(request.form.get('guests','0') or 0)
        except ValueError:
            guests = 0
        contact_name = request.form.get('contact_name')
        contact_phone = request.form.get('contact_phone')
        services = request.form.getlist('services')
        add_info = request.form.get('additional_info','')

        # price calculation logic (example):
        base = ev['base_price'] * guests
        svc_prices = {
            'catering': 300 * guests,   # per guest
            'decoration': 5000,
            'sound': 4000,
            'photography': 7000,
            'permit': 2000
        }
        services_cost = sum(svc_prices.get(s, 0) for s in services)
        total = base + services_cost

        request_number = f"REQ-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"
        db = get_db()
        user_id = session.get('user_id')
        db.execute('INSERT INTO requests (request_number,user_id,event_id,guests,services,total_price,created_at,status,contact_name,contact_phone,additional_info) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                   (request_number, user_id, event_id, guests, ','.join(services), total, datetime.utcnow().isoformat(), 'NEW', contact_name, contact_phone, add_info))
        db.commit()
        return redirect(url_for('request_view', request_number=request_number))

    return render_template('quote_form.html', event=ev)

@app.route('/request/<request_number>')
def request_view(request_number):
    r = query_db('SELECT r.*, e.title as event_title FROM requests r LEFT JOIN events e ON r.event_id = e.id WHERE r.request_number = ?', [request_number], one=True)
    if not r:
        flash('Request not found')
        return redirect(url_for('events'))
    return render_template('request_view.html', req=r)

@app.route('/myrequests')
def my_requests():
    user_id = session.get('user_id')
    if not user_id:
        flash('Please sign in to see your requests')
        return redirect(url_for('signin'))
    rs = query_db('SELECT r.*, e.title as event_title FROM requests r LEFT JOIN events e ON r.event_id = e.id WHERE r.user_id = ? ORDER BY r.created_at DESC', [user_id])
    return render_template('my_requests.html', requests=rs)

if __name__ == '__main__':
    # For quick dev testing. Use gunicorn/nginx for production.
    app.run(host='0.0.0.0', port=8000, debug=True)
