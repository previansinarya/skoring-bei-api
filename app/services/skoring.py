"""
Service: skoring.py
Modul 4 dari notebook — normalisasi min-max + skoring berbobot
Identik dengan SEL 12-17 notebook
"""
import pandas as pd
import numpy as np
from typing import Dict


# ── Default bobot ─────────────────────────────────────────
DEFAULT_BOBOT_RETURN = {
    "cumulative_return": 0.25,
    "avg_daily_return":  0.15,
    "sharpe_ratio":      0.35,
    "max_drawdown":      0.15,
    "win_rate":          0.10,
}
DEFAULT_BOBOT_VOLATILITAS = {
    "std_harian":          0.30,
    "volatilitas_tahunan": 0.30,
    "skewness":            0.15,
    "kurtosis":            0.15,
    "beta":                0.10,
}
DEFAULT_BOBOT_DIMENSI = {"return": 0.60, "volatilitas": 0.40}
DEFAULT_BOBOT_REZIM   = {"Krisis": 0.40, "Pemulihan": 0.35, "Normal": 0.25}

# Metrik yang "semakin tinggi = semakin baik"
METRIK_POSITIF = {
    "cumulative_return", "avg_daily_return", "sharpe_ratio",
    "win_rate", "skewness",
}
MAX_STD_TEORITIS = 57.7


def normalisasi_minmax(series: pd.Series, positif: bool = True) -> pd.Series:
    """Min-max normalisasi ke skala 0-100."""
    mn, mx = series.min(), series.max()
    if mx == mn:
        return pd.Series(50.0, index=series.index)
    norm = (series - mn) / (mx - mn) * 100
    return norm if positif else (100 - norm)


def hitung_skoring(
    hasil_semua:       Dict[str, pd.DataFrame],
    df_sektor:         pd.DataFrame,
    bobot_return:      Dict = None,
    bobot_volatilitas: Dict = None,
    bobot_dimensi:     Dict = None,
    bobot_rezim:       Dict = None,
) -> pd.DataFrame:
    """
    Normalisasi + skoring berbobot untuk semua emiten × rezim.
    Identik dengan SEL 12-17 notebook.
    Return df_skor lengkap dengan Skor_Final, Konsistensi, Kelas, Ranking.
    """
    bobot_return      = bobot_return      or DEFAULT_BOBOT_RETURN
    bobot_volatilitas = bobot_volatilitas or DEFAULT_BOBOT_VOLATILITAS
    bobot_dimensi     = bobot_dimensi     or DEFAULT_BOBOT_DIMENSI
    bobot_rezim       = bobot_rezim       or DEFAULT_BOBOT_REZIM

    kolom_return = list(bobot_return.keys())
    kolom_vol    = list(bobot_volatilitas.keys())
    semua_kolom  = kolom_return + kolom_vol

    # ── Normalisasi ────────────────────────────────────────
    hasil_norm    = {}
    skor_per_rezim = {}

    for nama_rezim, df_m in hasil_semua.items():
        df_norm = pd.DataFrame(index=df_m.index)

        for kolom in semua_kolom:
            if kolom not in df_m.columns:
                continue
            positif = kolom in METRIK_POSITIF
            df_norm[kolom] = normalisasi_minmax(df_m[kolom], positif=positif)

        hasil_norm[nama_rezim] = df_norm

        # ── Skor per rezim ─────────────────────────────────
        skor_return = pd.Series(0.0, index=df_norm.index)
        for metrik, bobot in bobot_return.items():
            if metrik in df_norm.columns:
                skor_return += df_norm[metrik].fillna(50) * bobot

        skor_vol = pd.Series(0.0, index=df_norm.index)
        for metrik, bobot in bobot_volatilitas.items():
            if metrik in df_norm.columns:
                skor_vol += df_norm[metrik].fillna(50) * bobot

        skor_rezim = (
            skor_return * bobot_dimensi["return"] +
            skor_vol    * bobot_dimensi["volatilitas"]
        )

        df_s = pd.DataFrame(index=df_norm.index)
        df_s["skor_return"]      = skor_return.round(2)
        df_s["skor_volatilitas"] = skor_vol.round(2)
        df_s["skor_rezim"]       = skor_rezim.round(2)
        skor_per_rezim[nama_rezim] = df_s

    # ── Gabungkan semua rezim ──────────────────────────────
    semua_emiten = list(hasil_semua[list(hasil_semua.keys())[0]].index)
    df_skor = pd.DataFrame(index=semua_emiten)
    df_skor.index.name = "Kode"

    for nama_rezim in bobot_rezim.keys():
        if nama_rezim not in skor_per_rezim:
            continue
        df_skor[f"skor_{nama_rezim}"]             = skor_per_rezim[nama_rezim]["skor_rezim"]
        df_skor[f"skor_{nama_rezim}_return"]      = skor_per_rezim[nama_rezim]["skor_return"]
        df_skor[f"skor_{nama_rezim}_volatilitas"] = skor_per_rezim[nama_rezim]["skor_volatilitas"]

    # ── Skor Final ─────────────────────────────────────────
    skor_final = pd.Series(0.0, index=df_skor.index)
    for nama_rezim, bobot in bobot_rezim.items():
        col = f"skor_{nama_rezim}"
        if col in df_skor.columns:
            skor_final += df_skor[col].fillna(50) * bobot
    df_skor["Skor_Final"] = skor_final.round(2)

    # ── Skor Konsistensi ───────────────────────────────────
    cols_rezim   = [f"skor_{r}" for r in bobot_rezim if f"skor_{r}" in df_skor.columns]
    std_rezim    = df_skor[cols_rezim].std(axis=1)
    df_skor["Skor_Konsistensi"] = (
        (100 - (std_rezim / MAX_STD_TEORITIS * 100)).clip(0, 100).round(2)
    )

    # ── Skor Final Plus (80% Final + 20% Konsistensi) ──────
    df_skor["Skor_Final_Plus"] = (
        df_skor["Skor_Final"] * 0.80 +
        df_skor["Skor_Konsistensi"] * 0.20
    ).round(2)

    # ── Sektor ────────────────────────────────────────────
    df_skor["Sektor"] = df_sektor["Sektor"]

    # ── Kelas ─────────────────────────────────────────────
    def klasifikasi(s):
        if s >= 80: return "A"
        if s >= 60: return "B"
        if s >= 40: return "C"
        if s >= 20: return "D"
        return "E"
    df_skor["Kelas"] = df_skor["Skor_Final"].apply(klasifikasi)

    # ── Ranking ───────────────────────────────────────────
    df_skor["Ranking_Global"] = (
        df_skor["Skor_Final"].rank(ascending=False, method="min").astype(int)
    )
    df_skor["Ranking_Sektor"] = (
        df_skor.groupby("Sektor")["Skor_Final"]
        .rank(ascending=False, method="min").astype(int)
    )

    return df_skor
