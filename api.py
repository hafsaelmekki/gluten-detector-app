from __future__ import annotations

import os
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, List, Literal, Optional

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from core import FoodScanner, GlutenAnalyzerLLM, OpenFoodFactsAPI
from core.openfoodfacts_api import OpenFoodFactsAPIError
from core.database import (
    Base,
    engine,
    ensure_history_columns,
    ensure_user_profile_schema,
    get_session,
)
from core.models import AnalysisLog, FavoriteRecipe, RecipeLog, UserProfile

API_KEY = os.getenv("GROQ_API_KEY")

app = FastAPI(title="Glutify API", version="1.1.0")

food_api = OpenFoodFactsAPI()
scanner = FoodScanner()
analyzer = GlutenAnalyzerLLM(API_KEY)


def _analysis_has_verdict(result: str) -> bool:
    if not result:
        return False
    first_line = result.splitlines()[0].strip().lower()
    keywords = ("sans", "risque", "interdit")
    return any(word in first_line for word in keywords)


class ProductPayload(BaseModel):
    product: Dict[str, Any]
    user_id: Optional[int] = None


class RecipeRequest(BaseModel):
    mode: Literal["creation", "adaptation"]
    input_text: str
    user_id: Optional[int] = None


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


class AnalysisLogSchema(BaseModel):
    id: int
    product_name: str
    result: str
    image_url: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RecipeLogSchema(BaseModel):
    id: int
    mode: str
    input_text: str
    recipe: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FavoriteRecipeSchema(BaseModel):
    id: int
    mode: str
    input_text: str
    recipe: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FavoriteRecipeRequest(BaseModel):
    mode: Literal["creation", "adaptation"]
    input_text: str
    recipe: str
    user_id: Optional[int] = None


class UserProfileSchema(BaseModel):
    id: int
    name: str
    email: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserProfileRequest(BaseModel):
    name: str
    email: Optional[str] = None
    password: str


class LoginRequest(BaseModel):
    identifier: str
    password: str


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_user_profile_schema()
    ensure_history_columns()


@app.get("/health")
def health_check() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/products/search", response_model=ProductsResponse)
def search_products(query: str) -> ProductsResponse:
    if not query:
        raise HTTPException(
            status_code=400, detail="Query parameter is required"
        )
    try:
        products = food_api.search_products(query)
    except OpenFoodFactsAPIError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return ProductsResponse(products=products)


@app.get("/products/{code}", response_model=ProductResponse)
def get_product(code: str) -> ProductResponse:
    product = food_api.search_product_by_code(code)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return ProductResponse(product=product)


@app.post("/analysis", response_model=AnalysisResponse)
def analyze_product(
    payload: ProductPayload, db: Session = Depends(get_session)
) -> AnalysisResponse:
    if not analyzer.client:
        raise HTTPException(status_code=500, detail="LLM is not configured")
    result = analyzer.analyze_product(payload.product)
    if not _analysis_has_verdict(result):
        return AnalysisResponse(result=result)
    product_name = payload.product.get("product_name") or "Produit"
    image_url = payload.product.get("image_front_small_url") or payload.product.get("image_url")
    log = AnalysisLog(
        product_name=str(product_name)[:255],
        result=result,
        image_url=image_url,
        user_id=payload.user_id,
    )
    db.add(log)
    db.commit()
    return AnalysisResponse(result=result)


@app.post("/recipes", response_model=RecipeResponse)
def generate_recipe(
    request: RecipeRequest, db: Session = Depends(get_session)
) -> RecipeResponse:
    if not analyzer.client:
        raise HTTPException(status_code=500, detail="LLM is not configured")
    recipe = analyzer.generate_recipe(request.mode, request.input_text)
    log = RecipeLog(
        mode=request.mode,
        input_text=request.input_text,
        recipe=recipe,
        user_id=request.user_id,
    )
    db.add(log)
    db.commit()
    return RecipeResponse(recipe=recipe)


@app.get("/history/analyses", response_model=List[AnalysisLogSchema])
def list_analysis_history(
    limit: int = 20,
    user_id: Optional[int] = None,
    db: Session = Depends(get_session),
) -> List[AnalysisLogSchema]:
    query = db.query(AnalysisLog).order_by(AnalysisLog.created_at.desc())
    if user_id is not None:
        query = query.filter(AnalysisLog.user_id == user_id)
    return query.limit(limit).all()


@app.get("/history/recipes", response_model=List[RecipeLogSchema])
def list_recipe_history(
    limit: int = 20,
    user_id: Optional[int] = None,
    db: Session = Depends(get_session),
) -> List[RecipeLogSchema]:
    query = db.query(RecipeLog).order_by(RecipeLog.created_at.desc())
    if user_id is not None:
        query = query.filter(RecipeLog.user_id == user_id)
    return query.limit(limit).all()


@app.get("/favorites", response_model=List[FavoriteRecipeSchema])
def list_favorites(
    limit: int = 20,
    user_id: Optional[int] = None,
    db: Session = Depends(get_session),
) -> List[FavoriteRecipeSchema]:
    query = db.query(FavoriteRecipe).order_by(FavoriteRecipe.created_at.desc())
    if user_id is not None:
        query = query.filter(FavoriteRecipe.user_id == user_id)
    return query.limit(limit).all()


@app.post("/favorites", response_model=FavoriteRecipeSchema)
def add_favorite(
    request: FavoriteRecipeRequest, db: Session = Depends(get_session)
) -> FavoriteRecipeSchema:
    fav = FavoriteRecipe(
        mode=request.mode,
        input_text=request.input_text,
        recipe=request.recipe,
        user_id=request.user_id,
    )
    db.add(fav)
    db.commit()
    db.refresh(fav)
    return fav


@app.delete("/favorites/{favorite_id}")
def delete_favorite(
    favorite_id: int, db: Session = Depends(get_session)
) -> Dict[str, str]:
    fav = db.get(FavoriteRecipe, favorite_id)
    if not fav:
        raise HTTPException(status_code=404, detail="Favorite not found")
    db.delete(fav)
    db.commit()
    return {"status": "deleted"}


@app.delete("/favorites")
def clear_favorites(
    user_id: Optional[int] = None, db: Session = Depends(get_session)
) -> Dict[str, str]:
    query = db.query(FavoriteRecipe)
    if user_id is not None:
        query = query.filter(FavoriteRecipe.user_id == user_id)
    query.delete()
    db.commit()
    return {"status": "cleared"}


@app.get("/users", response_model=List[UserProfileSchema])
def list_users(db: Session = Depends(get_session)) -> List[UserProfileSchema]:
    return db.query(UserProfile).order_by(UserProfile.created_at.desc()).all()


@app.post("/users", response_model=UserProfileSchema)
def create_user(
    request: UserProfileRequest, db: Session = Depends(get_session)
) -> UserProfileSchema:
    name = request.name.strip()
    password = request.password.strip()
    if not name or not password:
        raise HTTPException(
            status_code=400, detail="Nom et mot de passe requis"
        )
    user = UserProfile(
        name=name,
        email=(request.email or None),
        password=password,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.delete("/users/{user_id}")
def delete_user(
    user_id: int, db: Session = Depends(get_session)
) -> Dict[str, str]:
    user = db.get(UserProfile, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Profil introuvable")
    db.delete(user)
    db.commit()
    return {"status": "deleted"}


@app.post("/auth/login", response_model=UserProfileSchema)
def login_user(
    request: LoginRequest, db: Session = Depends(get_session)
) -> UserProfileSchema:
    identifier = request.identifier.strip()
    password = request.password.strip()
    if not identifier or not password:
        raise HTTPException(status_code=400, detail="Identifiants requis")
    query = db.query(UserProfile)
    user = query.filter(UserProfile.email == identifier).first()
    if not user:
        user = query.filter(UserProfile.name == identifier).first()
    if not user or user.password != password:
        raise HTTPException(status_code=401, detail="Connexion refusée")
    return user


@app.post("/scan", response_model=ScanResponse)
async def scan_barcode(file: UploadFile = File(...)) -> ScanResponse:
    data = await file.read()
    code = scanner.decode(BytesIO(data))
    if not code:
        raise HTTPException(status_code=400, detail="Unable to decode barcode")
    return ScanResponse(code=code)
