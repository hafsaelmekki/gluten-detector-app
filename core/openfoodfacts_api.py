from __future__ import annotations

from typing import Any, Dict, List, Optional

import requests

Product = Dict[str, Any]


class OpenFoodFactsAPI:
    BASE_URL = "https://world.openfoodfacts.org"
    NAME_FIELDS = (
        "product_name",
        "product_name_fr",
        "product_name_en",
        "generic_name",
        "generic_name_fr",
    )

    def _normalize_product(self, product: Product) -> Optional[Product]:
        if not isinstance(product, dict):
            return None
        for field in self.NAME_FIELDS:
            value = product.get(field)
            if value:
                if field == "product_name":
                    return product
                normalized = dict(product)
                normalized["product_name"] = value
                return normalized
        return None

    def search_products(self, name: str) -> List[Product]:
        try:
            url = f"{self.BASE_URL}/cgi/search.pl"
            params = {"search_terms": name, "search_simple": 1,
                      "action": "process", "json": 1, "page_size": 20}
            headers = {"User-Agent": "GlutifyApp - Windows - Version 1.0"}

            response = requests.get(
                url, params=params, headers=headers, timeout=10)
            response.raise_for_status()

            data = response.json()
            products: List[Product] = []
            for prod in data.get("products", []):
                normalized = self._normalize_product(prod)
                if normalized:
                    products.append(normalized)
            return products

        except Exception as e:
            print(
                f"⚠️ API EXTERNE INDISPONIBLE ({e}). Basculement sur les données de secours.")
            # LE MODE SURVIE : Si OpenFoodFacts plante, l'appli continue de marcher !
            return [
                {
                    "product_name": f"{name.capitalize()} (Mode Hors-Ligne)",
                    "brands": "Système de Secours Glutify",
                    "ingredients_text": "Sucre, pâte de cacao, beurre de cacao, émulsifiant. Peut contenir des traces de blé.",
                    "allergens": "en:gluten, en:soybeans",
                    "image_url": "https://images.openfoodfacts.org/images/products/304/692/002/2651/front_fr.109.400.jpg",
                    "id": "0000000000000"
                }
            ]

    def search_product_by_code(self, code: str) -> Optional[Product]:
        try:
            url = f"{self.BASE_URL}/api/v0/product/{code}.json"
            data = requests.get(url).json()
            if data.get("status") != 1:
                return None
            return self._normalize_product(data.get("product", {}))
        except Exception:
            return None

    def find_gluten_free_alternatives(self, category: str) -> List[Product]:
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
            products: List[Product] = []
            for prod in data.get("products", []):
                normalized = self._normalize_product(prod)
                if normalized:
                    products.append(normalized)
            return products
        except Exception:
            return []
