# Glutify App

Glutify is a Streamlit application that helps people living with celiac disease quickly evaluate food products, scan barcodes, and generate gluten-free recipe ideas. The UI is optimized for tablets/desktops and integrates computer vision, OpenFoodFacts data, and an LLM-powered analyzer.

## Features
- **Scanner & Analyse**
  - Text search through the OpenFoodFacts catalogue.
  - Barcode decoding through webcam or uploaded photos (via `pyzbar`).
  - Nutri-Score display plus automatic Groq LLM analysis that flags gluten risks and proposes safer alternatives.
- **Chef & Recettes**
  - Create new gluten-free recipes from a short prompt.
  - Adapt existing recipes into safe alternatives using the LLM.
- Responsive Streamlit UI with sidebar navigation, custom branding, and persistent session state.

## Project Structure
```
.
├── app.py                # Streamlit entrypoint wiring all components
├── core/
│   ├── __init__.py       # Exports the reusable classes
│   ├── app_ui.py         # All Streamlit layout and callbacks
│   ├── food_scanner.py   # Image barcode decoding helpers
│   ├── gluten_analyzer.py# Groq LLM wrapper for analysis/recipes
│   └── openfoodfacts_api.py # Requests-based OpenFoodFacts client
└── images/               # Branding assets (logo used in the sidebar/icon)
```

## Requirements
- Python 3.10+
- Streamlit and supporting libraries:
  - `streamlit`, `streamlit-option-menu`
  - `requests`, `Pillow`, `pyzbar`
  - `groq` SDK for LLM access

Install dependencies with `pip install -r requirements.txt` (create one if needed) or manually:
```
pip install streamlit requests groq Pillow pyzbar streamlit-option-menu
```
`pyzbar` may require system packages (zbar). On Windows, install the [ZBar binaries](https://github.com/NaturalHistoryMuseum/pyzbar#installation); on macOS/Linux use your package manager (`brew install zbar`, `apt-get install libzbar0`, etc.).

## Configuration
1. Create a `.streamlit/secrets.toml` file (or use Streamlit Cloud secrets) with your Groq API key:
```
GROQ_API_KEY="sk_your_key_here"
```
2. Ensure the `images/logo/logo_titre.png` file exists; it is used for both the sidebar logo and page icon.

## Running Locally
```
streamlit run app.py
```
The app exposes two sections via the sidebar:
- **Scanner & Analyse** – search/scan a product, run the LLM analysis, and view suggested gluten-free alternatives.
- **Chef & Recettes** – generate or adapt recipes with the LLM assistant.

## Development Notes
- Core functionality is organized into dedicated classes (scanner, API client, analyzer, UI) living under `core/`.
- All modules follow PEP 8 formatting and include type hints.
- Before committing changes, run:
```
pycodestyle app.py core
python -m py_compile app.py core/*.py
```
- Launch `streamlit run app.py` to manually verify UI changes.

## Deployment
Deploy on any platform that supports Streamlit (Streamlit Community Cloud, Azure, etc.). Set the `GROQ_API_KEY` secret in the deployment environment and ensure required system libs (`zbar`) are available.
