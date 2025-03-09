# Initialization code based on the Flask application setup: https://flask.palletsprojects.com/en/stable/quickstart/
import os
import re
import json
import time
import hmac
import string
import random
import base64
import hashlib
import requests
import psycopg2
import threading
from datetime import datetime
from logging.config import dictConfig
from flask import Flask, request, abort, jsonify, g

#############################################################
#              HOW DOES THE URL SHORTNER WORK?
#############################################################

# How the URL Shortening Process is Working:

# 1. User submits a long URL via a POST request (along with optional expiry time and custom short ID)
# 2. If a custom short ID is provided, we check if its available and store the URL under that ID
# 3. If no custom ID is provided, we generate a random 6 character short ID using Base62 encoding
# 4. We check for uniqueness by making sure the generated ID is not in use already
# 5. The mapping (short ID to original URL) is stored in a memory dictionary
# 6. The user gets the shortened URL as a response

# How the short URL is used:
# 1. A GET request fetches the original URL using the short ID
# 2. If the link has expired, it is deleted and error is returned
# 3. If the link is valid, the user gets the original URL as a response

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

#############################################################
#               DATA STORAGE & CONFIGURATION
#############################################################

# Memory storage for URL mappings
# 'id' : {'url', 'expiry_time'} pairs

# Get database connection URL from environment variables
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://grp331:Group33@localhost/url_shortener_db")

# Function to establish a database connection
def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def create_tables():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS urls (
                    id SERIAL PRIMARY KEY,
                    short_id TEXT UNIQUE NOT NULL,
                    original_url TEXT NOT NULL,
                    username TEXT NOT NULL REFERENCES users(username) ON DELETE CASCADE,
                    expiry_time BIGINT NULL
                );
            """)
            conn.commit()

SECRET_KEY = "Rigel"  # Secret key used for signing JWT tokens (must match with login.py)

# Regular expression for validating proper URL formats (only URLs starting with http or https)
URL_REGEX = re.compile(r'^(http|https)://[^ "<>]*$')

# Set of characters containing 26 lowercase letters (a-z) + 26 uppercase letters (A-Z) + 10 digits (0-9)
BASE62 = string.ascii_letters + string.digits

# JWT Secret Key (Must match authentication service)
AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL")

#############################################################
#  Verify the JWT token by making a request
#  to the authentication service login.py. If it's
#  valid, return the username. Otherwise return None
#############################################################
def verify_jwt(token):
    try:
        # Manually decode JWT token
        header, payload, signature = token.split(".")

        # Validate the signature using HMAC
        expected_signature = base64.urlsafe_b64encode(
            hmac.new(SECRET_KEY.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
        ).decode().rstrip("=")

        if signature != expected_signature:
            app.logger.info("Invalid JWT signature")
            return None  # Invalid signature

        # Decode payload and check expiration time
        decoded_payload = json.loads(base64.urlsafe_b64decode(payload + "==").decode())

        if decoded_payload["exp"] < time.time():
            app.logger.info("Token has expired")
            return None  # Token expired

        username = decoded_payload["username"]

        #############################################################
        #  Verify if the token exists in PostgreSQL instead of SESSION_STORE
        #############################################################
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT token FROM sessions WHERE username = %s", (username,))
                result = cur.fetchone()

                if not result:
                    app.logger.info(f"User '{username}' not found in database sessions")
                    return None  # User session not found

                stored_token = result[0]
                if stored_token != token:
                    app.logger.info(f"Token mismatch! Stored: {stored_token}, Provided: {token}")
                    return None  # Token has been replaced or invalidated

        app.logger.info(f"Token is valid for user: {username}")
        return username
    except Exception as e:
        app.logger.info(f"Exception in verify_jwt(): {str(e)}")
        return None  # Invalid token


#############################################################
# Middleware to authenticate incoming requests. Ensures
# that users are authenticated before accessing protected routes
#############################################################
@app.before_request
def authenticate_request():
    app.logger.info(f"Incoming request: {request.method} {request.path}")

    token = request.headers.get("Authorization")
    if not token:
        app.logger.info("Missing Authorization header")
        return jsonify({"error": "Missing token"}), 403

    #############################################################
    #  Verify JWT token using PostgreSQL instead of in-memory store
    #############################################################
    username = verify_jwt(token.replace("Bearer ", ""))
    if not username:
        app.logger.info("Invalid or expired token")
        return jsonify({"error": "Invalid or expired token"}), 403

    app.logger.info(f"Authenticated User: {username}")
    g.username = username  # Store authenticated user globally

    #############################################################
    #  Ensure user has an entry in the database (Previously URL_Mappings)
    #############################################################
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Check if the user exists in the database (Optional, but ensures data consistency)
            cur.execute("SELECT 1 FROM users WHERE username = %s", (username,))
            user_exists = cur.fetchone()

            if not user_exists:
                app.logger.info(f"User {username} does not exist in users table (Unexpected scenario)")
                return jsonify({"error": "User authentication error"}), 500

    app.logger.info(f"User {username} is verified in the database.")


#############################################################
#               SAFETY & VALIDITY CHECKS
#############################################################
def is_valid_url(url) -> bool:
    if url and URL_REGEX.match(url):
        return True
    return False

def is_id_available(id) -> bool:
    #############################################################
    #  Check if the short_id is already present in PostgreSQL
    #############################################################
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM urls WHERE short_id = %s", (id,))
            result = cur.fetchone()

    return result is None  # Returns True if ID is available, False otherwise


#############################################################
#                GENERATE RANDOM SHORT ID
#############################################################
#    Generates a random Base62 short ID with the specified length
#    Base62 encoding uses: 26 lowercase letters (a-z) + 26 uppercase letters (A-Z) + 10 digits (0-9)
#    This provides a total of 62 possible characters

#    Example:
#    Random 6-character ID could be "A1b2C3"
#    With 62^6 possible combinations (~56 billion) chances of repetition are very low.
#    However, to mitigate a potential collision, we verify the availability of the generated ID and then try regeneration.
#############################################################
def generate_short_id(length=6):
    id = ''.join(random.choices(BASE62, k=length))
    if is_id_available(id):
        return id
    return generate_short_id(length)

#############################################################
#       BASE URL MAPPINGS HANDLER (GET/DELETE METHODS)
#############################################################
#    This function covers the following functionality over the mappings present in memory
#       1. The GET method returns all the short IDs present in memory;
#       2. The DELETE method empties the memory of any mappings present.
#############################################################
@app.route("/", methods=["GET", "DELETE"])
def base_handler():
    if not hasattr(g, "username"):
        return jsonify({"error": "Unauthorized access"}), 403

    #############################################################
    #  GET: Retrieve all short IDs for the authenticated user
    #############################################################
    if request.method == "GET":
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT short_id FROM urls WHERE username = %s", (g.username,))
                mappings = [row[0] for row in cur.fetchall()]

        return jsonify({"value": mappings if mappings else None}), 200

    #############################################################
    #  DELETE: Remove all shortened URLs for the authenticated user
    #############################################################
    elif request.method == "DELETE":
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM urls WHERE username = %s", (g.username,))
                conn.commit()

        return "", 404

    
#############################################################
#       BASE URL ENTRY HANDLER (GET/DELETE METHODS)
#############################################################
#       The path specifier enforces that, in order for this case to be applicable, the unique_id must be present in the url. 
#       Otherwise, the request is handled by the base_handler()
#       This function covers the following functionality over a specific entry in the mappings:
#           1. The GET method returns all the short IDs present in memory;
#           2. The DELETE method empties the memory of any mappings present.
#############################################################
@app.route("/<string:id>", methods=["GET", "DELETE"])
def base_entry_handler(id):
    #############################################################
    #  Check if the requested URL belongs to the authenticated user
    #############################################################
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT original_url FROM urls WHERE short_id = %s AND username = %s", (id, g.username))
            result = cur.fetchone()

            if not result:
                return jsonify({"error": "Unauthorized Access or Short URL not found"}), 403

            original_url = result[0]

    #############################################################
    #  GET: Return the original URL
    #############################################################
    if request.method == "GET":
        return jsonify({"value": original_url}), 301

    #############################################################
    #  DELETE: Remove the shortened URL from the database
    #############################################################
    elif request.method == "DELETE":
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM urls WHERE short_id = %s AND username = %s", (id, g.username))
                conn.commit()

        return "", 204


#############################################################
#              CREATE SHORT URL (POST METHOD)
#############################################################
#    Creates a short URL with an optional custom short ID and expiry time.
#    BONUS Implementations:
#       1. User can define a custom short ID that can be assigned instead of the random one generated by BASE62 encoding;
#       2. User can set an expiry time for the shortened URL. It does not have an expiry time by default or if not set.
#    Request JSON format:
#    {
#        "value": "original URL",
#        "custom_id": "custom short id",  # Optional 
#        "expiry_time": "YYYY-MM-DD HH:MM:SS"  # Optional
#    }
#############################################################
@app.route("/", methods=["POST"])
def shorten_url():
    data: dict = request.json
    long_url = data.get("value", None)
    custom_id = data.get("custom_id", None)
    expiry_time = data.get("expiry_time", None)

    try:
        if not long_url:
            raise KeyError("URL is missing from request.", 400)

        if not is_valid_url(long_url):
            raise ValueError("Bad URL format", 400)

        #############################################################
        #  If a custom ID is provided, check availability in PostgreSQL
        #############################################################
        short_id = custom_id if custom_id else generate_short_id()

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                if custom_id:
                    cur.execute("SELECT 1 FROM urls WHERE short_id = %s", (custom_id,))
                    if cur.fetchone():
                        raise ValueError(f"Custom ID already taken: {custom_id}", 409)

                #############################################################
                #  If no custom ID is provided, check if the URL already exists
                #############################################################
                else:
                    cur.execute("SELECT short_id FROM urls WHERE original_url = %s AND username = %s",
                                (long_url, g.username))
                    existing_url = cur.fetchone()
                    if existing_url:
                        raise ValueError(f"Provided URL is already present under ID: {existing_url[0]}", 409)

                #############################################################
                #  Convert expiry date to UNIX timestamp if provided
                #############################################################
                expiry_timestamp = None
                if expiry_time:
                    try:
                        expiry_timestamp = float(datetime.strptime(expiry_time, "%Y-%m-%d %H:%M:%S").timestamp())
                    except ValueError:
                        raise ValueError("Invalid date format. Use 'YYYY-MM-DD HH:MM:SS'", 400)

                #############################################################
                #  Store the URL under the authenticated user in PostgreSQL
                #############################################################
                cur.execute("""
                    INSERT INTO urls (short_id, original_url, username, expiry_time)
                    VALUES (%s, %s, %s, %s)
                """, (short_id, long_url, g.username, expiry_timestamp))

                conn.commit()

        return jsonify({"id": short_id}), 201

    except (KeyError, ValueError) as e:
        return jsonify({"error": str(e.args[0])}), int(e.args[1])


#############################################################
#               UPDATE URL (PUT METHOD)
#############################################################
#    Updates a URL based on ID with a new URL
#    Request JSON format:
#    {
#        "url": "new url"
#    }
#    This implementation accepts both the url as:
#       1. A string
#       2. A JSON body
#############################################################

@app.route("/<string:id>", methods=["PUT"])
def update_entry_url(id):
    try:
        #############################################################
        #  Ensure the authenticated user owns the URL before updating
        #############################################################
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM urls WHERE short_id = %s AND username = %s", (id, g.username))
                url_exists = cur.fetchone()

                if not url_exists:
                    return jsonify({"error": "Unauthorized Access or Short URL not found"}), 403

        #############################################################
        #  Handle JSON payload safely
        #############################################################
        try:
            data = request.get_json()
        except Exception:
            data = json.loads(request.data.decode("utf-8") or "{}")

        new_url = data.get("url", None)
        if not new_url:
            raise ValueError("Missing 'url' in request body.", 400)

        # Validate new URL format
        if not is_valid_url(new_url):
            raise ValueError("Provided URL is not valid.", 400)

        #############################################################
        #  Update the URL in PostgreSQL
        #############################################################
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE urls 
                    SET original_url = %s 
                    WHERE short_id = %s AND username = %s
                """, (new_url, id, g.username))

                if cur.rowcount == 0:
                    return jsonify({"error": "Short URL not found or unauthorized"}), 404

                conn.commit()

        return jsonify({"message": "Update successful"}), 200

    except (KeyError, ValueError) as e:
        return jsonify({"error": str(e.args[0])}), int(e.args[1])

    
#############################################################
#         BONUS: UPDATE ID and TIMESTAMP (PATCH METHOD)
#############################################################
#    Updates a shortened URL or expiry time. 
#    At least one of these must be present in the request body.
#    Request JSON format:
#    {
#        "custom_id": "new short url"  # Optional
#        "expiry_time": "YYYY-MM-DD HH:MM:SS",  # Optional
#    }
#############################################################
@app.route("/<string:id>", methods=["PATCH"])
def update_url(id):
    try:
        #############################################################
        #  Ensure the authenticated user owns the URL before updating
        #############################################################
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT short_id FROM urls WHERE short_id = %s AND username = %s", (id, g.username))
                url_entry = cur.fetchone()

                if not url_entry:
                    raise KeyError("Unauthorized or URL not found.", 403)

        #############################################################
        #  Parse JSON request
        #############################################################
        data: dict = request.json
        new_expiry = data.get("expiry_time", None)
        new_custom_id = data.get("custom_id", None)

        if not new_custom_id and not new_expiry:
            raise ValueError("At least a new ID or a new expiry time must be provided.", 400)

        #############################################################
        #  Verify if the new custom ID is available
        #############################################################
        if new_custom_id and new_custom_id != id:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1 FROM urls WHERE short_id = %s", (new_custom_id,))
                    if cur.fetchone():
                        raise ValueError("Provided ID already taken.", 409)

        #############################################################
        #  Validate and convert expiry time
        #############################################################
        expiry_timestamp = None
        if new_expiry:
            try:
                expiry_timestamp = float(datetime.strptime(new_expiry, "%Y-%m-%d %H:%M:%S").timestamp())
            except ValueError:
                raise ValueError("Invalid date format. Use 'YYYY-MM-DD HH:MM:SS'", 400)

        #############################################################
        #  Perform updates in PostgreSQL
        #############################################################
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                if new_custom_id and new_custom_id != id:
                    # Update short_id and expiry_time together
                    cur.execute("""
                        UPDATE urls 
                        SET short_id = %s, expiry_time = %s
                        WHERE short_id = %s AND username = %s
                    """, (new_custom_id, expiry_timestamp, id, g.username))
                    id = new_custom_id  # Update reference to new ID
                else:
                    # Only update expiry_time if custom_id remains unchanged
                    cur.execute("""
                        UPDATE urls 
                        SET expiry_time = %s
                        WHERE short_id = %s AND username = %s
                    """, (expiry_timestamp, id, g.username))

                conn.commit()

        return jsonify({
            "message": "Updated successfully",
            "id": id,
            "expires_at": new_expiry
        }), 200

    except (KeyError, ValueError) as e:
        return jsonify({"error": str(e.args[0])}), int(e.args[1])


#############################################################
#               BONUS: AUTO CLEAN EXPIRED LINKS
#############################################################
def cleanup_expired_links():
    while True:
        time.sleep(600)  # Run every 10 minutes

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                #############################################################
                #  Delete all expired URLs in a single efficient query
                #############################################################
                cur.execute("""
                    DELETE FROM urls
                    WHERE expiry_time IS NOT NULL AND expiry_time < %s
                """, (time.time(),))

                deleted_rows = cur.rowcount  # Number of deleted entries
                conn.commit()

        if deleted_rows > 0:
            app.logger.info(f"Cleaned up {deleted_rows} expired links.")


if __name__ == "__main__":
    # Start auto cleanup thread
    cleanup_thread = threading.Thread(target=cleanup_expired_links, daemon=True)
    cleanup_thread.start()
    create_tables()
    app.run(host="0.0.0.0", port=5000, debug=True)


