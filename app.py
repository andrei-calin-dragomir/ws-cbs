from flask import Flask, request, jsonify, redirect
import re
import string
import random

app = Flask(__name__)

# In-memory storage for URL mappings
url_store = {}

# Regex for URL validation
URL_REGEX = re.compile(r'^(http|https)://[^ "<>]*$')

# Generate a short ID using Base62 encoding
BASE62 = string.ascii_letters + string.digits


def generate_short_id(length=6):
    return ''.join(random.choices(BASE62, k=length))


@app.route("/", methods=["POST"])
def shorten_url():
    data = request.json
    long_url = data.get("url")

    if not long_url or not URL_REGEX.match(long_url):
        return jsonify({"error": "Invalid URL format"}), 400

    # Check if URL already exists in the storage
    for short_id, stored_url in url_store.items():
        if stored_url == long_url:
            return jsonify({"short_id": short_id, "message": "URL already shortened"}), 200

    # If URL doesn't exist, generate a new short ID
    short_id = generate_short_id()
    while short_id in url_store:
        short_id = generate_short_id()

    url_store[short_id] = long_url
    return jsonify({"short_id": short_id}), 201


@app.route("/<string:short_id>", methods=["GET"])
def get_url(short_id):
    long_url = url_store.get(short_id)
    if long_url:
        return jsonify({"original_url": long_url}), 200  # Return URL in JSON
    return jsonify({"error": "Not found"}), 404


@app.route("/<string:short_id>", methods=["PUT"])
def update_url(short_id):
    if short_id not in url_store:
        return jsonify({"error": "Not found"}), 404

    data = request.json
    new_url = data.get("url")
    if not new_url or not URL_REGEX.match(new_url):
        return jsonify({"error": "Invalid URL"}), 400

    url_store[short_id] = new_url
    return jsonify({"message": "Updated successfully"}), 200


@app.route("/<string:short_id>", methods=["DELETE"])
def delete_url(short_id):
    if short_id in url_store:
        del url_store[short_id]
        return '', 204
    return jsonify({"error": "Not found"}), 404


@app.route("/", methods=["GET"])
def list_shortened_urls():
    return jsonify(list(url_store.keys())), 200


if __name__ == "__main__":
    app.run(debug=True)
