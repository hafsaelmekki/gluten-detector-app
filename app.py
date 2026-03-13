import re

import requests
import streamlit as st
from groq import Groq
from PIL import Image
from pyzbar.pyzbar import decode as decode_barcode
from streamlit_option_menu import option_menu

API_KEY = st.secrets["GROQ_API_KEY"]

st.set_page_config(page_title="GlutenFree App", page_icon="images/logo/logo_titre.png", layout="wide")


class FoodScanner:
    """Decode barcodes from an image."""

    @staticmethod
    def decode(image_file):
        try:
            img = Image.open(image_file)
            codes = decode_barcode(img)
            return codes[0].data.decode("utf-8") if codes else None
        except Exception:
            return None


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
            return [p for p in data.get("products", []) if p.get("product_name")]
        except Exception:
            return []

    def search_product_by_code(self, code):
        try:
            url = f"{self.BASE_URL}/api/v0/product/{code}.json"
            data = requests.get(url).json()
            return data["product"] if data.get("status") == 1 else None
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


class GlutenAnalyzerLLM:
    def __init__(self, api_key, model="llama-3.3-70b-versatile"):
        self.api_key = api_key
        self.model = model
        self.client = Groq(api_key=api_key) if api_key else None

    def analyze_product(self, product):
        if not self.client:
            return "⚠️ Erreur clé API"
        score = product.get("nutriscore_grade", "Inconnu").upper()
        prompt = f"""
        Produit : {product.get('product_name')}
        Ingrédients : {product.get('ingredients_text', 'Non listés')}
        Traces : {product.get('traces', 'Non indiqué')}
        Nutri-Score : {score}
        Analyse pour un coeliaque (Sans Gluten).
        RÈGLES STRICTES :
        1. Si INTERDIT (Blé, Orge, Seigle...) -> "🔴 CONTIENT DU GLUTEN".
        2. Si RISQUE (Avoine, Traces...) -> "⚠️ RISQUE (Traces/Contamination)".
        3. Si OK -> "🟢 SANS GLUTEN".
        IMPORTANT : Si ROUGE ou ORANGE, ajoute à la fin : "SEARCH_TERM: [Nom générique]" 
        SI VERT, N'AJOUTE RIEN.
        """
        try:
            response = self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=self.model,
                temperature=0.0,
            )
            return response.choices[0].message.content
        except Exception as exc:
            return f"Erreur : {exc}"

    def generate_recipe(self, mode, input_text):
        if not self.client:
            return "⚠️ Erreur clé API"
        system_prompt = "Chef sans gluten." if mode == "creation" else "Expert substitution."
        user_prompt = (
            f"Recette sans gluten pour : {input_text}."
            if mode == "creation"
            else f"Adapte en sans gluten :\n\n{input_text}"
        )
        try:
            response = self.client.chat.completions.create(
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                model=self.model,
            )
            return response.choices[0].message.content
        except Exception:
            return "Erreur"


class AppUI:
    def __init__(self, api_client, scanner, analyzer):
        self.api = api_client
        self.scanner = scanner
        self.analyzer = analyzer

    def init_session(self):
        defaults = {
            "produit_actuel": None,
            "analyse_actuelle": None,
            "alternatives_trouvees": None,
            "recette_generee": None,
            "last_search": None,
            "resultats_recherche": None,
            "search_query": "",
        }
        for key, value in defaults.items():
            st.session_state.setdefault(key, value)

    def render_sidebar(self):
        with st.sidebar:
            try:
                st.image("images/logo/logo_titre.png", use_container_width=True)
            except Exception:
                st.warning("⚠️ Logo introuvable (images/logo/logo_titre.png)")
                st.caption("Placez votre image dans le bon dossier.")
            st.write("")
            choix_section = option_menu(
                menu_title=None,
                options=["Scanner & Analyse", "Chef & Recettes"],
                icons=["upc-scan", "egg-fried"],
                default_index=0,
                styles={
                    "container": {"padding": "0!important", "background-color": "transparent"},
                    "icon": {"color": "#182032", "font-size": "18px"},
                    "nav-link": {
                        "font-size": "16px",
                        "text-align": "left",
                        "margin": "5px",
                        "color": "#182032",
                        "--hover-color": "#e1e1e1",
                    },
                    "nav-link-selected": {
                        "background-color": "#84bf78",
                        "color": "white",
                    },
                },
            )
            st.divider()
            if API_KEY:
                st.success("✅ Clé API connectée")
            else:
                st.error("❌ Clé API manquante")
            return choix_section

    def render(self):
        self.init_session()
        choix_section = self.render_sidebar()
        if choix_section == "Scanner & Analyse":
            self.render_scanner_section()
        else:
            self.render_recipes_section()

    def render_scanner_section(self):
        st.title("🔎 Scanner de Produits")
        st.markdown(
            """
            <style>
                .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] {
                    background-color: #84bf78 !important;
                    color: white !important;
                }
            </style>
            """,
            unsafe_allow_html=True,
        )
        tab1, tab2 = st.tabs(["⌨️ Recherche Texte", "📸 Code-Barres"])
        self.render_text_search_tab(tab1)
        self.render_barcode_tab(tab2)
        produit = st.session_state.produit_actuel
        if produit:
            self.render_product_details(produit)

    def render_text_search_tab(self, container):
        with container:
            col1, col2 = st.columns([3, 1])
            query = col1.text_input("Nom", key="search_query")
            trigger_search = col2.button("Chercher")
            should_search = (trigger_search and query) or (
                query and st.session_state.get("last_search") != query
            )
            if should_search and query:
                results = self.api.search_products(query)
                st.session_state.resultats_recherche = results
                st.session_state.last_search = query
            results = st.session_state.get("resultats_recherche")
            if results:
                options = {
                    f"{p['product_name']} ({p.get('brands', '')})": p for p in results
                }
                choix = st.selectbox("Sélectionnez :", list(options.keys()))
                if st.button("✅ Valider"):
                    st.session_state.produit_actuel = options[choix]
                    st.session_state.analyse_actuelle = None
                    st.session_state.alternatives_trouvees = None
                    st.rerun()

    def render_barcode_tab(self, container):
        with container:
            mode = st.radio("Source :", ["Webcam", "Fichier"], horizontal=True)
            image = (
                st.camera_input("Scan")
                if mode == "Webcam"
                else st.file_uploader("Image", type=["jpg", "png"])
            )
            if image:
                code_barre = self.scanner.decode(image)
                if code_barre:
                    st.success(f"Code : {code_barre}")
                    if st.button("✅ Valider et Analyser"):
                        produit = self.api.search_product_by_code(code_barre)
                        if produit:
                            st.session_state.produit_actuel = produit
                            st.session_state.analyse_actuelle = None
                            st.session_state.alternatives_trouvees = None
                            st.rerun()
                        else:
                            st.error("Produit inconnu")
                else:
                    st.error("Impossible de décoder l'image")

    def render_product_details(self, product):
        st.divider()
        analyse = st.session_state.analyse_actuelle
        if analyse:
            titre = analyse.split("\n")[0].replace("###", "").strip()
            if "🔴" in titre:
                st.error(f"# {titre}")
            elif "⚠️" in titre:
                st.warning(f"# {titre}")
            elif "🟢" in titre:
                st.success(f"# {titre}")
        col_img, col_infos, col_score = st.columns([1, 2, 1])
        with col_img:
            if product.get("image_front_small_url"):
                st.image(product.get("image_front_small_url"), width=150)
        with col_infos:
            st.subheader(product.get("product_name"))
            st.caption(f"Marque : {product.get('brands')}")
            ingredients = product.get("ingredients_text", "")
            if ingredients:
                st.write(f"**Ingrédients:** {ingredients[:200]}...")
            if not st.session_state.analyse_actuelle:
                if st.button("🧠 Lancer l'analyse", type="primary"):
                    with st.spinner("Analyse..."):
                        analyse = self.analyzer.analyze_product(product)
                        st.session_state.analyse_actuelle = analyse
                        match = re.search(r"SEARCH_TERM:\s*(.*)", analyse or "")
                        st.session_state.alternatives_trouvees = (
                            self.api.find_gluten_free_alternatives(match.group(1).strip())
                            if match
                            else None
                        )
                        st.rerun()
        with col_score:
            score = product.get("nutriscore_grade")
            if score:
                st.markdown("**Nutri-Score :**")
                st.image(
                    f"https://static.openfoodfacts.org/images/misc/nutriscore-{score}.svg",
                    width=100,
                )
        if st.session_state.analyse_actuelle:
            clean_text = re.sub(
                r"SEARCH_TERM:.*",
                "",
                "\n".join(st.session_state.analyse_actuelle.split("\n")[1:]),
            )
            st.markdown(clean_text)
        if st.session_state.alternatives_trouvees:
            st.divider()
            st.markdown("### ✨ Meilleures alternatives Sans Gluten :")
            cols = st.columns(3)
            for i, alt in enumerate(st.session_state.alternatives_trouvees):
                with cols[i]:
                    if alt.get("image_front_small_url"):
                        st.image(alt.get("image_front_small_url"), width=100)
                    st.write(f"**{alt.get('product_name')}**")

    def render_recipes_section(self):
        st.title("👨‍🍳 Le Chef Sans Gluten")
        mode_cuisine = st.radio(
            "Option :", ["✨ Créer une recette", "🔄 Adapter une recette"], horizontal=True
        )
        st.divider()
        if mode_cuisine == "✨ Créer une recette":
            col1, col2 = st.columns([2, 1])
            plat = col1.text_input("Plat souhaité")
            if col2.button("🍳 Générer") and plat:
                with st.spinner("Création..."):
                    st.session_state.recette_generee = self.analyzer.generate_recipe(
                        "creation", plat
                    )
        else:
            texte = st.text_area("Collez votre recette ici :")
            if st.button("✨ Transformer") and texte:
                with st.spinner("Adaptation..."):
                    st.session_state.recette_generee = self.analyzer.generate_recipe(
                        "adaptation", texte
                    )
        if st.session_state.recette_generee:
            st.markdown("---")
            st.subheader("🍽️ Résultat")
            st.markdown(st.session_state.recette_generee)


def main():
    api_client = OpenFoodFactsAPI()
    scanner = FoodScanner()
    analyzer = GlutenAnalyzerLLM(API_KEY)
    AppUI(api_client, scanner, analyzer).render()


if __name__ == "__main__":
    main()
