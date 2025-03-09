import os
import hmac
import time
import json
import base64
import hashlib
import psycopg2
from logging.config import dictConfig
from flask import Flask, request, jsonify, g

dictConfig({
    'version': 1,
    'formatters': {'default': {
        'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
    }},
    'handlers': {'wsgi': {
        'class': 'logging.StreamHandler',
        'stream': 'ext://flask.logging.wsgi_errors_stream',
        'formatter': 'default'
    }},
    'root': {
        'level': 'INFO',
        'handlers': ['wsgi']
    }
})

app = Flask(__name__)
SECRET_KEY = "Rigel"  # Secret key for signing JWT tokens

# Load DB URL from environment (set in docker-compose)
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://grp331:Group33@db/url_shortener_db")

# Function to connect to PostgreSQL
def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

# Tracking failed login attempts
FAILED_LOGINS = {}
LOCKOUT_THRESHOLD = 3 # Maximum failed login attempts before lockout
LOCKOUT_DURATION = 120 # Lockout time: 2 mins (120 secs)


def create_tables():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY,
                    password_hash TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    username TEXT PRIMARY KEY,
                    token TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS failed_logins (
                    username TEXT PRIMARY KEY,
                    attempts INTEGER DEFAULT 0,
                    lock_until BIGINT DEFAULT NULL
                );
            """)
            conn.commit()


#############################################################
#     MAYBE BONUS?: Hashing the password using SHA-256
#############################################################
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


#############################################################
#  Verifies that a password matches its stored SHA-256 hash
#############################################################
def verify_password(password, password_hash):
    return hash_password(password) == password_hash


#############################################################
#             Generating a JWT token manually
#############################################################
def generate_jwt(username):
    # Manually construct JWT
    header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).decode().rstrip("=")
    payload = base64.urlsafe_b64encode(json.dumps({"username": username, "exp": int(time.time()) + 3600}).encode()).decode().rstrip("=")
    signature = base64.urlsafe_b64encode(hmac.new(SECRET_KEY.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()).decode().rstrip("=")
    token = f"{header}.{payload}.{signature}"  # Constructing JWT manually

    # Store the manually created JWT in PostgreSQL instead of SESSION_STORE
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO sessions (username, token)
                VALUES (%s, %s)
                ON CONFLICT (username) DO UPDATE SET token = EXCLUDED.token;
            """, (username, token))
            conn.commit()

    app.logger.info(f"Token stored for {username}: {token}")
    return token


#############################################################
# Allows an authenticated user to update their password
# The user must provide the old password for verification
#############################################################
@app.route("/users", methods=["PUT"])
def change_password():
    token = request.headers.get("Authorization")
    if not token:
        return jsonify({"error": "Missing token"}), 403

    username = verify_jwt(token.replace("Bearer ", ""))
    if not username:
        return jsonify({"error": "Invalid or expired token"}), 403

    data = request.json
    old_password, new_password = data.get("old_password"), data.get("new_password")

    if not old_password or not new_password:
        return jsonify({"error": "Old and new passwords are required"}), 400

    #############################################################
    #  Verify old password from PostgreSQL instead of in-memory users_db
    #############################################################
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT password_hash FROM users WHERE username = %s", (username,))
            result = cur.fetchone()

            if not result or not verify_password(old_password, result[0]):
                return jsonify({"error": "Incorrect old password"}), 403

            # Update password with new hash in PostgreSQL
            new_password_hash = hash_password(new_password)
            cur.execute("UPDATE users SET password_hash = %s WHERE username = %s", (new_password_hash, username))

            # Invalidate old session to force re-login
            cur.execute("DELETE FROM sessions WHERE username = %s", (username,))
            conn.commit()

    return jsonify({"message": "Password changed successfully. Please log in again."}), 200


#############################################################
# BONUS: Logs out a user by removing their active
# session token
#############################################################
@app.route("/users/logout", methods=["POST"])
def logout():
    token = request.headers.get("Authorization")
    if not token:
        return jsonify({"error": "Missing token"}), 403

    username = verify_jwt(token.replace("Bearer ", ""))

    app.logger.info(f"Logging out user: {username}")

    #############################################################
    #  Fetch and display session state before logout
    #############################################################
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT token FROM sessions WHERE username = %s", (username,))
            session_exists = cur.fetchone() is not None  # Check if session exists

    app.logger.info(f"SESSION_STORE before logout: Exists in DB? {session_exists}")

    #############################################################
    #  Invalidate session in PostgreSQL instead of SESSION_STORE
    #############################################################
    if username and session_exists:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM sessions WHERE username = %s", (username,))
                conn.commit()

        app.logger.info("Token successfully removed from database")

    #############################################################
    #  Fetch and display session state after logout
    #############################################################
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT token FROM sessions WHERE username = %s", (username,))
            session_exists_after = cur.fetchone() is not None

    app.logger.info(f"SESSION_STORE after logout: Exists in DB? {session_exists_after}")

    return jsonify({"message": "Logged out successfully"}), 200


#############################################################
#    Verifies if a provided JWT token is valid and active
#############################################################
@app.route("/verify", methods=["GET"])
def verify_token():
    token = request.headers.get("Authorization")
    if not token:
        return jsonify({"error": "Missing token"}), 403

    username = verify_jwt(token.replace("Bearer ", ""))
    if not username:
        return jsonify({"error": "Invalid or expired token"}), 403

    return jsonify({"username": username}), 200


#############################################################
#  Verifies the JWT token by checking its signature,
#  expiry, and session activity
#############################################################
def verify_jwt(token):
    try:
        header, payload, signature = token.split(".")

        #############################################################
        #  Validate the signature manually (Base64 + HMAC)
        #############################################################
        expected_signature = base64.urlsafe_b64encode(
            hmac.new(SECRET_KEY.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
        ).decode().rstrip("=")

        if signature != expected_signature:
            app.logger.info("Invalid JWT signature")
            return None  # Invalid signature

        #############################################################
        #  Decode payload and check expiration time
        #############################################################
        decoded_payload = json.loads(base64.urlsafe_b64decode(payload + "==").decode())

        if decoded_payload["exp"] < time.time():
            app.logger.info("Token has expired")
            return None  # Token expired

        username = decoded_payload["username"]

        #############################################################
        #  Check if the token is still active in PostgreSQL instead of SESSION_STORE
        #############################################################
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT token FROM sessions WHERE username = %s", (username,))
                result = cur.fetchone()

        app.logger.info(f"SESSION_STORE during verification (DB check): Token exists? {bool(result)}")

        if not result:
            app.logger.info(f"User '{username}' not found in sessions database")
            return None  # User not logged in

        stored_token = result[0]
        if stored_token != token:
            app.logger.info(f"Token mismatch! Stored: {stored_token}, Provided: {token}")
            return None  # Token has been replaced or invalidated

        app.logger.info(f"Token is valid for user: {username}")
        return username
    except Exception as e:
        app.logger.info(f"Exception in verify_jwt: {str(e)}")
        return None  # Invalid token


#############################################################
#  Registers a new user by storing their username
#  and hashed password
#############################################################
@app.route("/users", methods=["POST"])
def register_user():
    data = request.json
    username, password = data.get("username"), data.get("password")

    if not username or not password:
        return jsonify({"error": "Missing username or password"}), 400

    hashed_password = hash_password(password)

    #############################################################
    #  Store new user in PostgreSQL instead of in-memory users_db
    #############################################################
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute("INSERT INTO users (username, password_hash) VALUES (%s, %s)", (username, hashed_password))
                conn.commit()
                return jsonify({"message": "User created successfully"}), 201
            except psycopg2.IntegrityError:
                conn.rollback()  # Prevent database issues
                return jsonify({"error": "Username already exists"}), 409


#############################################################
#  Authenticates a user and produces a JWT token if
#  creds are valid
#############################################################
@app.route("/users/login", methods=["POST"])
def login_user():
    app.logger.info("login_user() function triggered")

    data = request.json
    username, password = data.get("username"), data.get("password")

    app.logger.info(f"Login attempt for username: {username}")

    #############################################################
    # Account lockout after 3 failed attempts for 120 secs.
    #############################################################
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT attempts, lock_until FROM failed_logins WHERE username = %s", (username,))
            lock_data = cur.fetchone()

            if lock_data:
                attempts, lock_until = lock_data
                remaining_time = int((lock_until or 0) - time.time())

                if attempts >= LOCKOUT_THRESHOLD and remaining_time > 0:
                    app.logger.info(f"User {username} is locked out for {remaining_time} more seconds")
                    return jsonify({"error": f"Account temporarily locked. Try again in {remaining_time} seconds"}), 403

    #############################################################
    # Verify user credentials from PostgreSQL
    #############################################################
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT password_hash FROM users WHERE username = %s", (username,))
            result = cur.fetchone()

            if not result or not verify_password(password, result[0]):
                app.logger.info(f"Invalid login attempt for {username}")

                # Ensure the user exists in `failed_logins` and update accordingly
                cur.execute("""
                    INSERT INTO failed_logins (username, attempts, lock_until)
                    VALUES (%s, 1, %s)
                    ON CONFLICT (username) 
                    DO UPDATE SET attempts = failed_logins.attempts + 1, 
                    lock_until = CASE 
                        WHEN failed_logins.attempts + 1 >= %s THEN %s
                        ELSE failed_logins.lock_until
                    END;
                """, (username, time.time(), LOCKOUT_THRESHOLD, time.time() + LOCKOUT_DURATION))

                conn.commit()
                return jsonify({"error": "Invalid username or password"}), 403

            # Reset failed attempts on successful login
            cur.execute("DELETE FROM failed_logins WHERE username = %s", (username,))
            conn.commit()

    #############################################################
    # Generate JWT and return token
    #############################################################
    token = generate_jwt(username)
    return jsonify({"token": token}), 200


#############################################################
#   Method to ensure authentication is on protected route
#############################################################
@app.before_request
def authenticate_request():
    if request.path.startswith("/users") or request.path in ["/health", "/metrics"]:  # Skip authentication for user routes
        return
    token = request.headers.get("Authorization")
    if not token:
        return jsonify({"error": "Missing token"}), 403
    username = verify_jwt(token.replace("Bearer ", ""))
    if not username:
        return jsonify({"error": "Invalid or expired token"}), 403
    g.username = username  # Store the authenticated user globally


@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "healthy"}), 200


if __name__ == "__main__":
    create_tables()
    app.run(host="0.0.0.0", port=5001, debug=True)
