from groq import Groq


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
        IMPORTANT :
        Si ROUGE ou ORANGE, ajoute à la fin :
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

    def generate_recipe(self, mode, input_text):
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
