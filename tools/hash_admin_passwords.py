"""
One-off helper: hash seeded admin passwords in the Credentials table.

Usage (from project root d:\dbms\project\code):

    python tools\hash_admin_passwords.py

This script will:
 - import the Flask app and SQLAlchemy `db` from app.py
 - find all Credentials rows with role='Admin'
 - if the stored password doesn't look hashed (werkzeug default 'pbkdf2:' prefix), it will hash it
 - commit the changes and print a summary

IMPORTANT: Run this once. Do NOT run repeatedly unless you understand the stored passwords.
"""

import os
import sys
from werkzeug.security import generate_password_hash

# Ensure project root (one level up from tools/) is on sys.path so we can import app
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

try:
    from app import app, db, Credentials
except Exception as e:
    print('Error importing app from project root:', e)
    print('Make sure you run this script from the project root or use the provided instructions.')
    raise

def looks_hashed(pw: str) -> bool:
    # Werkzeug's generate_password_hash produces strings like 'pbkdf2:sha256:...'
    return isinstance(pw, str) and (pw.startswith('pbkdf2:') or pw.startswith('argon2:'))


def main():
    updated = []
    with app.app_context():
        admins = Credentials.query.filter_by(role='Admin').all()
        if not admins:
            print('No admin credentials found.')
            return
        for cred in admins:
            if cred.password is None:
                print(f"Skipping {cred.email}: empty password")
                continue
            if looks_hashed(cred.password):
                print(f"Already hashed: {cred.email}")
                continue
            # Hash and update
            old = cred.password
            cred.password = generate_password_hash(old)
            updated.append(cred.email)
        if updated:
            db.session.commit()
            print('Updated (hashed) the following admin emails:')
            for e in updated:
                print(' -', e)
        else:
            print('No admin passwords needed hashing.')

if __name__ == '__main__':
    main()
