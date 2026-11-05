"""
Backtest Bot Trading - 6 tháng (June 2025 - April 2026)
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any
import warnings
warnings.filterwarnings('ignore')

from algo_trading.ml import H1EnhancedModel
from okx_client_simple import OKXClient
import os
from dotenv import load_dotenv

load_dotenv()


class BacktestEngine:
    """Backtest engine với TP/SL và risk management"""
    
    def __init__(self, initial_capital: float = 10000):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.position = None  # 'LONG', 'SHORT', None
        self.entry_price = None
        self.position_size = 0
        self.trades = []
        self.equity_curve = [initial_capital]
        
        # Config (giống trading_bot_complete.py)
        self.risk_per_trade = 0.02  # 2%
        self.sl_pct = 0.015  # 1.5%
        self.tp_pct = 0.03   # 3%
        self.max_position_size = 10  # contracts
        self.fee_pct = 0.0004  # 0.04% taker fee
    
    def calculate_position_size(self, current_price: float) -> int:
        """Tính position size (contracts)"""
        risk_amount = self.capital * self.risk_per_trade
        sl_distance = current_price * self.sl_pct
        
        if sl_distance > 0:
            qty_btc = risk_amount / sl_distance
        else:
            qty_btc = risk_amount / current_price
        
        contracts = int(qty_btc / 0.01)  # 1 contract = 0.01 BTC
        contracts = min(contracts, self.max_position_size)
        return max(contracts, 1)
    
    def enter_position(self, direction: str, price: float, timestamp: pd.Timestamp):
        """Vào position"""
        if self.position:
            return
        
        contracts = self.calculate_position_size(price)
        notional = contracts * 0.01 * price
        fee = notional * self.fee_pct
        
        self.position = direction
        self.entry_price = price
        self.position_size = contracts
        self.capital -= fee  # Trừ fee
        
        # Calculate SL/TP
        if direction == 'LONG':
            self.sl_price = price * (1 - self.sl_pct)
            self.tp_price = price * (1 + self.tp_pct)
        else:
            self.sl_price = price * (1 + self.sl_pct)
            self.tp_price = price * (1 - self.tp_pct)
    
    def check_exit(self, current_price: float, timestamp: pd.Timestamp) -> tuple:
        """Kiểm tra SL/TP"""
        if not self.position:
            return False, None
        
        if self.position == 'LONG':
            if current_price <= self.sl_price:
                return True, 'SL'
            if current_price >= self.tp_price:
                return True, 'TP'
        else:
            if current_price >= self.sl_price:
                return True, 'SL'
            if current_price <= self.tp_price:
                return True, 'TP'
        
        return False, None
    
    def exit_position(self, price: float, timestamp: pd.Timestamp, reason: str = 'signal'):
        """Thoát position"""
        if not self.position:
            return
        
        notional = self.position_size * 0.01 * price
        fee = notional * self.fee_pct
        
        # Calculate P&L
        if self.position == 'LONG':
            pnl = (price - self.entry_price) * self.position_size * 0.01
        else:
            pnl = (self.entry_price - price) * self.position_size * 0.01
        
        pnl -= fee  # Trừ fee
        self.capital += pnl
        
        # Record trade
        self.trades.append({
            'entry_time': self.entry_time,
            'exit_time': timestamp,
            'direction': self.position,
            'entry_price': self.entry_price,
            'exit_price': price,
            'size': self.position_size,
            'pnl': pnl,
            'pnl_pct': (pnl / (self.entry_price * self.position_size * 0.01)) * 100,
            'reason': reason
        })
        
        # Reset
        self.position = None
        self.entry_price = None
        self.position_size = 0
        self.entry_time = None
    
    def update_equity(self, current_price: float):
        """Update equity curve"""
        equity = self.capital
        
        # Add unrealized P&L
        if self.position:
            if self.position == 'LONG':
                unrealized = (current_price - self.entry_price) * self.position_size * 0.01
            else:
                unrealized = (self.entry_price - current_price) * self.position_size * 0.01
            equity += unrealized
        
        self.equity_curve.append(equity)
    
    def run(self, df: pd.DataFrame, signals: np.ndarray, confidences: np.ndarray):
        """Chạy backtest"""
        print("Running backtest...")
        
        for i in range(len(df)):
            timestamp = df.index[i]
            current_price = df['close'].iloc[i]
            signal = signals[i]
            
            # Check SL/TP nếu đang có position
            if self.position:
                should_exit, reason = self.check_exit(current_price, timestamp)
                if should_exit:
                    self.exit_position(current_price, timestamp, reason)
            
            # Check signal
            if signal == 1 and not self.position:
                # Enter LONG
                self.enter_position('LONG', current_price, timestamp)
                self.entry_time = timestamp
            
            elif signal == -1 and not self.position:
                # Enter SHORT
                self.enter_position('SHORT', current_price, timestamp)
                self.entry_time = timestamp
            
            elif signal == 0 and self.position:
                # Exit
                self.exit_position(current_price, timestamp, 'signal')
            
            elif signal == 1 and self.position == 'SHORT':
                # Reverse
                self.exit_position(current_price, timestamp, 'reverse')
                self.enter_position('LONG', current_price, timestamp)
                self.entry_time = timestamp
            
            elif signal == -1 and self.position == 'LONG':
                # Reverse
                self.exit_position(current_price, timestamp, 'reverse')
                self.enter_position('SHORT', current_price, timestamp)
                self.entry_time = timestamp
            
            # Update equity
            self.update_equity(current_price)
        
        # Close any open position
        if self.position:
            self.exit_position(df['close'].iloc[-1], df.index[-1], 'end')
    
    def get_metrics(self) -> Dict[str, Any]:
        """Tính metrics"""
        if len(self.trades) == 0:
            return {'error': 'No trades'}
        
        trades_df = pd.DataFrame(self.trades)
        
        # Basic metrics
        total_trades = len(trades_df)
        wins = trades_df[trades_df['pnl'] > 0]
        losses = trades_df[trades_df['pnl'] <= 0]
        
        win_rate = len(wins) / total_trades if total_trades > 0 else 0
        
        avg_win = wins['pnl'].mean() if len(wins) > 0 else 0
        avg_loss = losses['pnl'].mean() if len(losses) > 0 else 0
        
        total_pnl = trades_df['pnl'].sum()
        total_return_pct = (self.capital / self.initial_capital - 1) * 100
        
        # Profit factor
        gross_profit = wins['pnl'].sum() if len(wins) > 0 else 0
        gross_loss = abs(losses['pnl'].sum()) if len(losses) > 0 else 1e-10
        profit_factor = gross_profit / gross_loss
        
        # Drawdown
        equity_series = pd.Series(self.equity_curve)
        running_max = equity_series.expanding().max()
        drawdown = (equity_series - running_max) / running_max
        max_drawdown = drawdown.min() * 100
        
        # Sharpe (simplified)
        returns = equity_series.pct_change().dropna()
        sharpe = returns.mean() / returns.std() * np.sqrt(252 * 24) if returns.std() > 0 else 0
        
        # By direction
        long_trades = trades_df[trades_df['direction'] == 'LONG']
        short_trades = trades_df[trades_df['direction'] == 'SHORT']
        
        # By exit reason
        sl_trades = trades_df[trades_df['reason'] == 'SL']
        tp_trades = trades_df[trades_df['reason'] == 'TP']
        
        return {
            'initial_capital': self.initial_capital,
            'final_capital': self.capital,
            'total_return': total_return_pct,
            'total_pnl': total_pnl,
            'total_trades': total_trades,
            'win_rate': win_rate * 100,
            'profit_factor': profit_factor,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe,
            'long_trades': len(long_trades),
            'long_win_rate': (len(long_trades[long_trades['pnl'] > 0]) / len(long_trades) * 100) if len(long_trades) > 0 else 0,
            'short_trades': len(short_trades),
            'short_win_rate': (len(short_trades[short_trades['pnl'] > 0]) / len(short_trades) * 100) if len(short_trades) > 0 else 0,
            'sl_count': len(sl_trades),
            'tp_count': len(tp_trades),
            'trades_detail': trades_df.to_dict('records')
        }


def main():
    print("=" * 70)
    print("BACKTEST BOT TRADING - 6 THÁNG (June 2025 - April 2026)")
    print("=" * 70)
    
    # Load model
    print("\n1. Loading H1 Enhanced Model...")
    import sklearn
    sklearn.set_config(assume_finite=True)
    
    model = H1EnhancedModel()
    
    # Try to load with allow_pickle
    try:
        import joblib
        model_dir = Path(__file__).parent / 'algo_trading' / 'ml' / 'models'
        
        # Load with allow_pickle=True
        model.trend_model = joblib.load(model_dir / 'h1_enhanced_model.pkl')
        model.scaler = joblib.load(model_dir / 'h1_enhanced_scaler.pkl')
        config_data = joblib.load(model_dir / 'h1_enhanced_config.pkl')
        model.feature_names = config_data.get('feature_names')
        model.config.update(config_data.get('config', {}))
        model.is_fitted = True
        print("✅ Model loaded")
    except Exception as e:
        print(f"❌ Error loading model: {e}")
        print("⚠️ Will train a simple model on the data...")
        model = None
    
    # Fetch data
    print("\n2. Fetching historical data from OKX...")
    okx = OKXClient(
        api_key=os.getenv('OKX_API_KEY'),
        api_secret=os.getenv('OKX_API_SECRET'),
        passphrase=os.getenv('OKX_PASSPHRASE'),
        demo_mode=True
    )
    
    # Fetch 6 months of H1 data (June 2025 - April 2026)
    # Approximately 6 * 30 * 24 = 4320 hours
    # OKX limit is 1440 per request, so we need multiple requests
    
    end_date = datetime(2026, 4, 16)  # Today
    start_date = datetime(2025, 6, 1)
    
    print(f"   Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    
    # Fetch in chunks
    all_data = []
    current_end = end_date
    
    while current_end > start_date:
        print(f"   Fetching data until {current_end.strftime('%Y-%m-%d')}...")
        df_chunk = okx.fetch_ohlcv('BTC-USDT', '1H', limit=1440)
        
        if df_chunk.empty:
            print("   ⚠️ No more data")
            break
        
        all_data.append(df_chunk)
        
        # Move to earlier period
        earliest_time = df_chunk.index[0]
        current_end = earliest_time - timedelta(hours=1)
        
        if len(all_data) >= 4:  # Enough data (~6 months)
            break
    
    # Combine all chunks
    df = pd.concat(all_data[::-1])  # Reverse to chronological order
    df = df[~df.index.duplicated(keep='last')]  # Remove duplicates
    df = df.sort_index()
    
    # Filter to exact date range
    df = df[(df.index >= start_date) & (df.index <= end_date)]
    
    print(f"✅ Fetched {len(df)} bars")
    print(f"   From: {df.index[0]}")
    print(f"   To: {df.index[-1]}")
    
    # Generate signals
    print("\n3. Generating signals...")
    
    if model is None:
        # Train simple model on the data
        print("   Training model on historical data...")
        model = H1EnhancedModel()
        
        # Use first 70% for training
        train_size = int(len(df) * 0.7)
        df_train = df.iloc[:train_size]
        
        try:
            train_metrics = model.train(df_train)
            print(f"   ✅ Model trained: {train_metrics}")
        except Exception as e:
            print(f"   ❌ Training failed: {e}")
            print("   Using simple momentum strategy instead...")
            # Fallback to simple strategy
            signals = np.zeros(len(df))
            mom = df['close'].pct_change(4)
            signals[mom > 0.01] = 1
            signals[mom < -0.01] = -1
            confidences = np.abs(mom)
            regimes = np.zeros(len(df))
            size_mult = np.ones(len(df))
    
    if model is not None:
        signals, confidences, regimes, size_mult = model.predict(df)
    else:
        # Already set above
        pass
    
    signal_counts = pd.Series(signals).value_counts().sort_index()
    print(f"   Signals: {dict(signal_counts)}")
    print(f"   (1=LONG, -1=SHORT, 0=HOLD)")
    
    # Run backtest
    print("\n4. Running backtest...")
    engine = BacktestEngine(initial_capital=10000)
    engine.run(df, signals, confidences)
    
    # Get metrics
    print("\n5. Results:")
    print("=" * 70)
    
    metrics = engine.get_metrics()
    
    if 'error' in metrics:
        print(f"❌ {metrics['error']}")
        return
    
    print(f"\n📊 PERFORMANCE SUMMARY")
    print(f"   Initial Capital:  ${metrics['initial_capital']:,.2f}")
    print(f"   Final Capital:    ${metrics['final_capital']:,.2f}")
    print(f"   Total Return:     {metrics['total_return']:+.2f}%")
    print(f"   Total P&L:        ${metrics['total_pnl']:+,.2f}")
    
    print(f"\n📈 TRADING STATISTICS")
    print(f"   Total Trades:     {metrics['total_trades']}")
    print(f"   Win Rate:         {metrics['win_rate']:.2f}%")
    print(f"   Profit Factor:    {metrics['profit_factor']:.2f}")
    print(f"   Avg Win:          ${metrics['avg_win']:,.2f}")
    print(f"   Avg Loss:         ${metrics['avg_loss']:,.2f}")
    print(f"   Max Drawdown:     {metrics['max_drawdown']:.2f}%")
    print(f"   Sharpe Ratio:     {metrics['sharpe_ratio']:.2f}")
    
    print(f"\n🎯 BY DIRECTION")
    print(f"   Long Trades:      {metrics['long_trades']} (WR: {metrics['long_win_rate']:.1f}%)")
    print(f"   Short Trades:     {metrics['short_trades']} (WR: {metrics['short_win_rate']:.1f}%)")
    
    print(f"\n🚪 EXIT REASONS")
    print(f"   Stop Loss:        {metrics['sl_count']}")
    print(f"   Take Profit:      {metrics['tp_count']}")
    print(f"   Signal/Other:     {metrics['total_trades'] - metrics['sl_count'] - metrics['tp_count']}")
    
    # Show first 10 trades
    print(f"\n📋 FIRST 10 TRADES:")
    print("-" * 70)
    for i, trade in enumerate(metrics['trades_detail'][:10], 1):
        print(f"{i}. {trade['entry_time'].strftime('%Y-%m-%d %H:%M')} | "
              f"{trade['direction']:5s} | "
              f"Entry: ${trade['entry_price']:,.0f} | "
              f"Exit: ${trade['exit_price']:,.0f} | "
              f"P&L: {trade['pnl_pct']:+.2f}% | "
              f"{trade['reason']}")
    
    print("\n" + "=" * 70)
    print("✅ Backtest completed!")
    
    # Save results
    results_file = 'backtest_results_6months.txt'
    with open(results_file, 'w', encoding='utf-8') as f:
        f.write("=" * 70 + "\n")
        f.write("BACKTEST RESULTS - 6 MONTHS (June 2025 - April 2026)\n")
        f.write("=" * 70 + "\n\n")
        
        f.write(f"Period: {df.index[0]} to {df.index[-1]}\n")
        f.write(f"Total Bars: {len(df)}\n\n")
        
        f.write("PERFORMANCE SUMMARY\n")
        f.write(f"Initial Capital:  ${metrics['initial_capital']:,.2f}\n")
        f.write(f"Final Capital:    ${metrics['final_capital']:,.2f}\n")
        f.write(f"Total Return:     {metrics['total_return']:+.2f}%\n")
        f.write(f"Total P&L:        ${metrics['total_pnl']:+,.2f}\n\n")
        
        f.write("TRADING STATISTICS\n")
        f.write(f"Total Trades:     {metrics['total_trades']}\n")
        f.write(f"Win Rate:         {metrics['win_rate']:.2f}%\n")
        f.write(f"Profit Factor:    {metrics['profit_factor']:.2f}\n")
        f.write(f"Avg Win:          ${metrics['avg_win']:,.2f}\n")
        f.write(f"Avg Loss:         ${metrics['avg_loss']:,.2f}\n")
        f.write(f"Max Drawdown:     {metrics['max_drawdown']:.2f}%\n")
        f.write(f"Sharpe Ratio:     {metrics['sharpe_ratio']:.2f}\n\n")
        
        f.write("ALL TRADES\n")
        f.write("-" * 70 + "\n")
        for i, trade in enumerate(metrics['trades_detail'], 1):
            f.write(f"{i}. {trade['entry_time'].strftime('%Y-%m-%d %H:%M')} | "
                   f"{trade['direction']:5s} | "
                   f"Entry: ${trade['entry_price']:,.0f} | "
                   f"Exit: ${trade['exit_price']:,.0f} | "
                   f"P&L: {trade['pnl_pct']:+.2f}% | "
                   f"{trade['reason']}\n")
    
    print(f"\n💾 Results saved to: {results_file}")


if __name__ == '__main__':
    main()
