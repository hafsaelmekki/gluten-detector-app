import streamlit as st
import requests
from groq import Groq
from PIL import Image
from pyzbar.pyzbar import decode
import re
from streamlit_option_menu import option_menu

# --- TA CLÉ API ---
API_KEY = API_KEY = st.secrets["GROQ_API_KEY"]

# 1. Configuration de la page
st.set_page_config(page_title="GlutenFree App", page_icon="images/logo/logo_titre.png", layout="wide")

# 2. Sidebar (LOGO LOCAL & COULEURS)
with st.sidebar:
    # --- CHANGEMENT 1 : LOGO LOCAL ---
    # Assurez-vous que le dossier images/logo/ existe !
    try:
        st.image("images/logo/logo_titre.png", use_container_width=True)
    except:
        st.warning("⚠️ Logo introuvable (images/logo/logo_titre.png)")
        st.caption("Placez votre image dans le bon dossier.")

    st.write("")  # Petit espace

    # --- CHANGEMENT 2 : COULEURS DU MENU ---
    choix_section = option_menu(
        menu_title=None,  # On retire le titre du menu car il y a le logo au dessus
        options=["Scanner & Analyse", "Chef & Recettes"],
        icons=["upc-scan", "egg-fried"],
        default_index=0,
        styles={
            "container": {"padding": "0!important", "background-color": "transparent"},
            # Ton Bleu Foncé
            "icon": {"color": "#182032", "font-size": "18px"},
            "nav-link": {
                "font-size": "16px",
                "text-align": "left",
                "margin": "5px",
                "color": "#182032",  # Texte en bleu foncé
                "--hover-color": "#e1e1e1"
            },
            "nav-link-selected": {
                "background-color": "#84bf78",  # Ton Vert
                "color": "white"  # Texte blanc sur fond vert
            },
        }
    )

    st.divider()
    st.success("✅ Clé API connectée")

# --- GESTION MÉMOIRE ---
if "produit_actuel" not in st.session_state:
    st.session_state.produit_actuel = None
if "analyse_actuelle" not in st.session_state:
    st.session_state.analyse_actuelle = None
if "alternatives_trouvees" not in st.session_state:
    st.session_state.alternatives_trouvees = None
if "recette_generee" not in st.session_state:
    st.session_state.recette_generee = None

# --- FONCTIONS ---


def chercher_produits_texte(nom):
    try:
        url = "https://world.openfoodfacts.org/cgi/search.pl"
        params = {"search_terms": nom, "search_simple": 1,
                  "action": "process", "json": 1, "page_size": 20}
        data = requests.get(url, params=params).json()
        return [p for p in data.get("products", []) if p.get("product_name")]
    except:
        return []


def chercher_produit_code(code):
    try:
        url = f"https://world.openfoodfacts.org/api/v0/product/{code}.json"
        data = requests.get(url).json()
        return data["product"] if data["status"] == 1 else None
    except:
        return None


def decoder_image(image_file):
    try:
        img = Image.open(image_file)
        codes = decode(img)
        return codes[0].data.decode("utf-8") if codes else None
    except:
        return None


def trouver_alternatives(categorie_produit):
    url = "https://world.openfoodfacts.org/cgi/search.pl"
    params = {"search_terms": f"{categorie_produit}", "tagtype_0": "labels", "tag_contains_0": "contains",
              "tag_0": "en:gluten-free", "sort_by": "popularity", "page_size": 3, "json": 1}
    try:
        data = requests.get(url, params=params).json()
        return data.get("products", [])
    except:
        return []


def analyser_produit_ia(produit):
    if not API_KEY:
        return "⚠️ Erreur clé API"
    client = Groq(api_key=API_KEY)
    score = produit.get('nutriscore_grade', 'Inconnu').upper()
    prompt = f"""
    Produit : {produit.get('product_name')}
    Ingrédients : {produit.get('ingredients_text', 'Non listés')}
    Traces : {produit.get('traces', 'Non indiqué')}
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
        return client.chat.completions.create(messages=[{"role": "user", "content": prompt}], model="llama-3.3-70b-versatile", temperature=0.0).choices[0].message.content
    except Exception as e:
        return f"Erreur : {e}"


def generer_recette_ia(mode, input_text):
    if not API_KEY:
        return "⚠️ Erreur clé API"
    client = Groq(api_key=API_KEY)
    sys = "Chef sans gluten." if mode == "creation" else "Expert substitution."
    usr = f"Recette sans gluten pour : {input_text}." if mode == "creation" else f"Adapte en sans gluten :\n\n{input_text}"
    try:
        return client.chat.completions.create(messages=[{"role": "system", "content": sys}, {"role": "user", "content": usr}], model="llama-3.3-70b-versatile").choices[0].message.content
    except:
        return "Erreur"


# ==========================================
# SECTION 1 : SCANNER
# ==========================================
if choix_section == "Scanner & Analyse":
    st.title("🔎 Scanner de Produits")

    # CSS Hack pour colorer les onglets (Optionnel mais joli avec tes couleurs)
    st.markdown("""
    <style>
        .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] {
            background-color: #84bf78 !important;
            color: white !important;
        }
    </style>
    """, unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["⌨️ Recherche Texte", "📸 Code-Barres"])

    with tab1:
        c1, c2 = st.columns([3, 1])
        query = c1.text_input("Nom", key="search_query")
        if c2.button("Chercher") or query:
            if query and "last_search" not in st.session_state or st.session_state.get("last_search") != query:
                res = chercher_produits_texte(query)
                st.session_state.resultats_recherche = res
                st.session_state.last_search = query
        if "resultats_recherche" in st.session_state and st.session_state.resultats_recherche:
            opts = {
                f"{p['product_name']} ({p.get('brands', '')})": p for p in st.session_state.resultats_recherche}
            choix = st.selectbox("Sélectionnez :", list(opts.keys()))
            if st.button("✅ Valider"):
                st.session_state.produit_actuel = opts[choix]
                st.session_state.analyse_actuelle = None
                st.session_state.alternatives_trouvees = None
                st.rerun()

    with tab2:
        mode = st.radio("Source :", ["Webcam", "Fichier"], horizontal=True)
        img = st.camera_input("Scan") if mode == "Webcam" else st.file_uploader(
            "Image", type=["jpg", "png"])
        if img:
            code = decoder_image(img)
            if code:
                st.success(f"Code : {code}")
                if st.button("✅ Valider et Analyser"):
                    p = chercher_produit_code(code)
                    if p:
                        st.session_state.produit_actuel = p
                        st.session_state.analyse_actuelle = None
                        st.session_state.alternatives_trouvees = None
                        st.rerun()
                    else:
                        st.error("Produit inconnu")

    if st.session_state.produit_actuel:
        p = st.session_state.produit_actuel
        st.divider()

        if st.session_state.analyse_actuelle:
            titre = st.session_state.analyse_actuelle.split(
                '\n')[0].replace("###", "").strip()
            if "🔴" in titre:
                st.error(f"# {titre}")
            elif "⚠️" in titre:
                st.warning(f"# {titre}")
            elif "🟢" in titre:
                st.success(f"# {titre}")

        col_img, col_infos, col_score = st.columns([1, 2, 1])
        with col_img:
            if p.get("image_front_small_url"):
                st.image(p.get("image_front_small_url"), width=150)
        with col_infos:
            st.subheader(p.get('product_name'))
            st.caption(f"Marque : {p.get('brands')}")
            st.write(f"**Ingrédients:** {p.get('ingredients_text')[:200]}...")
            if not st.session_state.analyse_actuelle:
                if st.button("🧠 Lancer l'analyse", type="primary"):
                    with st.spinner("Analyse..."):
                        analyse = analyser_produit_ia(p)
                        st.session_state.analyse_actuelle = analyse
                        match = re.search(r"SEARCH_TERM:\s*(.*)", analyse)
                        st.session_state.alternatives_trouvees = trouver_alternatives(
                            match.group(1).strip()) if match else None
                        st.rerun()
        with col_score:
            score = p.get("nutriscore_grade")
            if score:
                st.markdown("**Nutri-Score :**")
                st.image(
                    f"https://static.openfoodfacts.org/images/misc/nutriscore-{score}.svg", width=100)

        if st.session_state.analyse_actuelle:
            clean_text = re.sub(
                r"SEARCH_TERM:.*", "", "\n".join(st.session_state.analyse_actuelle.split('\n')[1:]))
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

# ==========================================
# SECTION 2 : RECETTES
# ==========================================
elif choix_section == "Chef & Recettes":
    st.title("👨‍🍳 Le Chef Sans Gluten")
    mode_cuisine = st.radio(
        "Option :", ["✨ Créer une recette", "🔄 Adapter une recette"], horizontal=True)
    st.divider()

    if mode_cuisine == "✨ Créer une recette":
        col1, col2 = st.columns([2, 1])
        plat = col1.text_input("Plat souhaité")
        if col2.button("🍳 Générer") and plat:
            with st.spinner("Création..."):
                st.session_state.recette_generee = generer_recette_ia(
                    "creation", plat)

    elif mode_cuisine == "🔄 Adapter une recette":
        txt = st.text_area("Collez votre recette ici :")
        if st.button("✨ Transformer") and txt:
            with st.spinner("Adaptation..."):
                st.session_state.recette_generee = generer_recette_ia(
                    "adaptation", txt)

    if st.session_state.recette_generee:
        st.markdown("---")
        st.subheader("🍽️ Résultat")
        st.markdown(st.session_state.recette_generee)
