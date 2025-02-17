import json
import base64
import hmac
import hashlib
import time
from flask import Flask, request, jsonify, g

app = Flask(__name__)
SECRET_KEY = "Rigel"  # Secret key for signing JWT tokens

# In-memory storage for users: { username : password_hash }
users_db = {}

# Stores active user sessions using JWT tokens { "username": "active_token" }
SESSION_STORE = {}

# Tracking failed login attempts
FAILED_LOGINS = {}
LOCKOUT_THRESHOLD = 3 # Maximum failed login attempts before lockout
LOCKOUT_DURATION = 120 # Lockout time: 2 mins (120 secs)

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
    header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).decode().rstrip("=")
    payload = base64.urlsafe_b64encode(json.dumps({"username": username, "exp": int(time.time()) + 3600}).encode()).decode().rstrip("=")
    signature = base64.urlsafe_b64encode(hmac.new(SECRET_KEY.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()).decode().rstrip("=")
    token = f"{header}.{payload}.{signature}"  # Constructing JWT manually

    SESSION_STORE[username] = token  # Store the active session
    print(f"SESSION_STORE after login: {SESSION_STORE}")
    return token


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

    print(f"Logging out user: {username}")
    print(f"SESSION_STORE before logout: {SESSION_STORE}")

    if username and username in SESSION_STORE:
        del SESSION_STORE[username]  # Invalidate session
        print("Token successfully removed from SESSION_STORE")

    print(f"SESSION_STORE after logout: {SESSION_STORE}")

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

        # Validate the signature
        expected_signature = base64.urlsafe_b64encode(
            hmac.new(SECRET_KEY.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
        ).decode().rstrip("=")

        if signature != expected_signature:
            print("Invalid JWT signature")
            return None  # Invalid signature

        decoded_payload = json.loads(base64.urlsafe_b64decode(payload + "==").decode())

        # Checking expiration
        if decoded_payload["exp"] < time.time():
            print("Token has expired")
            return None  # Token expired

        username = decoded_payload["username"]

        # Check if the token is still active in SESSION_STORE
        print(f"SESSION_STORE during verification: {SESSION_STORE}")

        if username not in SESSION_STORE:
            print(f"User '{username}' not found in SESSION_STORE")
            return None  # User not logged in

        if SESSION_STORE[username] != token:
            print(f"Token mismatch! Stored: {SESSION_STORE[username]}, Provided: {token}")
            return None  # Token has been replaced or invalidated

        print(f"Token is valid for user: {username}")
        return username
    except Exception as e:
        print(f"Exception in verify_jwt: {str(e)}")
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
    if username in users_db:
        return jsonify({"error": "Username already exists"}), 409
    users_db[username] = hash_password(password)
    return jsonify({"message": "User created successfully"}), 201


#############################################################
#  Authenticates a user and produces a JWT token if
#  creds are valid
#############################################################
@app.route("/users/login", methods=["POST"])
def login_user():
    print("login_user() function triggered")

    data = request.json
    username, password = data.get("username"), data.get("password")

    print(f"Login attempt for username: {username}")

########################################
# BONUS: Account lockout after
# 3 failed attempts for 120 secs.
########################################
    if username in FAILED_LOGINS:
        lock_data = FAILED_LOGINS[username]
        remaining_time = int(lock_data["lock_until"] - time.time())

        if lock_data["attempts"] >= LOCKOUT_THRESHOLD and remaining_time > 0:
            print(f"User {username} is locked out for {remaining_time} more seconds")
            return jsonify({"error": f"Account temporarily locked. Try again in {remaining_time} seconds"}), 403

    # Verify credentials
    if username not in users_db or not verify_password(password, users_db[username]):
        print(f"Invalid login attempt for {username}")

        if username not in FAILED_LOGINS:
            FAILED_LOGINS[username] = {"attempts": 1, "lock_until": 0}
        else:
            FAILED_LOGINS[username]["attempts"] += 1

            if FAILED_LOGINS[username]["attempts"] >= LOCKOUT_THRESHOLD:
                FAILED_LOGINS[username]["lock_until"] = time.time() + LOCKOUT_DURATION
                print(f"User {username} is now locked out until {FAILED_LOGINS[username]['lock_until']}")

        return jsonify({"error": "Invalid username or password"}), 403

    # Reset failed attempts on success
    if username in FAILED_LOGINS:
        del FAILED_LOGINS[username]

    token = generate_jwt(username)
    print(f"Login successful for {username}. Token issued.")
    return jsonify({"token": token}), 200


#############################################################
#   Method to ensure authentication is on protected route
#############################################################
@app.before_request
def authenticate_request():
    if request.path.startswith("/users"):  # Skip authentication for user routes
        return
    token = request.headers.get("Authorization")
    if not token:
        return jsonify({"error": "Missing token"}), 403
    username = verify_jwt(token.replace("Bearer ", ""))
    if not username:
        return jsonify({"error": "Invalid or expired token"}), 403
    g.username = username  # Store the authenticated user globally

if __name__ == "__main__":
    app.run(port=5001, debug=True)
