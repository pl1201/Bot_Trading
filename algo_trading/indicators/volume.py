"""
Volume-based indicators: VWAP
"""
import numpy as np
import pandas as pd
from .utils import ensure_datetime_index


def vwap(close: pd.Series, volume: pd.Series, window: int | None = None) -> pd.Series:
    """
    Volume Weighted Average Price (simplified version)
    
    Args:
        close: Close prices
        volume: Volume data
        window: Rolling window (if None, uses cumulative)
    """
    if volume is None or volume.isna().all():
        return close
    
    tpv = close * volume
    if window is None:
        cum_tpv = tpv.cumsum()
        cum_vol = volume.cumsum().replace(0, 1)
        return cum_tpv / cum_vol
    else:
        return (tpv.rolling(window=window, min_periods=window).sum() /
                volume.rolling(window=window, min_periods=window).sum().replace(0, 1))

