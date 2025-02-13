# Initialization code based on the Flask application setup: https://flask.palletsprojects.com/en/stable/quickstart/
from flask import Flask, request, abort, jsonify, g
import re
import json
import string
import random
import time
import threading
from datetime import datetime

import base64
import hmac
import hashlib

#############################################################
#              HOW DOES THE URL SHORTNER WORK?
#############################################################

# How the URL Shortening Process is Working:

# 1. User submits a long URL via a POST request (along with optional expiry time and custom short ID);
# 2. If a custom short ID is provided, we check if its available and store the URL under that ID;
# 3. If no custom ID is provided, we generate a random 6 character short ID using Base62 encoding;
# 4. We check for uniqueness by making sure the generated ID is not in use already;
# 5. The mapping (short ID to original URL) is stored in a memory dictionary;
# 6. The user gets the shortened URL as a response.

# How the short URL is used:
# 1. A GET request fetches the original URL using the short ID;
# 2. If the link has expired, it is deleted and error is returned;
# 3. If the link is valid, the user gets the original URL as a response.

app = Flask(__name__)

#############################################################
#               DATA STORAGE & CONFIGURATION
#############################################################

# Memory storage for URL mappings
# 'id' : {'url', 'expiry_time'} pairs
URL_Mappings = {}

#############################################################
#############################################################
SECRET_KEY = "Rigel"  # This must match login.py

#############################################################
#############################################################

# Regular expression for validating proper URL formats (only URLs starting with http or https)
URL_REGEX = re.compile(r'^(http|https)://[^ "<>]*$')

# Set of characters containing 26 lowercase letters (a-z) + 26 uppercase letters (A-Z) + 10 digits (0-9)
BASE62 = string.ascii_letters + string.digits

# JWT Secret Key (Must match authentication service)
AUTH_SERVICE_URL = "http://localhost:5001"

def verify_jwt(token):
    try:
        header, payload, signature = token.split(".")
        expected_signature = base64.urlsafe_b64encode(
            hmac.new(SECRET_KEY.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
        ).decode().rstrip("=")

        if signature != expected_signature:
            return None  # Invalid signature

        decoded_payload = json.loads(base64.urlsafe_b64decode(payload + "==").decode())
        if decoded_payload["exp"] < time.time():
            return None  # Token expired

        return decoded_payload["username"]
    except Exception:
        return None

@app.before_request
def authenticate_request():
    # if request.path == "/" and request.method == 
    #     return  # Allow the homepage (if needed), but require authentication elsewhere

    token = request.headers.get("Authorization")
    if not token:
        print("Missing Authorization header")
        return jsonify({"error": "Missing token"}), 403
    print(token)
    username = verify_jwt(token.replace("Bearer ", ""))
    if not username:
        print("Invalid or Expired Token")
        return jsonify({"error": "Invalid or expired token"}), 403

    print(f" Authenticated User: {username}")  # Debug print
    g.username = username  # Store authenticated user globally
    if username not in URL_Mappings:
        URL_Mappings[username] = {}

#############################################################
#               SAFETY & VALIDITY CHECKS
#############################################################
def is_valid_url(url) -> bool:
    if url and URL_REGEX.match(url):
        return True
    return False

def is_id_available(id) -> bool:
    return id not in URL_Mappings.get(g.username, {})



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
    if request.method == "GET":
        if not hasattr(g, "username"):
            return jsonify({"error": "Unauthorized access"}), 403

        # Only return URLs for the authenticated user
        mappings = URL_Mappings.get(g.username, {}).keys()
        return jsonify({"value": list(mappings) if mappings else None}), 200

    elif request.method == "DELETE":
        if not hasattr(g, "username"):
            return jsonify({"error": "Unauthorized access"}), 403

        # Remove all entries for the authenticated user
        URL_Mappings[g.username] = {}
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
    if g.username not in URL_Mappings:
        return jsonify({"error": "Unauthorized Access"}), 403

    if id not in URL_Mappings[g.username]:
        return "Short URL not found.", 404

    if request.method == "GET":
        return jsonify({"value": URL_Mappings[g.username][id]["url"]}), 301

    elif request.method == "DELETE":
        del URL_Mappings[g.username][id]
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
    data : dict = request.json
    long_url = data.get("value", None)
    custom_id = data.get("custom_id", None)
    expiry_time = data.get("expiry_time", None)

    try:
        if not long_url:
            raise KeyError("URL is missing from request.", 400)

        if not is_valid_url(long_url):
            raise ValueError("Bad URL format", 400)
            
        # Ensure user has an entry in URL_Mappings
        if g.username not in URL_Mappings:
            URL_Mappings[g.username] = {}

        # If a custom ID is provided, check availability first
        if custom_id:
            if custom_id in URL_Mappings[g.username]:
                raise ValueError(f"Custom ID already taken: {custom_id}", 409)
            short_id = custom_id
        else:
            # If no custom ID is given, check if the URL already exists for the user
            existent_id = next((k for k, v in URL_Mappings[g.username].items() if v['url'] == long_url), None)
            if existent_id:
                raise ValueError(f"Provided URL is already present under ID: {existent_id}", 409)

            short_id = generate_short_id()

        # Convert expiry date to UNIX timestamp if provided
        if expiry_time:
            try:
                expiry_time = float(datetime.strptime(expiry_time, "%Y-%m-%d %H:%M:%S").timestamp())
            except ValueError:
                raise ValueError("Invalid date format. Use 'YYYY-MM-DD HH:MM:SS'", 400)

        # Store the URL under the authenticated user
        URL_Mappings[g.username][short_id] = {'url': long_url, 'expiry_time': expiry_time}
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
        if g.username not in URL_Mappings:
            raise KeyError("Unauthorized Access", 403)

        if id not in URL_Mappings[g.username]:
            return "Short URL not found.", 404

        # Handle JSON payload
        try:
            data = request.get_json()
        except Exception:
            data = json.loads(request.data.decode("utf-8") or "{}")

        new_url = data.get("url", None)
        if not new_url:
            raise ValueError("Missing 'url' in request body.", 400)
        # Check URL validity
        if not is_valid_url(new_url):
            raise ValueError("Provided URL is not valid.", 400)

        # Update the URL under the authenticated user
        URL_Mappings[g.username][id]['url'] = new_url
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
        if g.username not in URL_Mappings or id not in URL_Mappings[g.username]:
            raise KeyError("Unauthorized or URL not found.", 403)

        data: dict = request.json

        new_expiry = data.get("expiry_time", None)
        new_custom_id = data.get("custom_id", None)

        if not new_custom_id and not new_expiry:
            raise ValueError("At least a new ID or a new expiry time must be provided.", 400)

        # Verify new ID availability within the user's namespace
        if new_custom_id and new_custom_id in URL_Mappings[g.username] and new_custom_id != id:
            raise ValueError("Provided ID already taken.", 409)

        # Validate and update expiry time
        if new_expiry:
            try:
                expiry_time = float(datetime.strptime(new_expiry, "%Y-%m-%d %H:%M:%S").timestamp())
            except ValueError:
                raise ValueError("Invalid date format. Use 'YYYY-MM-DD HH:MM:SS'", 400)
            URL_Mappings[g.username][id]['expiry_time'] = expiry_time

        # Update ID mapping if a new ID is provided
        if new_custom_id and new_custom_id != id:
            URL_Mappings[g.username][new_custom_id] = URL_Mappings[g.username].pop(id)
            id = new_custom_id

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
        time.sleep(600)  # Wait for 10 seconds before each cleanup cycle

        for user in URL_Mappings:
            expired_keys = [
                key for key, value in URL_Mappings[user].items()
                if value["expiry_time"] and time.time() > value["expiry_time"]
            ]

            # Ensure expired_keys is always defined before checking it
            if expired_keys:
                for key in expired_keys:
                    del URL_Mappings[user][key]
                print(f"✅ Cleaned up {len(expired_keys)} expired links for user: {user}")


if __name__ == "__main__":
    # Start auto cleanup thread
    cleanup_thread = threading.Thread(target=cleanup_expired_links, daemon=True)
    cleanup_thread.start()

    app.run(port=5000, debug=True)

