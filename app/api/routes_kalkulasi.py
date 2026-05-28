"""
routes_kalkulasi.py
Endpoint: POST /api/v1/kalkulasi/jalankan
Menerima konfigurasi sesi, menjalankan Modul 3+4, return hasil JSON
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
import pandas as pd
import numpy as np
import traceback

from app.services.data_fetcher import (
    DEFAULT_REZIM, DEFAULT_BI_RATE, DEFAULT_HARI_BURSA, segmentasi_rezim
)
from app.services.metrik import hitung_semua_metrik
from app.services.skoring import (
    hitung_skoring,
    DEFAULT_BOBOT_RETURN, DEFAULT_BOBOT_VOLATILITAS,
    DEFAULT_BOBOT_DIMENSI, DEFAULT_BOBOT_REZIM,
)

router = APIRouter(prefix="/kalkulasi", tags=["Kalkulasi"])


# ── Model request ──────────────────────────────────────────
class KonfigurasiBobot(BaseModel):
    bobot_return:      Dict[str, float] = Field(default=DEFAULT_BOBOT_RETURN)
    bobot_volatilitas: Dict[str, float] = Field(default=DEFAULT_BOBOT_VOLATILITAS)
    bobot_dimensi:     Dict[str, float] = Field(default=DEFAULT_BOBOT_DIMENSI)
    bobot_rezim:       Dict[str, float] = Field(default=DEFAULT_BOBOT_REZIM)


class KonfigurasiRezim(BaseModel):
    Krisis:    Dict[str, str] = Field(default=DEFAULT_REZIM["Krisis"])
    Pemulihan: Dict[str, str] = Field(default=DEFAULT_REZIM["Pemulihan"])
    Normal:    Dict[str, str] = Field(default=DEFAULT_REZIM["Normal"])


class RequestKalkulasi(BaseModel):
    # Data yang sudah di-fetch/upload (dikirim dari frontend via session_id)
    # Untuk prototype: terima raw data langsung
    session_id:  str
    rezim:       KonfigurasiRezim = Field(default_factory=KonfigurasiRezim)
    bi_rate:     Dict[str, float] = Field(default=DEFAULT_BI_RATE)
    hari_bursa:  int = Field(default=DEFAULT_HARI_BURSA)
    bobot:       KonfigurasiBobot = Field(default_factory=KonfigurasiBobot)


# ── Session store sederhana (in-memory) ───────────────────
# Dalam produksi, ini diganti Redis atau database
_sessions: Dict[str, Dict] = {}

def get_session(session_id: str) -> Dict:
    if session_id not in _sessions:
        raise HTTPException(404, f"Session '{session_id}' tidak ditemukan. Jalankan input data terlebih dahulu.")
    return _sessions[session_id]

def save_session(session_id: str, data: Dict):
    _sessions[session_id] = data


# ── Helper: convert DataFrame ke JSON-serializable ────────
def df_to_records(df: pd.DataFrame) -> List[Dict]:
    """Convert DataFrame ke list of dicts, handle NaN."""
    return df.replace({np.nan: None}).reset_index().to_dict(orient="records")


# ── Endpoints ─────────────────────────────────────────────
@router.post("/jalankan")
async def jalankan_kalkulasi(req: RequestKalkulasi):
    """
    Jalankan Modul 3 (kalkulasi metrik) + Modul 4 (skoring).
    Membutuhkan data yang sudah tersimpan di session via /input/fetch atau /input/upload.
    """
    try:
        sess = get_session(req.session_id)
        df_bersih   = sess["df_bersih"]
        return_ihsg = sess.get("return_ihsg")
        df_sektor   = sess["df_sektor"]

        rezim_config = {
            "Krisis":    req.rezim.Krisis,
            "Pemulihan": req.rezim.Pemulihan,
            "Normal":    req.rezim.Normal,
        }

        # Segmentasi rezim
        seg = segmentasi_rezim(df_bersih, return_ihsg, rezim_config)
        rezim_data = seg["rezim_data"]
        rezim_ihsg = seg["rezim_ihsg"]

        # Modul 3: kalkulasi metrik
        hasil_semua = hitung_semua_metrik(
            rezim_data=rezim_data,
            rezim_ihsg=rezim_ihsg,
            bi_rate=req.bi_rate,
            hari_bursa=req.hari_bursa,
        )

        # Modul 4: skoring
        df_skor = hitung_skoring(
            hasil_semua=hasil_semua,
            df_sektor=df_sektor,
            bobot_return=req.bobot.bobot_return,
            bobot_volatilitas=req.bobot.bobot_volatilitas,
            bobot_dimensi=req.bobot.bobot_dimensi,
            bobot_rezim=req.bobot.bobot_rezim,
        )

        # Simpan hasil ke session untuk export
        sess["hasil_semua"] = hasil_semua
        sess["df_skor"]     = df_skor
        sess["rezim_data"]  = rezim_data
        save_session(req.session_id, sess)

        # Susun respons
        ranking   = df_skor.sort_values("Ranking_Global")
        distribusi_kelas = df_skor["Kelas"].value_counts().to_dict()
        distribusi_sektor = df_skor.groupby("Sektor")["Skor_Final"].mean().round(2).to_dict()

        ringkasan_rezim = {}
        for nama, df_m in hasil_semua.items():
            ringkasan_rezim[nama] = {
                "n_hari_median":         float(df_m["n_hari"].median()),
                "cumulative_return_mean": float(df_m["cumulative_return"].mean()),
                "max_drawdown_mean":      float(df_m["max_drawdown"].mean()),
                "volatilitas_mean":       float(df_m["volatilitas_tahunan"].mean()),
                "sharpe_mean":            float(df_m["sharpe_ratio"].mean()),
                "beta_mean":              float(df_m["beta"].mean(skipna=True)),
            }

        return {
            "status":     "success",
            "n_emiten":   len(df_skor),
            "distribusi_kelas":  distribusi_kelas,
            "distribusi_sektor": distribusi_sektor,
            "ringkasan_rezim":   ringkasan_rezim,
            "ranking": df_to_records(
                ranking[[
                    "Sektor","Ranking_Global","Ranking_Sektor",
                    "Skor_Final","Skor_Konsistensi","Kelas",
                    "skor_Krisis","skor_Pemulihan","skor_Normal",
                ]].head(50)  # top 50 untuk performa
            ),
            "semua_emiten": df_to_records(
                ranking[["Sektor","Ranking_Global","Skor_Final","Kelas"]]
            ),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Error kalkulasi: {str(e)}\n{traceback.format_exc()}")


@router.get("/status/{session_id}")
async def cek_status(session_id: str):
    """Cek apakah sesi sudah punya hasil kalkulasi."""
    if session_id not in _sessions:
        return {"status": "not_found"}
    sess = _sessions[session_id]
    return {
        "status":       "ready" if "df_skor" in sess else "data_loaded",
        "n_emiten":     len(sess.get("df_bersih", {}).columns) if "df_bersih" in sess else 0,
        "has_result":   "df_skor" in sess,
    }


# Expose session store untuk dipakai routes lain
def get_session_store():
    return _sessions, save_session
