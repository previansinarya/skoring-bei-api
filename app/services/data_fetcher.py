"""
Service: data_fetcher.py
Modul 1+2 dari notebook — download data Yahoo Finance + preprocessing
Kode identik dengan notebook, dibungkus sebagai fungsi yang bisa dipanggil API
"""
import yfinance as yf
import pandas as pd
import numpy as np
from typing import Dict, List, Optional
import io


# ── Konstanta default (bisa di-override dari request) ──────
DEFAULT_REZIM = {
    "Krisis":    {"start": "2020-03-02", "end": "2020-06-30"},
    "Pemulihan": {"start": "2020-07-01", "end": "2021-12-31"},
    "Normal":    {"start": "2022-01-01", "end": "2025-12-31"},
}
DEFAULT_BI_RATE = {
    "Krisis":    0.0425,
    "Pemulihan": 0.0350,
    "Normal":    0.0500,
}
DEFAULT_HARI_BURSA   = 245
DEFAULT_MISSING_THR  = 0.30
DEFAULT_OUTLIER_THR  = 1.0
DEFAULT_TANGGAL_MULAI = "2019-12-30"
DEFAULT_TANGGAL_AKHIR = "2025-12-31"

SEKTOR_DEFAULT = {
    "Energy": [
        "AALI","ADMR","AKRA","APEX","ARCI","ARII","BIPI","BSSR","BUMI",
        "BYAN","DEWA","DSSA","ELSA","ENRG","ESSA","GEMS","GTBO","HRUM",
        "INCO","ITMG","KKGI","MBAP","MEDC","MITI","MYOH","PKPK","PTBA",
        "PTRO","RAJA","RUIS","SMMT","SMRU","SSMS","SUGI","TOBA",
    ],
    "Industrials": [
        "ABBA","AGRO","AMFG","APII","ARNA","ASII","AUTO","BATA","BELL",
        "BGTG","BRAM","CAKK","CLEO","CMNP","CTBN","DPNS","EKAD","ESTI",
        "FASW","GDST","GJTL","HMSP","IGAR","IMPC","INAI","INCF","INDF",
        "INDS","ISAT","ISSP","JECC","JPFA","KBLI","KIAS","KLBF","LION",
        "LMSH","MAIN","MARK","MDKI","MLIA","MYOR","NIKL","PICO","PRAS",
        "SCCO","SIDO","SRIL","SRSN","SSTM","TALF","TBMS","TCID","TKIM",
        "UNIC","UNVR","VOKS",
    ],
    "Consumer_NC": [
        "ADES","ADMG","AISA","ALTO","BISI","BTEK","CEKA","COCO","DLTA",
        "DSFI","FOOD","GGRM","HOKI","ICBP","IIKP","IKAN","JGLE","KEJU",
        "KINO","KPIG","LSIP","MAPA","MGNA","MLBI","PCAR","PJAA","PNGO",
        "PSDN","RANC","ROTI","SHID","SKBM","SKLT","SMAR","STTP","TBLA",
        "TCPI","TGKA","ULTJ","UNSP","WSKT",
    ],
    "Basic_Materials": [
        "AGII","AKKU","ALKA","AMRT","ANTM","BAJA","BKDP","BRPT","BTON",
        "CPIN","CTTH","EKAD","ETWA","FASW","GDST","GGRP","GJTL","IGAR",
        "IMPC","INAI","INKP","INTP","IPOL","ISSP","JPFA","KDSI","KIAS",
        "KRAS","LION","LMSH","LTLS","MDKI","MLIA","MOLI","NIKL","PBRX",
        "PBSA","PICO","POOL","SCCO","SMBR","SMCB","SMGR","SRSN","TALF",
        "TBMS","TIRA","TKIM","TOTO","UNIC","VOKS","WTON",
    ],
}


def build_sektor_map(sektor_dict: Dict[str, List[str]]) -> Dict[str, str]:
    """Buat mapping kode → sektor dari dict sektor → list kode."""
    m = {}
    for sektor, kodes in sektor_dict.items():
        for k in kodes:
            m[k] = sektor
    return m


def fetch_from_yahoo(
    sektor_dict: Dict[str, List[str]],
    tanggal_mulai: str = DEFAULT_TANGGAL_MULAI,
    tanggal_akhir: str = DEFAULT_TANGGAL_AKHIR,
    missing_threshold: float = DEFAULT_MISSING_THR,
    outlier_threshold: float = DEFAULT_OUTLIER_THR,
) -> Dict:
    """
    Download data dari Yahoo Finance dan lakukan preprocessing.
    Return dict berisi df_bersih, rezim_data, rezim_ihsg, df_sektor, log.
    Identik dengan SEL 4-6 notebook.
    """
    log = []
    sektor_map = build_sektor_map(sektor_dict)
    semua_emiten = list(dict.fromkeys(
        [k for kodes in sektor_dict.values() for k in kodes]
    ))

    # Download emiten — pakai session dengan User-Agent browser
    # untuk menghindari pemblokiran IP datacenter oleh Yahoo Finance
    import requests, time

    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
    })

    tickers_yf   = [f"{k}.JK" for k in semua_emiten]
    BATCH_SIZE   = 30   # Download per 30 ticker agar tidak kena rate limit
    frames_close = []

    for i in range(0, len(tickers_yf), BATCH_SIZE):
        batch = tickers_yf[i:i + BATCH_SIZE]
        try:
            raw_batch = yf.download(
                batch,
                start=tanggal_mulai,
                end=tanggal_akhir,
                auto_adjust=True,
                progress=False,
                threads=False,   # Satu per satu dalam batch agar lebih stabil
                session=session,
            )
            if raw_batch is not None and len(raw_batch) > 0:
                if isinstance(raw_batch.columns, pd.MultiIndex):
                    close_batch = raw_batch["Close"].copy()
                else:
                    close_batch = raw_batch[["Close"]].copy()
                    close_batch.columns = batch
                close_batch.columns = [c.replace(".JK", "") for c in close_batch.columns]
                frames_close.append(close_batch)
                log.append(f"Batch {i//BATCH_SIZE + 1}: {len(close_batch.columns)} saham OK")
        except Exception as e:
            log.append(f"Batch {i//BATCH_SIZE + 1} gagal: {e}")
        # Jeda antar batch agar tidak kena rate limit
        if i + BATCH_SIZE < len(tickers_yf):
            time.sleep(1)

    if not frames_close:
        raise ValueError("Semua batch download gagal. Yahoo Finance mungkin sedang down atau IP diblokir.")

    # Gabungkan semua batch
    df_close = pd.concat(frames_close, axis=1)
    # Hapus kolom duplikat (emiten yang muncul di lebih dari 1 sektor)
    df_close = df_close.loc[:, ~df_close.columns.duplicated()]
    df_close.index = pd.to_datetime(df_close.index).normalize()
    log.append(f"Download selesai: {df_close.shape[1]} saham, {df_close.shape[0]} hari")

    # Download IHSG — dengan fallback untuk berbagai versi yfinance
    try:
        raw_ihsg = yf.download("^JKSE", start=tanggal_mulai, end=tanggal_akhir,
                                auto_adjust=True, progress=False,
                                threads=False, session=session)
        if raw_ihsg is None or len(raw_ihsg) == 0:
            raise ValueError("data kosong")
        if isinstance(raw_ihsg.columns, pd.MultiIndex):
            lvl0 = raw_ihsg.columns.get_level_values(0)
            if "Close" in lvl0:
                ihsg_close = raw_ihsg["Close"].iloc[:, 0]
            else:
                ihsg_close = raw_ihsg.iloc[:, 0]
        else:
            ihsg_close = raw_ihsg["Close"] if "Close" in raw_ihsg.columns else raw_ihsg.iloc[:, 0]
        ihsg_close = ihsg_close.squeeze()
        ihsg_close.index = pd.to_datetime(ihsg_close.index).normalize()
        return_ihsg = ihsg_close.pct_change().iloc[1:]
        log.append(f"IHSG diunduh: {len(return_ihsg)} hari return")
    except Exception as e:
        log.append(f"IHSG gagal diunduh ({e}), beta akan NaN")
        return_ihsg = pd.Series(dtype=float)

    # Preprocessing
    df_return_raw = df_close.pct_change().iloc[1:].copy()

    # Buang emiten tidak ada data
    kosong = df_return_raw.columns[df_return_raw.isnull().all()].tolist()
    if kosong:
        log.append(f"Tidak ditemukan di YF: {kosong}")
    df_return_raw = df_return_raw.drop(columns=kosong, errors="ignore")

    # Outlier
    n_out = (df_return_raw.abs() > outlier_threshold).sum().sum()
    if n_out > 0:
        df_return_raw[df_return_raw.abs() > outlier_threshold] = np.nan
        log.append(f"{n_out} outlier (|return|>100%) diganti NaN")

    # Filter missing
    pct_missing = df_return_raw.isnull().mean(axis=0)
    mask_valid  = pct_missing <= missing_threshold
    df_bersih   = df_return_raw.loc[:, mask_valid].copy()
    dibuang = df_return_raw.columns[~mask_valid].tolist()
    if dibuang:
        log.append(f"Dibuang >30% missing: {dibuang}")
    log.append(f"Emiten valid: {len(df_bersih.columns)}")

    # Sektor info
    df_sektor = pd.DataFrame({
        "Kode":   list(df_bersih.columns),
        "Sektor": [sektor_map.get(k, "Lainnya") for k in df_bersih.columns],
    }).set_index("Kode")

    # Align IHSG
    return_ihsg_aligned = return_ihsg.reindex(df_bersih.index)

    return {
        "df_bersih":   df_bersih,
        "return_ihsg": return_ihsg_aligned,
        "df_sektor":   df_sektor,
        "log":         log,
    }


def parse_uploaded_file(
    file_bytes: bytes,
    filename: str,
    sektor_map: Dict[str, str],
) -> Dict:
    """
    Parse file Excel/CSV yang diupload pengguna.
    Format yang diharapkan (template):
        Kolom: Tanggal | Kode | Harga_Close
    Return dict berisi df_bersih, df_sektor, log.
    """
    log = []

    if filename.endswith(".csv"):
        df_raw = pd.read_csv(io.BytesIO(file_bytes))
    else:
        df_raw = pd.read_excel(io.BytesIO(file_bytes))

    # Validasi kolom
    required = {"Tanggal", "Kode", "Harga_Close"}
    missing_cols = required - set(df_raw.columns)
    if missing_cols:
        raise ValueError(
            f"Kolom tidak ditemukan: {missing_cols}. "
            f"Gunakan template yang tersedia."
        )

    # Pivot ke format wide (baris=tanggal, kolom=kode)
    df_raw["Tanggal"] = pd.to_datetime(df_raw["Tanggal"])
    df_pivot = df_raw.pivot(index="Tanggal", columns="Kode", values="Harga_Close")
    df_pivot.index = pd.to_datetime(df_pivot.index).normalize()

    # Hitung return
    df_return = df_pivot.pct_change().iloc[1:].copy()
    log.append(f"File diparse: {df_return.shape[1]} emiten, {df_return.shape[0]} hari")

    # Outlier & missing
    df_return[df_return.abs() > 1.0] = np.nan
    pct_missing = df_return.isnull().mean(axis=0)
    df_bersih   = df_return.loc[:, pct_missing <= 0.30].copy()
    log.append(f"Emiten valid setelah cleaning: {len(df_bersih.columns)}")

    df_sektor = pd.DataFrame({
        "Kode":   list(df_bersih.columns),
        "Sektor": [sektor_map.get(k, "Lainnya") for k in df_bersih.columns],
    }).set_index("Kode")

    return {
        "df_bersih": df_bersih,
        "df_sektor": df_sektor,
        "log":       log,
    }


def segmentasi_rezim(
    df_bersih: pd.DataFrame,
    return_ihsg: Optional[pd.Series],
    rezim_config: Dict,
    min_hari: int = 10,
) -> Dict:
    """
    Potong DataFrame return per rezim.
    Identik dengan SEL 6 notebook.
    """
    rezim_data = {}
    rezim_ihsg = {}

    for nama, batas in rezim_config.items():
        mask = (
            (df_bersih.index >= batas["start"]) &
            (df_bersih.index <= batas["end"])
        )
        sub_emiten = df_bersih.loc[mask].copy()
        rezim_data[nama] = sub_emiten

        if return_ihsg is not None:
            rezim_ihsg[nama] = return_ihsg.loc[mask].copy()
        else:
            rezim_ihsg[nama] = pd.Series(dtype=float)

    return {"rezim_data": rezim_data, "rezim_ihsg": rezim_ihsg}
