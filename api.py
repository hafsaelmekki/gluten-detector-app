from __future__ import annotations

import os
from io import BytesIO
from typing import Any, Dict, List, Literal, Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel

from core import FoodScanner, GlutenAnalyzerLLM, OpenFoodFactsAPI

API_KEY = os.getenv("GROQ_API_KEY")

app = FastAPI(title="Glutify API", version="1.0.0")

food_api = OpenFoodFactsAPI()
scanner = FoodScanner()
analyzer = GlutenAnalyzerLLM(API_KEY)


class ProductPayload(BaseModel):
    product: Dict[str, Any]


class RecipeRequest(BaseModel):
    mode: Literal["creation", "adaptation"]
    input_text: str


class RecipeResponse(BaseModel):
    recipe: str


class AnalysisResponse(BaseModel):
    result: str


class ProductResponse(BaseModel):
    product: Dict[str, Any]


class ProductsResponse(BaseModel):
    products: List[Dict[str, Any]]


class ScanResponse(BaseModel):
    code: Optional[str]


@app.get("/health")
def health_check() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/products/search", response_model=ProductsResponse)
def search_products(query: str) -> ProductsResponse:
    if not query:
        raise HTTPException(
            status_code=400, detail="Query parameter is required"
        )
    products = food_api.search_products(query)
    return ProductsResponse(products=products)


@app.get("/products/{code}", response_model=ProductResponse)
def get_product(code: str) -> ProductResponse:
    product = food_api.search_product_by_code(code)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return ProductResponse(product=product)


@app.post("/analysis", response_model=AnalysisResponse)
def analyze_product(payload: ProductPayload) -> AnalysisResponse:
    if not analyzer.client:
        raise HTTPException(status_code=500, detail="LLM is not configured")
    result = analyzer.analyze_product(payload.product)
    return AnalysisResponse(result=result)


@app.post("/recipes", response_model=RecipeResponse)
def generate_recipe(request: RecipeRequest) -> RecipeResponse:
    if not analyzer.client:
        raise HTTPException(status_code=500, detail="LLM is not configured")
    recipe = analyzer.generate_recipe(request.mode, request.input_text)
    return RecipeResponse(recipe=recipe)


@app.post("/scan", response_model=ScanResponse)
async def scan_barcode(file: UploadFile = File(...)) -> ScanResponse:
    data = await file.read()
    code = scanner.decode(BytesIO(data))
    if not code:
        raise HTTPException(status_code=400, detail="Unable to decode barcode")
    return ScanResponse(code=code)
