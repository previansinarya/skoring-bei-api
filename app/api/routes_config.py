"""routes_config.py — endpoint konfigurasi (placeholder)"""
from fastapi import APIRouter
router = APIRouter(prefix="/config", tags=["Konfigurasi"])

@router.get("/default-bobot")
async def get_default_bobot():
    from app.services.skoring import (
        DEFAULT_BOBOT_RETURN, DEFAULT_BOBOT_VOLATILITAS,
        DEFAULT_BOBOT_DIMENSI, DEFAULT_BOBOT_REZIM,
    )
    from app.services.data_fetcher import DEFAULT_REZIM, DEFAULT_BI_RATE, DEFAULT_HARI_BURSA
    return {
        "bobot_return":      DEFAULT_BOBOT_RETURN,
        "bobot_volatilitas": DEFAULT_BOBOT_VOLATILITAS,
        "bobot_dimensi":     DEFAULT_BOBOT_DIMENSI,
        "bobot_rezim":       DEFAULT_BOBOT_REZIM,
        "rezim":             DEFAULT_REZIM,
        "bi_rate":           DEFAULT_BI_RATE,
        "hari_bursa":        DEFAULT_HARI_BURSA,
    }
