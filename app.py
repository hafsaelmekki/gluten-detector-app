import streamlit as st

from core import AppUI, FoodScanner, GlutenAnalyzerLLM, OpenFoodFactsAPI

API_KEY = st.secrets["GROQ_API_KEY"]

st.set_page_config(page_title="GlutenFree App", page_icon="images/logo/logo_titre.png", layout="wide")


def main():
    api_client = OpenFoodFactsAPI()
    scanner = FoodScanner()
    analyzer = GlutenAnalyzerLLM(API_KEY)
    ui = AppUI(api_client, scanner, analyzer, api_key_present=bool(API_KEY))
    ui.render()


if __name__ == "__main__":
    main()
