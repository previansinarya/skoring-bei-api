"""
Service: metrik.py
Modul 3 dari notebook — kalkulasi 10 metrik per emiten per rezim
Identik dengan SEL 7-8 notebook, dibungkus sebagai fungsi
"""
import pandas as pd
import numpy as np
from scipy import stats
from typing import Dict


KOLOM_METRIK = [
    "cumulative_return", "avg_daily_return", "sharpe_ratio",
    "max_drawdown", "win_rate", "std_harian", "volatilitas_tahunan",
    "skewness", "kurtosis", "beta", "n_hari",
]


def hitung_metrik(
    return_series: pd.Series,
    return_pasar:  pd.Series,
    rf_tahunan:    float,
    hari_bursa:    int = 245,
) -> dict:
    """
    Hitung 10 metrik risiko-return dari satu seri return harian.
    Identik dengan SEL 7 notebook v3.
    """
    r = return_series.dropna()

    if len(r) < 5:
        return {m: np.nan for m in KOLOM_METRIK}

    # 1. Cumulative Return
    cr = (1 + r).prod() - 1

    # 2. Average Daily Return
    adr = r.mean()

    # 3. Sharpe Ratio (dengan BI Rate)
    rf_harian = rf_tahunan / hari_bursa
    std = r.std()
    sharpe = ((adr - rf_harian) / std * np.sqrt(hari_bursa)) if std > 0 else 0.0

    # 4. Maximum Drawdown
    cum  = (1 + r).cumprod()
    peak = cum.expanding().max()
    mdd  = ((cum - peak) / peak).min()

    # 5. Win Rate
    win_rate = (r > 0).sum() / len(r)

    # 6 & 7. Volatilitas
    vol_harian  = std
    vol_tahunan = std * np.sqrt(hari_bursa)

    # 8. Skewness
    skew = stats.skew(r)

    # 9. Kurtosis
    kurt = stats.kurtosis(r)

    # 10. Beta vs IHSG
    beta = np.nan
    r_pasar = return_pasar.dropna()
    idx_common = r.index.intersection(r_pasar.index)
    if len(idx_common) >= 5:
        r_e = r[idx_common].values
        r_p = r_pasar[idx_common].values
        cov_mat   = np.cov(r_e, r_p)
        var_pasar = cov_mat[1, 1]
        if var_pasar > 0:
            beta = round(cov_mat[0, 1] / var_pasar, 4)

    return {
        "cumulative_return":   round(cr, 6),
        "avg_daily_return":    round(adr, 6),
        "sharpe_ratio":        round(sharpe, 4),
        "max_drawdown":        round(mdd, 6),
        "win_rate":            round(win_rate, 4),
        "std_harian":          round(vol_harian, 6),
        "volatilitas_tahunan": round(vol_tahunan, 4),
        "skewness":            round(skew, 4),
        "kurtosis":            round(kurt, 4),
        "beta":                beta,
        "n_hari":              len(r),
    }


def hitung_semua_metrik(
    rezim_data: Dict[str, pd.DataFrame],
    rezim_ihsg: Dict[str, pd.Series],
    bi_rate:    Dict[str, float],
    hari_bursa: int = 245,
) -> Dict[str, pd.DataFrame]:
    """
    Jalankan hitung_metrik untuk semua emiten × semua rezim.
    Identik dengan SEL 8 notebook.
    Return dict {nama_rezim: DataFrame metrik}.
    """
    hasil_semua = {}

    for nama_rezim, df_rezim in rezim_data.items():
        rf         = bi_rate.get(nama_rezim, 0.05)
        r_ihsg_rez = rezim_ihsg.get(nama_rezim, pd.Series(dtype=float))

        baris = []
        for kode in df_rezim.columns:
            metrik = hitung_metrik(
                return_series=df_rezim[kode],
                return_pasar=r_ihsg_rez,
                rf_tahunan=rf,
                hari_bursa=hari_bursa,
            )
            metrik["kode"] = kode
            baris.append(metrik)

        df_m = pd.DataFrame(baris).set_index("kode")
        hasil_semua[nama_rezim] = df_m

    return hasil_semua


def gabungkan_semua_rezim(
    hasil_semua: Dict[str, pd.DataFrame]
) -> pd.DataFrame:
    """
    Gabungkan metrik semua rezim menjadi satu DataFrame lebar.
    Kolom format: {NamaRezim}_{nama_metrik}
    """
    frames = []
    for nama_rezim, df_m in hasil_semua.items():
        tmp = df_m[KOLOM_METRIK].copy()
        tmp.columns = [f"{nama_rezim}_{c}" for c in KOLOM_METRIK]
        frames.append(tmp)

    df_final = pd.concat(frames, axis=1)
    df_final.index.name = "Kode"
    return df_final
