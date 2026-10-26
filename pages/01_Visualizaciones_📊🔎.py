import streamlit as st

from app_utils import (
    build_macro_panel,
    calculate_macro_metrics,
    lag_figure,
    load_fed_macro,
    load_index_value,
    macro_correlation_table,
    macro_lag_table,
    macro_scatter_figure,
    macro_trends_figure,
    pct,
    rates_figure,
)


st.set_page_config(page_title="Visualizaciones | FED vs S&P 500", page_icon="📊", layout="wide")

index_value = load_index_value()
macro = load_fed_macro()
panel = build_macro_panel(index_value, macro)
metrics = calculate_macro_metrics(panel)
correlations = macro_correlation_table(panel)
lag_table = macro_lag_table(panel)

st.title("Politica monetaria y S&P 500")
st.caption("Base monetaria, tasa efectiva FED y desempeno del mercado")

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Retorno S&P 500", pct(metrics["sp500_return"]))
col2.metric("Base monetaria", pct(metrics["monetary_base_change"]))
col3.metric("Tasa FED inicial", f"{metrics['fed_funds_start']:.2f}%")
col4.metric("Tasa FED final", f"{metrics['fed_funds_end']:.2f}%")
col5.metric("Corr. S&P 500 - Base Monetaria", f"{metrics['corr_levels']:.2f}")


st.plotly_chart(macro_trends_figure(panel), use_container_width=True)
st.plotly_chart(rates_figure(panel), use_container_width=True)

st.subheader("Correlaciones principales")
st.dataframe(
    correlations.style.format({"correlacion": "{:.2f}"}),
    use_container_width=True,
)

left, right = st.columns(2)
with left:
    st.plotly_chart(
        macro_scatter_figure(
            panel,
            "monetary_base_yoy",
            "sp500_return_12m",
            "Base monetaria YoY vs retorno 12m del S&P 500",
        ),
        use_container_width=True,
    )
with right:
    st.plotly_chart(
        macro_scatter_figure(
            panel,
            "fed_funds_change_12m",
            "sp500_return_12m",
            "Cambio de tasa FED 12m vs retorno 12m del S&P 500",
        ),
        use_container_width=True,
    )

st.subheader("Analisis de rezagos")
st.plotly_chart(lag_figure(lag_table), use_container_width=True)

st.markdown(
    """
**Lectura:** este tablero mide asociaciones, no causalidad. Sirve para detectar periodos donde liquidez,
tasas y mercado se movieron juntos, y para formular hipotesis que luego podrian testearse con modelos
econometricos mas robustos.
"""
)
