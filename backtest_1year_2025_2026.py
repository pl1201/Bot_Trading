"""
Backtest 1 Year: 2025-01-01 to 2026-03-25
Using H1 Enhanced Model with Hybrid Regime Detection
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
import numpy as np
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

from algo_trading.ml.h1_enhanced_model import H1EnhancedModel

print("=" * 80)
print("BACKTEST 1 YEAR: 2025-01-01 to 2026-03-25")
print("=" * 80)

# Load data
data_path = Path(__file__).parent.parent / "data" / "okx_1h.csv"
print(f"\nLoading data from: {data_path}")

df = pd.read_csv(data_path)
df['timestamp'] = pd.to_datetime(df['timestamp'])
df.set_index('timestamp', inplace=True)
df.index = df.index.tz_localize(None)

# Filter to test period
test_start = pd.Timestamp('2025-01-01')
test_end = pd.Timestamp('2026-03-25')
test_data = df[(df.index >= test_start) & (df.index <= test_end)].copy()

print(f"Period: {test_data.index[0]} to {test_data.index[-1]}")
print(f"Total bars: {len(test_data)}")
print(f"Duration: {(test_data.index[-1] - test_data.index[0]).days} days")

# Load model
print("\nLoading H1 Enhanced Model...")
model = H1EnhancedModel()
if not model.load('h1_enhanced'):
    print("ERROR: Failed to load model!")
    sys.exit(1)

print("Model loaded successfully")
print(f"  - Hybrid mode: {model.config.get('use_hybrid_regime', False)}")
print(f"  - HMM weight: {model.config.get('hmm_weight', 0.0)}")
print(f"  - Simple weight: {model.config.get('simple_weight', 1.0)}")
print(f"  - Min trend prob: {model.config['min_trend_prob']}")
print(f"  - Min confidence: {model.config['min_confidence']}")

# Generate signals
print("\nGenerating signals...")
signals, confidences, regimes, size_mult = model.predict(test_data)

signal_counts = pd.Series(signals).value_counts().sort_index()
print(f"Signal distribution:")
print(f"  LONG (1):  {signal_counts.get(1, 0)}")
print(f"  SHORT (-1): {signal_counts.get(-1, 0)}")
print(f"  HOLD (0):  {signal_counts.get(0, 0)}")

# Backtest with detailed tracking
print("\nRunning backtest...")

holding = 8  # 8 hours
costs = 0.001  # 0.1% trading costs

trades = []
equity_curve = [1.0]
current_equity = 1.0

regime_names = ['TRENDING', 'RANGING', 'VOLATILE', 'CALM']

i = 0
while i < len(signals) - holding:
    if signals[i] == 0:
        i += 1
        continue
    
    entry_price = test_data['close'].iloc[i]
    exit_price = test_data['close'].iloc[i + holding]
    direction = signals[i]
    size = size_mult[i]
    
    # Calculate return
    price_change = (exit_price / entry_price - 1)
    ret = price_change * direction - costs
    ret *= size  # Apply position sizing
    
    # Update equity
    current_equity *= (1 + ret)
    equity_curve.append(current_equity)
    
    trades.append({
        'entry_time': test_data.index[i],
        'exit_time': test_data.index[i + holding],
        'direction': 'LONG' if direction == 1 else 'SHORT',
        'regime': regime_names[int(regimes[i])],
        'confidence': confidences[i],
        'size': size,
        'entry_price': entry_price,
        'exit_price': exit_price,
        'return_pct': ret * 100,
        'equity': current_equity
    })
    
    i += holding

if len(trades) == 0:
    print("\nNo trades generated!")
    print("Model is very selective - this is normal.")
    sys.exit(0)

# Calculate metrics
trades_df = pd.DataFrame(trades)
returns = trades_df['return_pct'].values / 100

wins = returns > 0
losses = returns < 0

win_sum = returns[wins].sum() if wins.any() else 0
loss_sum = abs(returns[losses].sum()) if losses.any() else 1e-10

# Drawdown
equity_series = pd.Series(equity_curve)
running_max = equity_series.expanding().max()
drawdown = (equity_series - running_max) / running_max
max_dd = drawdown.min()

# Print results
print("\n" + "=" * 80)
print("OVERALL PERFORMANCE")
print("=" * 80)
print(f"Total Trades:        {len(trades)}")
print(f"  - Long:            {(trades_df['direction'] == 'LONG').sum()}")
print(f"  - Short:           {(trades_df['direction'] == 'SHORT').sum()}")
print(f"\nWin Rate:            {wins.mean():.2%}")
print(f"Profit Factor:       {win_sum / loss_sum:.2f}")
print(f"\nTotal Return:        {(current_equity - 1) * 100:+.2f}%")
print(f"Final Equity:        {current_equity:.4f}x")
print(f"Avg Return/Trade:    {returns.mean() * 100:+.2f}%")
print(f"\nBest Trade:          {returns.max() * 100:+.2f}%")
print(f"Worst Trade:         {returns.min() * 100:+.2f}%")
print(f"Max Drawdown:        {max_dd * 100:.2f}%")
print(f"\nAvg Trades/Month:    {len(trades) / 15:.1f}")

# Monthly breakdown
print("\n" + "=" * 80)
print("MONTHLY BREAKDOWN")
print("=" * 80)
print(f"{'Month':<12} {'Trades':>8} {'Return %':>12} {'Win Rate':>12}")
print("-" * 80)

trades_df['month'] = pd.to_datetime(trades_df['entry_time']).dt.to_period('M')
for month in sorted(trades_df['month'].unique()):
    month_trades = trades_df[trades_df['month'] == month]
    month_return = month_trades['return_pct'].sum()
    month_wr = (month_trades['return_pct'] > 0).mean()
    print(f"{str(month):<12} {len(month_trades):>8} {month_return:>+11.2f}% {month_wr:>11.1%}")

# Regime breakdown
print("\n" + "=" * 80)
print("REGIME BREAKDOWN")
print("=" * 80)
print(f"{'Regime':<12} {'Trades':>8} {'Win Rate':>12} {'Avg Return':>14}")
print("-" * 80)

for regime in ['TRENDING', 'RANGING', 'VOLATILE', 'CALM']:
    regime_trades = trades_df[trades_df['regime'] == regime]
    if len(regime_trades) > 0:
        regime_wr = (regime_trades['return_pct'] > 0).mean()
        regime_avg = regime_trades['return_pct'].mean()
        print(f"{regime:<12} {len(regime_trades):>8} {regime_wr:>11.1%} {regime_avg:>+13.2f}%")

# Direction breakdown
print("\n" + "=" * 80)
print("DIRECTION BREAKDOWN")
print("=" * 80)
print(f"{'Direction':<12} {'Trades':>8} {'Win Rate':>12} {'Avg Return':>14}")
print("-" * 80)

for direction in ['LONG', 'SHORT']:
    dir_trades = trades_df[trades_df['direction'] == direction]
    if len(dir_trades) > 0:
        dir_wr = (dir_trades['return_pct'] > 0).mean()
        dir_avg = dir_trades['return_pct'].mean()
        print(f"{direction:<12} {len(dir_trades):>8} {dir_wr:>11.1%} {dir_avg:>+13.2f}%")

# Best trades
print("\n" + "=" * 80)
print("TOP 5 BEST TRADES")
print("=" * 80)
best_trades = trades_df.nlargest(5, 'return_pct')
for idx, trade in best_trades.iterrows():
    print(f"{trade['entry_time']} | {trade['direction']:5s} | {trade['regime']:8s} | "
          f"Conf: {trade['confidence']:.1%} | Return: {trade['return_pct']:+.2f}%")

# Worst trades
print("\n" + "=" * 80)
print("TOP 5 WORST TRADES")
print("=" * 80)
worst_trades = trades_df.nsmallest(5, 'return_pct')
for idx, trade in worst_trades.iterrows():
    print(f"{trade['entry_time']} | {trade['direction']:5s} | {trade['regime']:8s} | "
          f"Conf: {trade['confidence']:.1%} | Return: {trade['return_pct']:+.2f}%")

# Recent trades
print("\n" + "=" * 80)
print("LAST 10 TRADES")
print("=" * 80)
recent_trades = trades_df.tail(10)
for idx, trade in recent_trades.iterrows():
    print(f"{trade['entry_time']} | {trade['direction']:5s} | {trade['regime']:8s} | "
          f"Conf: {trade['confidence']:.1%} | Return: {trade['return_pct']:+.2f}% | "
          f"Equity: {trade['equity']:.4f}x")

# Save results
output_file = Path(__file__).parent / "backtest_1year_results.csv"
trades_df.to_csv(output_file, index=False)
print(f"\nResults saved to: {output_file}")

# Save summary
summary_file = Path(__file__).parent / "backtest_1year_summary.txt"
with open(summary_file, 'w') as f:
    f.write("=" * 80 + "\n")
    f.write("BACKTEST 1 YEAR: 2025-01-01 to 2026-03-25\n")
    f.write("=" * 80 + "\n\n")
    
    f.write(f"Period: {test_data.index[0]} to {test_data.index[-1]}\n")
    f.write(f"Total bars: {len(test_data)}\n")
    f.write(f"Duration: {(test_data.index[-1] - test_data.index[0]).days} days\n\n")
    
    f.write("MODEL CONFIG\n")
    f.write(f"Hybrid mode: {model.config.get('use_hybrid_regime', False)}\n")
    f.write(f"HMM weight: {model.config.get('hmm_weight', 0.0)}\n")
    f.write(f"Simple weight: {model.config.get('simple_weight', 1.0)}\n")
    f.write(f"Min trend prob: {model.config['min_trend_prob']}\n")
    f.write(f"Min confidence: {model.config['min_confidence']}\n\n")
    
    f.write("PERFORMANCE SUMMARY\n")
    f.write(f"Total Trades: {len(trades)}\n")
    f.write(f"Win Rate: {wins.mean():.2%}\n")
    f.write(f"Profit Factor: {win_sum / loss_sum:.2f}\n")
    f.write(f"Total Return: {(current_equity - 1) * 100:+.2f}%\n")
    f.write(f"Avg Return/Trade: {returns.mean() * 100:+.2f}%\n")
    f.write(f"Max Drawdown: {max_dd * 100:.2f}%\n")
    f.write(f"Avg Trades/Month: {len(trades) / 15:.1f}\n\n")
    
    f.write("DIRECTION BREAKDOWN\n")
    for direction in ['LONG', 'SHORT']:
        dir_trades = trades_df[trades_df['direction'] == direction]
        if len(dir_trades) > 0:
            dir_wr = (dir_trades['return_pct'] > 0).mean()
            dir_avg = dir_trades['return_pct'].mean()
            f.write(f"{direction}: {len(dir_trades)} trades, WR: {dir_wr:.1%}, Avg: {dir_avg:+.2f}%\n")

print(f"Summary saved to: {summary_file}")

print("\n" + "=" * 80)
print("BACKTEST COMPLETED")
print("=" * 80)
