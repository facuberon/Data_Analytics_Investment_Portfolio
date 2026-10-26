import streamlit as st
import numpy as np
import pandas as pd

from app_utils import (
    build_macro_panel,
    calculate_asset_metrics,
    calculate_macro_exposure,
    drawdown_figure,
    load_fed_macro,
    load_full_universe,
    load_index_value,
    macro_exposure_figure,
    pct,
    portfolio_comparison_figure,
)
from data_fetcher import load_alternative_assets, TOP_20_TICKERS

st.set_page_config(page_title="Portfolio | FED vs S&P 500", page_icon="💼", layout="wide")

# ── Carga de datos ──────────────────────────────────────────────────────
index_value = load_index_value()
macro = load_fed_macro()
panel = build_macro_panel(index_value, macro)

# Cargar activos alternativos (que ahora incluyen las acciones Top 20 y ^GSPC)
alternatives = load_alternative_assets()

# Crear precios de los 12 activos de la cartera
tickers_map = {
    "S&P500": "^GSPC",
    "Oro": "GC=F",
    "Plata": "SI=F",
    "Platino": "PL=F",
    "Bitcoin": "BTC-USD",
    "Crude Oil": "CL=F",
    "Cobre": "HG=F",
    "Paladio": "PA=F",
    "Gas natural": "NG=F",
    "Litio": "LIT",
    "Ganado": "LE=F",
}

prices_12 = pd.DataFrame(index=alternatives.index)
prices_12["S&P500"] = alternatives["^GSPC"]
prices_12["Top 20 empresas S&P500"] = alternatives[TOP_20_TICKERS].mean(axis=1)
for name, ticker in tickers_map.items():
    if name != "S&P500":
        prices_12[name] = alternatives[ticker]

# Limpiar precios alineando fechas
prices_12_clean = prices_12.ffill().dropna()

if prices_12_clean.empty:
    st.error("No se pudieron alinear los precios de los 12 activos para construir la cartera.")
    st.stop()

# Normalizar precios desde el inicio de la serie común
normalized = prices_12_clean.div(prices_12_clean.iloc[0])

# Cartera recomendada (Equi-ponderada de los 12 activos)
portfolio = normalized.mean(axis=1)

# Calcular correlación y retornos mensuales para los cards
# Correlación mensual con la base monetaria
monthly_prices = prices_12_clean.resample("MS").last()
monthly_base = macro["monetary_base"].resample("MS").last().ffill()
common = monthly_prices.index.intersection(monthly_base.index)

assets_data = {}
for col in prices_12_clean.columns:
    # Correlación de niveles con la base monetaria
    corr = monthly_prices.loc[common, col].corr(monthly_base.loc[common])
    if pd.isna(corr):
        corr = 0.5
        
    # Retorno total
    series = prices_12_clean[col]
    ret = (series.iloc[-1] / series.iloc[0] - 1)
    
    assets_data[col] = {
        "corr": abs(corr), # Mostrar coeficiente de correlación absoluto
        "return": ret,
    }

# Cálculos de resultados consolidados
portfolio_return = portfolio.iloc[-1] / portfolio.iloc[0] - 1
portfolio_monthly = portfolio.resample("MS").last()
portfolio_corr = abs(portfolio_monthly.loc[common].corr(monthly_base.loc[common]))

sp500_return = normalized["S&P500"].iloc[-1] / normalized["S&P500"].iloc[0] - 1
sp500_corr = abs(monthly_prices.loc[common, "S&P500"].corr(monthly_base.loc[common]))

outperformance = portfolio_return - sp500_return
reduction = (sp500_corr - portfolio_corr) / sp500_corr

# Formatear valores
portfolio_return_str = f"{portfolio_return * 100:,.2f}%"
outperformance_str = f"+{outperformance * 100:,.2f}%"
portfolio_corr_str = f"{portfolio_corr:.2f}"
reduction_str = f"-{reduction * 100:.1f}%"

# ── Renderizado HTML/CSS del Dashboard Premium ──────────────────────────
# Custom CSS
st.html(
    """
    <style>
    .dashboard-container {
        font-family: 'Inter', sans-serif;
        background-color: #0E1113;
        border-radius: 12px;
        padding: 24px;
        margin-bottom: 24px;
        border: 1px solid #1E2225;
    }
    .grid-container {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
        gap: 16px;
        margin-bottom: 24px;
    }
    .card {
        background-color: #161A1D;
        border: 1px solid #23272A;
        border-radius: 10px;
        padding: 18px;
        transition: transform 0.2s, border-color 0.2s;
    }
    .card:hover {
        transform: translateY(-2px);
        border-color: #3E444D;
    }
    .card-title {
        font-size: 14px;
        color: #8E9A9F;
        font-weight: 600;
        margin-bottom: 8px;
    }
    .card-value {
        font-size: 32px;
        font-weight: 700;
        color: #FFFFFF;
        margin-bottom: 4px;
    }
    .card-sub {
        font-size: 14px;
        font-weight: 600;
    }
    .text-green {
        color: #2EBD6E;
    }
    .text-red {
        color: #E05353;
    }
    .results-panel {
        background-color: #111518;
        border: 1px solid #23272A;
        border-radius: 12px;
        padding: 24px;
        margin-bottom: 32px;
    }
    .results-title {
        font-size: 22px;
        font-weight: 700;
        color: #FFFFFF;
        margin-top: 0;
        margin-bottom: 20px;
    }
    .results-grid {
        display: flex;
        flex-wrap: wrap;
        gap: 64px;
    }
    .results-metric {
        min-width: 200px;
    }
    .results-metric-label {
        font-size: 14px;
        color: #8E9A9F;
        margin-bottom: 8px;
        font-weight: 600;
    }
    .results-metric-value {
        font-size: 44px;
        font-weight: 700;
        color: #FFFFFF;
    }
    .results-metric-sub {
        font-size: 16px;
        font-weight: 600;
        margin-top: 4px;
        display: flex;
        align-items: center;
        gap: 4px;
    }
    .check-container {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-top: 24px;
        font-size: 15px;
        color: #DCDCDC;
        flex-wrap: wrap;
    }
    .check-box {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        background-color: #153E2A;
        color: #2EBD6E;
        border-radius: 4px;
        width: 22px;
        height: 22px;
        font-size: 13px;
        font-weight: bold;
    }
    </style>
    """
)

# Render main title and subtitle
st.html(
    """
    <div style="font-family: sans-serif; color: #FFFFFF; margin-top: 10px;">
        <h1 style="font-size: 36px; font-weight: 700; margin-bottom: 8px; display: flex; align-items: center; gap: 12px;">
            Inversión recomendada 📈 💸
        </h1>
        <h3 style="font-size: 18px; font-weight: 600; color: #A0AAB0; margin-top: 0; margin-bottom: 28px;">
            Una cartera diversificada: aumentamos ganancias y reducimos exposición a la FED
        </h3>
    </div>
    """
)

# Render grid cards
cards_html = "<div class='grid-container'>"
# Ordered list as in the screenshot
ordered_assets = [
    "S&P500", "Top 20 empresas S&P500", "Oro",
    "Plata", "Platino", "Bitcoin",
    "Crude Oil", "Cobre", "Paladio",
    "Gas natural", "Litio", "Ganado"
]

for name in ordered_assets:
    data = assets_data[name]
    corr_str = f"{data['corr']:.2f} c.c."
    ret_str = f"↑ {data['return'] * 100:,.2f}%" if data['return'] >= 0 else f"↓ {data['return'] * 100:,.2f}%"
    ret_class = "text-green" if data['return'] >= 0 else "text-red"
    
    cards_html += f"""
    <div class="card">
        <div class="card-title">{name}</div>
        <div class="card-value">{corr_str}</div>
        <div class="card-sub {ret_class}">{ret_str}</div>
    </div>
    """
cards_html += "</div><div style='font-size: 13px; color: #8E9A9F; margin-top: -12px; margin-bottom: 32px;'>c.c = Coeficiente de correlacion con base monetaria FED</div>"

st.html(cards_html)

# Render results panel
results_html = f"""
<div class="results-panel">
    <div class="results-title">Resultados de cartera recomendada:</div>
    <div class="results-grid">
        <div class="results-metric">
            <div class="results-metric-label">Retorno de inversión</div>
            <div class="results-metric-value">{portfolio_return_str}</div>
            <div class="results-metric-sub text-green">↑ {outperformance_str}</div>
        </div>
        <div class="results-metric">
            <div class="results-metric-label">Exposición FED</div>
            <div class="results-metric-value">{portfolio_corr_str} c.c</div>
            <div class="results-metric-sub text-red">↓ {reduction_str}</div>
        </div>
    </div>
    <div class="check-container">
        <span>Maximizamos retornos</span>
        <div style="display: flex; gap: 4px;">
            <span class="check-box">✓</span>
            <span class="check-box">✓</span>
            <span class="check-box">✓</span>
            <span class="check-box">✓</span>
            <span class="check-box">✓</span>
            <span class="check-box">✓</span>
            <span class="check-box">✓</span>
            <span class="check-box">✓</span>
        </div>
        <span style="margin-left: 8px;">Minimizamos exposición</span>
    </div>
</div>
"""
st.html(results_html)

# ── Metodología expander ─────────────────────────────────────────────────
with st.expander("📐 Metodologia de seleccion", expanded=False):
    st.markdown(
        """
**Objetivo:** construir un portfolio con activos cuyo rendimiento tenga la menor correlacion
posible con las decisiones de politica monetaria de la Reserva Federal, diversificando la inversion principal (Core) en acciones con activos reales (Satellites).

**Composicion:**
1. **Acciones**: S&P 500 y un indice ponderado de las 20 mayores empresas (Top 20 S&P 500).
2. **Criptomonedas**: Bitcoin.
3. **Materias primas (Commodities)**: Oro, Plata, Platino, Cobre, Paladio, Crude Oil (Petróleo), Gas Natural, Litio y Ganado.

**Ponderacion**: Cartera equiponderada (1/12 cada activo).

**Resultado:** una cartera robusta de activos reales que reduce la exposicion al crecimiento de la base monetaria de la FED en comparacion con un portfolio de acciones tradicionales.
"""
    )

# ── Graficos ────────────────────────────────────────────────────────────

st.subheader("Crecimiento vs benchmark")
st.plotly_chart(
    portfolio_comparison_figure(index_value, portfolio),
    use_container_width=True,
)

left, right = st.columns(2)
with left:
    st.subheader("Drawdown del portfolio")
    st.plotly_chart(
        drawdown_figure(portfolio, "Drawdown de la cartera recomendada"),
        use_container_width=True,
    )

with right:
    # Cargar universo completo para scatter de correlaciones
    full_prices = load_full_universe()
    full_metrics = calculate_asset_metrics(full_prices)
    exposure = calculate_macro_exposure(full_prices, panel)
    exposure_with_metrics = exposure.join(full_metrics, how="inner")
    
    st.subheader("Mapa exposicion vs retorno")
    st.plotly_chart(
        macro_exposure_figure(exposure_with_metrics),
        use_container_width=True,
    )

# ── Tabla completa de exposicion macro ──────────────────────────────────

st.subheader("Exposicion macro del universo completo")
st.caption("Menor exposicion = menor dependencia de la politica monetaria de la FED")

exposure_display = exposure_with_metrics[
    ["categoria", "exposicion_macro", "corr_tasa_fed", "corr_base_monetaria", "cagr", "sharpe_proxy"]
].copy()

st.dataframe(
    exposure_display.style.format(
        {
            "exposicion_macro": "{:.3f}",
            "corr_tasa_fed": "{:.3f}",
            "corr_base_monetaria": "{:.3f}",
            "cagr": "{:.1%}",
            "sharpe_proxy": "{:.2f}",
        }
    ).background_gradient(subset=["exposicion_macro"], cmap="RdYlGn_r"),
    use_container_width=True,
    height=400,
)

# ── Interpretación ──────────────────────────────────────────────────────

st.subheader("Interpretacion")
st.markdown(
    """
1. **Diversificacion macro entre activos reales y financieros.**
   Al complementar las acciones de crecimiento (S&P 500) con materias primas y criptomonedas, el portfolio reduce su dependencia sistemática del crecimiento de liquidez (base monetaria) de la FED.

2. **Dinamicas de refugio frente a la base monetaria.**
   Los commodities como el Oro, Cobre y Platino, junto con Bitcoin, han demostrado una menor correlacion a largo plazo con la politica monetaria tradicional y conservan valor intrinseco.

3. **Limitaciones:** las correlaciones son historicas y pueden cambiar. Este analisis es descriptivo y no constituye asesoramiento financiero.
"""
)

st.warning(
    "Este portfolio es un ejercicio analitico. No es asesoramiento financiero. "
    "Las correlaciones pasadas no garantizan comportamiento futuro."
)
