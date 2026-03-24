import os

import streamlit as st

from core import AppUI, FoodScanner, GlutenAnalyzerLLM, OpenFoodFactsAPI


def _get_secret(name: str, default: str = "") -> str:
    env_value = os.getenv(name)
    if env_value not in (None, ""):
        return env_value
    try:
        return st.secrets[name]
    except Exception:
        return default


API_KEY = _get_secret("GROQ_API_KEY", "")
BACKEND_URL = _get_secret("BACKEND_URL", "").strip()


st.set_page_config(
    page_title="GlutenFree App",
    page_icon="images/logo/logo_titre.png",
    layout="wide",
)


def main() -> None:
    api_client = OpenFoodFactsAPI()
    scanner = FoodScanner()
    analyzer = GlutenAnalyzerLLM(API_KEY)
    ui = AppUI(
        api_client,
        scanner,
        analyzer,
        api_key_present=bool(API_KEY),
        backend_base_url=BACKEND_URL or None,
    )
    ui.render()


if __name__ == "__main__":
    main()
