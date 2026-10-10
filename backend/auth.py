import sqlite3
import secrets
import hashlib
import hmac
from pathlib import Path
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request


# ==========================================
# DATABASE
# ==========================================

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

DATA_DIR.mkdir(exist_ok=True)

DATABASE = DATA_DIR / "users.db"


# ==========================================
# PASSWORD HASHING
# ==========================================

def hash_password(password: str, salt: bytes | None = None):
    """
    Securely hash a password using PBKDF2-HMAC-SHA256.
    """

    if salt is None:
        salt = secrets.token_bytes(16)

    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        200_000
    )

    return salt.hex(), password_hash.hex()


def verify_password(password: str, salt_hex: str, stored_hash: str):
    """
    Verify a password against the stored password hash.
    """

    salt = bytes.fromhex(salt_hex)

    _, password_hash = hash_password(
        password,
        salt
    )

    return hmac.compare_digest(
        password_hash,
        stored_hash
    )


# ==========================================
# SECURITY ANSWER HASHING
# ==========================================

def normalize_security_answer(answer: str) -> str:
    """Normalize answers so capitalization and extra spaces don't matter."""
    return " ".join(answer.strip().casefold().split())


def hash_security_answer(answer: str):
    """Hash a security answer using PBKDF2-HMAC-SHA256."""
    normalized_answer = normalize_security_answer(answer)

    salt = secrets.token_bytes(16)

    answer_hash = hashlib.pbkdf2_hmac(
        "sha256",
        normalized_answer.encode("utf-8"),
        salt,
        200_000
    )

    return salt.hex(), answer_hash.hex()


def verify_security_answer(
    answer: str,
    salt_hex: str,
    stored_hash: str
):
    """Verify a submitted security answer."""
    normalized_answer = normalize_security_answer(answer)

    salt = bytes.fromhex(salt_hex)

    answer_hash = hashlib.pbkdf2_hmac(
        "sha256",
        normalized_answer.encode("utf-8"),
        salt,
        200_000
    ).hex()

    return hmac.compare_digest(
        answer_hash,
        stored_hash
    )

# ==========================================
# DATABASE CONNECTION
# ==========================================

def get_connection():
    connection = sqlite3.connect(DATABASE)

    connection.row_factory = sqlite3.Row

    return connection


# ==========================================
# CREATE DATABASE TABLES
# ==========================================

def initialize_database():

    connection = get_connection()

    cursor = connection.cursor()

    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            password_salt TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    # Sessions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            expires_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)

    
    # Add security-question fields to existing databases.
    cursor.execute("PRAGMA table_info(users)")
    existing_columns = {
        row["name"] for row in cursor.fetchall()
    }

    if "security_question" not in existing_columns:
        cursor.execute("""
            ALTER TABLE users
            ADD COLUMN security_question TEXT
        """)

    if "security_answer_hash" not in existing_columns:
        cursor.execute("""
            ALTER TABLE users
            ADD COLUMN security_answer_hash TEXT
        """)

    if "security_answer_salt" not in existing_columns:
        cursor.execute("""
            ALTER TABLE users
            ADD COLUMN security_answer_salt TEXT
        """)

    connection.commit()

    connection.close()



def create_user(
    name: str,
    email: str,
    password: str,
    security_question: str,
    security_answer: str
):
    email = email.strip().lower()

    allowed_questions = {
        "What was the name of your first pet?",
        "What is the name of the city where you were born?",
        "What was your childhood nickname?",
        "What is the name of your favorite teacher?"
    }

    if security_question not in allowed_questions:
        raise ValueError("Please select a valid security question.")

    if len(normalize_security_answer(security_answer)) < 2:
        raise ValueError("Security answer must contain at least 2 characters.")

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            "SELECT id FROM users WHERE email = ?",
            (email,)
        )

        if cursor.fetchone():
            raise ValueError(
                "An account with this email already exists."
            )

        password_salt, password_hash = hash_password(password)

        answer_salt, answer_hash = hash_security_answer(
            security_answer
        )

        created_at = datetime.now(timezone.utc).isoformat()

        cursor.execute(
            """
            INSERT INTO users (
                name,
                email,
                password_hash,
                password_salt,
                created_at,
                security_question,
                security_answer_hash,
                security_answer_salt
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name.strip(),
                email,
                password_hash,
                password_salt,
                created_at,
                security_question,
                answer_hash,
                answer_salt
            )
        )

        connection.commit()
        return cursor.lastrowid

    finally:
        connection.close()


# ==========================================
# AUTHENTICATE USER
# ==========================================

def authenticate_user(
    email: str,
    password: str
):

    email = email.strip().lower()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM users
        WHERE email = ?
        """,
        (email,)
    )

    user = cursor.fetchone()

    connection.close()

    if not user:
        return None

    valid = verify_password(
        password,
        user["password_salt"],
        user["password_hash"]
    )

    if not valid:
        return None

    return user


# ==========================================
# CREATE LOGIN SESSION
# ==========================================

def create_session(user_id: int):

    token = secrets.token_urlsafe(48)

    expires_at = (
        datetime.now(timezone.utc)
        + timedelta(days=7)
    ).isoformat()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO sessions
        (token, user_id, expires_at)
        VALUES (?, ?, ?)
        """,
        (
            token,
            user_id,
            expires_at
        )
    )

    connection.commit()

    connection.close()

    return token


# ==========================================
# GET USER FROM SESSION
# ==========================================

def get_current_user(request: Request):

    token = request.cookies.get(
        "gridpulse_session"
    )

    if not token:
        return None

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            users.id,
            users.name,
            users.email,
            sessions.expires_at
        FROM sessions
        JOIN users
            ON users.id = sessions.user_id
        WHERE sessions.token = ?
        """,
        (token,)
    )

    user = cursor.fetchone()

    connection.close()

    if not user:
        return None

    expires_at = datetime.fromisoformat(
        user["expires_at"]
    )

    if expires_at < datetime.now(timezone.utc):

        delete_session(token)

        return None

    return user


# ==========================================
# DELETE SESSION
# ==========================================

def delete_session(token: str):

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        DELETE FROM sessions
        WHERE token = ?
        """,
        (token,)
    )

    connection.commit()

    connection.close()


# ==========================================
# REQUIRE LOGIN
# ==========================================

def require_user(request: Request):

    user = get_current_user(request)

    if not user:

        raise HTTPException(
            status_code=401,
            detail="Authentication required."
        )

    return user

# ==========================================
# FORGOT PASSWORD - GET SECURITY QUESTION
# ==========================================

def get_security_question(email: str):
    email = email.strip().lower()

    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            SELECT security_question
            FROM users
            WHERE email = ?
            """,
            (email,)
        )

        user = cursor.fetchone()

        if not user:
            return None

        return user["security_question"]

    finally:
        connection.close()


# ==========================================
# RESET PASSWORD USING SECURITY ANSWER
# ==========================================

def reset_password(
    email: str,
    security_answer: str,
    new_password: str
):
    email = email.strip().lower()

    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            SELECT
                id,
                security_answer_hash,
                security_answer_salt
            FROM users
            WHERE email = ?
            """,
            (email,)
        )

        user = cursor.fetchone()

        if not user:
            return False

        # Check that the account has a security answer
        if (
            not user["security_answer_hash"]
            or not user["security_answer_salt"]
        ):
            return False

        # Verify the supplied security answer
        answer_is_correct = verify_security_answer(
            security_answer,
            user["security_answer_salt"],
            user["security_answer_hash"]
        )

        if not answer_is_correct:
            return False

        # Hash the new password
        password_salt, password_hash = hash_password(
            new_password
        )

        # Update the password
        cursor.execute(
            """
            UPDATE users
            SET password_hash = ?,
                password_salt = ?
            WHERE id = ?
            """,
            (
                password_hash,
                password_salt,
                user["id"]
            )
        )

        # Invalidate existing login sessions
        cursor.execute(
            "DELETE FROM sessions WHERE user_id = ?",
            (user["id"],)
        )

        connection.commit()
        return True

    finally:
        connection.close()