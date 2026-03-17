# Glutify App

Glutify combines a Streamlit front-end with a FastAPI backend to help people living with celiac disease evaluate packaged foods, decode barcodes, and generate gluten-free recipes. The UI is optimized for desktop/tablet workflows while the API exposes the core logic for integrations or future mobile clients.

## Features
- **Scanner & Analyse (Streamlit)**
  - Text search through the OpenFoodFacts catalogue.
  - Barcode decoding through webcam or uploaded photos (via `pyzbar`).
  - Nutri-Score display plus automatic Groq LLM analysis that flags gluten risks and proposes safer alternatives.
- **Chef & Recettes (Streamlit)**
  - Create new gluten-free recipes from a short prompt.
  - Adapt existing recipes into safe alternatives using the LLM.
- **FastAPI Backend**
  - `/products/search` and `/products/{code}` endpoints powered by OpenFoodFacts.
  - `/scan` endpoint to decode uploaded barcode images.
  - `/analysis` and `/recipes` endpoints backed by the Groq LLM analyzer.

## Project Structure
```
.
├── app.py                  # Streamlit entrypoint wiring all components
├── api.py                  # FastAPI application exposing REST endpoints
├── core/
│   ├── __init__.py         # Exports the reusable classes
│   ├── app_ui.py           # Streamlit layout and callbacks
│   ├── food_scanner.py     # Image barcode decoding helpers
│   ├── gluten_analyzer.py  # Groq LLM wrapper for analysis/recipes
│   └── openfoodfacts_api.py# Requests-based OpenFoodFacts client
├── images/                 # Branding assets (logo used in the sidebar/icon)
└── README.md
```

## Requirements
- Python 3.10+
- Core libraries:
  - Streamlit stack: `streamlit`, `streamlit-option-menu`
  - Backend stack: `fastapi`, `uvicorn[standard]`, `pydantic`
  - Utilities: `requests`, `Pillow`, `pyzbar`, `groq`

Install dependencies with `pip install -r requirements.txt` (create one if needed) or manually:
```
pip install streamlit fastapi "uvicorn[standard]" pydantic requests groq Pillow pyzbar streamlit-option-menu
```
`pyzbar` may require system packages (zbar). On Windows, install the [ZBar binaries](https://github.com/NaturalHistoryMuseum/pyzbar#installation); on macOS/Linux use your package manager (`brew install zbar`, `apt-get install libzbar0`, etc.).

## Configuration
1. Provide your Groq API key.
   - Streamlit: `.streamlit/secrets.toml`
     ```
     GROQ_API_KEY = "sk_your_key_here"
     ```
   - FastAPI: environment variable `GROQ_API_KEY` (e.g., `export GROQ_API_KEY=sk_your_key_here`).
2. Ensure the branding asset `images/logo/logo_titre.png` exists; it is used both as sidebar logo and page icon.

## Running Locally
### Streamlit Front-End
```
streamlit run app.py
```
The sidebar exposes:
- **Scanner & Analyse** – search/scan a product, run the LLM analysis, and view suggested gluten-free alternatives.
- **Chef & Recettes** – generate or adapt recipes with the LLM assistant.

### FastAPI Backend
```
# Make sure GROQ_API_KEY is exported
uvicorn api:app --reload --port 8000
```
Key endpoints:
- `GET /health` – health check.
- `GET /products/search?query=...` – search OpenFoodFacts.
- `GET /products/{code}` – fetch a product by barcode.
- `POST /scan` – upload an image to decode its barcode.
- `POST /analysis` – send a product payload for LLM analysis.
- `POST /recipes` – request a recipe (`mode`: `creation` or `adaptation`).

## Docker
1. Ensure `GROQ_API_KEY` is available in your shell (e.g., `export GROQ_API_KEY=...`).
2. Build and start both services:
```
docker compose up --build
```
3. Access the apps:
   - Streamlit frontend: http://localhost:8501
   - FastAPI backend (docs at `/docs`): http://localhost:8000

Stop the stack with `docker compose down`. The compose file builds a single image and runs two containers (frontend + backend) sharing the same code base.

## Development Notes
- Core functionality lives in `core/` and is shared between Streamlit and FastAPI.
- All modules follow PEP 8 formatting and include type hints.
- Before committing changes, run:
```
pycodestyle app.py core api.py
python -m py_compile app.py api.py core/*.py
```
- Launch `streamlit run app.py` or `uvicorn api:app --reload` to manually verify UI/API changes.

## Deployment
- **Streamlit**: Deploy on Streamlit Community Cloud or any container-friendly platform. Configure `GROQ_API_KEY` in secrets and ensure zbar is available.
- **FastAPI**: Deploy with Uvicorn/Gunicorn or another ASGI server. Set `GROQ_API_KEY`, expose the desired port, and provide system packages required by `pyzbar`.
