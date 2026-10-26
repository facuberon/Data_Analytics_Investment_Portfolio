import numpy as np
import pandas as pd
import streamlit as st

from data_fetcher import (
    ALTERNATIVE_TICKERS,
    BOND_TICKERS,
    load_alternative_assets,
    load_fed_macro,
    load_full_universe,
    load_index_value,
    load_sp500_prices,
)

TRADING_DAYS = 252


def build_macro_panel(index_value: pd.DataFrame, macro: pd.DataFrame) -> pd.DataFrame:
    sp500_monthly = index_value["Total Value"].resample("MS").last().rename("sp500_value")
    panel = pd.concat([sp500_monthly, macro], axis=1).sort_index()
    panel = panel.loc[sp500_monthly.index.min() : sp500_monthly.index.max()].ffill()
    panel["sp500_return_1m"] = panel["sp500_value"].pct_change()
    panel["sp500_return_12m"] = panel["sp500_value"].pct_change(12)
    panel["sp500_forward_return_12m"] = panel["sp500_value"].shift(-12) / panel["sp500_value"] - 1
    panel["monetary_base_yoy"] = panel["monetary_base"].pct_change(12)
    panel["fed_funds_change_12m"] = panel["fed_funds_rate"].diff(12)
    return panel.dropna(subset=["sp500_value", "fed_funds_rate", "monetary_base"])


def calculate_macro_metrics(panel: pd.DataFrame) -> dict:
    usable = panel.dropna(subset=["sp500_return_12m", "monetary_base_yoy", "fed_funds_change_12m"])
    return {
        "start": usable.index.min().date(),
        "end": usable.index.max().date(),
        "sp500_return": usable["sp500_value"].iloc[-1] / usable["sp500_value"].iloc[0] - 1,
        "monetary_base_change": usable["monetary_base"].iloc[-1] / usable["monetary_base"].iloc[0] - 1,
        "fed_funds_start": usable["fed_funds_rate"].iloc[0],
        "fed_funds_end": usable["fed_funds_rate"].iloc[-1],
        "corr_money_sp500": usable["monetary_base_yoy"].corr(usable["sp500_return_12m"]),
        "corr_rate_sp500": usable["fed_funds_change_12m"].corr(usable["sp500_return_12m"]),
        "corr_levels": usable["monetary_base"].corr(usable["sp500_value"]),
    }



def macro_correlation_table(panel: pd.DataFrame) -> pd.DataFrame:
    usable = panel.dropna(
        subset=[
            "sp500_return_12m",
            "sp500_forward_return_12m",
            "monetary_base_yoy",
            "fed_funds_rate",
            "fed_funds_change_12m",
        ]
    )
    rows = [
        ("Base monetaria (Nivel)", "S&P 500 (Nivel)", usable["monetary_base"], usable["sp500_value"]),
        ("Base monetaria YoY", "S&P 500 retorno 12m", usable["monetary_base_yoy"], usable["sp500_return_12m"]),
        ("Base monetaria YoY", "S&P 500 retorno futuro 12m", usable["monetary_base_yoy"], usable["sp500_forward_return_12m"]),
        ("Tasa FED", "S&P 500 retorno 12m", usable["fed_funds_rate"], usable["sp500_return_12m"]),
        ("Cambio tasa FED 12m", "S&P 500 retorno 12m", usable["fed_funds_change_12m"], usable["sp500_return_12m"]),
        (
            "Cambio tasa FED 12m",
            "S&P 500 retorno futuro 12m",
            usable["fed_funds_change_12m"],
            usable["sp500_forward_return_12m"],
        ),
    ]

    return pd.DataFrame(
        [
            {
                "variable_macro": macro_name,
                "variable_sp500": sp500_name,
                "correlacion": macro_series.corr(sp500_series),
            }
            for macro_name, sp500_name, macro_series, sp500_series in rows
        ]
    )


def macro_regime_table(panel: pd.DataFrame) -> pd.DataFrame:
    usable = panel.dropna(subset=["sp500_forward_return_12m", "fed_funds_rate", "monetary_base_yoy"]).copy()
    usable["regimen_tasas"] = pd.cut(
        usable["fed_funds_rate"],
        bins=[-np.inf, 2, 5, np.inf],
        labels=["Tasas bajas (<2%)", "Tasas medias (2-5%)", "Tasas altas (>5%)"],
    )
    usable["regimen_emision"] = pd.cut(
        usable["monetary_base_yoy"],
        bins=[-np.inf, 0, 0.1, np.inf],
        labels=["Contraccion monetaria", "Expansion moderada", "Expansion fuerte"],
    )
    rate_summary = usable.groupby("regimen_tasas", observed=True)["sp500_forward_return_12m"].agg(["count", "mean", "median"])
    money_summary = usable.groupby("regimen_emision", observed=True)["sp500_forward_return_12m"].agg(["count", "mean", "median"])
    rate_summary.insert(0, "tipo_regimen", "Tasa FED")
    money_summary.insert(0, "tipo_regimen", "Base monetaria")
    return pd.concat([rate_summary, money_summary]).rename_axis("regimen").reset_index()


def macro_lag_table(panel: pd.DataFrame, max_lag: int = 18) -> pd.DataFrame:
    rows = []
    for lag in range(max_lag + 1):
        rows.append(
            {
                "rezago_meses": lag,
                "base_monetaria_yoy_vs_sp500_12m": panel["monetary_base_yoy"].shift(lag).corr(panel["sp500_return_12m"]),
                "cambio_tasa_fed_12m_vs_sp500_12m": panel["fed_funds_change_12m"].shift(lag).corr(panel["sp500_return_12m"]),
            }
        )
    return pd.DataFrame(rows)


def pct(value: float, decimals: int = 1) -> str:
    if pd.isna(value) or np.isinf(value):
        return "n/a"
    return f"{value * 100:,.{decimals}f}%"


def money(value: float) -> str:
    if pd.isna(value) or np.isinf(value):
        return "n/a"
    return f"${value:,.0f}"


def calculate_asset_metrics(prices: pd.DataFrame, min_years: float = 5.0) -> pd.DataFrame:
    metrics_list = []
    prices_filled = prices.ffill()
    
    for ticker in prices_filled.columns:
        series = prices_filled[ticker].dropna()
        if len(series) < 10:
            continue
            
        years = (series.index[-1] - series.index[0]).days / 365.25
        if years < min_years:
            continue
            
        returns = series.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
        if len(returns) == 0:
            continue
            
        cumulative_return = series.iloc[-1] / series.iloc[0] - 1
        cagr = (series.iloc[-1] / series.iloc[0]) ** (1 / years) - 1
        volatility = returns.std() * np.sqrt(TRADING_DAYS)
        sharpe_proxy = cagr / volatility if volatility > 0 else np.nan
        drawdown = series / series.cummax() - 1
        max_drawdown = drawdown.min()
        
        metrics_list.append({
            "ticker": ticker,
            "retorno_total": cumulative_return,
            "cagr": cagr,
            "volatilidad": volatility,
            "max_drawdown": max_drawdown,
            "sharpe_proxy": sharpe_proxy,
            "cobertura_datos": len(series) / len(prices),
        })
        
    if not metrics_list:
        return pd.DataFrame()
        
    df = pd.DataFrame(metrics_list).set_index("ticker")
    return df.replace([np.inf, -np.inf], np.nan).dropna().sort_values("sharpe_proxy", ascending=False)



def calculate_index_metrics(index_value: pd.DataFrame) -> dict:
    series = index_value["Total Value"].dropna()
    returns = series.pct_change().dropna()
    years = (series.index[-1] - series.index[0]).days / 365.25
    cumulative_return = series.iloc[-1] / series.iloc[0] - 1
    cagr = (series.iloc[-1] / series.iloc[0]) ** (1 / years) - 1
    volatility = returns.std() * np.sqrt(TRADING_DAYS)
    max_drawdown = (series / series.cummax() - 1).min()
    return {
        "start": series.index.min().date(),
        "end": series.index.max().date(),
        "companies": None,
        "observations": len(series),
        "cumulative_return": cumulative_return,
        "cagr": cagr,
        "volatility": volatility,
        "max_drawdown": max_drawdown,
        "start_value": series.iloc[0],
        "end_value": series.iloc[-1],
    }


def build_portfolio(prices: pd.DataFrame, metrics: pd.DataFrame, size: int = 12) -> tuple[pd.Series, pd.DataFrame]:
    selected = metrics.head(size).index.tolist()
    normalized = prices[selected].ffill().dropna()
    weights = pd.Series(1 / len(selected), index=selected)
    portfolio = normalized.div(normalized.iloc[0]).mul(weights, axis=1).sum(axis=1)
    allocation = metrics.loc[selected, ["retorno_total", "cagr", "volatilidad", "max_drawdown", "sharpe_proxy"]].copy()
    allocation.insert(0, "peso", weights)
    return portfolio, allocation


def index_figure(index_value: pd.DataFrame):
    import plotly.express as px

    fig = px.line(index_value, x=index_value.index, y="Total Value", template="plotly_white")
    fig.update_layout(
        title="Valor agregado del universo S&P 500",
        xaxis_title="Fecha",
        yaxis_title="Valor total",
        hovermode="x unified",
        margin=dict(l=20, r=20, t=55, b=20),
    )
    return fig


def macro_trends_figure(panel: pd.DataFrame):
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Scatter(x=panel.index, y=panel["sp500_value"], mode="lines", name="S&P 500 agregado"),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(x=panel.index, y=panel["monetary_base"], mode="lines", name="Base monetaria FED"),
        secondary_y=True,
    )
    fig.update_layout(
        template="plotly_white",
        title="S&P 500 y base monetaria de la FED",
        hovermode="x unified",
        margin=dict(l=20, r=20, t=55, b=20),
    )
    fig.update_yaxes(title_text="Valor S&P 500", secondary_y=False)
    fig.update_yaxes(title_text="Base monetaria, miles de millones USD", secondary_y=True)
    return fig


def rates_figure(panel: pd.DataFrame):
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Scatter(x=panel.index, y=panel["sp500_return_12m"], mode="lines", name="S&P 500 retorno 12m"),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(x=panel.index, y=panel["fed_funds_rate"], mode="lines", name="Tasa efectiva FED"),
        secondary_y=True,
    )
    fig.update_layout(
        template="plotly_white",
        title="Retorno 12m del S&P 500 vs. tasa efectiva FED",
        hovermode="x unified",
        margin=dict(l=20, r=20, t=55, b=20),
    )
    fig.update_yaxes(title_text="Retorno S&P 500 12m", tickformat=".0%", secondary_y=False)
    fig.update_yaxes(title_text="Tasa FED (%)", secondary_y=True)
    return fig


def macro_scatter_figure(panel: pd.DataFrame, x_col: str, y_col: str, title: str):
    import plotly.express as px

    labels = {
        "monetary_base_yoy": "Base monetaria YoY",
        "fed_funds_change_12m": "Cambio tasa FED 12m",
        "sp500_return_12m": "S&P 500 retorno 12m",
        "sp500_forward_return_12m": "S&P 500 retorno futuro 12m",
    }
    chart = panel.dropna(subset=[x_col, y_col]).copy()
    chart["year"] = chart.index.year.astype(str)
    fig = px.scatter(
        chart,
        x=x_col,
        y=y_col,
        color="year",
        template="plotly_white",
        labels=labels,
        title=title,
    )
    if x_col != "fed_funds_change_12m":
        fig.update_xaxes(tickformat=".0%")
    fig.update_yaxes(tickformat=".0%")
    fig.update_layout(margin=dict(l=20, r=20, t=55, b=20), showlegend=False)
    return fig


def lag_figure(lag_table: pd.DataFrame):
    import plotly.graph_objects as go

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=lag_table["rezago_meses"],
            y=lag_table["base_monetaria_yoy_vs_sp500_12m"],
            mode="lines+markers",
            name="Base monetaria YoY",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=lag_table["rezago_meses"],
            y=lag_table["cambio_tasa_fed_12m_vs_sp500_12m"],
            mode="lines+markers",
            name="Cambio tasa FED 12m",
        )
    )
    fig.update_layout(
        template="plotly_white",
        title="Correlacion por rezago contra retorno 12m del S&P 500",
        xaxis_title="Rezago de variable macro (meses)",
        yaxis_title="Correlacion",
        hovermode="x unified",
        margin=dict(l=20, r=20, t=55, b=20),
    )
    return fig


def drawdown_figure(series: pd.Series, title: str):
    import plotly.express as px

    drawdown = series / series.cummax() - 1
    fig = px.area(x=drawdown.index, y=drawdown.values, template="plotly_white")
    fig.update_layout(
        title=title,
        xaxis_title="Fecha",
        yaxis_title="Drawdown",
        hovermode="x unified",
        margin=dict(l=20, r=20, t=55, b=20),
    )
    fig.update_yaxes(tickformat=".0%")
    return fig


def risk_return_figure(metrics: pd.DataFrame):
    import plotly.express as px

    chart = metrics.head(80).reset_index().rename(columns={"index": "ticker"})
    fig = px.scatter(
        chart,
        x="volatilidad",
        y="cagr",
        size="retorno_total",
        color="max_drawdown",
        hover_name="ticker",
        color_continuous_scale="RdYlGn",
        template="plotly_white",
    )
    fig.update_layout(
        title="Mapa de retorno anualizado vs. riesgo",
        xaxis_title="Volatilidad anualizada",
        yaxis_title="CAGR",
        margin=dict(l=20, r=20, t=55, b=20),
    )
    fig.update_xaxes(tickformat=".0%")
    fig.update_yaxes(tickformat=".0%")
    return fig


def portfolio_comparison_figure(index_value: pd.DataFrame, portfolio: pd.Series):
    import plotly.graph_objects as go

    benchmark = index_value["Total Value"].dropna()
    comparison = pd.concat(
        [
            benchmark.rename("Benchmark S&P 500"),
            portfolio.rename("Cartera recomendada"),
        ],
        axis=1,
    ).dropna()
    
    # Re-normalizar para que ambos inicien en 1.0 en la primera fecha comun
    if not comparison.empty:
        comparison = comparison.div(comparison.iloc[0])
        
    fig = go.Figure()
    for column in comparison.columns:
        fig.add_trace(go.Scatter(x=comparison.index, y=comparison[column], mode="lines", name=column))
    fig.update_layout(
        template="plotly_white",
        title="Crecimiento de USD 1 invertido",
        xaxis_title="Fecha",
        yaxis_title="Valor normalizado",
        hovermode="x unified",
        margin=dict(l=20, r=20, t=55, b=20),
    )
    return fig



def table_for_display(metrics: pd.DataFrame) -> pd.DataFrame:
    display = metrics.copy()
    for column in ["retorno_total", "cagr", "volatilidad", "max_drawdown", "sharpe_proxy", "cobertura_datos"]:
        display[column] = display[column].astype(float)
    return display


# ── Portfolio anti-correlacion FED ──────────────────────────────────────


def calculate_macro_exposure(
    prices: pd.DataFrame, panel: pd.DataFrame, min_overlap: int = 24
) -> pd.DataFrame:
    """
    Para cada activo, calcula la correlacion de su retorno 12m con las
    variables de politica monetaria (tasa FED y base monetaria).
    Devuelve un score de 'exposicion macro' = promedio |correlaciones|.
    """
    # Precios mensuales y retornos 12m
    monthly = prices.resample("MS").last()
    returns_12m = monthly.pct_change(12)

    macro_vars = panel[["fed_funds_change_12m", "monetary_base_yoy"]].dropna()

    results = []
    for ticker in returns_12m.columns:
        asset_ret = returns_12m[ticker].dropna()
        common = asset_ret.index.intersection(macro_vars.index)
        if len(common) < min_overlap:
            continue

        r = asset_ret.loc[common]
        m = macro_vars.loc[common]

        corr_rate = r.corr(m["fed_funds_change_12m"])
        corr_money = r.corr(m["monetary_base_yoy"])

        if pd.isna(corr_rate) or pd.isna(corr_money):
            continue

        # Categoria del activo
        if ticker in ALTERNATIVE_TICKERS:
            categoria = ALTERNATIVE_TICKERS[ticker]
        else:
            categoria = "Accion S&P 500"

        results.append(
            {
                "ticker": ticker,
                "categoria": categoria,
                "corr_tasa_fed": corr_rate,
                "corr_base_monetaria": corr_money,
                "exposicion_macro": (abs(corr_rate) + abs(corr_money)) / 2,
            }
        )

    return (
        pd.DataFrame(results)
        .set_index("ticker")
        .sort_values("exposicion_macro")
    )


def build_anti_fed_portfolio(
    prices: pd.DataFrame,
    panel: pd.DataFrame,
    metrics: pd.DataFrame,
    size: int = 12,
) -> tuple[pd.Series, pd.DataFrame]:
    """
    Construye un portfolio de activos con menor correlacion a la
    politica monetaria de la FED. Excluye bonos gubernamentales.
    Requiere Sharpe positivo.
    """
    exposure = calculate_macro_exposure(prices, panel)

    # Combinar con metricas de riesgo-retorno
    combined = exposure.join(metrics, how="inner")

    # Excluir bonos gubernamentales
    combined = combined[~combined.index.isin(BOND_TICKERS)]

    # Filtrar: Sharpe positivo
    combined = combined[combined["sharpe_proxy"] > 0]

    if combined.empty:
        return pd.Series(dtype=float), pd.DataFrame()

    # Seleccion balanceada por categorias
    # 1. Crypto (Bitcoin y Ethereum)
    cryptos = combined[combined["categoria"].isin(["Bitcoin", "Ethereum"])]

    # 2. Commodities (maximo 4, evitando duplicar el mismo subyacente)
    underlying_map = {
        "GC=F": "Oro", "GLD": "Oro",
        "SI=F": "Plata", "SLV": "Plata",
        "CL=F": "Petroleo", "USO": "Petroleo",
        "HG=F": "Cobre",
        "NG=F": "Gas Natural",
        "DBA": "Agricultura",
        "DBC": "Diversificado",
    }
    commodities = combined[combined["categoria"].str.contains("Oro|Plata|Petroleo|Cobre|Gas|Agricultura|Commodities", case=False, na=False)].copy()
    commodities["underlying"] = commodities.index.map(underlying_map)
    selected_comm = commodities.sort_values("exposicion_macro").drop_duplicates(subset=["underlying"]).head(4)

    # 3. Acciones del S&P 500 para completar el tamaño
    num_stocks = max(0, size - len(cryptos) - len(selected_comm))
    stocks = combined[combined["categoria"] == "Accion S&P 500"]
    selected_stocks = stocks.sort_values("exposicion_macro").head(num_stocks)

    # Combinar selecciones
    selected = pd.concat([cryptos, selected_comm, selected_stocks])

    # Si por alguna razon no se alcanzo el tamaño deseado, rellenar con lo que quede
    if len(selected) < size and len(selected) < len(combined):
        remaining = combined[~combined.index.isin(selected.index)]
        fill_size = size - len(selected)
        selected = pd.concat([selected, remaining.sort_values("exposicion_macro").head(fill_size)])

    tickers = selected.index.tolist()
    if not tickers:
        return pd.Series(dtype=float), pd.DataFrame()

    normalized = prices[tickers].ffill().dropna()
    weights = pd.Series(1 / len(tickers), index=tickers)
    portfolio = normalized.div(normalized.iloc[0]).mul(weights, axis=1).sum(axis=1)

    allocation = selected[
        [
            "categoria",
            "exposicion_macro",
            "corr_tasa_fed",
            "corr_base_monetaria",
            "retorno_total",
            "cagr",
            "volatilidad",
            "max_drawdown",
            "sharpe_proxy",
        ]
    ].copy()
    allocation.insert(0, "peso", weights)

    return portfolio, allocation



def macro_exposure_figure(exposure: pd.DataFrame, top_n: int = 60):
    """Scatter de exposicion macro vs CAGR, coloreado por categoria."""
    import plotly.express as px

    chart = exposure.head(top_n).reset_index()
    # Plotly Express requiere que la columna usada para 'size' sea estrictamente positiva
    chart["sharpe_size"] = chart["sharpe_proxy"].clip(lower=0.01)
    
    fig = px.scatter(
        chart,
        x="exposicion_macro",
        y="cagr",
        color="categoria",
        size="sharpe_size",
        hover_name="ticker",
        hover_data={"sharpe_proxy": True, "sharpe_size": False},
        template="plotly_white",
        labels={
            "exposicion_macro": "Exposicion a politica FED",
            "cagr": "CAGR",
            "categoria": "Tipo de activo",
            "sharpe_proxy": "Sharpe",
        },
    )
    fig.update_layout(
        title="Retorno vs exposicion a politica monetaria FED",
        xaxis_title="Exposicion macro (menor = menos correlacion con FED)",
        yaxis_title="CAGR",
        margin=dict(l=20, r=20, t=55, b=20),
    )
    fig.update_yaxes(tickformat=".0%")
    fig.update_xaxes(tickformat=".2f")
    return fig

