# Glutify App

Glutify pairs a Streamlit front-end with a FastAPI backend to help people living with celiac disease inspect packaged foods, decode barcodes, and generate gluten-free recipes. The Streamlit UI targets desktop/tablet usage while the API exposes every capability for external integrations or future mobile clients.

## Features
- **Scanner & Analysis (Streamlit)**
  - Search OpenFoodFacts by name or barcode.
  - Decode images or webcam streams through `pyzbar`.
  - Display Nutri-Score data, run the Groq LLM analysis, highlight gluten risks, and suggest safer alternatives.
  - Persist the analysis history through the backend/SQL database.
- **Chef & Recipes (Streamlit)**
  - Generate new gluten-free recipes from a prompt.
  - Adapt an unsafe recipe into a safe alternative via the LLM assistant.
- **Persistent favorites**
  - Save favorite recipes via the FastAPI/PostgreSQL backend and manage them from the UI.
- **User profiles**
  - Create/select profiles with passwords to personalize the experience (history + favorites per profile).
- **FastAPI backend**
  - `/products/search`, `/products/{code}`, `/scan`, `/analysis`, `/recipes`, `/history/*`, `/favorites`, `/users`, `/auth/login`, and `/health` endpoints.

## Project Structure
```
.
├── app.py                  # Streamlit entrypoint wiring all components
├── api.py                  # FastAPI application exposing REST endpoints
├── core/
│   ├── __init__.py         # Exports the reusable classes
│   ├── app_ui.py           # Streamlit layout and callbacks
│   ├── database.py         # SQLAlchemy engine/session helpers
│   ├── food_scanner.py     # Image barcode decoding helpers
│   ├── gluten_analyzer.py  # Groq LLM wrapper for analysis/recipes
│   ├── models.py           # ORM models (analysis & recipe logs)
│   └── openfoodfacts_api.py# Requests-based OpenFoodFacts client
├── images/                 # Branding assets (logo used in the sidebar/icon)
├── test_api.py             # Pytest smoke test for the FastAPI app
├── requirements.txt
└── README.md
```

## Requirements
- Python 3.10+
- Core libraries (`requirements.txt` already pins versions):
  - Streamlit stack: `streamlit`, `streamlit-option-menu`, `Pillow`, `pyzbar`.
  - Backend stack: `fastapi`, `uvicorn[standard]`, `pydantic`, `SQLAlchemy`, `psycopg2-binary`.
  - Utilities: `requests`, `groq`, `httpx` (for tests), `pytest`.

Install every dependency with:
```
pip install -r requirements.txt
```
`pyzbar` requires the ZBar system library. On Windows, install the [ZBar binaries](https://github.com/NaturalHistoryMuseum/pyzbar#installation); on macOS/Linux use `brew install zbar` or `apt-get install libzbar0`.

## Configuration
1. Provide your Groq API key.
   - Streamlit: `.streamlit/secrets.toml`
     ```
     GROQ_API_KEY = "sk_your_key_here"
     ```
   - FastAPI: environment variable `GROQ_API_KEY` (for example `setx GROQ_API_KEY sk_your_key_here` on Windows or `export GROQ_API_KEY=sk_your_key_here` on Unix shells).
2. Configure the PostgreSQL connection string.
   - FastAPI (`api.py`) reads `DATABASE_URL` (e.g., `postgresql+psycopg2://user:password@host/db`).
   - Streamlit can also read it from `st.secrets` when you surface DB-backed features.
3. Ensure the branding asset `images/logo/logo_titre.png` exists; it is used in the sidebar and as page icon.
4. Set `BACKEND_URL` so Streamlit can talk to FastAPI (`http://localhost:8000` locally or `http://backend:8000` in Docker).

## Running Locally
### Streamlit front-end
```
streamlit run app.py
```
The sidebar exposes:
- **Scanner & Analysis** - search or scan a product, run the LLM analysis, review gluten warnings, and view suggested alternatives.
- **Chef & Recipes** - generate or adapt recipes with the LLM assistant.
Ensure `BACKEND_URL` points to the FastAPI host if you want history/favorites to be persisted.

### FastAPI backend
```
# Make sure GROQ_API_KEY and DATABASE_URL are exported
uvicorn api:app --reload --port 8000
```
The interactive docs are available at `http://localhost:8000/docs`.

### Tests
Run the smoke suite locally before pushing:
```
pytest
```

## Docker
1. Export `GROQ_API_KEY` and `DATABASE_URL` in your shell (`export` on Unix, `set`/`setx` on Windows PowerShell).
2. Build and start the stack:
```
docker compose up --build
```
3. Access the services:
   - Streamlit front-end: http://localhost:8501
   - FastAPI backend + docs: http://localhost:8000 (OpenAPI at `/docs`)

Stop everything with `docker compose down`. The compose file builds one image and runs two containers (frontend + backend) that share the same source tree.

## Development Notes
- Shared logic lives in `core/`.
- Follow PEP 8 formatting and keep type hints in place.
- Before committing, run:
```
pycodestyle app.py core api.py
python -m py_compile app.py api.py core/*.py
pytest
```
- Launch `streamlit run app.py` or `uvicorn api:app --reload` to manually verify UI/API changes.

## Deployment
- **Streamlit**: Deploy on Streamlit Community Cloud or any container-friendly platform. Configure the Groq key in secrets, and ensure the OS ships ZBar.
- **FastAPI**: Deploy with Uvicorn/Gunicorn or another ASGI server. Provide `GROQ_API_KEY`, `DATABASE_URL`, expose the API port, and install any system packages required by `pyzbar`.
