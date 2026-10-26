import streamlit as st

from app_utils import (
    build_macro_panel,
    calculate_macro_metrics,
    load_fed_macro,
    load_index_value,
    load_sp500_prices,
    pct,
)
from data_fetcher import data_source_status


st.set_page_config(
    page_title="FED vs S&P 500 Analytics",
    page_icon="📈",
    layout="wide",
)

prices = load_sp500_prices()
index_value = load_index_value()
macro = load_fed_macro()
panel = build_macro_panel(index_value, macro)
metrics = calculate_macro_metrics(panel)

st.title("FED vs S&P 500 Analytics")
st.caption("Tasas de interes, emision monetaria y mercado accionario estadounidense")

st.markdown(
    """
Este proyecto analiza la relacion entre la politica monetaria de la Reserva Federal y el comportamiento del
S&P 500. El foco no es predecir precios puntuales, sino evaluar si los cambios en liquidez y costo del dinero
coinciden con distintos regimenes de retorno del mercado.

La pregunta guia es: **como se relacionan la tasa efectiva de fondos federales y la base monetaria de la FED
con el desempeno del S&P 500 desde el ano 2000?**
"""
)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Periodo alineado", f"{metrics['start'].year}-{metrics['end'].year}")
col2.metric("Activos S&P 500", f"{prices.shape[1]:,}")
col3.metric("Retorno S&P 500", pct(metrics["sp500_return"]))
col4.metric("Cambio base monetaria", pct(metrics["monetary_base_change"]))

st.subheader("Que demuestra este proyecto")

left, right = st.columns([1.2, 1])

with left:
    st.markdown(
        """
- Integracion de datos financieros diarios con series macroeconomicas mensuales de FRED.
- Transformacion temporal: resampling mensual, retornos 12m, variacion YoY y cambios de tasas.
- Analisis de correlacion contemporanea y con rezagos.
- Comparacion por regimenes monetarios: tasas bajas, medias, altas y expansion/contraccion de base monetaria.
- Comunicacion clara de hallazgos sin confundir correlacion con causalidad.
"""
    )

with right:
    status = data_source_status()
    all_fresh = all(s.get("fresh", False) for s in status.values())
    any_exists = any(s.get("exists", False) for s in status.values())

    if all_fresh:
        st.success(
            "✅ Datos actualizados automaticamente desde FRED y Yahoo Finance. "
            "Cache de 24 h activo."
        )
    elif any_exists:
        st.info(
            "📦 Usando datos cacheados localmente. Se actualizaran "
            "automaticamente al expirar el cache de 24 h."
        )
    else:
        st.warning(
            "⏳ Primera ejecucion: se descargaran datos de FRED y Yahoo Finance. "
            "Esto puede tardar unos minutos."
        )

st.subheader("Hipotesis de trabajo")
st.markdown(
    """
1. Cuando la base monetaria crece con fuerza, aumenta la liquidez disponible y puede acompanar multiples mas altos.
2. Cuando las tasas suben, sube el costo de oportunidad y los activos de riesgo suelen enfrentar mas presion.
3. La relacion no es mecanica: inflacion, beneficios corporativos, shocks externos y expectativas tambien importan.
4. Se puede usar la correlacion macro para construir un portfolio con menor exposicion a la politica de la FED.
"""
)
