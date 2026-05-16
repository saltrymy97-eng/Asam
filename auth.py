# auth.py
import hashlib
from database import get_conn

def hash_password(pwd):
    return hashlib.sha256(pwd.encode()).hexdigest()

def authenticate(username, password):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT role FROM users WHERE username=? AND password_hash=?", (username, hash_password(password)))
    row = cur.fetchone()
    conn.close()
    return row['role'] if row else None
