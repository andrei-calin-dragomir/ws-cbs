# Initialization code based on the Flask application setup: https://flask.palletsprojects.com/en/stable/quickstart/
from flask import Flask, request, abort, jsonify
import re
import string
import random

# 'ID' : 'Url' pairs
URL_Mappings = {}

app = Flask(__name__)

def is_id_available(id) -> bool:
    if id in URL_Mappings.values():
        return False
    return True

def generate_short_id(length=6):
    # Generate a short ID using Base62 encoding
    BASE62 = string.ascii_letters + string.digits

    id = ''.join(random.choices(BASE62, k=length))
    if is_id_available(id):
        return id
    return generate_short_id(length)

def is_valid_url(url) -> bool:
    # Regex for URL validation
    URL_REGEX = re.compile(r'^(http|https)://[^ "<>]*$')
    if url and URL_REGEX.match(url):
        return True
    return False

@app.route('/', methods=['GET', 'DELETE', 'POST'])
def base_handler():
    if request.method == 'GET':
        # Return all the IDs present in memory
        return jsonify({"value" : list(URL_Mappings.keys()) if URL_Mappings else None}), 200
    elif request.method == 'DELETE':
        # Remove all entries from memory
        URL_Mappings.clear()
        return '', 404
    elif request.method == 'POST':
        try:
            data = request.json
            long_url = data.get("value")
            # Check validity of request contents
            if is_valid_url(long_url):
                # We check the existence of the url in memory
                if long_url in set(URL_Mappings.values()):
                    # This lookup method is inspired from this StackOverflow post: https://stackoverflow.com/a/8023329/12995174
                    existent_id = next((k for k, v in URL_Mappings.items() if v == long_url), None)
                    raise ValueError(f"Provided URL is already present under ID: {existent_id}")
                
                # Generate a new ID for the new url
                id = generate_short_id()
                # Add the new ID - url pair to memory
                URL_Mappings[id] = long_url
                return jsonify({"id": id}), 201
            else:
                raise ValueError("Provided URL is not valid.")
        except ValueError as e:
            return jsonify({"error" : str(e)}), 400

# The path specifier enforces that, in order for this case to be applicable, the unique_id must be present in the request. 
# Otherwise, the request is handled by the base_handler()
@app.route('/<request_id>', methods=['GET', 'PUT', 'DELETE'])
def id_handler(request_id):
    
    # Check if ID exists in memory
    if request_id not in URL_Mappings:
        # Provided ID does not exist in memory
        return jsonify({"error" : f"Provided ID {request_id} does not exist in memory."}), 404
    
    if request.method == 'GET':
        # Return the url for the provided ID
        return jsonify({"value" : URL_Mappings[request_id]}), 301
    
    elif request.method == 'DELETE':
        # Remove the ID - URL entry from memory
        del URL_Mappings[request_id]
        return '', 204
    
    elif request.method == 'PUT':
        # Check validity of request contents
        try:
            data = request.json
            long_url = data.get("url")
            
            # New URL must be provided with the ID in this case
            if not long_url:
                raise ValueError("Missing 'url' in request body.")
            
            # Check URL validity
            if not is_valid_url(long_url):
                raise ValueError("Provided URL is not valid.")
            
            # Update the mapping
            URL_Mappings[request_id] = long_url                   
            return '', 200
        except ValueError as e:
            return jsonify({"error" : str(e)}), 400

    