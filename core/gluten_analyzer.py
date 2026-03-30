from __future__ import annotations

from typing import Any, Dict, Optional

from groq import Groq

try:
    from .rag_engine import GlutenRAG
except Exception as exc:
    GlutenRAG = None  # type: ignore
    _rag_import_error = exc
else:
    _rag_import_error = None

Product = Dict[str, Any]


class GlutenAnalyzerLLM:
    """Analyse les produits et recettes via Groq + moteur RAG."""

    def __init__(
        self, api_key: Optional[str], model: str = "llama-3.3-70b-versatile"
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.client = Groq(api_key=api_key) if api_key else None

        self.rag: Any = None
        if GlutenRAG is None:
            if _rag_import_error:
                print(f"Avertissement RAG indisponible : {_rag_import_error}")
        else:
            try:
                print("Chargement du moteur RAG medical...")
                self.rag = GlutenRAG()
            except Exception as exc:
                print(f"Avertissement RAG inactif : {exc}")

    def analyze_product(self, product: Product) -> str:
        if not self.client:
            return "⚠️ Erreur clé API"

        ingredients = product.get("ingredients_text", "Non listés")
        traces = product.get("traces", "Non indiqué")
        score = product.get("nutriscore_grade", "Inconnu").upper()

        contexte_medical = "Aucune règle spécifique trouvée."
        if self.rag and ingredients != "Non listés":
            try:
                contexte_medical = self.rag.search_rules(ingredients)
            except Exception as exc:
                print(f"Avertissement RAG ignoré : {exc}")

        prompt = f"""
        Tu es un expert médical intransigeant de la maladie coeliaque.

        RÈGLES MÉDICALES OFFICIELLES (À RESPECTER STRICTEMENT) :
        {contexte_medical}

        PRODUIT À ANALYSER :
        Nom : {product.get('product_name')}
        Ingrédients : {ingredients}
        Traces : {traces}
        Nutri-Score : {score}

        Analyse la compatibilité de ce produit pour un coeliaque EN TE BASANT UNIQUEMENT SUR LES RÈGLES CI-DESSUS (ne devine rien).

        FORMAT DE RÉPONSE OBLIGATOIRE :
        VERDICT : écris exactement l'une des valeurs ci-dessous, sans texte supplémentaire.
            - SANS GLUTEN
            - RISQUE (Traces/Contamination)
            - INTERDIT
        JUSTIFICATION : 1 à 2 phrases qui citent les ingrédients détectés et la règle médicale utilisée.

        IMPORTANT :
        Si ROUGE ou ORANGE, ajoute à la fin de ta réponse :
        "SEARCH_TERM: [Nom générique]"
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

    def generate_recipe(self, mode: str, input_text: str) -> str:
        if not self.client:
            return "⚠️ Erreur clé API"
        system_prompt = (
            "Chef sans gluten."
            if mode == "creation"
            else "Expert substitution."
        )
        user_prompt = (
            f"Recette sans gluten pour : {input_text}."
            if mode == "creation"
            else f"Adapte en sans gluten :\n\n{input_text}"
        )
        try:
            response = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                model=self.model,
            )
            return response.choices[0].message.content
        except Exception:
            return "Erreur"
