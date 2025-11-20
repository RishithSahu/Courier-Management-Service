from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
from datetime import datetime
from zoneinfo import ZoneInfo
import smtplib
from email.message import EmailMessage
import traceback
import os
import secrets
import re
import json
from functools import wraps
from sqlalchemy import text

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)  # Generate a secure random key

# Load notification configuration from environment (optional)
app.config['SMTP_SERVER'] = os.environ.get('SMTP_SERVER')
app.config['SMTP_PORT'] = int(os.environ.get('SMTP_PORT')) if os.environ.get('SMTP_PORT') else None
app.config['SMTP_USERNAME'] = os.environ.get('SMTP_USERNAME')
app.config['SMTP_PASSWORD'] = os.environ.get('SMTP_PASSWORD')
app.config['SMTP_USE_TLS'] = os.environ.get('SMTP_USE_TLS') in ('1', 'true', 'True')
app.config['EMAIL_FROM'] = os.environ.get('EMAIL_FROM')
app.config['TWILIO_ACCOUNT_SID'] = os.environ.get('TWILIO_ACCOUNT_SID')
app.config['TWILIO_AUTH_TOKEN'] = os.environ.get('TWILIO_AUTH_TOKEN')
app.config['TWILIO_FROM_NUMBER'] = os.environ.get('TWILIO_FROM_NUMBER')

# Database configuration
# Use the mysqlconnector dialect so SQLAlchemy uses mysql-conne
# ctor-python (already installed).
# Note: URL-encode special characters in the password. The original password contained '@'.
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+mysqlconnector://root:root@localhost/courierdb'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Helper to get current time in IST (Asia/Kolkata)
def ist_now():
    return datetime.now(ZoneInfo('Asia/Kolkata'))


@app.context_processor
def inject_now():
    """Expose a `now()` helper to templates returning current IST datetime.

    Templates can call `now().year` (used in the footer) safely.
    """
    return {'now': lambda: ist_now()}


def luhn_check(card_number: str) -> bool:
    """Return True if card_number passes Luhn checksum. Expects digits-only string."""
    try:
        digits = [int(ch) for ch in card_number if ch.isdigit()]
    except Exception:
        return False
    if not digits:
        return False
    checksum = 0
    parity = len(digits) % 2
    for i, d in enumerate(digits):
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


def validate_expiry_server(expiry: str) -> bool:
    """Validate expiry in MM/YY or MM/YYYY format and ensure it's in the future (IST).

    Returns True if expiry is valid and in future.
    """
    if not expiry:
        return False
    parts = expiry.split('/')
    if len(parts) != 2:
        return False
    try:
        month = int(parts[0])
        year = int(parts[1])
    except ValueError:
        return False
    if month < 1 or month > 12:
        return False
    if year < 100:
        year += 2000

    # Compare using year/month tuples to avoid tz-aware vs naive datetime comparisons.
    # A card with expiry in the current month should still be considered valid (expires end of month),
    # so we treat expiry as valid when (year, month) >= (current_year, current_month).
    now = ist_now()
    try:
        return (year, month) >= (now.year, now.month)
    except Exception:
        # Fallback conservative behavior
        return False


# Notification configuration stored in the database so admins can manage credentials via UI
class NotificationConfig(db.Model):
    __tablename__ = 'Notification_config'
    id = db.Column(db.Integer, primary_key=True)
    smtp_server = db.Column(db.String(255))
    smtp_port = db.Column(db.Integer)
    smtp_username = db.Column(db.String(255))
    smtp_password = db.Column(db.Text)  # sensitive - restrict access via admin UI
    smtp_use_tls = db.Column(db.Boolean, default=True)
    email_from = db.Column(db.String(255))

    twilio_account_sid = db.Column(db.String(255))
    twilio_auth_token = db.Column(db.Text)
    twilio_from_number = db.Column(db.String(50))

def get_notification_settings(refresh=False):
    """Return a dict with notification configuration.

    Priority: cached DB config -> environment variables -> defaults (None).
    The result is cached on app.config['NOTIFY_CFG'] for performance.
    """
    if not refresh and app.config.get('NOTIFY_CFG'):
        return app.config['NOTIFY_CFG']

    cfg = {
        'SMTP_SERVER': os.environ.get('SMTP_SERVER'),
        'SMTP_PORT': int(os.environ.get('SMTP_PORT')) if os.environ.get('SMTP_PORT') else None,
        'SMTP_USERNAME': os.environ.get('SMTP_USERNAME'),
        'SMTP_PASSWORD': os.environ.get('SMTP_PASSWORD'),
        'SMTP_USE_TLS': os.environ.get('SMTP_USE_TLS') in ('1', 'true', 'True'),
        'EMAIL_FROM': os.environ.get('EMAIL_FROM'),
        'TWILIO_ACCOUNT_SID': os.environ.get('TWILIO_ACCOUNT_SID'),
        'TWILIO_AUTH_TOKEN': os.environ.get('TWILIO_AUTH_TOKEN'),
        'TWILIO_FROM_NUMBER': os.environ.get('TWILIO_FROM_NUMBER')
    }

    # If DB has a record, use its non-empty values to override env vars
    try:
        db_cfg = NotificationConfig.query.first()
        if db_cfg:
            if db_cfg.smtp_server:
                cfg['SMTP_SERVER'] = db_cfg.smtp_server
            if db_cfg.smtp_port:
                cfg['SMTP_PORT'] = db_cfg.smtp_port
            if db_cfg.smtp_username:
                cfg['SMTP_USERNAME'] = db_cfg.smtp_username
            if db_cfg.smtp_password:
                cfg['SMTP_PASSWORD'] = db_cfg.smtp_password
            if db_cfg.smtp_use_tls is not None:
                cfg['SMTP_USE_TLS'] = bool(db_cfg.smtp_use_tls)
            if db_cfg.email_from:
                cfg['EMAIL_FROM'] = db_cfg.email_from

            if db_cfg.twilio_account_sid:
                cfg['TWILIO_ACCOUNT_SID'] = db_cfg.twilio_account_sid
            if db_cfg.twilio_auth_token:
                cfg['TWILIO_AUTH_TOKEN'] = db_cfg.twilio_auth_token
            if db_cfg.twilio_from_number:
                cfg['TWILIO_FROM_NUMBER'] = db_cfg.twilio_from_number
    except Exception:
        app.logger.exception('Failed to read NotificationConfig from DB')

    # Cache for subsequent calls
    app.config['NOTIFY_CFG'] = cfg
    return cfg

def save_notification_settings(form_data):
    """Save provided settings into the DB (create or update the single config row).

    form_data should be a dict with keys matching NotificationConfig fields.
    """
    try:
        cfg = NotificationConfig.query.first()
        if not cfg:
            cfg = NotificationConfig()
            db.session.add(cfg)

        # Update fields only if present in form_data
        for key, attr in (
            ('SMTP_SERVER', 'smtp_server'),
            ('SMTP_PORT', 'smtp_port'),
            ('SMTP_USERNAME', 'smtp_username'),
            ('SMTP_PASSWORD', 'smtp_password'),
            ('SMTP_USE_TLS', 'smtp_use_tls'),
            ('EMAIL_FROM', 'email_from'),
            ('TWILIO_ACCOUNT_SID', 'twilio_account_sid'),
            ('TWILIO_AUTH_TOKEN', 'twilio_auth_token'),
            ('TWILIO_FROM_NUMBER', 'twilio_from_number'),
        ):
            if key in form_data:
                val = form_data.get(key)
                # type conversions
                if attr == 'smtp_port' and val:
                    try:
                        val = int(val)
                    except ValueError:
                        val = None
                if attr == 'smtp_use_tls':
                    val = True if form_data.get('SMTP_USE_TLS') in ('1', 'true', 'True', 'on') else False
                setattr(cfg, attr, val)

        db.session.commit()
        # Refresh cached config
        get_notification_settings(refresh=True)
        return True
    except Exception:
        db.session.rollback()
        app.logger.exception('Failed to save notification settings')
        return False


# Notification helpers
def send_email(to_address, subject, body):
    """Send email via configured SMTP server. If SMTP not configured, log the message."""
    cfg = get_notification_settings()
    smtp_server = cfg.get('SMTP_SERVER')
    smtp_port = cfg.get('SMTP_PORT')
    smtp_user = cfg.get('SMTP_USERNAME')
    smtp_pass = cfg.get('SMTP_PASSWORD')
    email_from = cfg.get('EMAIL_FROM') or smtp_user

    if not smtp_server or not smtp_port:
        app.logger.info('SMTP not configured, email to %s skipped. Subject: %s Body: %s', to_address, subject, body)
        return

    try:
        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = email_from
        msg['To'] = to_address
        msg.set_content(body)

        with smtplib.SMTP(smtp_server, smtp_port, timeout=10) as s:
            if app.config.get('SMTP_USE_TLS'):
                s.starttls()
            if smtp_user and smtp_pass:
                s.login(smtp_user, smtp_pass)
            s.send_message(msg)
        app.logger.info('Email sent to %s subject=%s', to_address, subject)
    except Exception:
        app.logger.exception('Failed to send email to %s', to_address)


def send_sms(phone_number, message):
    """Send SMS via Twilio if configured; otherwise log the message.

    Requires TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER in app.config.
    If twilio client is not installed or config missing, this will log only.
    """
    cfg = get_notification_settings()
    account_sid = cfg.get('TWILIO_ACCOUNT_SID')
    auth_token = cfg.get('TWILIO_AUTH_TOKEN')
    from_number = cfg.get('TWILIO_FROM_NUMBER')

    if not account_sid or not auth_token or not from_number:
        app.logger.info('SMS not configured, skipping SMS to %s. Message: %s', phone_number, message)
        return

    try:
        from twilio.rest import Client
    except Exception:
        app.logger.exception('Twilio package not available; cannot send SMS to %s', phone_number)
        return

    try:
        client = Client(account_sid, auth_token)
        client.messages.create(body=message, from_=from_number, to=phone_number)
        app.logger.info('SMS sent to %s', phone_number)
    except Exception:
        app.logger.exception('Failed to send SMS to %s', phone_number)


def notify_parties(courier, status, current_location=None, agent=None):
    """Notify sender and receiver about a courier status update via email and SMS.

    courier: Courier instance
    status: string status
    current_location: optional string
    agent: optional DeliveryAgent instance
    """
    try:
        when = ist_now().strftime('%Y-%m-%d %H:%M:%S %Z')
        subject = f'Courier Update: {courier.billno} is now {status}'
        details = [f'Bill No: {courier.billno}', f'Status: {status}', f'Time: {when}']
        if current_location:
            details.append(f'Location: {current_location}')
        details.append(f'Sender: {courier.sname} <{courier.semail}> | {courier.sphone}')
        details.append(f'Receiver: {courier.rname} <{courier.remail}> | {courier.rphone}')
        if agent:
            details.append('--- Delivery Agent Details ---')
            details.append(f'Name: {agent.name}')
            details.append(f'Email: {agent.email}')
            details.append(f'Phone: {agent.phone}')
        body = '\n'.join(details)

        # Send emails
        if courier.semail:
            send_email(courier.semail, subject, body)
        if courier.remail and courier.remail != courier.semail:
            send_email(courier.remail, subject, body)

        # Send SMS (shorter content)
        sms_msg = f'Courier {courier.billno}: {status} at {when}.'
        if agent and status == 'Out for Delivery':
            sms_msg += f' Agent: {agent.name} ({agent.phone}).'

        if courier.sphone:
            send_sms(courier.sphone, sms_msg)
        if courier.rphone and courier.rphone != courier.sphone:
            send_sms(courier.rphone, sms_msg)

    except Exception:
        app.logger.exception('Failed to notify parties for courier %s', getattr(courier, 'cid', 'unknown'))

# Models
class User(db.Model):
    __tablename__ = 'User'
    uid = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(50))
    phoneno = db.Column(db.String(20))
    aid = db.Column(db.Integer, db.ForeignKey('Admin.aid'))

class Admin(db.Model):
    __tablename__ = 'Admin'
    aid = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(50))
    phoneno = db.Column(db.String(20))

class Credentials(db.Model):
    __tablename__ = 'Credentials'
    email = db.Column(db.String(50), primary_key=True)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum('User', 'Admin'), nullable=False)
    uid = db.Column(db.Integer, db.ForeignKey('User.uid'))
    aid = db.Column(db.Integer, db.ForeignKey('Admin.aid'))

class Courier(db.Model):
    __tablename__ = 'Courier'
    cid = db.Column(db.Integer, primary_key=True)
    uid = db.Column(db.Integer, db.ForeignKey('User.uid'))
    semail = db.Column(db.String(50), nullable=False)
    remail = db.Column(db.String(50), nullable=False)
    sname = db.Column(db.String(50), nullable=False)
    rname = db.Column(db.String(50), nullable=False)
    sphone = db.Column(db.String(20), nullable=False)
    rphone = db.Column(db.String(20), nullable=False)
    saddress = db.Column(db.String(100), nullable=False)
    raddress = db.Column(db.String(100), nullable=False)
    weight = db.Column(db.Numeric(5,2), nullable=False)
    billno = db.Column(db.Integer, unique=True, nullable=False)
    courier_type = db.Column(db.Enum('Domestic', 'International'), default='Domestic')
    country = db.Column(db.String(50), default='India')
    date = db.Column(db.Date, nullable=False)
    agentid = db.Column(db.Integer, db.ForeignKey('Delivery_agent.agentid'))
    priceid = db.Column(db.Integer, db.ForeignKey('Courier_pricing.priceid'))
    # Relationships
    tracking = db.relationship('CourierTracking', backref='courier', lazy=True)
    payments = db.relationship('Payment', backref='courier', lazy=True)

class CourierTracking(db.Model):
    __tablename__ = 'Courier_tracking'
    trackid = db.Column(db.Integer, primary_key=True)
    cid = db.Column(db.Integer, db.ForeignKey('Courier.cid'), nullable=False)
    status = db.Column(db.String(50), nullable=False)
    current_location = db.Column(db.String(100))
    updated_at = db.Column(db.DateTime, default=ist_now)

class Payment(db.Model):
    __tablename__ = 'Payments'
    pid = db.Column(db.Integer, primary_key=True)
    cid = db.Column(db.Integer, db.ForeignKey('Courier.cid'), nullable=False)
    uid = db.Column(db.Integer, db.ForeignKey('User.uid'), nullable=False)
    amount = db.Column(db.Numeric(10,2), nullable=False)
    payment_mode = db.Column(db.Enum('Credit Card', 'Debit Card', 'UPI', 'Net Banking', 'Cash on Delivery'))
    payment_status = db.Column(db.Enum('Pending', 'Completed', 'Failed'), default='Pending')
    transaction_date = db.Column(db.DateTime, default=ist_now)

class CourierPricing(db.Model):
    __tablename__ = 'Courier_pricing'
    priceid = db.Column(db.Integer, primary_key=True)
    courier_type = db.Column(db.Enum('Domestic', 'International'), nullable=False)
    min_weight = db.Column(db.Numeric(5,2), default=0.00)
    max_weight = db.Column(db.Numeric(5,2), default=0.00)
    base_price = db.Column(db.Numeric(10,2), nullable=False)
    price_per_km = db.Column(db.Numeric(10,2), nullable=False)
    aid = db.Column(db.Integer, db.ForeignKey('Admin.aid'))

class DeliveryAgent(db.Model):
    __tablename__ = 'Delivery_agent'
    agentid = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(50), unique=True, nullable=False)
    phone = db.Column(db.String(20))
    assigned_area = db.Column(db.String(100))
    couriers = db.relationship('Courier', backref='delivery_agent', lazy=True)

# Authentication decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in first.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_role' not in session or session['user_role'] != 'Admin':
            flash('Admin access required.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def agent_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_role' not in session or session['user_role'] != 'Agent':
            flash('Delivery agent access required.', 'danger')
            return redirect(url_for('agent_login'))
        return f(*args, **kwargs)
    return decorated_function

# Routes
@app.route('/')
def index():
    # If a user is already logged in, send them to their role-specific home/dashboard
    if 'user_role' in session:
        role = session.get('user_role')
        if role == 'Admin':
            return redirect(url_for('admin_dashboard'))
        elif role == 'Agent':
            return redirect(url_for('agent_dashboard'))
        else:
            return redirect(url_for('dashboard'))
    # Public landing page for unauthenticated visitors
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    # Redirect if already logged in
    if 'user_id' in session:
        if session.get('user_role') == 'Admin':
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        credentials = Credentials.query.filter_by(email=email).first()
        
        if credentials and check_password_hash(credentials.password, password):
            if credentials.role == 'User':
                user = User.query.filter_by(email=email).first()
                session['user_id'] = user.uid
                session['user_email'] = user.email
                session['user_role'] = 'User'
                flash('Welcome back!', 'success')
                return redirect(url_for('dashboard'))
            else:
                admin = Admin.query.filter_by(email=email).first()
                session['user_id'] = admin.aid
                session['user_email'] = admin.email
                session['user_role'] = 'Admin'
                flash('Welcome back, Admin!', 'success')
                return redirect(url_for('admin_dashboard'))
        
        flash('Invalid email or password', 'danger')
    return render_template('login.html')


@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    """Separate admin login page with enhanced validation and security checks."""
    # Redirect if already logged in
    if 'user_id' in session:
        if session.get('user_role') == 'Admin':
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        if not email or not password:
            flash('Please provide both email and password', 'danger')
            return render_template('admin_login.html')

        credentials = Credentials.query.filter_by(email=email, role='Admin').first()
        
        # Debug: Print found credentials (remove in production)
        if credentials:
            print(f"Found credentials for {email}, checking password...")
            # For seeded admin accounts, the password might be plain text
            # Try both direct comparison and hash verification
            password_valid = (credentials.password == password or 
                            check_password_hash(credentials.password, password))
        else:
            print(f"No admin credentials found for {email}")
            password_valid = False
        
        # Check if this email exists but is a user account
        if not credentials and Credentials.query.filter_by(email=email, role='User').first():
            flash('This email is registered as a user account. Please use the regular login page.', 'warning')
            return render_template('admin_login.html')

        if credentials and password_valid:
            admin = Admin.query.filter_by(email=email).first()
            # This should always be true if credentials exist, but check for data integrity
            if not admin:
                flash('Admin account data inconsistency. Please contact support.', 'danger')
                return render_template('admin_login.html')
            
            # Clear any existing session data first
            session.clear()
            # Set admin session data
            session['user_id'] = admin.aid
            session['user_email'] = admin.email
            session['user_role'] = 'Admin'
            flash(f'Welcome back, {admin.name or "Admin"}!', 'success')
            return redirect(url_for('admin_dashboard'))
        
        # Generic error for security (don't reveal if email exists)
        flash('Invalid admin credentials', 'danger')
    return render_template('admin_login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        name = request.form['name']
        phone = request.form['phone']
        
        if Credentials.query.filter_by(email=email).first():
            flash('Email already registered', 'danger')
            return redirect(url_for('register'))
        
        # Create new user
        user = User(email=email, name=name, phoneno=phone)
        db.session.add(user)
        db.session.flush()  # To get the user id
        
        # Create credentials
        hashed_password = generate_password_hash(password)
        credentials = Credentials(email=email, password=hashed_password, role='User', uid=user.uid)
        db.session.add(credentials)
        
        try:
            db.session.commit()
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
        except:
            db.session.rollback()
            flash('Registration failed. Please try again.', 'danger')
            
    return render_template('register.html')

@app.route('/dashboard')
@login_required
def dashboard():
    if session['user_role'] == 'User':
        couriers = Courier.query.filter_by(uid=session['user_id']).all()
        return render_template('dashboard.html', couriers=couriers)
    return redirect(url_for('admin_dashboard'))

@app.route('/create_courier', methods=['GET', 'POST'])
@login_required
def create_courier():
    if request.method == 'POST':
        try:
            # Get and validate weight
            try:
                weight = float(request.form['weight'])
                if weight <= 0:
                    flash('Weight must be greater than 0', 'danger')
                    return render_template('create_courier.html')
                if weight > 50:  # Maximum weight limit of 50kg
                    flash('Weight exceeds maximum limit of 50kg. Please contact support for heavy shipments.', 'danger')
                    return render_template('create_courier.html')
            except ValueError:
                flash('Invalid weight value', 'danger')
                return render_template('create_courier.html')

            # Get form data
            courier_data = {
                'uid': session['user_id'],
                'semail': request.form['semail'],
                'remail': request.form['remail'],
                'sname': request.form['sname'],
                'rname': request.form['rname'],
                'sphone': request.form['sphone'],
                'rphone': request.form['rphone'],
                'saddress': request.form['saddress'],
                'raddress': request.form['raddress'],
                'weight': weight,
                'courier_type': request.form['courier_type'],
                'country': request.form['country'],
                'date': ist_now().date(),
                'billno': int(ist_now().timestamp())
            }

            # Validate price category exists for the weight
            price_category = db.session.query(CourierPricing).filter(
                CourierPricing.courier_type == courier_data['courier_type'],
                CourierPricing.min_weight <= courier_data['weight'],
                CourierPricing.max_weight >= courier_data['weight']
            ).first()

            if not price_category:
                flash('No pricing available for this weight category. Please contact support.', 'danger')
                return render_template('create_courier.html')

            amount = price_category.base_price

            # Create courier entry
            courier = Courier(**courier_data)
            courier.priceid = price_category.priceid
            db.session.add(courier)
            db.session.flush()  # obtain courier.cid

            # Create tracking entry (initial status Pending)
            tracking = CourierTracking(
                cid=courier.cid,
                status='Pending',
                current_location=courier_data['saddress'],
                updated_at=ist_now()
            )
            db.session.add(tracking)

            # Create a payment record with no payment_mode yet and Pending status
            payment = Payment(
                cid=courier.cid,
                uid=session['user_id'],
                amount=amount,
                payment_mode=None,
                payment_status='Pending'
            )
            db.session.add(payment)

            db.session.commit()
            db.session.refresh(courier)
            flash('Courier created successfully. Please complete payment to confirm the delivery.', 'success')
            # Notify sender/receiver about creation (Pending)
            try:
                notify_parties(courier, 'Pending', current_location=courier.saddress)
            except Exception:
                app.logger.exception('Notification failed after courier creation for %s', courier.cid)
            # Redirect to payment page for this courier
            return redirect(url_for('payment', courier_id=courier.cid))

        except Exception as e:
            db.session.rollback()
            flash('Error creating courier. Please try again.', 'danger')
            app.logger.exception('Error in create_courier: %s', e)

    return render_template('create_courier.html')

@app.route('/track_courier', methods=['GET', 'POST'])
def track_courier():
    """Show tracking info. Accepts either a POST form parameter 'tracking_number'
    or a GET query parameter 'tracking_number' so links can open the page
    pre-populated for a specific courier.
    """
    tracking_info = None

    # Allow tracking number via query string (e.g. ?tracking_number=1001) or POST form
    tracking_number = request.args.get('tracking_number')
    if not tracking_number and request.method == 'POST':
        tracking_number = request.form.get('tracking_number')

    if tracking_number:
        courier = Courier.query.filter_by(billno=tracking_number).first()
        if courier:
            tracking_info = CourierTracking.query.filter_by(cid=courier.cid).order_by(CourierTracking.updated_at.desc()).all()
        else:
            flash('Invalid tracking number', 'danger')

    return render_template('track_courier.html', tracking_info=tracking_info)

@app.route('/admin_dashboard')
@admin_required
def admin_dashboard():
    # Get couriers ordered by date in descending order (newest first)
    couriers = Courier.query.order_by(Courier.date.desc()).all()
    # Get users ordered by UID in descending order
    users = User.query.order_by(User.uid.desc()).all()
    # Get payments ordered by transaction date in descending order
    payments = Payment.query.order_by(Payment.transaction_date.desc()).all()
    # Get all delivery agents
    delivery_agents = DeliveryAgent.query.all()
    # Get unassigned couriers
    unassigned_couriers = Courier.query.filter_by(agentid=None).all()
    
    return render_template('admin_dashboard.html', 
                         couriers=couriers, 
                         users=users, 
                         payments=payments,
                         delivery_agents=delivery_agents,
                         unassigned_couriers=unassigned_couriers)

@app.route('/payment/<int:courier_id>', methods=['GET', 'POST'])
@login_required
def payment(courier_id):
    payment = Payment.query.filter_by(cid=courier_id).first()

    if not payment:
        flash('Payment record not found for this courier.', 'danger')
        return redirect(url_for('dashboard'))

    # Authorization: users can only pay for their own courier; admins may view all
    if session.get('user_role') != 'Admin' and payment.uid != session.get('user_id'):
        flash('You are not authorized to complete this payment.', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        chosen_mode = request.form.get('payment_mode')
        # Allowed modes must exactly match the ENUM values used in the DB
        allowed_modes = {'Credit Card', 'Debit Card', 'UPI', 'Net Banking', 'Cash on Delivery'}

        if not chosen_mode or chosen_mode not in allowed_modes:
            flash('Please select a valid payment method.', 'danger')
            return render_template('payment.html', payment=payment)

        # Update payment record safely
        try:
            # Server-side validation per payment mode to avoid spoofing client-side checks
            if chosen_mode in ('Credit Card', 'Debit Card'):
                # Accept digits-only card numbers (users don't need to provide grouping).
                raw_card = (request.form.get('card_number') or '').strip()
                expiry = (request.form.get('expiry') or '').strip()
                cvv = (request.form.get('cvv') or '').strip()

                # Strip any non-digit characters and validate length == 16
                card_number = re.sub(r'\D', '', raw_card)
                if len(card_number) != 16:
                    flash('Card number must contain exactly 16 digits.', 'danger')
                    return render_template('payment.html', payment=payment)

                # Keep expiry and CVV checks
                if not validate_expiry_server(expiry):
                    flash('Card expiry is invalid or the card has expired.', 'danger')
                    return render_template('payment.html', payment=payment)
                if not cvv.isdigit() or len(cvv) not in (3, 4):
                    flash('Invalid CVV.', 'danger')
                    return render_template('payment.html', payment=payment)

            elif chosen_mode == 'UPI':
                upi_id = (request.form.get('upi_id') or '').strip()
                # Basic UPI id pattern (local@bank / user@upi)
                if not re.match(r'^[\w.\-]+@[\w.\-]+$', upi_id):
                    flash('Invalid UPI ID format.', 'danger')
                    return render_template('payment.html', payment=payment)

            # For Net Banking and Cash on Delivery we accept the choice server-side

            # If validations pass, call stored procedure to mark payment completed and insert tracking.
            try:
                with db.engine.begin() as conn:
                    conn.execute(text("CALL sp_mark_payment_completed(:cid)"), {"cid": courier_id})
                flash('Payment completed successfully!', 'success')
                return redirect(url_for('dashboard'))
            except Exception as e:
                app.logger.exception('Stored procedure sp_mark_payment_completed failed: %s', e)
                flash('An error occurred while processing the payment. Please try again.', 'danger')
                return render_template('payment.html', payment=payment)
        except Exception as e:
            db.session.rollback()
            app.logger.exception('Error completing payment: %s', e)
            flash('An error occurred while processing the payment. Please try again.', 'danger')
            return render_template('payment.html', payment=payment)

    return render_template('payment.html', payment=payment)


@app.route('/agent_login', methods=['GET', 'POST'])
def agent_login():
    # Simple login for delivery agents
    if 'user_id' in session and session.get('user_role') == 'Agent':
        return redirect(url_for('agent_dashboard'))

    if request.method == 'POST':
        # Login via email + phone number (no password)
        email = request.form.get('email')
        phone = request.form.get('phone')
        agent = DeliveryAgent.query.filter_by(email=email).first()
        if agent and agent.phone and phone and agent.phone == phone:
            session.clear()
            session['user_id'] = agent.agentid
            session['user_email'] = agent.email
            session['user_role'] = 'Agent'
            flash(f'Welcome, {agent.name}!', 'success')
            return redirect(url_for('agent_dashboard'))
        flash('Invalid email or phone number for delivery agent.', 'danger')

    return render_template('agent_login.html')


@app.route('/agent_dashboard')
@agent_required
def agent_dashboard():
    agent_id = session.get('user_id')
    couriers = Courier.query.filter_by(agentid=agent_id).all()
    return render_template('agent_dashboard.html', couriers=couriers)


@app.route('/agent_mark_delivered/<int:courier_id>', methods=['POST'])
@agent_required
def agent_mark_delivered(courier_id):
    agent_id = session.get('user_id')
    courier = Courier.query.get_or_404(courier_id)
    if courier.agentid != agent_id:
        flash('You are not assigned to this courier.', 'danger')
        return redirect(url_for('agent_dashboard'))
    # Check if courier is already delivered (closed)
    last_tracking = CourierTracking.query.filter_by(cid=courier_id).order_by(CourierTracking.updated_at.desc()).first()
    if last_tracking and last_tracking.status == 'Delivered':
        flash('This courier has already been marked as Delivered (closed). Contact admin to reopen.', 'warning')
        return redirect(url_for('agent_dashboard'))

    try:
        tracking = CourierTracking(
            cid=courier_id,
            status='Delivered',
            current_location='Delivery Address',
            updated_at=ist_now()
        )
        db.session.add(tracking)
        db.session.commit()
        db.session.refresh(courier)
        agent = DeliveryAgent.query.get(agent_id)
        try:
            notify_parties(courier, 'Delivered', current_location='Delivery Address', agent=agent)
        except Exception:
            app.logger.exception('Notification failed after delivery for courier %s', courier_id)

        flash('Marked as delivered. Good job!', 'success')
    except Exception as e:
        db.session.rollback()
        app.logger.exception('Error marking delivered by agent %s: %s', agent_id, e)
        flash('Error marking courier as delivered.', 'danger')

    return redirect(url_for('agent_dashboard'))

@app.route('/assign_courier/<int:courier_id>', methods=['POST'])
@admin_required
def assign_courier(courier_id):
    """Assign a courier to a delivery agent and update its status."""
    agent_id = request.form.get('agent_id')
    
    if not agent_id:
        flash('Please select a delivery agent.', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    try:
        # Use stored procedure to assign agent and insert tracking if changed
        with db.engine.begin() as conn:
            conn.execute(text("CALL sp_assign_agent(:cid, :aid)"), {"cid": courier_id, "aid": int(agent_id)})
        # Refresh courier and notify parties from app side
        courier = Courier.query.get_or_404(courier_id)
        db.session.refresh(courier)
        agent = DeliveryAgent.query.get(int(agent_id))
        try:
            notify_parties(courier, 'Out for Delivery', current_location='Local Delivery Hub', agent=agent)
        except Exception:
            app.logger.exception('Notification failed after assigning courier %s to agent %s', courier_id, agent_id)
        flash('Courier successfully assigned to agent.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error assigning courier to agent.', 'danger')
        app.logger.exception('Error in assign_courier: %s', e)
    
    return redirect(url_for('admin_dashboard'))

@app.route('/logout')
def logout():
    """Clear session data and redirect to home."""
    was_admin = session.get('user_role') == 'Admin'
    session.clear()
    flash('You have been logged out successfully.', 'success')
    if was_admin:
        return redirect(url_for('admin_login'))
    return redirect(url_for('login'))


@app.route('/update_status/<int:courier_id>', methods=['POST'])
@admin_required
def update_status(courier_id):
    """Update the status of a courier (admin only).

    Expects form fields:
    - status: one of allowed statuses
    - current_location: optional string
    """
    # Admins can set these statuses; Delivered is reserved for delivery agents
    allowed_statuses = {'Pending', 'Out for Delivery', 'In Transit', 'Cancelled'}
    status = request.form.get('status')
    current_location = request.form.get('current_location') or 'Not specified'

    if not status or status not in allowed_statuses:
        flash('Invalid status selected.', 'danger')
        return redirect(url_for('admin_dashboard'))

    try:
        # Load the courier first so we can adjust assignment if needed
        courier = Courier.query.get_or_404(courier_id)

        # If admin sets status to Pending, unassign any currently assigned delivery agent
        if status == 'Pending' and courier.agentid is not None:
            app.logger.info('Admin set status to Pending - unassigning agent %s from courier %s', courier.agentid, courier_id)
            courier.agentid = None

        tracking = CourierTracking(
            cid=courier_id,
            status=status,
            current_location=current_location,
            updated_at=ist_now()
        )
        db.session.add(tracking)
        db.session.commit()
        db.session.refresh(courier)

        # After commit, agent should be None if we unassigned above
        agent = DeliveryAgent.query.get(courier.agentid) if courier.agentid else None
        try:
            notify_parties(courier, status, current_location=current_location, agent=agent)
        except Exception:
            app.logger.exception('Notification failed for status update %s on courier %s', status, courier_id)

        # Inform admin if an unassignment happened
        if status == 'Pending':
            flash(f'Courier status updated to "{status}". Any assigned agent (if present) was unassigned.', 'success')
        else:
            flash(f'Courier status updated to "{status}".', 'success')
    except Exception as e:
        db.session.rollback()
        app.logger.exception('Error updating status for courier %s: %s', courier_id, e)
        flash('Error updating courier status.', 'danger')

    return redirect(url_for('admin_dashboard'))


@app.route('/notify_test/<int:courier_id>')
@admin_required
def notify_test(courier_id):
    """Trigger notify_parties for a courier (admin-only). Useful for debugging email/SMS config.

    Query params:
      status - status string to send (default: Pending)
      loc - optional current_location string
    """
    courier = Courier.query.get_or_404(courier_id)
    status = request.args.get('status', 'Pending')
    current_location = request.args.get('loc')
    agent = DeliveryAgent.query.get(courier.agentid) if courier.agentid else None
    try:
        notify_parties(courier, status, current_location=current_location, agent=agent)
        msg = f'Notification triggered for courier {courier.billno} with status {status}'
        app.logger.info(msg)
        return msg, 200
    except Exception as e:
        app.logger.exception('notify_test failed for courier %s: %s', courier_id, e)
        return 'Notification failed; check server logs for details.', 500


@app.route('/admin/notify_test')
@admin_required
def admin_notify_test():
    """Admin-only test endpoint to exercise email/SMS sending.

    Usage (GET): /admin/notify_test?email=foo@bar.com&phone=+911234567890&message=Hello
    Returns JSON indicating whether sending was attempted. Only available to logged-in admins.
    """
    email = request.args.get('email')
    phone = request.args.get('phone')
    message = request.args.get('message', 'Test notification from Courier Management System')

    results = {'email': None, 'sms': None}
    if email:
        try:
            send_email(email, 'Test notification', message)
            results['email'] = 'sent'
        except Exception as e:
            app.logger.exception('admin_notify_test email failed: %s', e)
            results['email'] = f'error: {str(e)}'

    if phone:
        try:
            send_sms(phone, message)
            results['sms'] = 'sent'
        except Exception as e:
            app.logger.exception('admin_notify_test sms failed: %s', e)
            results['sms'] = f'error: {str(e)}'

    return jsonify(results)


@app.route('/admin/notification_config', methods=['GET', 'POST'])
@admin_required
def admin_notification_config():
    """Admin UI to view and update SMTP/Twilio notification settings stored in the DB."""
    if request.method == 'POST':
        # Collect form fields and save
        form_data = {
            'SMTP_SERVER': request.form.get('SMTP_SERVER'),
            'SMTP_PORT': request.form.get('SMTP_PORT'),
            'SMTP_USERNAME': request.form.get('SMTP_USERNAME'),
            'SMTP_PASSWORD': request.form.get('SMTP_PASSWORD'),
            'SMTP_USE_TLS': request.form.get('SMTP_USE_TLS'),
            'EMAIL_FROM': request.form.get('EMAIL_FROM'),
            'TWILIO_ACCOUNT_SID': request.form.get('TWILIO_ACCOUNT_SID'),
            'TWILIO_AUTH_TOKEN': request.form.get('TWILIO_AUTH_TOKEN'),
            'TWILIO_FROM_NUMBER': request.form.get('TWILIO_FROM_NUMBER')
        }
        ok = save_notification_settings(form_data)
        if ok:
            flash('Notification settings saved.', 'success')
        else:
            flash('Failed to save settings. Check server logs.', 'danger')
        return redirect(url_for('admin_notification_config'))

    # GET: prefill fields from current config
    cfg = get_notification_settings()
    return render_template('admin_notification_config.html', cfg=cfg)


@app.route('/admin/debug_config')
@admin_required
def admin_debug_config():
    """Return simple JSON showing whether SMTP and SMS (Twilio) configs are present.

    This is safe for admins to run: it does NOT return any secret values, only boolean
    indicators that the necessary config is set in app.config.
    """
    smtp_ok = bool(app.config.get('SMTP_SERVER') and app.config.get('SMTP_PORT'))
    sms_ok = bool(app.config.get('TWILIO_ACCOUNT_SID') and app.config.get('TWILIO_AUTH_TOKEN') and app.config.get('TWILIO_FROM_NUMBER'))
    email_from_set = bool(app.config.get('EMAIL_FROM'))
    return jsonify({
        'smtp_configured': smtp_ok,
        'sms_configured': sms_ok,
        'email_from_set': email_from_set
    })

if __name__ == '__main__':
    app.run(debug=True)