import time
import requests

# API Base URL
BASE_URL = "http://localhost/api/shorten/"

# Your JWT Token (Replace this with your actual token)
JWT_TOKEN = "eyJhbGciOiAiSFMyNTYiLCAidHlwIjogIkpXVCJ9.eyJ1c2VybmFtZSI6ICJ0ZXN0X3VzZXIiLCAiZXhwIjogMTc0MTUyOTI4OH0._Axz7bwa6ESraPmdAR2O07yU8xz2v0FY4My6iMudcf4"

# Test URL to shorten
TEST_URL = "https://example2.com"

# Headers for authentication
HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer eyJhbGciOiAiSFMyNTYiLCAidHlwIjogIkpXVCJ9.eyJ1c2VybmFtZSI6ICJ0ZXN0X3VzZXIiLCAiZXhwIjogMTc0MTUyOTI4OH0._Axz7bwa6ESraPmdAR2O07yU8xz2v0FY4My6iMudcf4"
}


def measure_time(func, *args):
    """Measures execution time of a function."""
    start = time.time()
    result = func(*args)
    end = time.time()
    return result, round(end - start, 5)  # Time in seconds


def shorten_url():
    """Sends a POST request to shorten a URL."""
    response = requests.post(BASE_URL, json={"value": TEST_URL}, headers=HEADERS)
    return response.json()


def retrieve_url(short_id):
    """Retrieves the original URL normally."""
    response = requests.get(BASE_URL + short_id, headers=HEADERS)
    return response.json()


# 1️⃣ Measure URL Shortening Time
shortened_data, shorten_time = measure_time(shorten_url)
short_id = shortened_data.get("id")

print(f"🔗 Shortened URL ID: {short_id}")
print(f"⏳ Time taken to shorten URL: {shorten_time} seconds\n")

# 2️⃣ Measure URL Retrieval (Without Redis - First Time)
retrieved_data, retrieve_time_db = measure_time(retrieve_url, short_id)
print(f"🔍 First retrieval (DB query): {retrieve_time_db} seconds\n")

# 3️⃣ Measure URL Retrieval (With Redis - Second Time)
retrieved_data_cache, retrieve_time_cache = measure_time(retrieve_url, short_id)
print(f"⚡ Second retrieval (Redis cache): {retrieve_time_cache} seconds\n")
