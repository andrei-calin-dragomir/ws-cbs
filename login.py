import json
import base64
import hmac
import hashlib
import time
from flask import Flask, request, jsonify, g

app = Flask(__name__)
SECRET_KEY = "Rigel"  # Keep this secret and do not expose it

# In-memory storage for users: { username : password_hash}
users_db = {}

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password, password_hash):
    return hash_password(password) == password_hash

def generate_jwt(username):
    header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).decode().rstrip("=")
    payload = base64.urlsafe_b64encode(json.dumps({"username": username, "exp": int(time.time()) + 3600}).encode()).decode().rstrip("=")
    signature = base64.urlsafe_b64encode(hmac.new(SECRET_KEY.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()).decode().rstrip("=")
    return f"{header}.{payload}.{signature}"

def verify_jwt(token):
    try:
        header, payload, signature = token.split(".")
        expected_signature = base64.urlsafe_b64encode(hmac.new(SECRET_KEY.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()).decode().rstrip("=")
        if signature != expected_signature:
            return None
        data = json.loads(base64.urlsafe_b64decode(payload + "==").decode())
        if data["exp"] < time.time():
            return None  # Token expired
        return data["username"]
    except Exception:
        return None

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

@app.route("/users/login", methods=["POST"])
def login_user():
    data = request.json
    username, password = data.get("username"), data.get("password")
    if username not in users_db or not verify_password(password, users_db[username]):
        return jsonify({"error": "Invalid username or password"}), 403
    token = generate_jwt(username)
    return jsonify({"token": token}), 200

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
