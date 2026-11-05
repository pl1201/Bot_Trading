import pandas as pd
import numpy as np
from .moving_averages import sma, ema, wma
from .rsi import rsi
from .macd import macd
from .bollinger_bands import bollinger_bands
from .volatility import atr
from .volume import vwap
from .zscore import zscore

def add_basic_indicators(df: pd.DataFrame) -> pd.DataFrame:
    '''Add basic technical indicators'''
    df['SMA20'] = sma(df['close'], 20)
    df['EMA20'] = ema(df['close'], 20)
    df['WMA20'] = wma(df['close'], 20)

    # RSI
    df['RSI14'] = rsi(df['close'], 14)

    # MACD
    df['EMA12'] = ema(df['close'], 12)
    df['EMA26'] = ema(df['close'], 26)
    df['MACD'] = df['EMA12'] - df['EMA26']
    df['MACD_SIGNAL'] = ema(df['MACD'], 9)
    df['MACD_HIST'] = df['MACD'] - df['MACD_SIGNAL']

    # Bollinger Bands
    bb_upper, bb_mid, bb_lower = bollinger_bands(df['close'], 20, 2)
    df['BB_MID'] = bb_mid
    df['BB_UPPER'] = bb_upper
    df['BB_LOWER'] = bb_lower

    # ATR
    df['ATR14'] = atr(df, 14)

    # VWAP
    if 'volume' in df.columns:
        df['VWAP'] = vwap(df['close'], df['volume'])
    else:
        df['VWAP'] = df['close']

    # Z-Score
    df['Z20'] = zscore(df['close'], 20)

    return df

def add_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    '''Add all indicators (basic only, no ICT/Fib for now)'''
    df = add_basic_indicators(df)
    return df