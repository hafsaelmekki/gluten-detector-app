import requests


class OpenFoodFactsAPI:
    BASE_URL = "https://world.openfoodfacts.org"

    def search_products(self, name):
        try:
            url = f"{self.BASE_URL}/cgi/search.pl"
            params = {
                "search_terms": name,
                "search_simple": 1,
                "action": "process",
                "json": 1,
                "page_size": 20,
            }
            data = requests.get(url, params=params).json()
            return [
                p for p in data.get("products", []) if p.get("product_name")
            ]
        except Exception:
            return []

    def search_product_by_code(self, code):
        try:
            url = f"{self.BASE_URL}/api/v0/product/{code}.json"
            data = requests.get(url).json()
            return data.get("product") if data.get("status") == 1 else None
        except Exception:
            return None

    def find_gluten_free_alternatives(self, category):
        try:
            url = f"{self.BASE_URL}/cgi/search.pl"
            params = {
                "search_terms": f"{category}",
                "tagtype_0": "labels",
                "tag_contains_0": "contains",
                "tag_0": "en:gluten-free",
                "sort_by": "popularity",
                "page_size": 3,
                "json": 1,
            }
            data = requests.get(url, params=params).json()
            return data.get("products", [])
        except Exception:
            return []
