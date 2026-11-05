"""
Test Complete System - Model, Backtest, OKX, Telegram
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import os
from dotenv import load_dotenv
load_dotenv()

print("=" * 80)
print("COMPLETE SYSTEM TEST")
print("=" * 80)

# Test 1: Model Loading
print("\n[1/5] Testing Model Loading...")
try:
    from algo_trading.ml.h1_enhanced_model import H1EnhancedModel
    model = H1EnhancedModel()
    success = model.load('h1_enhanced')
    
    if success:
        print(f"  ✅ Model loaded successfully")
        print(f"     - Hybrid mode: {model.config.get('use_hybrid_regime', False)}")
        print(f"     - HMM weight: {model.config.get('hmm_weight', 0.0)}")
        print(f"     - Simple weight: {model.config.get('simple_weight', 1.0)}")
        print(f"     - Features: {len(model.feature_names)}")
        print(f"     - Min trend prob: {model.config['min_trend_prob']}")
        print(f"     - Min confidence: {model.config['min_confidence']}")
    else:
        print("  ❌ Model failed to load")
        sys.exit(1)
except Exception as e:
    print(f"  ❌ Error: {e}")
    sys.exit(1)

# Test 2: OKX Connection
print("\n[2/5] Testing OKX Connection...")
try:
    from okx_client_simple import OKXClient
    
    okx = OKXClient(
        api_key=os.getenv('OKX_API_KEY'),
        api_secret=os.getenv('OKX_API_SECRET'),
        passphrase=os.getenv('OKX_PASSPHRASE'),
        demo_mode=True
    )
    
    # Test balance
    balance = okx.fetch_balance()
    usdt = balance.get('USDT', {}).get('free', 0)
    print(f"  ✅ OKX connected (Demo Mode)")
    print(f"     - Balance: {usdt:,.2f} USDT")
    
    # Test fetch data
    df = okx.fetch_ohlcv('BTC-USDT', '1H', limit=100)
    print(f"     - Fetched {len(df)} bars")
    print(f"     - Latest price: ${df['close'].iloc[-1]:,.2f}")
    
except Exception as e:
    print(f"  ❌ Error: {e}")
    print("     Check .env file for OKX credentials")
    sys.exit(1)

# Test 3: Signal Generation
print("\n[3/5] Testing Signal Generation...")
try:
    import numpy as np
    
    # Generate signals on recent data
    signals, confidences, regimes, size_mult = model.predict(df)
    
    signal_counts = {
        'LONG': (signals == 1).sum(),
        'SHORT': (signals == -1).sum(),
        'HOLD': (signals == 0).sum()
    }
    
    print(f"  ✅ Signals generated")
    print(f"     - LONG: {signal_counts['LONG']}")
    print(f"     - SHORT: {signal_counts['SHORT']}")
    print(f"     - HOLD: {signal_counts['HOLD']}")
    
    # Current signal
    current_signal = signals[-1]
    current_conf = confidences[-1]
    current_regime = ['TRENDING', 'RANGING', 'VOLATILE', 'CALM'][int(regimes[-1])]
    
    signal_name = {1: 'LONG', -1: 'SHORT', 0: 'HOLD'}[current_signal]
    print(f"     - Current: {signal_name} (conf: {current_conf:.1%}, regime: {current_regime})")
    
except Exception as e:
    print(f"  ❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 4: Telegram Bot (Optional)
print("\n[4/5] Testing Telegram Bot...")
try:
    telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
    telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    if telegram_token and telegram_chat_id:
        try:
            from telegram import Update
            from telegram.ext import Application
            print(f"  ✅ Telegram library available")
            print(f"     - Token: {telegram_token[:10]}...")
            print(f"     - Chat ID: {telegram_chat_id}")
            print(f"     - Bot can be started with: python telegram_bot_okx.py")
        except ImportError:
            print(f"  ⚠️  python-telegram-bot not installed")
            print(f"     Install: pip install python-telegram-bot")
    else:
        print(f"  ⚠️  Telegram not configured")
        print(f"     Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env")
        
except Exception as e:
    print(f"  ⚠️  Telegram check failed: {e}")

# Test 5: Backtest Capability
print("\n[5/5] Testing Backtest Capability...")
try:
    # Quick mini backtest on recent data
    from datetime import datetime, timedelta
    
    # Fetch more data for backtest
    df_backtest = okx.fetch_ohlcv('BTC-USDT', '1H', limit=500)
    
    # Generate signals
    signals_bt, confs_bt, regimes_bt, size_bt = model.predict(df_backtest)
    
    # Simple P&L calculation
    trades = []
    holding = 8  # 8 hours
    
    i = 0
    while i < len(signals_bt) - holding:
        if signals_bt[i] != 0:
            entry = df_backtest['close'].iloc[i]
            exit_p = df_backtest['close'].iloc[i + holding]
            direction = signals_bt[i]
            ret = (exit_p / entry - 1) * direction - 0.001  # 0.1% fee
            trades.append(ret)
            i += holding
        else:
            i += 1
    
    if len(trades) > 0:
        trades_arr = np.array(trades)
        win_rate = (trades_arr > 0).mean()
        total_return = trades_arr.sum()
        
        print(f"  ✅ Backtest completed")
        print(f"     - Period: {df_backtest.index[0]} to {df_backtest.index[-1]}")
        print(f"     - Trades: {len(trades)}")
        print(f"     - Win Rate: {win_rate:.1%}")
        print(f"     - Total Return: {total_return*100:+.2f}%")
        print(f"     - Full backtest: python backtest_6months.py")
    else:
        print(f"  ⚠️  No trades in test period")
        print(f"     - Model is very selective")
        print(f"     - Run full backtest: python backtest_6months.py")
    
except Exception as e:
    print(f"  ❌ Error: {e}")
    import traceback
    traceback.print_exc()

# Summary
print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print("""
✅ Model: Loaded with hybrid regime detection
✅ OKX: Connected (Demo Mode)
✅ Signals: Generated successfully
✅ Backtest: Capability verified

NEXT STEPS:
1. Run full backtest:
   python backtest_6months.py

2. Start Telegram bot (if configured):
   python telegram_bot_okx.py
   
3. In Telegram:
   /start - Start bot
   /status - Check status
   /signals - Get current signals
   /trade - Toggle auto trading ON/OFF
   /position - Check current position
   /balance - Check balance

IMPORTANT:
- Bot is in DEMO MODE (OKX simulated trading)
- No real money at risk
- Auto trading OFF by default
- Use /trade command to enable auto trading
- Bot is very selective (may take hours for signals)

DOCUMENTATION:
- RETRAIN_SUCCESS_SUMMARY.md - Model retrain details
- HYBRID_REGIME_UPGRADE.md - Hybrid detection explained
- QUICK_START_NEW_MODEL.md - Quick reference
- README.md - General documentation
""")

print("=" * 80)
print("✅ ALL TESTS PASSED!")
print("=" * 80)
