"""
Extraccion automatica de datos: FED (FRED API), S&P 500 (Yahoo Finance),
commodities y crypto. Cache en disco con TTL de 24h.
"""

import os
import time
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

DATA_DIR = Path(__file__).resolve().parent
CACHE_DIR = DATA_DIR / ".data_cache"
CACHE_TTL = 86_400  # 24 horas en segundos

# ── Universo de activos alternativos ────────────────────────────────────

COMMODITY_FUTURES: dict[str, str] = {
    "GC=F": "Oro",
    "SI=F": "Plata",
    "CL=F": "Petroleo Crude Oil",
    "HG=F": "Cobre",
    "NG=F": "Gas natural",
    "PL=F": "Platino",
    "PA=F": "Paladio",
    "LE=F": "Ganado",
}

COMMODITY_ETFS: dict[str, str] = {
    "GLD": "Oro (ETF)",
    "SLV": "Plata (ETF)",
    "USO": "Petroleo (ETF)",
    "DBA": "Agricultura (ETF)",
    "DBC": "Commodities (ETF)",
    "LIT": "Litio",
}

CRYPTO_TICKERS: dict[str, str] = {
    "BTC-USD": "Bitcoin",
    "ETH-USD": "Ethereum",
}

ALTERNATIVE_TICKERS: dict[str, str] = {
    **COMMODITY_FUTURES,
    **COMMODITY_ETFS,
    **CRYPTO_TICKERS,
}

TOP_20_TICKERS: list[str] = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "BRK-B", "LLY", "AVGO", "TSLA",
    "JPM", "UNH", "V", "XOM", "MA", "PG", "COST", "HD", "JNJ", "NFLX"
]

# Tickers de bonos gubernamentales a excluir del portfolio
BOND_TICKERS: set[str] = {
    "TLT", "IEF", "SHY", "TIP", "GOVT", "BND", "AGG",
    "VGSH", "VGIT", "VGLT", "VTIP", "EDV", "ZROZ",
    "TMF", "TBT", "SCHO", "SCHR", "SCHZ",
}



# ── Utilidades de cache ─────────────────────────────────────────────────

def _cache_path(name: str) -> Path:
    CACHE_DIR.mkdir(exist_ok=True)
    return CACHE_DIR / f"{name}.csv"


def _cache_is_fresh(path: Path) -> bool:
    if not path.exists():
        return False
    return (time.time() - path.stat().st_mtime) < CACHE_TTL


def _get_fred_api_key() -> str | None:
    """Busca FRED API key en secrets de Streamlit o variable de entorno."""
    try:
        return st.secrets["FRED_API_KEY"]
    except Exception:
        pass
    return os.environ.get("FRED_API_KEY")


# ── Datos de la FED (FRED API) ──────────────────────────────────────────

def _fetch_fed_macro(api_key: str, start_date: str = "1954-07-01") -> pd.DataFrame:
    """Descarga FEDFUNDS y BOGMBASE desde FRED."""
    from fredapi import Fred

    fred = Fred(api_key=api_key)
    fedfunds = fred.get_series("FEDFUNDS", observation_start=start_date)
    bogmbase = fred.get_series("BOGMBASE", observation_start=start_date)

    macro = pd.DataFrame(
        {"fed_funds_rate": fedfunds, "monetary_base": bogmbase}
    )
    macro.index.name = "date"
    macro["fed_funds_rate"] = pd.to_numeric(macro["fed_funds_rate"], errors="coerce")
    macro["monetary_base"] = pd.to_numeric(macro["monetary_base"], errors="coerce")
    return macro.sort_index()


@st.cache_data(ttl=CACHE_TTL, show_spinner="Descargando datos de la FED…")
def load_fed_macro() -> pd.DataFrame:
    """Carga datos macro de la FED con cache de 24 h y descarga automatica."""
    cache = _cache_path("fed_macro")
    if _cache_is_fresh(cache):
        macro = pd.read_csv(cache, index_col=0, parse_dates=True)
        macro.index.name = "date"
        return macro

    api_key = _get_fred_api_key()
    if not api_key:
        st.error(
            "⚠️ FRED_API_KEY no configurada. "
            "Agregala en `.streamlit/secrets.toml` o como variable de entorno."
        )
        st.stop()

    try:
        macro = _fetch_fed_macro(api_key)
        macro.to_csv(cache)
        return macro
    except Exception as exc:
        st.error(f"Error al descargar datos de FRED: {exc}")
        st.stop()


# ── S&P 500 (Yahoo Finance + Wikipedia) ─────────────────────────────────

def _fetch_sp500_tickers() -> list[str]:
    """Obtiene la lista actual de tickers del S&P 500 desde Wikipedia."""
    import io

    import requests

    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    tables = pd.read_html(io.StringIO(resp.text))
    df = tables[0]
    # Yahoo Finance usa '-' donde el ticker tiene '.' (e.g. BRK.B -> BRK-B)
    tickers = df["Symbol"].str.replace(".", "-", regex=False).tolist()
    return sorted(set(tickers))


def _fetch_prices(tickers: list[str], start: str = "2000-01-01") -> pd.DataFrame:
    """Descarga precios de cierre ajustados desde Yahoo Finance."""
    import yfinance as yf

    data = yf.download(
        tickers,
        start=start,
        auto_adjust=True,
        progress=False,
    )

    if data.empty:
        return pd.DataFrame()

    # yfinance devuelve MultiIndex (Price, Ticker) para multiples tickers
    if isinstance(data.columns, pd.MultiIndex):
        level_values = data.columns.get_level_values(0).unique()
        if "Close" in level_values:
            prices = data["Close"]
        else:
            # Fallback: tomar el primer nivel
            prices = data[level_values[0]]
    else:
        # Un solo ticker: columnas simples
        if "Close" in data.columns:
            name = tickers[0] if len(tickers) == 1 else "Close"
            prices = data[["Close"]].rename(columns={"Close": name})
        else:
            prices = data

    prices.index = pd.to_datetime(prices.index)
    prices.index.name = "date"
    return prices.sort_index()


@st.cache_data(ttl=CACHE_TTL, show_spinner="Descargando precios del S&P 500 (puede tardar unos minutos)…")
def load_sp500_prices() -> pd.DataFrame:
    """Carga precios del S&P 500 con cache de 24 h."""
    cache = _cache_path("sp500_prices")
    if _cache_is_fresh(cache):
        prices = pd.read_csv(cache, index_col=0, parse_dates=True)
        prices.index.name = "date"
        return prices.sort_index()

    try:
        tickers = _fetch_sp500_tickers()
        prices = _fetch_prices(tickers)
        prices.to_csv(cache)
        return prices
    except Exception as exc:
        st.error(f"Error al descargar precios del S&P 500: {exc}")
        st.stop()


@st.cache_data(ttl=CACHE_TTL, show_spinner="Calculando valor del indice…")
def load_index_value() -> pd.DataFrame:
    """Genera el valor agregado del S&P 500 sumando precios de componentes."""
    cache = _cache_path("index_value")
    if _cache_is_fresh(cache):
        value = pd.read_csv(cache, index_col=0, parse_dates=True)
        value.index.name = "date"
        return value.sort_index()

    prices = load_sp500_prices()
    total = prices.sum(axis=1).rename("Total Value").to_frame()
    total.index.name = "date"
    total.to_csv(cache)
    return total.sort_index()


# ── Activos alternativos (commodities + crypto) ─────────────────────────

@st.cache_data(ttl=CACHE_TTL, show_spinner="Descargando commodities y crypto…")
def load_alternative_assets() -> pd.DataFrame:
    """Descarga precios de commodities (futuros + ETFs) y crypto."""
    cache = _cache_path("alternative_assets")
    if _cache_is_fresh(cache):
        prices = pd.read_csv(cache, index_col=0, parse_dates=True)
        prices.index.name = "date"
        return prices.sort_index()

    try:
        tickers = list(ALTERNATIVE_TICKERS.keys()) + TOP_20_TICKERS + ["^GSPC"]
        prices = _fetch_prices(tickers)
        prices.to_csv(cache)
        return prices
    except Exception as exc:
        st.error(f"Error al descargar activos alternativos: {exc}")
        st.stop()


# ── Universo completo ───────────────────────────────────────────────────

@st.cache_data(ttl=CACHE_TTL, show_spinner="Armando universo completo de activos…")
def load_full_universe() -> pd.DataFrame:
    """Combina precios del S&P 500 con commodities y crypto."""
    sp500 = load_sp500_prices()
    alternatives = load_alternative_assets()
    # Agregar activos alternativos que no esten ya en el S&P 500
    alt_new = alternatives[[c for c in alternatives.columns if c not in sp500.columns]]
    return pd.concat([sp500, alt_new], axis=1)


# ── Estado del cache ────────────────────────────────────────────────────

def data_source_status() -> dict[str, dict]:
    """Devuelve estado de cada archivo de cache."""
    status = {}
    for name in ("fed_macro", "sp500_prices", "index_value", "alternative_assets"):
        path = _cache_path(name)
        if path.exists():
            age_hours = (time.time() - path.stat().st_mtime) / 3600
            status[name] = {
                "exists": True,
                "fresh": age_hours < (CACHE_TTL / 3600),
                "age_hours": round(age_hours, 1),
            }
        else:
            status[name] = {"exists": False, "fresh": False, "age_hours": None}
    return status
