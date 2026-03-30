from __future__ import annotations

from typing import Any, Dict, List, Optional

from collections import deque
import time
from threading import Lock
import requests

Product = Dict[str, Any]


class OpenFoodFactsAPIError(RuntimeError):
    """Raised when OpenFoodFacts cannot be reached."""


class OpenFoodFactsAPI:
    BASE_URL = "https://world.openfoodfacts.net"
    MAX_RETRIES = 3
    BACKOFF_SECONDS = 1.5
    NAME_FIELDS = (
        "product_name",
        "product_name_fr",
        "product_name_en",
        "generic_name",
        "generic_name_fr",
    )

    RATE_LIMIT_REQUESTS = 60
    RATE_LIMIT_WINDOW = 60.0

    def __init__(self) -> None:
        self._recent_requests = deque()
        self._rate_lock = Lock()

    def _acquire_rate_slot(self) -> None:
        while True:
            now = time.time()
            with self._rate_lock:
                window_start = now - self.RATE_LIMIT_WINDOW
                while self._recent_requests and self._recent_requests[0] < window_start:
                    self._recent_requests.popleft()
                if len(self._recent_requests) < self.RATE_LIMIT_REQUESTS:
                    self._recent_requests.append(now)
                    return
                wait_for = self._recent_requests[0] + \
                    self.RATE_LIMIT_WINDOW - now
            if wait_for > 0:
                print(
                    f"[INFO] Rate limit OpenFoodFacts atteint, pause {wait_for:.1f}s"
                )
                time.sleep(wait_for)
            else:
                time.sleep(0.1)

    def rate_limit_status(self) -> Dict[str, float]:
        now = time.time()
        with self._rate_lock:
            window_start = now - self.RATE_LIMIT_WINDOW
            while self._recent_requests and self._recent_requests[0] < window_start:
                self._recent_requests.popleft()
            remaining = max(0, self.RATE_LIMIT_REQUESTS -
                            len(self._recent_requests))
            reset_in = 0.0
            if self._recent_requests:
                reset_in = self._recent_requests[0] + \
                    self.RATE_LIMIT_WINDOW - now
        return {
            "limit": float(self.RATE_LIMIT_REQUESTS),
            "remaining": float(remaining),
            "reset_in": max(0.0, reset_in),
        }

    def _request_with_retry(
        self,
        *,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 10,
    ) -> requests.Response:
        last_error: Optional[Exception] = None
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                self._acquire_rate_slot()
                response = requests.get(
                    url, params=params, headers=headers, timeout=timeout
                )
                response.raise_for_status()
                return response
            except requests.RequestException as exc:
                last_error = exc
                if attempt == self.MAX_RETRIES:
                    break
                sleep_for = self.BACKOFF_SECONDS * attempt
                print(
                    f"[WARN] OpenFoodFacts tentative {attempt}/{self.MAX_RETRIES} echouee ({exc})."
                )
                time.sleep(sleep_for)
        raise OpenFoodFactsAPIError(
            "OpenFoodFacts indisponible apres plusieurs tentatives"
        ) from last_error

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
        url = f"{self.BASE_URL}/cgi/search.pl"
        params = {
            "search_terms": name,
            "search_simple": 1,
            "action": "process",
            "json": 1,
            "page_size": 20,
        }
        headers = {"User-Agent": "GlutifyApp - Windows - Version 1.0"}

        response = self._request_with_retry(
            url=url, params=params, headers=headers)

        try:
            data = response.json()
        except ValueError as exc:
            raise OpenFoodFactsAPIError(
                "Reponse OpenFoodFacts invalide") from exc

        products: List[Product] = []
        for prod in data.get("products", []):
            normalized = self._normalize_product(prod)
            if normalized:
                products.append(normalized)
        return products

    def search_product_by_code(self, code: str) -> Optional[Product]:
        url = f"{self.BASE_URL}/api/v0/product/{code}.json"
        response = self._request_with_retry(url=url)
        try:
            data = response.json()
        except ValueError as exc:
            raise OpenFoodFactsAPIError(
                "Reponse OpenFoodFacts invalide") from exc
        if data.get("status") != 1:
            return None
        return self._normalize_product(data.get("product", {}))

    def find_gluten_free_alternatives(self, category: str) -> List[Product]:
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
        response = self._request_with_retry(url=url, params=params)
        try:
            data = response.json()
        except ValueError as exc:
            raise OpenFoodFactsAPIError(
                "Reponse OpenFoodFacts invalide") from exc

        products: List[Product] = []
        for prod in data.get("products", []):
            normalized = self._normalize_product(prod)
            if normalized:
                products.append(normalized)
        return products
