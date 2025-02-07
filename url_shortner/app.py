# Initialization code based on the Flask application setup: https://flask.palletsprojects.com/en/stable/quickstart/
from flask import Flask, request, abort

URL_Mappings = {
    # 'url_short' : 'url_long' # The short url is created using a hashing algorithm
}

app = Flask(__name__)

@app.route('/', methods=['GET', 'DELETE'])
def base_handler():
    if request.method == 'GET':
        return URL_Mappings.keys(), 200
    elif request.method == 'DELETE':
        URL_Mappings.clear()
        return 404

# The path specifier enforces that, in order for this case to be applicable, the unique_id must be present in the request. 
# Otherwise, the request is handled by the base_handler() or the url_handler() (if a url is passed on path instead of a numerical value)
@app.route('/<int:request_id>', methods=['GET', 'PUT', 'DELETE'])
def id_handler(request_id):
    try:
        # Check if ID exists in memory
        url = URL_Mappings.get(request_id, None)
        if url:
            if request.method == 'GET':
                return url, 301
            
            elif request.method == 'DELETE':
                del URL_Mappings[request_id]
                return 204
            
            elif request.method == 'PUT':
                data = request.get_json()
                # New URL must be provided with the ID in this case
                if not data or 'url' not in data:
                    raise "Missing 'url' in request body."
                # Update the mapping
                if is_valid_url(data['url']):
                    URL_Mappings[request_id] = data['url']
                else:
                    raise "Provided URL is not valid."
                return 200
        else:
            # Provided ID does not exist in memory
            abort(404)
    except Exception as e:
        abort(400, e)

@app.route('/<str:url>', methods=['POST'])
def url_handler(url):
    try:
        if is_valid_url(url):
            # We generate the hash key for the url
            id = positive_hash(url)

            # We check the existence of the url in memory
            existent_url = URL_Mappings.get(id, None)
            if existent_url:
                # If the url provided is already stored, raise the following error
                if url == existent_url:
                    raise f"Provided URL is already present under ID: {id}"
                # If the url provided is not matching the url found in memory but the generated hash key is present, a collision was found
                else:
                    raise "Generated ID already exists."
            URL_Mappings[id] = url
            return id, 201
        else:
            raise "Provided URL is not valid."
    except Exception as e:
        abort(400, e)

# The in-built python hashing function is not stable across multiple sessions but for this specific assignment session persistence is not required.
# We enforce that the hash value returned remains in the positive range due to the constraint introduced by the variable rule we use for the /:id endpoint.
# This solution is inspired from this post: https://stackoverflow.com/questions/18766535/positive-integer-from-python-hash-function
def positive_hash(value):
    return hash(value) % (2**31)  # Limits to range [0, 2^31 - 1]

def is_valid_url(url) -> bool:
    pass