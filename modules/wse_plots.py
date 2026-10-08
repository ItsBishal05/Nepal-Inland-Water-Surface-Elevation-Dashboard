import plotly.graph_objects as go
import numpy as np
import pandas as pd
import math
import re
from modules.stats_utils import compute_trend, flag_outliers_iqr


def clean_station_name(name):
    """Clean station name by removing WSE-related suffixes and normalizing spaces."""
    if pd.isna(name) or name is None:
        return "Unknown Station"
    name = str(name).strip()
    suffixes = [
        r"\s*WSE\s+Temporal\s+Analysis\s+data",
        r"\s*WSE\s+data",
        r"_WSE_Temporal_Analysis_data",
        r"\.csv$"
    ]
    for suffix in suffixes:
        name = re.sub(suffix + r"\s*$", "", name, flags=re.IGNORECASE)
    name = name.replace("_", " ")
    return " ".join(name.split())


def create_wse_time_series_plot(feature_data, feature_name, feature_type=None):
    """
    Create interactive WSE time series plot with quality-based coloring.

    feature_data : DataFrame with columns 'Date', 'WSE', 'quality_label'
    feature_name : display name (lake name or river name)
    feature_type : optional, 'lake' or 'river' — only affects the plot title
    """
    if feature_data.empty:
        return None

    feature_data = feature_data.sort_values('Date').copy()
    display_name = clean_station_name(feature_name)

    # Flag outliers via IQR
    feature_data["is_outlier_wse"] = flag_outliers_iqr(feature_data, "WSE")

    # Split into outliers vs non-outliers
    wse_non = feature_data[feature_data["is_outlier_wse"] == False]
    wse_out = feature_data[feature_data["is_outlier_wse"] == True]

    # Within non-outliers, split by quality
    wse_good    = wse_non[wse_non["quality_label"] == "Good"]
    wse_suspect = wse_non[wse_non["quality_label"] == "Suspect"]

    # Fit trend on all non-outlier data (Good + Suspect)
    trend_wse = None
    if len(wse_non) >= 2:
        trend_wse = compute_trend(wse_non["Date"], wse_non["WSE"])

    fig = go.Figure()

    # --- Continuous line through ALL non-outlier points (Good + Suspect) ---
    fig.add_trace(go.Scatter(
        x=wse_non["Date"],
        y=wse_non["WSE"],
        mode='lines',
        name='WSE (all non-outliers)',
        line=dict(color='#1a5276', width=2),
        hoverinfo='skip',
        showlegend=False
    ))

    # --- Good non-outliers (blue markers only) ---
    fig.add_trace(go.Scatter(
        x=wse_good["Date"],
        y=wse_good["WSE"],
        mode='markers',
        name='Good (quality 0)',
        marker=dict(color='#1a5276', size=7, line=dict(width=1, color='white')),
        hovertemplate='<b>Date</b>: %{x|%Y-%m-%d}<br><b>WSE</b>: %{y:.2f} m<br><b>Quality</b>: Good<extra></extra>'
    ))

    # --- Suspect non-outliers (orange markers only) ---
    if not wse_suspect.empty:
        fig.add_trace(go.Scatter(
            x=wse_suspect["Date"],
            y=wse_suspect["WSE"],
            mode='markers',
            name='Suspect (quality 1)',
            marker=dict(color='#e67e22', size=7, line=dict(width=1, color='white')),
            hovertemplate='<b>Date</b>: %{x|%Y-%m-%d}<br><b>WSE</b>: %{y:.2f} m<br><b>Quality</b>: Suspect<extra></extra>'
        ))

    # --- Outliers (red ✕) ---
    if not wse_out.empty:
        fig.add_trace(go.Scatter(
            x=wse_out["Date"],
            y=wse_out["WSE"],
            mode='markers',
            name='Outliers',
            marker=dict(color='red', size=8, symbol='x', line=dict(width=1, color='white')),
            hovertemplate='<b>Date</b>: %{x|%Y-%m-%d}<br><b>WSE</b>: %{y:.2f} m<br><b>Outlier</b><extra></extra>'
        ))

    # Dashed connections between outliers and neighboring non-outliers
    add_outlier_connections(fig, feature_data)

    # Trend line
    if trend_wse:
        add_trend_line(fig, wse_non, trend_wse)

    # Configure layout (title, axes, legend)
    configure_plot_layout(fig, feature_data, display_name, wse_non, feature_type)

    return fig, wse_non, trend_wse


def add_outlier_connections(fig, feature_data):
    """Add dashed lines connecting outliers"""
    df_sorted = feature_data.sort_values("Date")
    is_non_outlier = ~df_sorted["is_outlier_wse"]
    non_outlier_indices = np.where(is_non_outlier)[0]

    if len(non_outlier_indices) >= 2:
        for i in range(len(non_outlier_indices) - 1):
            start_idx = non_outlier_indices[i]
            end_idx = non_outlier_indices[i + 1]
            segment = df_sorted.iloc[start_idx:end_idx + 1]
            outlier_segment = segment[segment["is_outlier_wse"]]

            if not outlier_segment.empty:
                # Connect first non-outlier to first outlier
                first_non_outlier = segment.iloc[0]
                first_outlier = outlier_segment.iloc[0]
                fig.add_trace(go.Scatter(
                    x=[first_non_outlier["Date"], first_outlier["Date"]],
                    y=[first_non_outlier["WSE"], first_outlier["WSE"]],
                    mode='lines',
                    line=dict(color='red', width=1, dash='dash'),
                    showlegend=False,
                    hoverinfo='skip',
                    name=''
                ))

                # Connect consecutive outliers
                for j in range(len(outlier_segment) - 1):
                    curr = outlier_segment.iloc[j]
                    next_ = outlier_segment.iloc[j + 1]
                    fig.add_trace(go.Scatter(
                        x=[curr["Date"], next_["Date"]],
                        y=[curr["WSE"], next_["WSE"]],
                        mode='lines',
                        line=dict(color='red', width=1, dash='dash'),
                        showlegend=False,
                        hoverinfo='skip',
                        name=''
                    ))

                # Connect last outlier to next non-outlier
                last_outlier = outlier_segment.iloc[-1]
                second_non_outlier = segment.iloc[-1]
                fig.add_trace(go.Scatter(
                    x=[last_outlier["Date"], second_non_outlier["Date"]],
                    y=[last_outlier["WSE"], second_non_outlier["WSE"]],
                    mode='lines',
                    line=dict(color='red', width=1, dash='dash'),
                    showlegend=False,
                    hoverinfo='skip',
                    name=''
                ))


def add_trend_line(fig, wse_non, trend_wse):
    """Add trend line to the plot"""
    x_vals = wse_non["Date"]
    x_num = np.array([d.toordinal() for d in x_vals])
    y_fit = trend_wse.intercept + trend_wse.slope * x_num

    fig.add_trace(go.Scatter(
        x=x_vals,
        y=y_fit,
        mode='lines',
        name='Trend',
        line=dict(color='navy', width=2, dash='dash'),
        hovertemplate='<b>Trend</b>: %{y:.2f} m<extra></extra>'
    ))


def configure_plot_layout(fig, feature_data, feature_name, wse_non, feature_type=None):
    """Configure the plot layout and axes"""
    # Calculate y-axis range
    y_min = feature_data["WSE"].min()
    y_max = feature_data["WSE"].max()
    bottom_buffer = 0.10
    top_buffer = 0.03
    y_min_pad = y_min - bottom_buffer
    y_max_pad = y_max + top_buffer

    # Dynamic y-ticks
    y_range = y_max - y_min
    base_interval = y_range / 4
    adjusted_interval = math.floor(base_interval * 2) / 2
    major_interval = max(math.floor(adjusted_interval) + 0.5 if adjusted_interval % 1 != 0 else adjusted_interval, 0.5)
    y_min_round = math.floor(y_min_pad / major_interval) * major_interval
    y_max_round = math.ceil(y_max_pad / major_interval) * major_interval
    major_ticks = np.arange(y_min_round, y_max_round + major_interval, major_interval)
    if len(major_ticks) > 6:
        major_ticks = np.linspace(y_min_round, y_max_round, 6, endpoint=True)

    # Generate monthly x-axis ticks
    date_min = feature_data["Date"].min()
    date_max = feature_data["Date"].max()
    start_date = date_min.replace(day=1)
    end_date = (date_max + pd.offsets.MonthEnd(0)).replace(day=1) + pd.offsets.MonthBegin(1)
    monthly_ticks = pd.date_range(start=start_date, end=end_date, freq='MS')

    # Title — vary by feature type if provided
    if feature_type == 'lake':
        title_text = f"Temporal Analysis (Lake): {feature_name}"
    elif feature_type == 'river':
        title_text = f"Temporal Analysis (River Node): {feature_name}"
    else:
        title_text = f"Temporal Analysis: {feature_name}"

    fig.update_layout(
        title=dict(
            text=title_text,
            font=dict(size=16, color='#2d3748', family='Arial Black, sans-serif'),
            x=0.5,
            xanchor='center',
            pad=dict(t=20)
        ),
        xaxis_title=dict(
            text="Date",
            font=dict(size=14, color='#2d3748', family='Arial Black, sans-serif')
        ),
        yaxis_title=dict(
            text="Water Surface Elevation (m)",
            font=dict(size=14, color='blue', family='Arial Black, sans-serif')
        ),
        xaxis=dict(
            tickmode='array',
            tickvals=monthly_ticks,
            ticktext=[tick.strftime('%Y-%m') for tick in monthly_ticks],
            tickfont=dict(size=10, color='#2d3748', family='Arial, sans-serif'),
            tickangle=45,
            gridcolor='rgba(0,0,0,0.7)',
            gridwidth=1.2,
            zeroline=True,
            zerolinecolor='black',
            zerolinewidth=1
        ),
        yaxis=dict(
            tickfont=dict(size=10, color='blue', family='Arial, sans-serif'),
            range=[y_min_round, y_max_round],
            tickvals=[y_min_round] + major_ticks.tolist() + [y_max_round],
            ticktext=[f"{y_min_round:.2f}"] + [f"{tick:.2f}" for tick in major_ticks] + [f"{y_max_round:.2f}"],
            showgrid=True,
            gridcolor='rgba(200,200,200,0.5)',
            gridwidth=1.0,
            zeroline=True,
            zerolinecolor='black',
            zerolinewidth=1.2
        ),
        hovermode="x unified",
        hoverdistance=5,
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.35,
            xanchor="center",
            x=0.5,
            font=dict(size=11, family='Arial, sans-serif')
        ),
        height=500,
        template="plotly_white",
        margin=dict(l=50, r=50, t=80, b=80)
    )

    # Add reference lines
    mean_wse = wse_non["WSE"].mean()
    fig.add_hline(y=mean_wse, line_dash="dash", line_color="lightgray", line_width=1,
                  annotation_text="Mean", annotation_position="top right")
    fig.add_hline(y=y_min_round, line_dash="solid", line_color="black", line_width=2, layer="below")
    fig.add_hline(y=y_max_round, line_dash="solid", line_color="lightgray", line_width=1, layer="below")

    # Add vertical tick marks
    unique_dates = sorted(feature_data["Date"].unique())
    tick_height = (y_max_round - y_min_round) * 0.01

    for date in unique_dates:
        fig.add_shape(
            type="line",
            x0=date, y0=y_min_round,
            x1=date, y1=y_min_round + tick_height,
            line=dict(color="black", width=1),
            layer="below"
        )