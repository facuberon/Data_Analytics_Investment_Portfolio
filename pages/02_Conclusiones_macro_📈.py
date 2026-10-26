import streamlit as st

from app_utils import (
    build_macro_panel,
    calculate_macro_metrics,
    load_fed_macro,
    load_index_value,
    macro_regime_table,
    pct,
)


st.set_page_config(page_title="Conclusiones | FED vs S&P 500", page_icon="📈", layout="wide")

index_value = load_index_value()
macro = load_fed_macro()
panel = build_macro_panel(index_value, macro)
regimes = macro_regime_table(panel)
metrics = calculate_macro_metrics(panel)

st.title("Conclusiones macro")
st.caption("Como leer la relacion entre tasas, emision monetaria y S&P 500")


latest = panel.dropna(subset=["fed_funds_rate", "monetary_base", "sp500_return_12m", "monetary_base_yoy"]).iloc[-1]

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Fecha analizada", latest.name.strftime("%Y-%m"))
col2.metric("Tasa FED", f"{latest['fed_funds_rate']:.2f}%")
col3.metric("Base monetaria YoY", pct(latest["monetary_base_yoy"]))
col4.metric("S&P 500 12m", pct(latest["sp500_return_12m"]))
col5.metric("Corr. S&P 500 - Base Monetaria", f"{metrics['corr_levels']:.2f}")


st.subheader("Retorno futuro por regimen monetario")
st.dataframe(
    regimes.style.format(
        {
            "count": "{:.0f}",
            "mean": "{:.1%}",
            "median": "{:.1%}",
        }
    ),
    use_container_width=True,
)

st.subheader("Hallazgos para portfolio")
st.markdown(
    f"""
1. **La base monetaria y el S&P 500 tienden a compartir direccion en horizontes amplios.**
   La correlacion de niveles es de **{metrics['corr_levels']:.2f}**, mientras que la correlacion entre la variacion de base monetaria (YoY) y el retorno del S&P 500 (12m) es de **{metrics['corr_money_sp500']:.2f}**. La expansion de liquidez no explica todo el mercado, pero ayuda a contextualizar periodos de fuerte repricing.

2. **Las subas de tasas suelen coincidir con presion sobre valuaciones.**
   La correlacion entre el cambio en la tasa de la FED (12m) y el retorno del S&P 500 (12m) es de **{metrics['corr_rate_sp500']:.2f}**. Cuando el costo del dinero sube, el mercado reevalua crecimiento futuro, deuda corporativa y primas de riesgo.

3. **El rezago importa.**
   El impacto de la politica monetaria no aparece necesariamente en el mismo mes. Por eso la app compara relaciones
   contemporaneas y con rezagos.

4. **La conclusion correcta no es "comprar o vender", sino mejorar el marco de decision.**
   El analisis permite explicar en que regimen macro se encuentra el mercado y que riesgos conviene monitorear.
"""
)


st.warning(
    """
Este dashboard no es asesoramiento financiero. Es un caso de analisis de datos macro-financieros y sus resultados
deben interpretarse como evidencia descriptiva, no como prueba causal.
"""
)
