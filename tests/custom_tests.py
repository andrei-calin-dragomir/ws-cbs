import unittest
import requests

class TestURLShortener(unittest.TestCase):
    
    base_url = "http://127.0.0.1:5000"

    def test_get_all_ids(self):
        response = requests.get(f"{self.base_url}/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("value", response.json())

    def test_delete_all_ids(self):
        response = requests.delete(f"{self.base_url}/")
        self.assertEqual(response.status_code, 404)

    def test_shorten_url(self):
        url_to_shorten = "https://example123.com"
        response = requests.post(f"{self.base_url}/", json={"value": url_to_shorten})
        self.assertEqual(response.status_code, 201)
        self.assertIsNotNone(response.json().get("id"))

    def test_shorten_url_invalid(self):
        response = requests.post(f"{self.base_url}/", json={"value": "invalid-url"})
        self.assertEqual(response.status_code, 400)

    def test_shorten_url_custom_id(self):
        response = requests.post(f"{self.base_url}/", json={"value": "https://example321.com", "custom_id": "custom123"})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["id"], "custom123")

    def test_shorten_url_duplicate(self):
        requests.post(f"{self.base_url}/", json={"value": "https://example.com", "custom_id": "duplicate"})
        response = requests.post(f"{self.base_url}/", json={"value": "https://example.com", "custom_id": "duplicate"})
        self.assertEqual(response.status_code, 409)

    def test_get_url_by_id(self):
        requests.post(f"{self.base_url}/", json={"value": "https://example.com", "custom_id": "gettest"})
        response = requests.get(f"{self.base_url}/gettest")
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response.json()["value"], "https://example.com")

    def test_get_url_invalid_id(self):
        response = requests.get(f"{self.base_url}/invalidid")
        self.assertEqual(response.status_code, 404)

    def test_delete_url_by_id(self):
        requests.post(f"{self.base_url}/", json={"value": "https://example.com", "custom_id": "deletetest"})
        response = requests.delete(f"{self.base_url}/deletetest")
        self.assertEqual(response.status_code, 204)
        response = requests.get(f"{self.base_url}/deletetest")
        self.assertEqual(response.status_code, 404)

    def test_update_url(self):
        response = requests.post(f"{self.base_url}/", json={"value": "https://example1234.com", "custom_id": "updatetest"})
        response = requests.put(f"{self.base_url}/updatetest", json={"url": "https://newexample2.com"})
        self.assertEqual(response.status_code, 200)
        response = requests.get(f"{self.base_url}/updatetest")
        self.assertEqual(response.json()["value"], "https://newexample2.com")

    def test_update_url_invalid(self):
        response = requests.put(f"{self.base_url}/invalidid", json={"url": "https://newexample.com"})
        self.assertEqual(response.status_code, 404)

    def test_patch_update(self):
        requests.post(f"{self.base_url}/", json={"value": "https://patch.com", "custom_id": "patchtest"})
        response = requests.patch(f"{self.base_url}/patchtest", json={"custom_id": "patchedid"})
        self.assertEqual(response.status_code, 200)
        response = requests.get(f"{self.base_url}/patchedid")
        self.assertEqual(response.json()["value"], "https://patch.com")

    def test_patch_update_invalid(self):
        response = requests.patch(f"{self.base_url}/invalidid", json={"custom_id": "newid"})
        self.assertEqual(response.status_code, 404)

if __name__ == '__main__':
    unittest.main()