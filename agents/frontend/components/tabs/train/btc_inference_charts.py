"""agents.frontend.components.tabs.train.btc_inference_charts

Purpose
-------
Build the Plotly figure used by the BTC Live Inference section.

Responsibilities
----------------
- Render the BTCUSDT candlestick chart.
- Render the LONG/SHORT ML score subplot.
- Overlay readable BUY/SELL markers derived from the `signal` column.

Inputs / Outputs
----------------
Inputs:
- df: pandas.DataFrame with columns documented in `docs/modules/BTC_INFERENCE_SCORING.md`
- colors: dict-like containing dark theme colors (see `shared/colors.py`)
- signal_colors: mapping {signal -> hex color}

Output:
- plotly.graph_objects.Figure

Dependencies
------------
- plotly
- pandas

Limitations
-----------
- Signal markers are derived from discrete `signal` values and rendered at
  `high`/`low` +/- a small offset; extremely tight ranges may reduce spacing.
"""

from __future__ import annotations

from typing import Mapping

import pandas as pd

import plotly.graph_objects as go
from plotly.subplots import make_subplots


_LONG_SIGNALS = ("BUY", "STRONG BUY")
_SHORT_SIGNALS = ("SELL", "STRONG SELL")


def build_btc_inference_figure(
    *,
    df: pd.DataFrame,
    colors: Mapping[str, str],
    signal_colors: Mapping[str, str],
) -> go.Figure:
    """Build the BTC inference figure (price + ML score subplots).

    Notes
    -----
    - Signals are rendered as marker + text traces to keep labels readable.
    - Text uses a dark background with a colored border for contrast.
    """

    _validate_df(df)

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        row_heights=[0.7, 0.3],
        subplot_titles=("BTCUSDT Price", "ML Scores (LONG / SHORT)"),
    )

    customdata = _build_customdata(df)

    fig.add_trace(
        go.Candlestick(
            x=df["timestamp"],
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name="BTCUSDT",
            increasing_line_color=colors["bullish"],
            decreasing_line_color=colors["bearish"],
            customdata=customdata,
            hovertemplate=(
                "%{x}<br>"
                "O:%{open:.2f} H:%{high:.2f} L:%{low:.2f} C:%{close:.2f}<br>"
                "LONG raw:%{customdata[0]:.6f} | LONG (0-100):%{customdata[2]:.1f}<br>"
                "SHORT raw:%{customdata[1]:.6f} | SHORT (0-100):%{customdata[3]:.1f}<br>"
                "Net:%{customdata[4]:+.1f} | Conf:%{customdata[5]:.1f}<br>"
                "Signal:%{customdata[6]}"
                "<extra></extra>"
            ),
        ),
        row=1,
        col=1,
    )

    _add_signal_marker_traces(fig=fig, df=df, colors=colors, signal_colors=signal_colors)

    fig.add_trace(
        go.Scatter(
            x=df["timestamp"],
            y=df["score_long_0_100"],
            mode="lines",
            name="LONG (0-100)",
            line=dict(color=colors["long"], width=2),
            customdata=customdata,
            hovertemplate=(
                "%{x}<br>"
                "LONG (0-100):%{y:.1f}<br>"
                "LONG raw:%{customdata[0]:.6f}<br>"
                "SHORT (0-100):%{customdata[3]:.1f}<br>"
                "Net:%{customdata[4]:+.1f} | Conf:%{customdata[5]:.1f}<br>"
                "Signal:%{customdata[6]}"
                "<extra></extra>"
            ),
        ),
        row=2,
        col=1,
    )

    fig.add_trace(
        go.Scatter(
            x=df["timestamp"],
            y=df["score_short_0_100"],
            mode="lines",
            name="SHORT (0-100)",
            line=dict(color=colors["short"], width=2),
            customdata=customdata,
            hovertemplate=(
                "%{x}<br>"
                "SHORT (0-100):%{y:.1f}<br>"
                "SHORT raw:%{customdata[1]:.6f}<br>"
                "LONG (0-100):%{customdata[2]:.1f}<br>"
                "Net:%{customdata[4]:+.1f} | Conf:%{customdata[5]:.1f}<br>"
                "Signal:%{customdata[6]}"
                "<extra></extra>"
            ),
        ),
        row=2,
        col=1,
    )

    # Threshold lines (0..100 scale)
    fig.add_hline(
        y=70,
        line_dash="dash",
        line_color=colors["success"],
        row=2,
        col=1,
        annotation_text="Strong Signal (70)",
        annotation_font_color=colors["text"],
        annotation_bgcolor=colors["card"],
    )
    fig.add_hline(
        y=50,
        line_dash="dot",
        line_color=colors["warning"],
        row=2,
        col=1,
        annotation_text="Signal (50)",
        annotation_font_color=colors["text"],
        annotation_bgcolor=colors["card"],
    )
    fig.add_hline(
        y=30,
        line_dash="dot",
        line_color=colors["muted"],
        row=2,
        col=1,
    )

    fig.update_layout(
        plot_bgcolor=colors["card"],
        paper_bgcolor=colors["background"],
        font=dict(color=colors["text"]),
        xaxis_rangeslider_visible=False,
        height=600,
        legend=dict(
            bgcolor="rgba(0,0,0,0.5)",
            orientation="h",
            y=1.02,
            x=0.5,
            xanchor="center",
        ),
        margin=dict(l=20, r=20, t=60, b=20),
    )

    fig.update_xaxes(gridcolor=colors["border"], showgrid=True)
    fig.update_yaxes(gridcolor=colors["border"], showgrid=True)
    fig.update_yaxes(range=[0, 100], row=2, col=1)
    fig.update_yaxes(zeroline=False, row=1, col=1)

    return fig


def _build_customdata(df: pd.DataFrame) -> list[tuple]:
    return list(
        zip(
            df["score_long_raw"],
            df["score_short_raw"],
            df["score_long_0_100"],
            df["score_short_0_100"],
            df["net_score_-100_100"],
            df["confidence_0_100"],
            df["signal"],
        )
    )


def _add_signal_marker_traces(
    *,
    fig: go.Figure,
    df: pd.DataFrame,
    colors: Mapping[str, str],
    signal_colors: Mapping[str, str],
) -> None:
    # Goal: make LONG/SHORT entry points clearly visible on top of the price chart.
    # We group BUY+STRONG BUY into a single LONG trace, and SELL+STRONG SELL into a
    # single SHORT trace. This keeps the legend clean and answers the UI need:
    # "where is LONG and where is SHORT".

    offset = _estimate_marker_offset(df)

    long_mask = df["signal"].astype(str).isin(_LONG_SIGNALS)
    short_mask = df["signal"].astype(str).isin(_SHORT_SIGNALS)

    _add_entry_markers(
        fig=fig,
        df=df,
        mask=long_mask,
        y_source="low",
        y_offset=-offset,
        legend_name="LONG",
        text_label="LONG",
        marker_symbol="triangle-up",
        marker_color=colors["long"],
        colors=colors,
    )
    _add_entry_markers(
        fig=fig,
        df=df,
        mask=short_mask,
        y_source="high",
        y_offset=offset,
        legend_name="SHORT",
        text_label="SHORT",
        marker_symbol="triangle-down",
        marker_color=colors["short"],
        colors=colors,
    )

    # Improve readability globally for marker labels (dark background bubble)
    fig.update_traces(
        selector=dict(mode="markers+text"),
        textfont=dict(color=colors["text"], size=12),
    )

    # Plotly doesn't support per-text background natively for scatter text.
    # We simulate it with a small annotation layer per marker would be too heavy.
    # Instead, we keep labels short (BUY/SELL) and enlarge markers.


def _estimate_marker_offset(df: pd.DataFrame) -> float:
    """Return a robust price offset used to keep markers away from candles."""

    close = pd.to_numeric(df["close"], errors="coerce")
    high = pd.to_numeric(df["high"], errors="coerce")
    low = pd.to_numeric(df["low"], errors="coerce")

    base_price = float(close.median())
    if not pd.notna(base_price) or base_price <= 0:
        base_price = float(close.dropna().iloc[-1])

    candle_range = (high - low).replace([float("inf"), float("-inf")], pd.NA)
    range_median = float(candle_range.dropna().median()) if candle_range.notna().any() else 0.0

    # Primary offset: derived from typical candle height. Fallback: percent of price.
    return max(range_median * 0.8, base_price * 0.002)


def _add_entry_markers(
    *,
    fig: go.Figure,
    df: pd.DataFrame,
    mask: pd.Series,
    y_source: str,
    y_offset: float,
    legend_name: str,
    text_label: str,
    marker_symbol: str,
    marker_color: str,
    colors: Mapping[str, str],
) -> None:
    """Add a single LONG/SHORT markers trace."""

    if not mask.any():
        return

    y = pd.to_numeric(df[y_source], errors="coerce") + float(y_offset)

    hover_cols = [
        "signal",
        "net_score_-100_100",
        "confidence_0_100",
        "score_long_0_100",
        "score_short_0_100",
    ]
    customdata = df.loc[mask, hover_cols].to_numpy()

    fig.add_trace(
        go.Scatter(
            x=df.loc[mask, "timestamp"],
            y=y.loc[mask],
            mode="markers+text",
            name=legend_name,
            text=[text_label] * int(mask.sum()),
            textposition=("top center" if marker_symbol == "triangle-up" else "bottom center"),
            cliponaxis=False,
            marker=dict(
                symbol=marker_symbol,
                size=18,
                color=marker_color,
                opacity=1.0,
                line=dict(color=colors["background"], width=2),
            ),
            textfont=dict(
                color=colors["text"],
                size=11,
                family="Arial",
            ),
            customdata=customdata,
            hovertemplate=(
                "%{x}<br>"
                "Entry:%{text}<br>"
                "Signal:%{customdata[0]}<br>"
                "Net:%{customdata[1]:+.1f} | Conf:%{customdata[2]:.1f}<br>"
                "LONG:%{customdata[3]:.1f} | SHORT:%{customdata[4]:.1f}"
                "<extra></extra>"
            ),
        ),
        row=1,
        col=1,
    )


def _validate_df(df: pd.DataFrame) -> None:
    required = {
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "score_long_raw",
        "score_short_raw",
        "score_long_0_100",
        "score_short_0_100",
        "net_score_-100_100",
        "confidence_0_100",
        "signal",
    }
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"BTC inference dataframe missing columns: {sorted(missing)}")


__all__ = ["build_btc_inference_figure"]
