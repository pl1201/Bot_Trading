"""
Bollinger Bands
"""
import pandas as pd
from .moving_averages import sma


def bollinger_bands(series: pd.Series, window: int = 20, k: float = 2.0):
    """
    Bollinger Bands

    Returns:
        upper_band, middle_band, lower_band
    """
    ma = sma(series, window)
    std = series.rolling(window=window, min_periods=window).std(ddof=0)
    upper = ma + k * std
    lower = ma - k * std
    return upper, ma, lower
