"""
routes_input.py
Endpoint: POST /api/v1/input/fetch  — ambil dari Yahoo Finance
Endpoint: POST /api/v1/input/upload — upload file Excel/CSV
Endpoint: GET  /api/v1/input/template — download template Excel
"""
import uuid
import io
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Dict, List, Optional
import pandas as pd

from app.services.data_fetcher import (
    fetch_from_yahoo, parse_uploaded_file,
    build_sektor_map, SEKTOR_DEFAULT,
    DEFAULT_TANGGAL_MULAI, DEFAULT_TANGGAL_AKHIR,
)
from app.api.routes_kalkulasi import save_session

router = APIRouter(prefix="/input", tags=["Input Data"])


class RequestFetchYahoo(BaseModel):
    sektor: Dict[str, List[str]] = SEKTOR_DEFAULT
    tanggal_mulai: str = DEFAULT_TANGGAL_MULAI
    tanggal_akhir: str = DEFAULT_TANGGAL_AKHIR


@router.post("/fetch")
async def fetch_yahoo(req: RequestFetchYahoo):
    """
    Download data harga dari Yahoo Finance untuk emiten yang dipilih.
    Simpan ke session, return session_id.
    """
    try:
        result = fetch_from_yahoo(
            sektor_dict=req.sektor,
            tanggal_mulai=req.tanggal_mulai,
            tanggal_akhir=req.tanggal_akhir,
        )

        session_id = str(uuid.uuid4())
        save_session(session_id, {
            "df_bersih":   result["df_bersih"],
            "return_ihsg": result["return_ihsg"],
            "df_sektor":   result["df_sektor"],
            "sumber":      "yahoo_finance",
        })

        sektor_counts = result["df_sektor"]["Sektor"].value_counts().to_dict()

        return {
            "status":         "success",
            "session_id":     session_id,
            "n_emiten":       len(result["df_bersih"].columns),
            "n_hari":         len(result["df_bersih"]),
            "sektor_counts":  sektor_counts,
            "log":            result["log"],
            "periode":        {
                "mulai": str(result["df_bersih"].index[0].date()),
                "akhir": str(result["df_bersih"].index[-1].date()),
            },
        }

    except Exception as e:
        raise HTTPException(500, f"Gagal mengunduh data: {str(e)}")


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    sektor_json: str = "{}",   # JSON string mapping kode→sektor
):
    """
    Upload file Excel/CSV dengan format template.
    Kolom wajib: Tanggal | Kode | Harga_Close
    """
    import json

    if not file.filename.endswith((".xlsx", ".xls", ".csv")):
        raise HTTPException(400, "Format file harus .xlsx, .xls, atau .csv")

    try:
        sektor_map = json.loads(sektor_json) if sektor_json != "{}" else {}
        file_bytes = await file.read()

        result = parse_uploaded_file(
            file_bytes=file_bytes,
            filename=file.filename,
            sektor_map=sektor_map,
        )

        session_id = str(uuid.uuid4())
        save_session(session_id, {
            "df_bersih":   result["df_bersih"],
            "return_ihsg": None,   # file upload tidak ada IHSG otomatis
            "df_sektor":   result["df_sektor"],
            "sumber":      "upload",
        })

        return {
            "status":        "success",
            "session_id":    session_id,
            "n_emiten":      len(result["df_bersih"].columns),
            "n_hari":        len(result["df_bersih"]),
            "log":           result["log"],
            "emiten_list":   list(result["df_bersih"].columns),
        }

    except ValueError as e:
        raise HTTPException(422, str(e))
    except Exception as e:
        raise HTTPException(500, f"Gagal memproses file: {str(e)}")


@router.get("/template")
async def download_template():
    """
    Download template Excel untuk mode upload file.
    Kolom: Tanggal | Kode | Harga_Close
    """
    df_template = pd.DataFrame({
        "Tanggal":     ["2020-01-02", "2020-01-03", "2020-01-06"],
        "Kode":        ["AALI",       "AALI",       "AALI"],
        "Harga_Close": [11500,        11400,        11350],
    })

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_template.to_excel(writer, sheet_name="Data", index=False)

        # Sheet petunjuk
        petunjuk = pd.DataFrame({
            "Kolom":       ["Tanggal", "Kode", "Harga_Close"],
            "Format":      ["YYYY-MM-DD", "Kode saham BEI (tanpa .JK)", "Angka desimal"],
            "Wajib":       ["Ya", "Ya", "Ya"],
            "Keterangan":  [
                "Tanggal hari perdagangan",
                "Contoh: AALI, BBCA, TLKM",
                "Harga penutupan harian (bisa adjusted atau raw)",
            ],
        })
        petunjuk.to_excel(writer, sheet_name="Petunjuk", index=False)

    output.seek(0)
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=template_upload_bei.xlsx"},
    )


@router.get("/emiten-default")
async def get_emiten_default():
    """Return daftar emiten default per sektor."""
    return {
        "sektor": SEKTOR_DEFAULT,
        "total":  sum(len(v) for v in SEKTOR_DEFAULT.values()),
    }
