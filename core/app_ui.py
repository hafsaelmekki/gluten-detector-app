from __future__ import annotations

import re
from datetime import datetime
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Sequence,
    Tuple,
    TYPE_CHECKING,
)

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
            "recettes_favorites": [],
            "favorites_cache": None,
            "scanner_choice": "🔎 Analyse",
            "chef_choice": "✨ Créer",
            "active_section": "scanner",
            "last_search": None,
            "resultats_recherche": None,
            "search_query": "",
            "analysis_history": None,
        }
        for key, value in defaults.items():
            st.session_state.setdefault(key, value)

    def render_sidebar(self) -> Tuple[str, str, str]:
        with st.sidebar:
            try:
                st.image(
                    "images/logo/logo_titre.png", use_container_width=True
                )
            except Exception:
                st.warning("⚠️ Logo introuvable (images/logo/logo_titre.png)")
                st.caption("Placez votre image dans le bon dossier.")
            st.write("")
            st.markdown(
                (
                    "<div style='font-weight:bold;color:#182032;'>"
                    "Scanner & Analyse</div>"
                ),
                unsafe_allow_html=True,
            )
            scanner_options = ["🔎 Analyse", "📜 Historique"]
            scanner_choice = option_menu(
                menu_title=None,
                options=scanner_options,
                icons=["search", "journal-text"],
                default_index=scanner_options.index(
                    st.session_state.scanner_choice
                ),
                styles=self._submenu_style(),
                key="scanner_mode",
            )
            if scanner_choice != st.session_state.scanner_choice:
                st.session_state.scanner_choice = scanner_choice
                st.session_state.active_section = "scanner"

            st.markdown(
                "<hr style='margin:10px 0;'>",
                unsafe_allow_html=True,
            )
            st.markdown(
                (
                    "<div style='font-weight:bold;color:#182032;'>"
                    "Chef & Recettes</div>"
                ),
                unsafe_allow_html=True,
            )
            chef_options = ["✨ Créer", "🔄 Adapter", "❤️ Favoris"]
            chef_choice = option_menu(
                menu_title=None,
                options=chef_options,
                icons=["stars", "pencil-square", "heart"],
                default_index=chef_options.index(
                    st.session_state.chef_choice
                ),
                styles=self._submenu_style(),
                key="mode_recette",
            )
            if chef_choice != st.session_state.chef_choice:
                st.session_state.chef_choice = chef_choice
                st.session_state.active_section = "chef"

            st.divider()
            if self.api_key_present:
                st.success("✅ Clé API connectée")
            else:
                st.error("❌ Clé API manquante")
        return (
            st.session_state.active_section,
            st.session_state.scanner_choice,
            st.session_state.chef_choice,
        )

    def render(self) -> None:
        self.init_session()
        active_section, sous_scanner, sous_chef = self.render_sidebar()
        if active_section == "scanner":
            if sous_scanner == "📜 Historique":
                self.render_history_section()
            else:
                self.render_scanner_section(show_history=False)
        else:
            if sous_chef == "❤️ Favoris":
                self.render_favorites_section()
            else:
                mode = (
                    "creation" if sous_chef == "✨ Créer" else "adaptation"
                )
                self.render_recipes_section(mode=mode)

    def render_scanner_section(self, show_history: bool = True) -> None:
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
        if show_history:
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
        rows_html = [
            "<table style='width:100%; border-collapse:collapse;'>",
            "<thead><tr><th style='text-align:left;'>Produit</th>"
            "<th style='text-align:left;'>Date</th>"
            "<th style='text-align:left;'>Résultat</th></tr></thead><tbody>",
        ]
        for entry in history:
            produit = entry.get("product_name", "Produit")
            date = self._format_timestamp(entry.get("created_at"))
            statut = self._extract_status(entry.get("result"))
            image = entry.get("image_url")
            color = "#e57373" if statut == "Contient du gluten" else "#aed581"
            image_html = (
                f"<img src='{image}' alt='{produit}' height='60'>"
                if image
                else ""
            )
            rows_html.append(
                "<tr>"
                f"<td>{image_html}<div>{produit}</div></td>"
                f"<td>{date}</td>"
                f"<td style='background:{color};padding:6px;'>{statut}</td>"
                "</tr>"
            )
        rows_html.append("</tbody></table>")
        st.markdown("\n".join(rows_html), unsafe_allow_html=True)

    def render_recipes_section(self, mode: str) -> None:
        st.title("👨‍🍳 Le Chef Sans Gluten")
        st.subheader(
            "✨ Créer une recette"
            if mode == "creation"
            else "🔄 Adapter une recette"
        )
        st.divider()
        user_input = ""
        if mode == "creation":
            col1, col2 = st.columns([2, 1])
            plat = col1.text_input("Plat souhaité", key="create_input")
            user_input = plat
            if col2.button("🍳 Générer", key="create_button") and plat:
                with st.spinner("Création..."):
                    recette = self._run_recipe("creation", plat)
                    if recette:
                        st.session_state.recette_generee = recette
        else:
            texte = st.text_area(
                "Collez votre recette ici :",
                key="adapt_input",
            )
            user_input = texte
            if st.button("✨ Transformer", key="adapt_button") and texte:
                with st.spinner("Adaptation..."):
                    recette = self._run_recipe("adaptation", texte)
                    if recette:
                        st.session_state.recette_generee = recette
        if st.session_state.recette_generee:
            st.markdown("---")
            st.subheader("🍽️ Résultat")
            st.markdown(st.session_state.recette_generee)
            if st.button(
                "❤️ Ajouter aux favoris",
                key=f"fav_{mode}",
            ):
                self._add_favorite(
                    mode,
                    user_input,
                    st.session_state.recette_generee,
                )

    def render_favorites_section(self) -> None:
        st.title("❤️ Recettes favorites")
        favoris = self._get_favorites()
        if not favoris:
            st.info("Aucune recette enregistrée pour le moment.")
            return
        col_clear, _ = st.columns([1, 3])
        if col_clear.button("🗑️ Vider les favoris"):
            self._clear_favorites()
            st.success("Favoris supprimés")
            st.experimental_rerun()
        for idx, fav in enumerate(favoris):
            title = fav.get("input") or fav.get("input_text") or "Recette"
            header = title if title.strip() else "Recette"
            subtitle = (
                f"{fav.get('mode', '')} · "
                f"{self._format_timestamp(fav.get('created_at', ''))}"
            )
            with st.expander(header, expanded=False):
                st.caption(subtitle)
                st.markdown(fav.get("recipe", ""))
                if st.button("Supprimer", key=f"fav_del_{idx}"):
                    self._delete_favorite(idx, favoris)
                    st.experimental_rerun()

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
    def _submenu_style() -> Dict[str, Dict[str, str]]:
        return {
            "container": {
                "padding": "0!important",
                "background-color": "transparent",
                "margin-top": "4px",
                "margin-left": "15px",
            },
            "icon": {"color": "#182032", "font-size": "16px"},
            "nav-link": {
                "font-size": "14px",
                "text-align": "left",
                "margin": "0px",
                "color": "#182032",
                "--hover-color": "#e1e1e1",
            },
            "nav-link-selected": {
                "background-color": "#5c7cfa",
                "color": "white",
            },
        }

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
        first_line = value.splitlines()[0].replace("###", "").strip()
        lowered = first_line.lower()
        if "🔴" in first_line or "⚠️" in first_line:
            return "Contient du gluten"
        if "contient" in lowered or (
            "gluten" in lowered and "sans" not in lowered
        ):
            return "Contient du gluten"
        return "Sans gluten"

    def _get_favorites(self) -> List[Dict[str, str]]:
        if self.backend_url:
            if st.session_state.favorites_cache is None:
                data = self._backend_request(
                    "get",
                    "/favorites",
                    on_error=lambda _: st.warning(
                        "Impossible de charger les favoris depuis le backend."
                    ),
                )
                st.session_state.favorites_cache = (
                    data if isinstance(data, list) else []
                )
            return st.session_state.favorites_cache or []
        return st.session_state.recettes_favorites or []

    def _add_favorite(self, mode: str, user_input: str, recipe: str) -> None:
        payload = {
            "mode": mode,
            "input_text": user_input or "",
            "recipe": recipe,
        }
        if self.backend_url:
            resp = self._backend_request(
                "post",
                "/favorites",
                json=payload,
                on_error=lambda _: st.error(
                    "Impossible d'enregistrer la recette dans les favoris."
                ),
            )
            if resp:
                st.session_state.favorites_cache = None
                st.toast("Ajouté aux favoris ✅")
            return
        entry = {
            "mode": "Création" if mode == "creation" else "Adaptation",
            "input": payload["input_text"],
            "recipe": recipe,
            "created_at": datetime.utcnow().isoformat(),
        }
        favs = st.session_state.get("recettes_favorites", [])
        favs.insert(0, entry)
        st.session_state.recettes_favorites = favs[:20]
        st.toast("Ajouté aux favoris ✅")

    def _delete_favorite(
        self, index: int, favorites: List[Dict[str, str]]
    ) -> None:
        if self.backend_url and favorites:
            fav_id = favorites[index].get("id")
            if fav_id:
                self._backend_request(
                    "delete",
                    f"/favorites/{fav_id}",
                    on_error=lambda _: st.error(
                        "Suppression impossible sur le backend."
                    ),
                )
                st.session_state.favorites_cache = None
                return
        st.session_state.recettes_favorites.pop(index)

    def _clear_favorites(self) -> None:
        if self.backend_url:
            self._backend_request(
                "delete",
                "/favorites",
                on_error=lambda _: st.error(
                    "Impossible de vider les favoris sur le backend."
                ),
            )
            st.session_state.favorites_cache = None
            return
        st.session_state.recettes_favorites = []
