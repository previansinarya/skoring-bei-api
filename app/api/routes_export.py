"""routes_export.py — endpoint download Excel hasil analisis"""
import io
import numpy as np
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import pandas as pd

from app.api.routes_kalkulasi import get_session_store

router = APIRouter(prefix="/export", tags=["Export"])


@router.get("/excel/{session_id}")
async def export_excel(session_id: str):
    """Download hasil analisis lengkap sebagai Excel."""
    store, _ = get_session_store()
    if session_id not in store or "df_skor" not in store[session_id]:
        raise HTTPException(404, "Hasil belum tersedia. Jalankan kalkulasi terlebih dahulu.")

    sess    = store[session_id]
    df_skor = sess["df_skor"]
    hasil_semua = sess.get("hasil_semua", {})

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        # Sheet 1: Ranking global
        kolom = [
            "Sektor","Ranking_Global","Ranking_Sektor","Skor_Final",
            "Skor_Konsistensi","Kelas","skor_Krisis","skor_Pemulihan","skor_Normal",
        ]
        df_skor[kolom].sort_values("Ranking_Global").to_excel(
            writer, sheet_name="Ranking_Global"
        )

        # Sheet 2-4: per rezim
        kolom_m = [
            "cumulative_return","avg_daily_return","sharpe_ratio","max_drawdown",
            "win_rate","std_harian","volatilitas_tahunan","skewness","kurtosis","beta","n_hari"
        ]
        for nama_rezim, df_m in hasil_semua.items():
            df_m[kolom_m].round(6).to_excel(writer, sheet_name=nama_rezim[:31])

        # Sheet 5: ringkasan sektor
        ring = df_skor.groupby("Sektor").agg(
            n_emiten  = ("Skor_Final","count"),
            skor_mean = ("Skor_Final","mean"),
            skor_max  = ("Skor_Final","max"),
            skor_min  = ("Skor_Final","min"),
            kelas_A   = ("Kelas", lambda x: (x=="A").sum()),
            kelas_B   = ("Kelas", lambda x: (x=="B").sum()),
            kelas_C   = ("Kelas", lambda x: (x=="C").sum()),
            kelas_D   = ("Kelas", lambda x: (x=="D").sum()),
            kelas_E   = ("Kelas", lambda x: (x=="E").sum()),
        ).round(2)
        ring.to_excel(writer, sheet_name="Ringkasan_Sektor")

    output.seek(0)
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=hasil_skoring_bei.xlsx"},
    )
