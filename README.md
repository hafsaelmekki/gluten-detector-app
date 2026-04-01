# Glutify App

Glutify couples a Streamlit front-end with a FastAPI backend so people living with celiac disease can interrogate packaged foods, decode barcodes, and create/adapt gluten-free recipes. The UI presents every check in one screen (product data, verdict, justification, photo, nutrition facts, and safer alternatives) while the backend exposes the same capabilities for future mobile apps or integrations.

## Features
- **Scanner & Analysis (Streamlit)**  
  Search OpenFoodFacts by name/barcode, capture barcodes with `pyzbar`, display the product photo + composition, run the Groq LLM, and render an explicit verdict (`SANS GLUTEN`, `RISQUE`, `INTERDIT`) with a short justification. When the verdict is risky/forbidden the LLM adds `SEARCH_TERM: <nom generique>` so the UI and user know what to research next.
- **Grounded medical knowledge (RAG)**  
  `core/rag_engine.py` indexes `regles_gluten.txt` with FAISS + HuggingFace embeddings. During each analysis the retrieved medical paragraphs are injected into the Groq prompt so the verdict is grounded on your curated guidance.
- **Auditable history & alternatives**  
  Successful analyses are pushed to the backend only when a verdict is returned. The history tab shows the color-coded verdict, timestamp, explanation, and a dedicated thumbnail column. Risky or forbidden outcomes trigger an alternative search so the UI can list 3 gluten-free substitutes.
- **Chef & Recipes**  
  Dedicated modes to create new gluten-free recipes or adapt unsafe recipes; results can be saved in favorites.
- **Profiles & favorites**  
  Password-protected local profiles scope histories, recipes, and favorites.
- **FastAPI backend**  
  REST endpoints for `/products/search`, `/products/{code}`, `/analysis`, `/recipes`, `/history/*`, `/favorites`, `/users`, `/auth/login`, `/scan`, and `/health`. All endpoints are shared with the UI and external clients.

## Project Structure
```
.
|-- app.py                  # Streamlit entrypoint
|-- api.py                  # FastAPI application
|-- core/
|   |-- __init__.py
|   |-- app_ui.py           # Streamlit layout + callbacks
|   |-- database.py         # SQLAlchemy helpers
|   |-- food_scanner.py     # pyzbar wrapper
|   |-- gluten_analyzer.py  # Groq + RAG orchestrator
|   |-- models.py           # ORM models
|   |-- openfoodfacts_api.py# resilient client + rate limiter
|   |-- rag_engine.py       # FAISS + LangChain glue
|-- images/                 # Branding assets (logo used in UI)
|-- regles_gluten.txt       # Medical guidance indexed by the RAG
|-- requirements.txt
|-- docker/
|   |-- Dockerfile
|   |-- docker-compose.yml
|-- test_api.py
|-- .streamlit/
    |-- config.toml
    |-- secrets.toml (never committed; see Configuration)
```

## Requirements
- **Python**: 3.10 or newer (3.11/3.12 tested).
- **Pip dependencies**: everything is pinned in `requirements.txt` and grouped by stack (Streamlit UI, FastAPI backend, shared utilities, LLM/RAG, tooling). Install them all with:
  ```
  python -m pip install --upgrade pip
  pip install -r requirements.txt
  ```
- **System libraries**:
  - `pyzbar` needs ZBar. On Windows install the [ZBar binaries](https://github.com/NaturalHistoryMuseum/pyzbar#installation). On macOS: `brew install zbar`. On Debian/Ubuntu: `sudo apt-get install libzbar0`.
  - `faiss-cpu` requires AVX instructions and the Microsoft Visual C++ runtime on Windows.
  - PyTorch + torchvision are listed explicitly in the requirements. If pip cannot find a wheel for your platform, install the official CPU builds:  
    `pip install torch==2.2.1 torchvision==0.17.1 --index-url https://download.pytorch.org/whl/cpu`
- **Optional but recommended**: set `HF_TOKEN` for authenticated Hugging Face downloads so the embedding model is fetched faster.

## Configuration
1. **Groq API key**  
   - Streamlit: add it to `.streamlit/secrets.toml`  
     ```
     GROQ_API_KEY = "sk_xxx"
     ```  
   - FastAPI: export `GROQ_API_KEY` in your shell (`setx GROQ_API_KEY sk_xxx` on Windows PowerShell, `export GROQ_API_KEY=sk_xxx` on Unix shells).
2. **Backend URL**  
   The UI reads `BACKEND_URL` from `st.secrets` or the environment. Use `http://localhost:8000` during local development or the container hostname (`http://backend:8000`) when running Docker Compose.
3. **Database**  
   The backend defaults to SQLite (`glutify.db`). To use PostgreSQL, export `DATABASE_URL` (`postgresql+psycopg2://user:pass@host/db`). Streamlit reads the same value from `st.secrets` so both apps stay in sync.
4. **Hugging Face token (optional)**  
   Set `HF_TOKEN` to avoid throttling when downloading `sentence-transformers/all-MiniLM-L6-v2`. On Windows: `setx HF_TOKEN hf_xxx`. On Unix: `export HF_TOKEN=hf_xxx`.
5. **Medical rules**  
   Edit `regles_gluten.txt` to mirror your own medical constraints. The file is loaded at startup, chunked, and indexed by FAISS; updating it only requires restarting the process.
6. **Branding**  
   Place your logo under `images/logo/logo_titre.png` so Streamlit can render it in the sidebar and as the favicon.

## LLM & RAG Workflow
1. `OpenFoodFactsAPI` fetches the product and enforces 60 req/min with exponential backoff. Failures bubble up as explicit warnings instead of silent fallbacks.
2. `GlutenAnalyzerLLM` retrieves the top rules from the FAISS index, injects them into the Groq prompt, and requests a deterministic response (`temperature=0`).
3. The assistant must output `VERDICT` + `JUSTIFICATION`. When the verdict is `RISQUE` or `INTERDIT`, it appends `SEARCH_TERM: <nom generique>`. The UI shows that sentence and also reuses the search term to propose gluten-free alternatives.
4. Only successful analyses (`Sans gluten`, `Risque`, `Interdit`) are persisted. The backend stores the verdict, justification, timestamp, user id, and the product thumbnail URL. Failed/offline searches never pollute the audit trail.
5. The history tab renders a table with a dedicated image column and color-coded verdict badges: green (`Sans gluten`), amber (`Risque`), red (`Interdit`).

## Running Locally
1. **Start the FastAPI backend**
   ```
   python -m uvicorn api:app --reload --port 8000
   ```
   Watch the logs: the RAG engine prints "Chargement du moteur RAG medical..." and Groq/Sentence-Transformers warnings if tokens or models are missing.
2. **Verify the health endpoint**
   - CLI: `Invoke-RestMethod http://127.0.0.1:8000/health` (PowerShell) or `curl http://127.0.0.1:8000/health`.
   - Network check: `Test-NetConnection 127.0.0.1 -Port 8000` if the request hangs.
3. **Launch Streamlit**
   ```
   streamlit run app.py
   ```
   Ensure `BACKEND_URL` points to `http://127.0.0.1:8000`; otherwise the UI stays in read-only/offline mode.
4. **Tests**
   ```
   pytest
   ```
5. **System dependencies**
   ZBar must be installed so barcode scans work. Restart Streamlit after installing it so `pyzbar` can load the DLL/SO.

## Docker
1. Export `GROQ_API_KEY`, `DATABASE_URL`, and optionally `HF_TOKEN`/`BACKEND_URL` in your shell.
2. Build and start both services (run commands from the `docker/` directory so the compose file is discovered):
   ```
   cd docker
   docker compose up --build
   ```
3. Streamlit lives at `http://localhost:8501`, FastAPI (and `/docs`) at `http://localhost:8000`.  
   Stop everything with `docker compose down` from the same `docker/` folder.

## Troubleshooting
- **OpenFoodFacts returns 503 / stays offline**  
  The client retries three times with exponential backoff and logs `[WARN]` entries. Wait a few seconds between attempts or switch to a different search term. Because rate limiting is enforced inside `OpenFoodFactsAPI`, hammering the command line with repeated calls will pause automatically instead of triggering bans.
- **`/health` hangs**  
  The backend is not running or another process owns port 8000. Stop the orphaned server (`Ctrl+C`) and restart `uvicorn`. Use `Test-NetConnection 127.0.0.1 -Port 8000` to confirm the port is reachable before starting Streamlit.
- **Embedding downloads stall**  
  Set `HF_TOKEN`, clear `%USERPROFILE%\.cache\huggingface` (or `~/.cache/huggingface`), then restart the backend. Authenticated pulls are much faster and survive rate limits.
- **PyTorch installation fails**  
  Use the CPU wheel command shown in the Requirements section. If you already installed PyTorch separately, remove it before reinstalling to avoid ABI mismatches with `faiss-cpu`.
- **History entry missing**  
  Only analyses with a verdict are persisted. Searches that fail, stay offline, or where the LLM response does not include `Sans gluten/Risque/Interdit` are ignored by design.

## Development Notes
- Shared logic lives under `core/`.
- Keep code formatted (PEP 8) and type hinted.
- Before committing, run:
  ```
  pycodestyle app.py core api.py
  python -m py_compile app.py api.py core/*.py
  pytest
  ```
- Launch `streamlit run app.py` and `uvicorn api:app --reload` in separate terminals to manually validate UI + API changes.

## Deployment
- **Streamlit**: Streamlit Community Cloud or any container-friendly host. Provide `GROQ_API_KEY`, optionally `HF_TOKEN`, and ensure the OS bundles ZBar.
- **FastAPI**: Deploy behind Uvicorn/Gunicorn or another ASGI server. Supply `GROQ_API_KEY`, `DATABASE_URL`, and make `regles_gluten.txt` available. Expose `/health` for liveness and ensure system packages required by `pyzbar`, `faiss-cpu`, and PyTorch are installed.
