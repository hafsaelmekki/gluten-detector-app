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

from uuid import uuid4


import requests

import streamlit as st

from streamlit.delta_generator import DeltaGenerator

from streamlit_option_menu import option_menu

from .openfoodfacts_api import OpenFoodFactsAPIError


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
            "profils_locaux": [],
            "profiles_cache": None,
            "profil_actif": None,
            "scanner_choice": "Analyse",
            "chef_choice": "Créer",
            "active_section": "welcome",
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

                st.warning(
                    "Logo introuvable (images/logo/logo_titre.png)"
                )

                st.caption("Placez votre image dans le bon dossier.")

            st.write("")

            if not self._render_profile_block():

                return ("none", "", "")

            scanner_color = (
                "#0c7a52"
                if st.session_state.active_section == "scanner"
                else "#2b4c3f"
            )

            st.markdown(
                (
                    "<div style='font-weight:bold;color:"
                    f"{scanner_color};'>Scanner & Analyse</div>"
                ),
                unsafe_allow_html=True,
            )

            scanner_options = ["Analyse", "Historique"]

            scanner_choice = option_menu(
                menu_title=None,
                options=scanner_options,
                icons=["search", "journal-text"],
                default_index=scanner_options.index(
                    st.session_state.scanner_choice
                ),
                styles=self._submenu_style(
                    highlight_active=(
                        st.session_state.active_section == "scanner"
                    )
                ),
                key="scanner_mode",
            )

            if scanner_choice != st.session_state.scanner_choice:

                st.session_state.scanner_choice = scanner_choice

                st.session_state.active_section = "scanner"

            st.markdown(
                "<hr style='margin:10px 0;'>",
                unsafe_allow_html=True,
            )

            chef_color = (
                "#0c7a52"
                if st.session_state.active_section == "chef"
                else "#2b4c3f"
            )

            st.markdown(
                (
                    "<div style='font-weight:bold;color:"
                    f"{chef_color};'>Chef & Recettes</div>"
                ),
                unsafe_allow_html=True,
            )

            chef_options = [
                "Créer",
                "Adapter",
                "Favoris",
            ]

            chef_choice = option_menu(
                menu_title=None,
                options=chef_options,
                icons=["stars", "pencil-square", "heart"],
                default_index=chef_options.index(st.session_state.chef_choice),
                styles=self._submenu_style(
                    highlight_active=(
                        st.session_state.active_section == "chef"
                    )
                ),
                key="mode_recette",
            )

            if chef_choice != st.session_state.chef_choice:

                st.session_state.chef_choice = chef_choice

                st.session_state.active_section = "chef"

            st.divider()

            if self.api_key_present:

                st.success("Clé API connectée")

            else:

                st.error("Clé API manquante")

        return (
            st.session_state.active_section,
            st.session_state.scanner_choice,
            st.session_state.chef_choice,
        )

    def _render_profile_block(self) -> bool:

        st.markdown("## Compte")

        profiles = self._get_profiles()

        active_id = st.session_state.profil_actif

        current = self._find_profile(profiles, active_id)

        if current:

            name = current.get("name", "Utilisateur")

            st.success(f"Connecté en tant que {name}")

            email = current.get("email")

            if email:

                st.caption(f"Email : {email}")

            logout_clicked = st.button(
                "🔒 Déconnexion", key="logout_btn", type="secondary"
            )

            if logout_clicked:

                self._set_active_profile(None)

                st.rerun()

            return True

        st.info("Connectez-vous ou inscrivez-vous pour continuer.")

        st.markdown("#### Connexion")

        with st.form("login_form", clear_on_submit=False):

            identifier = st.text_input("Email ou nom", key="login_identifier")

            password = st.text_input(
                "Mot de passe", type="password", key="login_password"
            )

            login_submit = st.form_submit_button("Se connecter")

        if login_submit:

            if self._login_profile(identifier, password):

                st.success("Connexion réussie")

                st.rerun()

            else:

                st.error("Identifiants invalides")

        st.markdown("#### Inscription")

        with st.form("signup_form", clear_on_submit=True):

            nom = st.text_input("Nom complet", key="profil_nom")

            email = st.text_input("Email (optionnel)", key="profil_email")

            password_new = st.text_input(
                "Mot de passe", type="password", key="profil_password"
            )

            signup_submit = st.form_submit_button("Créer un compte")

        if signup_submit:

            if self._add_profile(nom, email, password_new):

                st.session_state.active_section = "scanner"

                st.rerun()

        return False

    def render(self) -> None:

        self.init_session()

        self._inject_theme_styles()

        active_section, sous_scanner, sous_chef = self.render_sidebar()

        if active_section == "none":



            self.render_welcome_section(show_login_hint=True)



            return



        if active_section == "welcome":

            self.render_welcome_section()

            return

        if active_section == "scanner":

            if sous_scanner == "Historique":

                self.render_history_section()

            else:

                self.render_scanner_section(show_history=False)

        else:

            if sous_chef == "Favoris":

                self.render_favorites_section()

            else:

                mode = (
                    "creation" if sous_chef == "Créer" else "adaptation"
                )

                self.render_recipes_section(mode=mode)

    def render_scanner_section(self, show_history: bool = True) -> None:

        st.title("Scanner de produits")

        st.markdown(
            """

            <style>

                .stTabs [data-baseweb="tab-list"]

                button[aria-selected="true"] {

                    background-color: #0fbf83 !important;

                    color: #05261b !important;

                    box-shadow: 0 8px 22px rgba(15, 191, 131, 0.35);

                }

            </style>

            """,
            unsafe_allow_html=True,
        )

        tab1, tab2 = st.tabs(
            ["Recherche texte", "Code-barres"]
        )

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

            with col2:

                st.markdown("<div style='height:0.8rem;'></div>", unsafe_allow_html=True)

                trigger_search = st.button("Chercher")

            should_search = (trigger_search and query) or (
                query and st.session_state.get("last_search") != query
            )

            if should_search and query:

                results = self._search_products(query)

                st.session_state.resultats_recherche = results or []

                st.session_state.last_search = query

            results: Optional[List[Product]] = st.session_state.get(
                "resultats_recherche"
            )

            display_results = (results or [])[:10]

            last_query = st.session_state.get("last_search")

            if display_results:

                options: Dict[str, Product] = {
                    f"{p['product_name']} ({p.get('brands', '')})": p
                    for p in display_results
                }

                choix = st.selectbox("Sélectionnez :", list(options.keys()))

                if st.button("Valider"):

                    self._select_product(options[choix], auto_analyze=True)

            elif last_query:

                st.info(f'Aucun produit trouvé pour "{last_query}".')

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

                    if st.button("Valider et analyser"):

                        try:
                            produit = self.api.search_product_by_code(code_barre)
                        except OpenFoodFactsAPIError as exc:
                            st.error("Impossible de contacter OpenFoodFacts pour ce code-barres. R?essayez plus tard.")
                            print(f"[WARN] scan code indisponible: {exc}")
                            produit = None

                        if produit:

                            self._select_product(produit, auto_analyze=True)

                        else:

                            st.error("Produit inconnu")

                else:

                    st.error("Impossible de décoder l'image")

    def render_product_details(self, product: Product) -> None:

        st.divider()

        analyse: Optional[str] = st.session_state.analyse_actuelle
        analyse_lines = analyse.splitlines() if analyse else []

        col_img, col_infos, col_score = st.columns([1, 2, 1])

        with col_img:

            if product.get("image_front_small_url"):

                st.image(product.get("image_front_small_url"), width=150)

        with col_infos:

            st.subheader(product.get("product_name"))

            st.caption(f"Marque : {product.get('brands')}")

            ingredients = product.get("ingredients_text", "")

            if ingredients:

                st.write(f"**Ingredients:** {ingredients[:200]}...")

            if not st.session_state.analyse_actuelle:

                if st.button("Lancer l'analyse", type="primary"):

                    if self._run_and_store_analysis(product):

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

        if analyse_lines:

            titre = analyse_lines[0].replace("###", "").strip()

            titre_lower = titre.lower()

            verdict_renderer = st.info

            if "interdit" in titre_lower or ("contient" in titre_lower and "sans" not in titre_lower):

                verdict_renderer = st.error

            elif "risque" in titre_lower:

                verdict_renderer = st.warning

            elif "sans" in titre_lower:

                verdict_renderer = st.success

            verdict_renderer(f"# {titre}")

            detail_lines: List[str] = []

            for detail_line in analyse_lines[1:]:

                stripped = detail_line.strip()

                if not stripped:

                    continue

                if stripped.upper().startswith("IMPORTANT"):

                    continue

                if stripped.startswith('"SEARCH_TERM') or stripped.startswith("'SEARCH_TERM"):

                    continue

                if stripped.upper().startswith("SI ROUGE") or stripped.upper().startswith("SI VERT"):

                    continue

                detail_lines.append(detail_line)

            clean_text = re.sub(
                r"SEARCH_TERM:.*",
                "",
                "\n".join(detail_lines),
            ).strip()

            if clean_text:

                st.markdown("### Justification")

                st.markdown(clean_text)

        if st.session_state.alternatives_trouvees:

            st.divider()

            st.markdown("### Meilleures alternatives sans gluten :")

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

        st.markdown("### Historique des analyses")

        if not self.backend_url:

            st.info(
                "Définissez BACKEND_URL pour activer la journalisation "
                "et l'historique."
            )

            return

        params = self._backend_user_params()

        if params is None:

            st.info("Connectez-vous pour consulter votre historique.")

            return

        refresh = st.button(
            "Rafraîchir l'historique", key="refresh_history"
        )

        if refresh or st.session_state.analysis_history is None:

            data = self._backend_request(
                "get",
                "/history/analyses",
                params=params,
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

        st.markdown(
            """
            <style>
            .gl-history-grid {
                display: flex;
                flex-direction: column;
                gap: 0;
                margin-top: 0.5rem;
                border: 1px solid #d9eee4;
                border-radius: 14px;
                overflow: hidden;
            }
            .gl-history-grid [data-testid="stVerticalBlock"],
            .gl-history-grid [data-testid="stHorizontalBlock"] {
                margin: 0 !important;
                padding: 0 !important;
            }
            .gl-history-image {
                width: 60px;
                height: 60px;
                border-radius: 14px;
                background: #f0faf6;
                display: flex;
                align-items: center;
                justify-content: center;
                overflow: hidden;
            }
            .gl-history-image img {
                width: 60px;
                height: 60px;
                object-fit: cover;
            }
            .gl-history-title {
                font-weight: 600;
                color: #0e3023;
                margin-bottom: 2px;
            }
            .gl-history-meta {
                font-size: 0.85rem;
                color: #526158;
            }
            .gl-history-status-badge {
                padding: 0.35rem 0.9rem;
                border-radius: 999px;
                font-weight: 600;
                font-size: 0.85rem;
                text-align: center;
                min-width: 110px;
                color: #0b2419;
            }
            .gl-history-action button {
                border-radius: 999px;
                border: 1px solid rgba(226, 99, 99, 0.4);
                background: rgba(226, 99, 99, 0.08);
                color: #a53030;
                font-size: 0.9rem;
                padding: 0.25rem 0.9rem;
            }
            .gl-history-action button:hover {
                background: rgba(226, 99, 99, 0.2);
                border-color: rgba(226, 99, 99, 0.6);
            }
            </style>
            """,
            unsafe_allow_html=True,
        )

        grid_container = st.container()
        grid_container.markdown("<div class='gl-history-grid'>", unsafe_allow_html=True)

        for index, entry in enumerate(history):

            produit = entry.get("product_name", "Produit")

            date = self._format_timestamp(entry.get("created_at"))

            statut = self._extract_status(entry.get("result"))

            color_map = {
                "Interdit": "#e57373",
                "Risque": "#ffb74d",
                "Sans gluten": "#aed581",
            }

            display_status = statut or "Indisponible"

            image = entry.get("image_url")

            color = color_map.get(statut, "#cfd8dc")

            entry_id = entry.get("id")

            with grid_container:

                card = st.container()

                col_img, col_body, col_status, col_action = card.columns(
                    [0.9, 3, 1.2, 0.6]
                )

                with col_img:

                    if image:

                        st.markdown(
                            f"<div class='gl-history-image'><img src='{image}' alt='{produit}'></div>",
                            unsafe_allow_html=True,
                        )

                    else:

                        st.markdown(
                            "<div class='gl-history-image'>??</div>",
                            unsafe_allow_html=True,
                        )

                with col_body:

                    st.markdown(
                        f"<div class='gl-history-title'>{produit}</div>",
                        unsafe_allow_html=True,
                    )

                    st.markdown(
                        f"<div class='gl-history-meta'>{date}</div>",
                        unsafe_allow_html=True,
                    )

                with col_status:

                    st.markdown(
                        f"<div class='gl-history-status-badge' style='background:{color};'>{display_status}</div>",
                        unsafe_allow_html=True,
                    )

                with col_action:

                    st.markdown(
                        "<div class='gl-history-action'>",
                        unsafe_allow_html=True,
                    )

                    if entry_id is not None:

                        if st.button(
                            "🗑️",
                            key=f"history_delete_{entry_id}",
                            help="Supprimer cette analyse",
                        ):

                            self._delete_history_entry(entry_id)

                    else:

                        if st.button(
                            "🗑️",
                            key=f"history_delete_placeholder_{index}",
                            help="Supprimer cette analyse",
                        ):

                            self._delete_history_entry(None, fallback_index=index)


    def render_welcome_section(self, show_login_hint: bool = False) -> None:

        active_id = st.session_state.get("profil_actif")

        profile_name: Optional[str] = None

        if active_id is not None:

            profile = self._find_profile(self._get_profiles(), active_id)

            if profile:

                profile_name = (
                    profile.get("name")
                    or profile.get("email")
                    or str(profile.get("id"))
                )

        subtitle = (
            f"Votre espace personnalisé est prêt, {profile_name}."
            if profile_name
            else "Optimisez vos contrôles produits et vos recettes sans gluten."
        )

        headline = (
            f"## Tableau de bord Glutify · {profile_name}"
            if profile_name
            else "## Tableau de bord Glutify"
        )

        st.markdown(headline)
        st.caption(subtitle)

        st.write(
            "Glutify centralise vos contrôles de produits, la génération de recettes "
            "sans gluten et l'audit des décisions médicalisées. L'application combine "
            "un scanner OpenFoodFacts, votre moteur RAG médical et un historique "
            "traçable pour accompagner chaque profil au quotidien."
        )

        st.markdown(
            """
            **Sections principales**
            - `Scanner & Analyse` : recherche textuelle ou scan pour obtenir un verdict médicalisé, justifications et alternatives.
            - `Historique` : accès immédiat aux analyses archivées, filtres par profil et suivi des verdicts.
            - `Chef & Recettes` : modes Création/Adaptation avec sauvegarde dans les favoris.
            - `Favoris` : recettes validées et prêtes à partager ou adapter à nouveau.
            """
        )

        st.write(
            "Toutes les actions sont journalisées par profil. Pensez à vous authentifier pour synchroniser votre historique et vos favoris."
        )

        if show_login_hint:

            st.info(
                "Connectez-vous pour déverrouiller l'analyse, les recettes et vos favoris."
            )



    def render_recipes_section(self, mode: str) -> None:

        st.title("Le Chef sans gluten")

        st.subheader(
            "Créer une recette"
            if mode == "creation"
            else "Adapter une recette"
        )

        st.divider()

        user_input = ""

        if mode == "creation":

            col1, col2 = st.columns([2, 1])

            plat = col1.text_input("Plat souhaité", key="create_input")

            user_input = plat

            with col2:

                st.markdown(
                    "<div style='height:1.2rem;'></div>", unsafe_allow_html=True
                )

                trigger_generate = st.button("Générer", key="create_button")

            if trigger_generate and plat:

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

            if st.button("Transformer", key="adapt_button") and texte:

                with st.spinner("Adaptation..."):

                    recette = self._run_recipe("adaptation", texte)

                    if recette:

                        st.session_state.recette_generee = recette

        if st.session_state.recette_generee:

            st.markdown("---")

            st.subheader("Résultat")

            st.markdown(st.session_state.recette_generee)

            if st.button(
                "Ajouter aux favoris",
                key=f"fav_{mode}",
            ):

                if self._add_favorite(
                    mode,
                    user_input,
                    st.session_state.recette_generee,
                ):

                    st.toast("Favori enregistré")

    def render_favorites_section(self) -> None:

        st.title("Recettes favorites")

        owner = self._current_profile_id()

        if not owner:

            st.info("Connectez-vous pour consulter vos favoris.")

            return

        favoris = self._get_favorites()

        if not favoris:

            st.info("Aucune recette enregistrée pour le moment.")

            return

        clear_clicked = st.button(
            "Vider les favoris",
            key="fav_clear_all",
            help="Supprimer toutes les recettes sauvegardées",
            type="primary",
        )

        if clear_clicked:

            self._clear_favorites()

            st.success("Favoris supprimés")

            st.rerun()

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

                    st.rerun()

    def _select_product(
        self, product: Product, *, auto_analyze: bool = False
    ) -> None:

        st.session_state.produit_actuel = product

        st.session_state.analyse_actuelle = None

        st.session_state.alternatives_trouvees = None

        if auto_analyze and self._run_and_store_analysis(product):

            st.rerun()

            return

        st.rerun()

    def _run_and_store_analysis(
        self, product: Product, message: str = "Analyse..."
    ) -> bool:

        with st.spinner(message):

            analyse = self._run_analysis(product)

        if analyse:

            self._store_analysis_result(analyse, product)

            return True

        return False

    def _store_analysis_result(
        self, analyse: str, product: Optional[Product] = None
    ) -> None:

        st.session_state.analyse_actuelle = analyse

        statut = self._extract_status(analyse)

        if not statut:

            st.session_state.alternatives_trouvees = None

            return

        if statut.lower().startswith("sans"):

            st.session_state.alternatives_trouvees = None

            return

        term = self._extract_search_term(analyse)

        if not term and product:

            term = self._guess_generic_term(product)

        if not term:

            st.session_state.alternatives_trouvees = None

            return

        try:

            st.session_state.alternatives_trouvees = (
                self.api.find_gluten_free_alternatives(term)
            )

        except OpenFoodFactsAPIError as exc:

            st.warning("Alternatives indisponibles (OpenFoodFacts).")

            print(f"[WARN] alternatives indisponibles: {exc}")

            st.session_state.alternatives_trouvees = None

    def _search_products(self, query: str) -> List[Product]:
        if self.backend_url:
            data = self._backend_request(
                "get",
                "/products/search",
                params={"query": query},
                on_error=lambda _: st.error(
                    "Impossible de récupérer les produits depuis le backend."
                ),
            )

            # Read backend responses while suppressing user-facing noise
            if isinstance(data, dict):
                products = data.get("products") or []
                return [
                    prod
                    for prod in products
                    if isinstance(prod, dict) and prod.get("product_name")
                ]

            elif isinstance(data, list):
                return [
                    prod for prod in data
                    if isinstance(prod, dict) and prod.get("product_name")
                ]

            return []

        try:
            return self.api.search_products(query)
        except OpenFoodFactsAPIError as exc:
            st.error("OpenFoodFacts est temporairement indisponible. Merci de reessayer.")
            print(f"[WARN] search_products indisponible: {exc}")
            return []

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
                json={
                    "product": product,
                    "user_id": self._current_backend_user_id(),
                },
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
                json={
                    "mode": mode,
                    "input_text": input_text,
                    "user_id": self._current_backend_user_id(),
                },
                on_error=lambda _: st.error(
                    "Impossible de contacter le backend pour la recette."
                ),
            )

            if isinstance(data, dict):

                return data.get("recipe")

        return self.analyzer.generate_recipe(mode, input_text)

    @staticmethod
    def _inject_theme_styles() -> None:

        st.markdown(
            """
            <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Space+Grotesk:wght@500&display=swap');
            :root {
                --gl-forest: #0b3d2e;
                --gl-emerald: #0fbf83;
                --gl-mint: #dff7ec;
                --gl-cloud: #f5fffb;
                --gl-charcoal: #122820;
                --gl-sage: #7fcfaf;
            }
            html, body, .stApp {
                background-color: var(--gl-cloud);
                color: var(--gl-charcoal);
                font-family: "Inter","Segoe UI",system-ui,-apple-system,BlinkMacSystemFont;
            }
            .block-container {
                padding-top: 1.5rem;
                padding-bottom: 2rem;
                max-width: 1200px;
            }
            [data-testid="stSidebar"] {
                background: linear-gradient(180deg, #f3fff9 0%, #d8faeb 45%, #b2f3d9 100%);
                color: #0d3f2d;
                border-right: none;
                box-shadow: 4px 0 18px rgba(9, 46, 37, 0.18);
            }
            [data-testid="stSidebar"] * {
                color: inherit;
            }
            [data-testid="stSidebar"] .stButton>button {
                border: 1px solid rgba(12, 58, 43, 0.25);
                color: #ffffff;
                background: #0c4a35;
                box-shadow: none;
            }
            [data-testid="stSidebar"] .stButton {
                display: inline-flex;
                align-items: center;
                margin-right: 8px;
                margin-bottom: 0.4rem;
            }
            [data-testid="stSidebar"] .stButton>button:hover {
                background: rgba(255,255,255,0.55);
            }
            .stButton>button {
                background: linear-gradient(120deg, #0fbf83, #13d49a);
                color: #052419;
                border: none;
                border-radius: 999px;
                padding: 0.45rem 1.75rem;
                font-weight: 600;
                box-shadow: 0 10px 25px rgba(16, 191, 131, 0.35);
                transition: all 0.15s ease-out;
            }
            .stButton>button:hover {
                color: #02150e;
                transform: translateY(-1px);
                box-shadow: 0 14px 32px rgba(16, 191, 131, 0.45);
            }
            .stButton>button:active {
                transform: translateY(0);
            }
            .stTabs [data-baseweb="tab-list"] button {
                border-radius: 999px;
                border: none;
                background: rgba(15, 191, 131, 0.12);
                color: var(--gl-forest);
                font-weight: 500;
            }
            .stTabs [data-baseweb="tab-content"] {
                background: #ffffff;
                border-radius: 24px;
                padding: 1.15rem;
                box-shadow: 0 20px 45px rgba(9, 40, 30, 0.08);
            }
            .stAlert {
                border-radius: 16px;
                border-left: 4px solid var(--gl-emerald);
                background: rgba(15, 191, 131, 0.08);
                color: var(--gl-forest);
            }
            section[data-testid="stSidebar"] button[kind="secondary"] {
                border-radius: 8px;
                padding: 0.15rem 0.85rem;
                background: #0c4a35;
                color: #ffffff;
                border: 1px solid rgba(12, 74, 53, 0.35);
                font-size: 0.7rem;
                min-height: 1.8rem;
                box-shadow: none;
                width: auto;
                display: inline-flex;
                align-items: center;
                justify-content: center;
                gap: 4px;
                margin-right: 6px;
            }
            section[data-testid="stSidebar"] button[kind="secondary"]:hover {
                background: #0a3727;
                border-color: rgba(15, 191, 131, 0.6);
                color: #e6fff5;
            }
            input, textarea, div[data-baseweb="input"], .stSelectbox>div>div, .stMultiSelect>div>div {
                border-radius: 14px !important;
                border: 1px solid #b8e4d2 !important;
                background-color: #ffffff !important;
            }
            input, textarea {
                color: var(--gl-charcoal) !important;
            }
            .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
                color: var(--gl-forest);
                font-family: "Space Grotesk","Inter","Segoe UI",sans-serif;
            }
            .stMarkdown p {
                color: var(--gl-charcoal);
                font-size: 1rem;
            }
            div[data-testid="stMetricValue"] {
                color: var(--gl-emerald);
            }
            div[data-testid="stHorizontalBlock"]>div>div {
                background: #ffffff;
                border-radius: 20px;
                box-shadow: 0 20px 45px rgba(7, 32, 24, 0.08);
                padding: 1rem;
            }
            footer, header {visibility: hidden;}
            ::selection {
                background: rgba(15, 191, 131, 0.35);
                color: #042116;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )

    @staticmethod
    def _submenu_style(highlight_active: bool = True) -> Dict[str, Dict[str, str]]:

        styles = {
            "container": {
                "padding": "0!important",
                "background-color": "transparent",
                "margin-top": "4px",
                "margin-left": "15px",
            },
            "icon": {"color": "#12553e", "font-size": "17px"},
            "nav-link": {
                "font-size": "14px",
                "text-align": "left",
                "margin": "0px",
                "color": "#0d3f2d",
                "--hover-color": "rgba(13,63,45,0.08)",
                "border-radius": "10px",
                "border": "1px solid transparent",
            },
        }

        if highlight_active:

            styles["nav-link-selected"] = {
                "background-color": "rgba(15, 191, 131, 0.15)",
                "color": "#0b3a2b",
                "border": "1px solid rgba(15, 191, 131, 0.35)",
            }

        else:

            styles["nav-link-selected"] = {
                "background-color": "transparent",
                "color": "#0d3f2d",
            }

        return styles

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

        if "erreur" in lowered:
            return ""

        if "interdit" in lowered or ("contient" in lowered and "sans" not in lowered):
            return "Interdit"

        if "risque" in lowered:
            return "Risque"

        if "sans" in lowered:
            return "Sans gluten"

        return ""

    @staticmethod
    def _extract_search_term(value: Optional[str]) -> Optional[str]:

        if not value:

            return None

        match = re.search(
            r"search[\s_-]*term\s*[:=]\s*(.+)",
            value,
            flags=re.IGNORECASE,
        )

        if not match:

            return None

        raw = match.group(1).strip().strip('"').strip("'")

        clean = raw.splitlines()[0].strip()

        return clean or None

    @staticmethod
    def _guess_generic_term(product: Optional[Product]) -> Optional[str]:

        if not product:

            return None

        candidates: List[str] = []

        for key in (
            "generic_name_fr",
            "generic_name",
            "categories",
            "product_name",
        ):

            value = product.get(key)

            if isinstance(value, str) and value.strip():

                candidates.append(value.split(",")[0].strip())

        tags = product.get("categories_tags")

        if isinstance(tags, list):

            for tag in tags:

                if not isinstance(tag, str):
                    continue

                if ":" in tag:

                    tag = tag.split(":", 1)[1]

                tag_clean = tag.replace("-", " ").strip()

                if tag_clean:
                    candidates.append(tag_clean)

        for candidate in candidates:

            if candidate:

                return candidate

        return None

    def _get_favorites(self) -> List[Dict[str, str]]:

        if self.backend_url:

            params = self._backend_user_params()

            if params is None:

                return []

            if st.session_state.favorites_cache is None:

                data = self._backend_request(
                    "get",
                    "/favorites",
                    params=params,
                    on_error=lambda _: st.warning(
                        "Impossible de charger les favoris depuis le backend."
                    ),
                )

                st.session_state.favorites_cache = (
                    data if isinstance(data, list) else []
                )

            return st.session_state.favorites_cache or []

        owner = self._current_profile_id()

        if not owner:

            return []

        result = []

        for fav in st.session_state.recettes_favorites or []:

            owner_id = fav.get("owner_id")

            if owner_id in (None, owner):

                if owner_id is None:

                    fav["owner_id"] = owner

                result.append(fav)

        return result

    def _add_favorite(self, mode: str, user_input: str, recipe: str) -> bool:

        payload = {
            "mode": mode,
            "input_text": user_input or "",
            "recipe": recipe,
            "user_id": self._current_backend_user_id(),
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

                st.toast("Ajouté aux favoris")

                return True

            return False

        entry = {
            "mode": "Création" if mode == "creation" else "Adaptation",
            "input": payload["input_text"],
            "recipe": recipe,
            "owner_id": self._current_profile_id(),
            "created_at": datetime.utcnow().isoformat(),
        }

        favs = st.session_state.get("recettes_favorites", [])

        favs.insert(0, entry)

        st.session_state.recettes_favorites = favs[:20]

        st.toast("Ajouté aux favoris")

        return True

    def _delete_favorite(
        self, index: int, favorites: List[Dict[str, str]]
    ) -> None:

        if self.backend_url and favorites:

            fav_id = favorites[index].get("id")

            if fav_id:

                self._backend_request(
                    "delete",
                    f"/favorites/{fav_id}",
                    params=self._backend_user_params(),
                    on_error=lambda _: st.error(
                        "Suppression impossible sur le backend."
                    ),
                )

                st.session_state.favorites_cache = None

                return

        owner = self._current_profile_id()

        if not owner:

            return

        if 0 <= index < len(st.session_state.recettes_favorites):

            entry = st.session_state.recettes_favorites[index]

            if entry.get("owner_id") in (None, owner):

                st.session_state.recettes_favorites.pop(index)

    def _clear_favorites(self) -> None:

        if self.backend_url:

            self._backend_request(
                "delete",
                "/favorites",
                params=self._backend_user_params(),
                on_error=lambda _: st.error(
                    "Impossible de vider les favoris sur le backend."
                ),
            )

            st.session_state.favorites_cache = None

            return

        owner = self._current_profile_id()

        if not owner:

            return

        st.session_state.recettes_favorites = [
            fav
            for fav in st.session_state.recettes_favorites
            if fav.get("owner_id") not in (None, owner)
        ]

    def _delete_history_entry(
        self, entry_id: Optional[int], fallback_index: Optional[int] = None
    ) -> None:

        if entry_id is None:

            history = st.session_state.analysis_history or []

            if fallback_index is not None and 0 <= fallback_index < len(history):

                history.pop(fallback_index)

                st.session_state.analysis_history = history

                st.toast("Analyse retirée localement.")

            else:

                st.warning("Impossible de supprimer cette entrée.")

            return

        if not self.backend_url:

            st.warning(
                "Connexion au backend requise pour supprimer définitivement une analyse."
            )

            return

        params = self._backend_user_params()

        if params is None:

            st.info("Connectez-vous pour gérer votre historique.")

            return

        response = self._backend_request(
            "delete",
            f"/history/analyses/{entry_id}",
            params=params,
            on_error=lambda _: st.error(
                "Suppression impossible pour cette analyse."
            ),
        )

        if isinstance(response, dict):

            history = st.session_state.analysis_history or []

            st.session_state.analysis_history = [
                row for row in history if row.get("id") != entry_id
            ]

            st.toast("Analyse supprimée.")

            st.rerun()

    def _get_profiles(self) -> List[Dict[str, Any]]:

        if self.backend_url:

            if st.session_state.profiles_cache is None:

                data = self._backend_request(
                    "get",
                    "/users",
                    on_error=lambda _: st.warning(
                        "Impossible de charger les profils depuis le backend."
                    ),
                )

                st.session_state.profiles_cache = (
                    data if isinstance(data, list) else []
                )

            return st.session_state.profiles_cache or []

        return st.session_state.profils_locaux or []

    def _add_profile(self, name: str, email: str, password: str) -> bool:

        clean_name = name.strip()

        clean_password = password.strip()

        if not clean_name or not clean_password:

            st.warning("Nom et mot de passe requis.")

            return False

        payload = {
            "name": clean_name,
            "email": email.strip() or None,
            "password": clean_password,
        }

        if self.backend_url:

            resp = self._backend_request(
                "post",
                "/users",
                json=payload,
                on_error=lambda _: st.error(
                    "Impossible de créer le profil sur le backend."
                ),
            )

            if resp:

                st.session_state.profiles_cache = None

                self._set_active_profile(resp.get("id"))

                st.toast("Profil ajouté")

                return True

            return False

        entry = {
            "id": str(uuid4()),
            "name": clean_name,
            "email": payload["email"],
            "password": clean_password,
            "created_at": datetime.utcnow().isoformat(),
        }

        locaux = st.session_state.profils_locaux

        locaux.insert(0, entry)

        st.session_state.profils_locaux = locaux

        self._set_active_profile(entry["id"])

        st.toast("Profil ajouté")

        return True

    def _delete_profile(self, profile_id: Optional[Any]) -> None:

        if not profile_id:

            return

        if self.backend_url:

            self._backend_request(
                "delete",
                f"/users/{profile_id}",
                on_error=lambda _: st.error(
                    "Impossible de supprimer ce profil sur le backend."
                ),
            )

            st.session_state.profiles_cache = None

        else:

            locaux = st.session_state.profils_locaux

            st.session_state.profils_locaux = [
                p for p in locaux if str(p.get("id")) != str(profile_id)
            ]

        if str(st.session_state.profil_actif) == str(profile_id):

            self._set_active_profile(None)

    def _login_profile(self, identifier: str, password: str) -> bool:

        ident = identifier.strip()

        pwd = password.strip()

        if not ident or not pwd:

            st.warning("Identifiants requis.")

            return False

        if self.backend_url:

            resp = self._backend_request(
                "post",
                "/auth/login",
                json={"identifier": ident, "password": pwd},
                on_error=lambda _: st.error(
                    "Connexion impossible via le backend."
                ),
            )

            if resp:

                st.session_state.profiles_cache = None

                self._set_active_profile(resp.get("id"))

                return True

            return False

        for profile in st.session_state.profils_locaux:

            if (
                profile.get("email") == ident or profile.get("name") == ident
            ) and profile.get("password") == pwd:

                self._set_active_profile(profile.get("id"))

                return True

        return False

    @staticmethod
    def _format_profile_label(profile: Dict[str, Any]) -> str:

        email = profile.get("email")

        name = profile.get("name", "Profil")

        return f"{name} ({email})" if email else name

    @staticmethod
    def _find_profile(
        profiles: List[Dict[str, Any]], profile_id: Optional[Any]
    ) -> Optional[Dict[str, Any]]:

        if not profile_id:

            return None

        for profile in profiles:

            if str(profile.get("id")) == str(profile_id):

                return profile

        return None

    def _set_active_profile(self, profile_id: Optional[Any]) -> None:

        prev = st.session_state.get("profil_actif")

        prev_norm = str(prev) if prev is not None else None

        new_norm = str(profile_id) if profile_id is not None else None

        st.session_state.profil_actif = profile_id

        if prev_norm == new_norm:

            return

        self._reset_user_context()

    def _reset_user_context(self) -> None:

        for key in [
            "produit_actuel",
            "analyse_actuelle",
            "alternatives_trouvees",
            "recette_generee",
            "resultats_recherche",
            "last_search",
        ]:

            st.session_state[key] = None

        st.session_state.analysis_history = None

        st.session_state.favorites_cache = None

        st.session_state.active_section = "welcome"

        st.session_state.scanner_choice = "Analyse"

        st.session_state.chef_choice = "Créer"

    @staticmethod
    def _current_profile_id() -> Optional[str]:

        pid = st.session_state.get("profil_actif")

        return str(pid) if pid is not None else None

    def _current_backend_user_id(self) -> Optional[int]:

        if not self.backend_url:

            return None

        pid = st.session_state.get("profil_actif")

        try:

            return int(pid)

        except (TypeError, ValueError):

            return None

    def _backend_user_params(self) -> Optional[Dict[str, int]]:

        uid = self._current_backend_user_id()

        if uid is None:

            return None

        return {"user_id": uid}
