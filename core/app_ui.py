from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Optional, Sequence, TYPE_CHECKING

import requests
import streamlit as st
from streamlit.delta_generator import DeltaGenerator
from streamlit_option_menu import option_menu

if TYPE_CHECKING:
    from .food_scanner import FoodScanner
    from .gluten_analyzer import GlutenAnalyzerLLM
    from .openfoodfacts_api import OpenFoodFactsAPI

Product = Dict[str, Any]


class AppUI:
    def __init__(
        self,
        api_client: OpenFoodFactsAPI,
        scanner: FoodScanner,
        analyzer: GlutenAnalyzerLLM,
        api_key_present: bool,
        backend_base_url: Optional[str] = None,
    ) -> None:
        self.api = api_client
        self.scanner = scanner
        self.analyzer = analyzer
        self.api_key_present = api_key_present
        self.backend_url = (
            backend_base_url.rstrip("/") if backend_base_url else None
        )

    def init_session(self) -> None:
        defaults = {
            "produit_actuel": None,
            "analyse_actuelle": None,
            "alternatives_trouvees": None,
            "recette_generee": None,
            "last_search": None,
            "resultats_recherche": None,
            "search_query": "",
            "analysis_history": None,
        }
        for key, value in defaults.items():
            st.session_state.setdefault(key, value)

    def render_sidebar(self) -> str:
        with st.sidebar:
            try:
                st.image(
                    "images/logo/logo_titre.png", use_container_width=True
                )
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
                    "container": {
                        "padding": "0!important",
                        "background-color": "transparent",
                    },
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
            if self.api_key_present:
                st.success("✅ Clé API connectée")
            else:
                st.error("❌ Clé API manquante")
        return choix_section

    def render(self) -> None:
        self.init_session()
        choix_section = self.render_sidebar()
        if choix_section == "Scanner & Analyse":
            self.render_scanner_section()
        else:
            self.render_recipes_section()

    def render_scanner_section(self) -> None:
        st.title("🔎 Scanner de Produits")
        st.markdown(
            """
            <style>
                .stTabs [data-baseweb="tab-list"]
                button[aria-selected="true"] {
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
        produit: Optional[Product] = st.session_state.produit_actuel
        if produit:
            self.render_product_details(produit)
        st.divider()
        self.render_history_section()

    def render_text_search_tab(self, container: DeltaGenerator) -> None:
        with container:
            col1, col2 = st.columns([3, 1])
            query: str = col1.text_input("Nom", key="search_query")
            trigger_search = col2.button("Chercher")
            should_search = (trigger_search and query) or (
                query and st.session_state.get("last_search") != query
            )
            if should_search and query:
                results = self.api.search_products(query)
                st.session_state.resultats_recherche = results
                st.session_state.last_search = query
            results: Optional[List[Product]] = st.session_state.get(
                "resultats_recherche"
            )
            if results:
                options: Dict[str, Product] = {
                    f"{p['product_name']} ({p.get('brands', '')})": p
                    for p in results
                }
                choix = st.selectbox("Sélectionnez :", list(options.keys()))
                if st.button("✅ Valider"):
                    st.session_state.produit_actuel = options[choix]
                    st.session_state.analyse_actuelle = None
                    st.session_state.alternatives_trouvees = None
                    st.rerun()

    def render_barcode_tab(self, container: DeltaGenerator) -> None:
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

    def render_product_details(self, product: Product) -> None:
        st.divider()
        analyse: Optional[str] = st.session_state.analyse_actuelle
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
                        analyse = self._run_analysis(product)
                        if analyse:
                            st.session_state.analyse_actuelle = analyse
                            match = re.search(
                                r"SEARCH_TERM:\s*(.*)", analyse or ""
                            )
                            st.session_state.alternatives_trouvees = (
                                self.api.find_gluten_free_alternatives(
                                    match.group(1).strip()
                                )
                                if match
                                else None
                            )
                            st.rerun()
        with col_score:
            score = product.get("nutriscore_grade")
            if score:
                st.markdown("**Nutri-Score :**")
                st.image(
                    (
                        "https://static.openfoodfacts.org/images/misc/"
                        f"nutriscore-{score}.svg"
                    ),
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
            cols: Sequence[DeltaGenerator] = st.columns(3)
            for i, alt in enumerate(st.session_state.alternatives_trouvees):
                if i >= len(cols):
                    break
                with cols[i]:
                    if alt.get("image_front_small_url"):
                        st.image(
                            alt.get("image_front_small_url"),
                            width=100,
                        )
                    st.write(f"**{alt.get('product_name')}**")

    def render_history_section(self) -> None:
        st.markdown("### 📜 Historique des analyses")
        if not self.backend_url:
            st.info(
                "Définissez BACKEND_URL pour activer la journalisation "
                "et l'historique."
            )
            return
        refresh = st.button("🔄 Rafraîchir l'historique", key="refresh_history")
        if refresh or st.session_state.analysis_history is None:
            data = self._backend_request(
                "get",
                "/history/analyses",
                on_error=lambda _: st.warning(
                    "Impossible de récupérer l'historique du backend."
                ),
            )
            st.session_state.analysis_history = (
                data if isinstance(data, list) else []
            )
        history = st.session_state.analysis_history or []
        if not history:
            st.info("Aucune analyse enregistrée pour le moment.")
            return
        rows = []
        for entry in history:
            rows.append(
                {
                    "Produit": entry.get("product_name", "Produit"),
                    "Date": self._format_timestamp(entry.get("created_at")),
                    "Résultat": self._extract_status(entry.get("result")),
                }
            )
        st.table(rows)

    def render_recipes_section(self) -> None:
        st.title("👨‍🍳 Le Chef Sans Gluten")
        mode_cuisine = st.radio(
            "Option :",
            ["✨ Créer une recette", "🔄 Adapter une recette"],
            horizontal=True,
        )
        st.divider()
        if mode_cuisine == "✨ Créer une recette":
            col1, col2 = st.columns([2, 1])
            plat = col1.text_input("Plat souhaité")
            if col2.button("🍳 Générer") and plat:
                with st.spinner("Création..."):
                    recette = self._run_recipe("creation", plat)
                    if recette:
                        st.session_state.recette_generee = recette
        else:
            texte = st.text_area("Collez votre recette ici :")
            if st.button("✨ Transformer") and texte:
                with st.spinner("Adaptation..."):
                    recette = self._run_recipe("adaptation", texte)
                    if recette:
                        st.session_state.recette_generee = recette
        if st.session_state.recette_generee:
            st.markdown("---")
            st.subheader("🍽️ Résultat")
            st.markdown(st.session_state.recette_generee)

    def _backend_request(
        self,
        method: str,
        endpoint: str,
        *,
        on_error: Optional[Callable[[Exception], None]] = None,
        **kwargs: Any,
    ) -> Optional[Any]:
        if not self.backend_url:
            return None
        url = f"{self.backend_url}{endpoint}"
        try:
            response = requests.request(
                method,
                url,
                timeout=kwargs.pop("timeout", 15),
                **kwargs,
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            if on_error:
                on_error(exc)
            return None

    def _run_analysis(self, product: Product) -> Optional[str]:
        if self.backend_url:
            data = self._backend_request(
                "post",
                "/analysis",
                json={"product": product},
                on_error=lambda _: st.error(
                    "Impossible de contacter le backend pour l'analyse."
                ),
            )
            if isinstance(data, dict):
                st.session_state.analysis_history = None
                return data.get("result")
        return self.analyzer.analyze_product(product)

    def _run_recipe(self, mode: str, input_text: str) -> Optional[str]:
        if self.backend_url:
            data = self._backend_request(
                "post",
                "/recipes",
                json={"mode": mode, "input_text": input_text},
                on_error=lambda _: st.error(
                    "Impossible de contacter le backend pour la recette."
                ),
            )
            if isinstance(data, dict):
                return data.get("recipe")
        return self.analyzer.generate_recipe(mode, input_text)

    @staticmethod
    def _format_timestamp(value: Optional[str]) -> str:
        if not value:
            return ""
        clean = value.replace("T", " ")
        if "+" in clean:
            clean = clean.split("+")[0]
        if "Z" in clean:
            clean = clean.replace("Z", "")
        return clean.split(".")[0]

    @staticmethod
    def _extract_status(value: Optional[str]) -> str:
        if not value:
            return ""
        first_line = value.splitlines()[0]
        return first_line.replace("###", "").strip()
