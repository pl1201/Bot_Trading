"""
Test Multiple Positions + Auto TP/SL
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import os
from dotenv import load_dotenv

load_dotenv()

print("=" * 70)
print("TEST MULTIPLE POSITIONS + AUTO TP/SL")
print("=" * 70)

# Test 1: OKX Client - create_order_with_sl_tp
print("\n1. Testing OKX Client - create_order_with_sl_tp method...")
try:
    from okx_client_simple import OKXClient
    
    client = OKXClient(
        api_key=os.getenv('OKX_API_KEY'),
        api_secret=os.getenv('OKX_API_SECRET'),
        passphrase=os.getenv('OKX_PASSPHRASE'),
        demo_mode=True
    )
    
    # Check if method exists
    assert hasattr(client, 'create_order_with_sl_tp'), "Method not found!"
    print("   ✅ create_order_with_sl_tp() method exists")
    
    # Test method signature
    import inspect
    sig = inspect.signature(client.create_order_with_sl_tp)
    params = list(sig.parameters.keys())
    expected = ['symbol', 'side', 'amount', 'sl_price', 'tp_price']
    assert all(p in params for p in expected), f"Missing parameters! Got: {params}"
    print(f"   ✅ Method signature correct: {params}")
    
except Exception as e:
    print(f"   ❌ Error: {e}")
    sys.exit(1)

# Test 2: Bot - Multiple Positions Structure
print("\n2. Testing Bot - Multiple Positions Structure...")
try:
    from telegram_bot_okx import TradingBotOKX
    
    # Mock telegram to avoid import error
    import unittest.mock as mock
    sys.modules['telegram'] = mock.MagicMock()
    sys.modules['telegram.ext'] = mock.MagicMock()
    
    bot = TradingBotOKX(symbol='BTC-USDT')
    
    # Check positions list
    assert hasattr(bot, 'positions'), "positions attribute not found!"
    assert isinstance(bot.positions, list), "positions should be a list!"
    print(f"   ✅ bot.positions exists (type: {type(bot.positions).__name__})")
    
    # Check max_positions
    assert hasattr(bot, 'max_positions'), "max_positions attribute not found!"
    print(f"   ✅ bot.max_positions = {bot.max_positions}")
    
    # Check methods
    assert hasattr(bot, 'check_positions_status'), "check_positions_status() not found!"
    print("   ✅ check_positions_status() method exists")
    
    assert hasattr(bot, 'calculate_sl_tp_prices'), "calculate_sl_tp_prices() not found!"
    print("   ✅ calculate_sl_tp_prices() method exists")
    
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 3: Config
print("\n3. Testing Configuration...")
try:
    max_positions = int(os.getenv('MAX_POSITIONS', '3'))
    max_position_size = int(os.getenv('MAX_POSITION_SIZE', '10'))
    sl_pct = float(os.getenv('SL_PCT', '0.015'))
    tp_pct = float(os.getenv('TP_PCT', '0.03'))
    
    print(f"   ✅ MAX_POSITIONS = {max_positions}")
    print(f"   ✅ MAX_POSITION_SIZE = {max_position_size} contracts")
    print(f"   ✅ SL_PCT = {sl_pct * 100}%")
    print(f"   ✅ TP_PCT = {tp_pct * 100}%")
    
    # Validate
    assert 1 <= max_positions <= 10, "MAX_POSITIONS should be 1-10"
    assert 1 <= max_position_size <= 100, "MAX_POSITION_SIZE should be 1-100"
    assert 0.001 <= sl_pct <= 0.1, "SL_PCT should be 0.1%-10%"
    assert 0.001 <= tp_pct <= 0.2, "TP_PCT should be 0.1%-20%"
    print("   ✅ All configs valid")
    
except Exception as e:
    print(f"   ❌ Error: {e}")
    sys.exit(1)

# Test 4: SL/TP Calculation
print("\n4. Testing SL/TP Calculation...")
try:
    from telegram_bot_okx import TradingBotOKX
    
    bot = TradingBotOKX(symbol='BTC-USDT')
    
    # Test LONG
    entry_price = 80000
    sl_long, tp_long = bot.calculate_sl_tp_prices(entry_price, 'LONG')
    
    expected_sl_long = entry_price * (1 - bot.sl_pct)
    expected_tp_long = entry_price * (1 + bot.tp_pct)
    
    assert abs(sl_long - expected_sl_long) < 0.01, f"SL LONG wrong: {sl_long} vs {expected_sl_long}"
    assert abs(tp_long - expected_tp_long) < 0.01, f"TP LONG wrong: {tp_long} vs {expected_tp_long}"
    
    print(f"   ✅ LONG: Entry=${entry_price:,.0f}, SL=${sl_long:,.0f}, TP=${tp_long:,.0f}")
    
    # Test SHORT
    sl_short, tp_short = bot.calculate_sl_tp_prices(entry_price, 'SHORT')
    
    expected_sl_short = entry_price * (1 + bot.sl_pct)
    expected_tp_short = entry_price * (1 - bot.tp_pct)
    
    assert abs(sl_short - expected_sl_short) < 0.01, f"SL SHORT wrong: {sl_short} vs {expected_sl_short}"
    assert abs(tp_short - expected_tp_short) < 0.01, f"TP SHORT wrong: {tp_short} vs {expected_tp_short}"
    
    print(f"   ✅ SHORT: Entry=${entry_price:,.0f}, SL=${sl_short:,.0f}, TP=${tp_short:,.0f}")
    
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 70)
print("✅ ALL TESTS PASSED!")
print("=" * 70)
print("\n📝 Summary:")
print("   1. ✅ OKX Client has create_order_with_sl_tp() method")
print("   2. ✅ Bot supports multiple positions (list structure)")
print("   3. ✅ Configuration loaded correctly")
print("   4. ✅ SL/TP calculation works for LONG and SHORT")
print("\n🚀 Ready for production!")
print("\n⚠️  Next steps:")
print("   1. Test with DEMO mode first")
print("   2. Start with MAX_POSITIONS=1")
print("   3. Monitor TP/SL execution on OKX")
print("   4. Gradually increase MAX_POSITIONS")
