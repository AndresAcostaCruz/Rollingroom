"""
Digital Humidor & Engagement Platform
====================================

This file defines a minimal Flask application implementing core
functionality for the Rolling Room digital humidor and engagement
platform.  The goal of this MVP (minimum viable product) is to
demonstrate how users can create accounts, register purchased
products, build a personal collection (their digital humidor), and
unlock badges based on their behaviour.  Retailers are also
represented and each registration is tied back to the store where
the item was purchased.  All information is stored in a local
SQLite database via SQLAlchemy.  A simple Bootstrap‑based user
interface is provided in the ``templates`` directory.

Key features implemented in this file:

* **User management** – sign up, log in, and log out.  Passwords
  are hashed using Werkzeug for security.  Session cookies keep
  track of authenticated users.
* **Product catalogue** – A small catalogue of products is seeded
  into the database on first run.  Each product represents a
  cannabis item manufactured by Rolling Room.
* **Product registration** – Users can register purchased products
  using a unique code printed on the packaging.  The code is
  single‑use; once consumed it cannot be reused.  Registrations
  record the user, the product, the retailer where it was bought
  and the timestamp.
* **Digital humidor** – When a product is registered it appears in
  the user’s personal collection.  The dashboard shows all items
  registered by the account along with basic details.
* **Badges** – A basic gamification layer awards badges when
  thresholds are reached.  For example, registering your first
  product grants the ``First Flame`` badge.  The badge logic can
  easily be extended for more complex behaviours (collecting a
  series, attending an event, etc.).
* **Retailer attribution** – Each registration links back to a
  retailer record.  The dashboard tallies registrations by store
  and displays leaderboards for top performing retailers and
  consumers.  These metrics can help drive retailer incentive
  programmes and community engagement.

This code is meant to be run locally for demonstration purposes.
To start the application install the dependencies (see the
``requirements.txt`` file) and run:

    FLASK_APP=app.py flask run

Then visit http://localhost:5000/ in your browser.

Note: For a production system you would want to extend this
codebase with robust error handling, input validation, email
confirmation flows, secure session management, access control for
admin/retailer dashboards, and a comprehensive front‑end built
with a modern JavaScript framework.  The intent here is to
provide a clear, concise reference implementation rather than a
complete product.
"""

from __future__ import annotations

import os
from datetime import datetime

from flask import (
    Flask, render_template, redirect, url_for, request, flash,
    session
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

# -----------------------------------------------------------------------------
# Application configuration
#
# A random secret key should be set in production.  For demonstration
# purposes we derive the secret from an environment variable or use a
# fallback constant.  SQLAlchemy is configured to use a local SQLite
# database stored in the ``instance`` folder.  Flask will create this
# directory automatically.

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'change-me-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///rollingroom.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


# -----------------------------------------------------------------------------
# Database models
#
# These classes define the tables used by the application.  Each model
# corresponds to a table in the SQLite database.  SQLAlchemy handles
# object–relational mapping (ORM) for us, allowing Python objects to be
# persisted and queried easily.

class User(db.Model):
    """Registered consumer of the platform."""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    # Role defines whether this is a consumer or a retailer staff.  The default
    # is ``consumer``.  Retailers have separate accounts so they can access
    # store dashboards.  See the ``RetailerAccount`` model below for the
    # mapping between retailers and accounts.
    role = db.Column(db.String(20), default='consumer')
    # Points are awarded for verified registrations and engagement events.
    points = db.Column(db.Integer, default=0)
    registrations = db.relationship('Registration', backref='user', lazy=True)
    badges = db.relationship('UserBadge', backref='user', lazy=True)

    experience_logs = db.relationship('ExperienceLog', backref='user', lazy=True)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Retailer(db.Model):
    """Retailer (dispensary) where products are sold."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    registrations = db.relationship('Registration', backref='retailer', lazy=True)

    # Retailer accounts allow store staff or ambassadors to log in and
    # view store-specific dashboards.  Each account points back to the
    # underlying retailer record.
    accounts = db.relationship('RetailerAccount', backref='retailer', lazy=True)


class Product(db.Model):
    """Cannabis product manufactured by Rolling Room."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    sku = db.Column(db.String(64), unique=True, nullable=False)
    series = db.Column(db.String(120), nullable=True)
    description = db.Column(db.Text, nullable=True)
    registrations = db.relationship('Registration', backref='product', lazy=True)


class Registration(db.Model):
    """A verified registration of a purchased product by a user."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    retailer_id = db.Column(db.Integer, db.ForeignKey('retailer.id'), nullable=False)
    code = db.Column(db.String(64), unique=True, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


class Badge(db.Model):
    """A collectible badge that can be earned by users."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)


class UserBadge(db.Model):
    """Association table linking users to badges they have earned."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    badge_id = db.Column(db.Integer, db.ForeignKey('badge.id'), nullable=False)
    awarded_at = db.Column(db.DateTime, default=datetime.utcnow)
    badge = db.relationship('Badge', lazy=True)


class RetailerAccount(db.Model):
    """Credentials for retailer staff to access store dashboards."""
    id = db.Column(db.Integer, primary_key=True)
    retailer_id = db.Column(db.Integer, db.ForeignKey('retailer.id'), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class ExperienceLog(db.Model):
    """Private structured logging of a product experience."""
    id = db.Column(db.Integer, primary_key=True)
    registration_id = db.Column(db.Integer, db.ForeignKey('registration.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    enjoyed_at = db.Column(db.DateTime, default=datetime.utcnow)
    location = db.Column(db.String(120), nullable=True)
    session_duration = db.Column(db.String(120), nullable=True)  # e.g. "Long Sesh", "Short" etc.
    group_type = db.Column(db.String(50), nullable=True)  # solo/shared
    smoothness = db.Column(db.Integer, nullable=True)  # scale 1-5
    notes = db.Column(db.Text, nullable=True)
    registration = db.relationship('Registration', lazy=True)


# -----------------------------------------------------------------------------
# Helper functions

def award_badges(user: User) -> None:
    """Assign badges to a user based on their behaviour.

    This function examines the number of products the user has
    registered and awards badges when certain thresholds are reached.
    Additional badge logic can be inserted here (e.g. series
    completions, event participation, care access engagements).
    """
    reg_count = Registration.query.filter_by(user_id=user.id).count()

    # Badge for first product registration
    first_flame = Badge.query.filter_by(name='First Flame').first()
    if reg_count >= 1 and first_flame:
        if not UserBadge.query.filter_by(user_id=user.id, badge_id=first_flame.id).first():
            db.session.add(UserBadge(user_id=user.id, badge_id=first_flame.id))
            flash('Congratulations! You earned the First Flame badge!', 'success')

    # Badge for 5 products
    five_sesh = Badge.query.filter_by(name='5G Society').first()
    if reg_count >= 5 and five_sesh:
        if not UserBadge.query.filter_by(user_id=user.id, badge_id=five_sesh.id).first():
            db.session.add(UserBadge(user_id=user.id, badge_id=five_sesh.id))
            flash('You are now part of the 5G Society!', 'success')

    # Badge for collecting all products in a series
    # For each series present in the catalogue, check if user has at least one
    # registration for every product in that series.  Award once per series.
    all_series = db.session.query(Product.series).distinct().all()
    for (series,) in all_series:
        if series:
            products_in_series = Product.query.filter_by(series=series).all()
            # skip if there are no products in this series (shouldn't happen)
            if not products_in_series:
                continue
            # Count how many of the products the user has registered
            user_product_ids = set(r.product_id for r in user.registrations if r.product.series == series)
            if len(user_product_ids) == len(products_in_series):
                badge_series = Badge.query.filter_by(name='Series Collector').first()
                if badge_series and not UserBadge.query.filter_by(user_id=user.id, badge_id=badge_series.id).first():
                    db.session.add(UserBadge(user_id=user.id, badge_id=badge_series.id))
                    flash(f'You completed {series}! Series Collector badge awarded.', 'success')

    # Badge for multi-store explorer: registered products across 3 unique retailers
    unique_retailers = {r.retailer_id for r in user.registrations}
    if len(unique_retailers) >= 3:
        multi_store_badge = Badge.query.filter_by(name='Multi-Store Explorer').first()
        if multi_store_badge and not UserBadge.query.filter_by(user_id=user.id, badge_id=multi_store_badge.id).first():
            db.session.add(UserBadge(user_id=user.id, badge_id=multi_store_badge.id))
            flash('You explored multiple retailers! Multi-Store Explorer badge awarded.', 'success')

    db.session.commit()


def award_points(user: User, amount: int, reason: str | None = None) -> None:
    """Add points to a user and optionally record the reason.

    Points are added to the user’s balance whenever they perform high signal
    actions such as verified product registrations, experience logs, or
    community engagements.  The ``reason`` argument is not persisted at
    present, but could be logged to an audit table for deeper analytics.
    """
    user.points += amount
    db.session.commit()
    flash(f'You earned {amount} points!', 'info')


# -----------------------------------------------------------------------------
# CLI commands
#
# These are Flask CLI commands for initializing the database and seeding
# some sample data.  You can run them from the command line with
# ``flask initdb`` and ``flask seed``.  This avoids having to write
# manual SQL.

@app.cli.command('initdb')
def initdb_command() -> None:
    """Create all database tables."""
    db.drop_all()
    db.create_all()
    print('Initialized the database.')


@app.cli.command('seed')
def seed_command() -> None:
    """Populate the database with seed data."""
    # Add some retailers
    retailers = ['Downtown Dispensary', 'Westside Cannabis', 'Mountain View Retail']
    for name in retailers:
        if not Retailer.query.filter_by(name=name).first():
            db.session.add(Retailer(name=name))

    # Add some products
    products = [
        ('TOPSHELF Munyunz 5g', 'TOP-001', 'Series 01'),
        ('100% Kief Series 01', 'TOP-002', 'Series 01'),
        ('Long Sesh Cultivar Drop', 'TOP-003', 'Series 02'),
        ('Premium Flower Series 1.5g', 'TOP-004', 'Series 02'),
    ]
    for name, sku, series in products:
        if not Product.query.filter_by(sku=sku).first():
            db.session.add(Product(name=name, sku=sku, series=series, description=f'{name} from {series}'))

    # Add some badges
    badges = [
        ('First Flame', 'Registered your first product'),
        ('5G Society', 'Registered five products'),
        ('Series Collector', 'Completed all products in a series'),
        ('Multi-Store Explorer', 'Registered products across three retailers'),
    ]
    for name, desc in badges:
        if not Badge.query.filter_by(name=name).first():
            db.session.add(Badge(name=name, description=desc))

    # Create a simple retailer account for demonstration (email: staff@example.com, password: password)
    first_retailer = Retailer.query.first()
    if first_retailer:
        if not RetailerAccount.query.filter_by(email='staff@example.com').first():
            acc = RetailerAccount(email='staff@example.com', retailer_id=first_retailer.id)
            acc.set_password('password')
            db.session.add(acc)

    db.session.commit()
    print('Seeded the database with retailers, products, and badges.')


# -----------------------------------------------------------------------------
# User authentication helpers

def current_user() -> User | None:
    """Return the currently logged in user, if any."""
    uid = session.get('user_id')
    if uid:
        return User.query.get(uid)
    return None

def current_retailer_account() -> RetailerAccount | None:
    """Return the currently logged in retailer account, if any."""
    acc_id = session.get('retailer_account_id')
    if acc_id:
        return RetailerAccount.query.get(acc_id)
    return None


@app.context_processor
def inject_globals():
    """Inject common functions and variables into all templates."""
    return dict(
        current_user=current_user(),
        current_retailer_account=current_retailer_account(),
    )


# -----------------------------------------------------------------------------
# Routes
#
# The following functions define the HTTP endpoints of the application.
# Each route returns an HTML page rendered from a Jinja2 template.  Some
# routes also handle form submissions (POST requests) and perform
# actions such as creating users or registering products.

@app.route('/')
def index():
    user = current_user()
    if user:
        return redirect(url_for('dashboard'))
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        if User.query.filter((User.username == username) | (User.email == email)).first():
            flash('Username or email already exists.', 'danger')
            return redirect(url_for('register'))
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            flash('Logged in successfully.', 'success')
            return redirect(url_for('dashboard'))
        flash('Invalid credentials.', 'danger')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))


@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    user = current_user()
    if not user:
        return redirect(url_for('login'))

    if request.method == 'POST':
        # Process product registration
        product_id = request.form.get('product_id')
        retailer_id = request.form.get('retailer_id')
        code = request.form.get('code').strip()

        # Validate inputs
        if not (product_id and retailer_id and code):
            flash('All fields are required.', 'danger')
            return redirect(url_for('dashboard'))

        if Registration.query.filter_by(code=code).first():
            flash('This code has already been registered.', 'danger')
            return redirect(url_for('dashboard'))

        try:
            registration = Registration(
                user_id=user.id,
                product_id=int(product_id),
                retailer_id=int(retailer_id),
                code=code,
            )
            db.session.add(registration)
            db.session.commit()
            # Award points for a successful verified registration
            award_points(user, amount=10, reason='Verified registration')
            award_badges(user)
            flash('Product registered successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error registering product: {e}', 'danger')

        return redirect(url_for('dashboard'))

    # GET request: display dashboard
    registrations = Registration.query.filter_by(user_id=user.id).order_by(Registration.timestamp.desc()).all()
    retailers = Retailer.query.all()
    products = Product.query.all()

    # Compute leaderboards
    top_retailers = (
        db.session.query(Retailer.name, db.func.count(Registration.id).label('count'))
        .join(Registration)
        .group_by(Retailer.id)
        .order_by(db.desc('count'))
        .limit(5)
        .all()
    )
    top_consumers = (
        db.session.query(User.username, db.func.count(Registration.id).label('count'))
        .join(Registration)
        .group_by(User.id)
        .order_by(db.desc('count'))
        .limit(5)
        .all()
    )

    user_badges = UserBadge.query.filter_by(user_id=user.id).all()

    return render_template(
        'dashboard.html',
        user=user,
        registrations=registrations,
        retailers=retailers,
        products=products,
        top_retailers=top_retailers,
        top_consumers=top_consumers,
        user_badges=user_badges,
        points=user.points,
    )


# -----------------------------------------------------------------------------
# Experience logging

@app.route('/experience/<int:registration_id>', methods=['GET', 'POST'])
def log_experience(registration_id: int):
    user = current_user()
    if not user:
        return redirect(url_for('login'))
    registration = Registration.query.get_or_404(registration_id)
    if registration.user_id != user.id:
        flash('You are not authorized to log this experience.', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        location = request.form.get('location')
        session_duration = request.form.get('session_duration')
        group_type = request.form.get('group_type')
        smoothness = request.form.get('smoothness')
        notes = request.form.get('notes')

        exp_log = ExperienceLog(
            registration_id=registration.id,
            user_id=user.id,
            location=location,
            session_duration=session_duration,
            group_type=group_type,
            smoothness=int(smoothness) if smoothness else None,
            notes=notes,
        )
        db.session.add(exp_log)
        db.session.commit()
        award_points(user, amount=5, reason='Logged experience')
        flash('Experience logged successfully!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('log_experience.html', registration=registration)


# -----------------------------------------------------------------------------
# Care access

@app.route('/care')
def care():
    """Display care-access categories and resources."""
    # In a real implementation these categories and links would be dynamic
    care_categories = [
        {
            'title': 'Mental Health Support',
            'description': 'Resources for stress, anxiety, and emotional well-being.',
            'links': [
                {'title': 'Wellness Together Canada', 'url': 'https://wellnesstogether.ca/en-CA'},
                {'title': 'CMHA', 'url': 'https://cmha.ca/'}
            ],
        },
        {
            'title': 'Veteran Services',
            'description': 'Support programmes for veterans and their families.',
            'links': [
                {'title': 'VAC Assistance Service', 'url': 'https://www.veterans.gc.ca/'}
            ],
        },
        {
            'title': 'Addiction Recovery',
            'description': 'Information and assistance for substance use and recovery.',
            'links': [
                {'title': 'Alberta Health Services', 'url': 'https://www.albertahealthservices.ca/'},
                {'title': 'Health Canada Resources', 'url': 'https://www.canada.ca/en/health-canada.html'},
            ],
        },
    ]
    return render_template('care.html', categories=care_categories)


# -----------------------------------------------------------------------------
# Simple AI assistant

@app.route('/assistant', methods=['GET', 'POST'])
def assistant():
    user = current_user()
    if not user:
        return redirect(url_for('login'))
    answer = None
    if request.method == 'POST':
        query = request.form.get('query', '').strip().lower()
        # Basic Q&A: match product names and return description
        matched_product = Product.query.filter(Product.name.ilike(f'%{query}%')).first()
        if matched_product:
            answer = matched_product.description
        else:
            # default fallback
            answer = "I'm sorry, I couldn't find information about that. Try asking about a product name."
    return render_template('assistant.html', answer=answer)


# -----------------------------------------------------------------------------
# Retailer account login and dashboard

@app.route('/retailer/login', methods=['GET', 'POST'])
def retailer_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        account = RetailerAccount.query.filter_by(email=email).first()
        if account and account.check_password(password):
            session['retailer_account_id'] = account.id
            flash('Retailer login successful.', 'success')
            return redirect(url_for('retailer_dashboard'))
        flash('Invalid retailer credentials.', 'danger')
    return render_template('retailer_login.html')


@app.route('/retailer/logout')
def retailer_logout():
    session.pop('retailer_account_id', None)
    flash('Retailer logged out.', 'info')
    return redirect(url_for('index'))


@app.route('/retailer/dashboard')
def retailer_dashboard():
    account = current_retailer_account()
    if not account:
        flash('Please log in as a retailer.', 'warning')
        return redirect(url_for('retailer_login'))
    retailer = account.retailer
    # Registrations for this retailer
    regs = Registration.query.filter_by(retailer_id=retailer.id).order_by(Registration.timestamp.desc()).all()
    # Top consumers by count within this store
    store_top_consumers = (
        db.session.query(User.username, db.func.count(Registration.id).label('count'))
        .join(Registration)
        .filter(Registration.retailer_id == retailer.id)
        .group_by(User.id)
        .order_by(db.desc('count'))
        .limit(5)
        .all()
    )
    return render_template('retailer_dashboard.html', account=account, retailer=retailer, registrations=regs, store_top_consumers=store_top_consumers)


# -----------------------------------------------------------------------------
# Error handlers

@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404


@app.errorhandler(500)
def server_error(error):
    return render_template('500.html'), 500


if __name__ == '__main__':
    app.run(debug=True)