# Courier Management System

A lightweight Courier Management web application built with Flask, SQLAlchemy and MySQL. This project demonstrates role-based workflows for customers, admins, and delivery agents and includes tracking, payments (simulated), and notifications.

## Features

- User registration and login
- Create courier shipments (sender/receiver details, addresses, weight, type)
- Payment page with client-side and server-side validations (simulated payment)
- Admin dashboard to view couriers, assign agents, and see payments
- Agent dashboard to view assigned shipments and mark deliveries
- Courier tracking history in `Courier_tracking`
- Notification system (email/SMS) with DB-backed configuration and in-app fallback
- Stored procedures, functions, views, and triggers for consistent event handling

## Getting Started

Prerequisites
- Python 3.10+ (the project was developed using Python 3.11)
- MySQL server
- Recommended: virtual environment

1. Clone repository

```powershell
# from Windows PowerShell
git clone <repo-url> .
cd d:\dbms\project\code
```

2. Install dependencies

```powershell
pip install -r requirements.txt
```

If there is no `requirements.txt`, install the main packages:

```powershell
pip install flask sqlalchemy mysql-connector-python reportlab
```

3. Configure database

- Create a MySQL database named `courierdb` or update `app.config['SQLALCHEMY_DATABASE_URI']` in `app.py` with your credentials.
- Create tables by running the app once (the app uses SQLAlchemy models). Alternatively, use migrations if you add Alembic.

4. (Optional) Configure notification credentials

Set environment variables or use the Admin UI (`/admin/notification_config`) to configure SMTP/Twilio:

```powershell
$env:SMTP_SERVER='smtp.example.com'
$env:SMTP_PORT='587'
$env:SMTP_USERNAME='user'
$env:SMTP_PASSWORD='pass'
$env:EMAIL_FROM='no-reply@example.com'
$env:TWILIO_ACCOUNT_SID='..'
$env:TWILIO_AUTH_TOKEN='..'
$env:TWILIO_FROM_NUMBER='+1...'
```

5. Run the application

```powershell
python app.py
```

Open `http://127.0.0.1:5000` in a browser.

## Database objects of note
- Tables: `Courier`, `Courier_tracking`, `Payments`, `Delivery_agent`, `User`, `Admin`, `Credentials`, `Notification_config`
- Stored Procedures: `sp_mark_payment_completed`, `sp_assign_agent`
- Functions: `fn_payment_status`, `fn_last_tracking_status`
- Views: `vw_courier_summary`, `vw_agent_assignments`
- Triggers: `trg_payments_after_insert`, `trg_courier_after_update_agent` (created with dedupe logic)

## Running tests / manual checks
- Create a courier, check `Payments` row created and `Courier_tracking` initial Pending.
- On the payment page, enter a 16-digit card number and valid expiry — server will call `sp_mark_payment_completed` and you should see `Payment Received` in tracking.
- Assign an agent from admin dashboard — `sp_assign_agent` will be called and tracking will show assignment.

## Notes & Cautions
- Payments are simulated — do not store real card data. Integrate a PCI-compliant payment gateway for production use.
- Notification credentials are stored in DB; consider encrypting or using a secrets manager.
- If you change tracking logic, centralize it (either app procedures or triggers) to avoid duplication.

## Development notes
- Primary app file: `app.py`
- Templates: `templates/`
- Static: `static/`
- Report: `REPORT.md` and `REPORT.pdf`

## Future Improvements
- Real payment gateway integration
- Automated tests and CI
- Notification history UI
- Encrypt stored secrets or use a secrets manager

---

If you want, I can:
- Add `requirements.txt` (I can generate one from the environment),
- Add a `Procfile` or `Dockerfile` for deployment,
- Create a one-page project summary PDF optimized for submission.

Which would you like next? (I can also push these files into a Git branch or package the project.)