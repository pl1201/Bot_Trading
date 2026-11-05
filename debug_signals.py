"""
Debug Script - Tại Sao Không Có Signal?
Phân tích chi tiết từng filter
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import os
import numpy as np
import pandas as pd
from dotenv import load_dotenv
load_dotenv()

from algo_trading.ml.h1_enhanced_model import H1EnhancedModel
from okx_client_simple import OKXClient

print("=" * 80)
print("DEBUG: TẠI SAO KHÔNG CÓ SIGNAL?")
print("=" * 80)

# Load model
print("\n[1] Loading model...")
model = H1EnhancedModel()
if not model.load('h1_enhanced'):
    print("ERROR: Model not found!")
    sys.exit(1)

print("✅ Model loaded")
print(f"Config:")
print(f"  - use_hybrid_regime: {model.config.get('use_hybrid_regime')}")
print(f"  - min_trend_prob: {model.config['min_trend_prob']}")
print(f"  - min_confidence: {model.config['min_confidence']}")
print(f"  - min_mtf_score: {model.config['min_mtf_score']}")
print(f"  - adx_min: {model.config['adx_min']}")
print(f"  - momentum_confirm: {model.config.get('momentum_confirm', False)}")

# Fetch data
print("\n[2] Fetching data from OKX...")
okx = OKXClient(
    api_key=os.getenv('OKX_API_KEY'),
    api_secret=os.getenv('OKX_API_SECRET'),
    passphrase=os.getenv('OKX_PASSPHRASE'),
    demo_mode=True
)

df = okx.fetch_ohlcv('BTC-USDT', '1H', limit=1000)
print(f"✅ Fetched {len(df)} bars")
print(f"Latest: {df.index[-1]}, Price: ${df['close'].iloc[-1]:,.2f}")

# Build features
print("\n[3] Building features...")
data = model.build_features(df)
data = model.build_mtf_context(data)
print(f"✅ Features built: {len(data.columns)} columns")

# Detect regime
print("\n[4] Detecting regime...")
regime, regime_probs = model.detect_regime(df)
print(f"✅ Regime detected")

# Get latest values
latest_idx = -1
latest_regime = regime.iloc[latest_idx]
regime_names = ['TRENDING', 'RANGING', 'VOLATILE', 'CALM']
print(f"\nLatest Regime: {regime_names[latest_regime]}")
print(f"Regime Probabilities:")
for col in regime_probs.columns:
    print(f"  - {col}: {regime_probs[col].iloc[latest_idx]:.2%}")

# Get model prediction
print("\n[5] Getting model prediction...")
available_feats = [f for f in model.feature_names if f in data.columns]
if len(available_feats) < len(model.feature_names):
    missing = set(model.feature_names) - set(available_feats)
    for m in missing:
        data[m] = 0.0

X = data[model.feature_names].fillna(0)
X_scaled = model.scaler.transform(X)
proba = model.trend_model.predict_proba(X_scaled)
pred = model.trend_model.predict(X_scaled)

latest_pred = pred[latest_idx]
latest_proba = proba[latest_idx]
pred_names = {0: 'HOLD', 1: 'LONG', 2: 'SHORT'}

print(f"\nRaw Model Prediction: {pred_names[latest_pred]}")
print(f"Probabilities:")
print(f"  - HOLD:  {latest_proba[0]:.2%}")
print(f"  - LONG:  {latest_proba[1]:.2%}")
print(f"  - SHORT: {latest_proba[2]:.2%}")
print(f"Max Confidence: {np.max(latest_proba):.2%}")

# Check filters
print("\n" + "=" * 80)
print("FILTER ANALYSIS")
print("=" * 80)

# Filter 1: Regime
print(f"\n[Filter 1] Regime Check")
print(f"  Current: {regime_names[latest_regime]}")
print(f"  Skip ranging: {model.config['skip_ranging']}")
if model.config['skip_ranging'] and latest_regime == 1:
    print(f"  ❌ FILTERED: Ranging regime (skip_ranging=True)")
else:
    print(f"  ✅ PASS")

# Filter 2: Trend Probability
print(f"\n[Filter 2] Trend Probability Check")
trend_prob = regime_probs['prob_trending'].iloc[latest_idx]
min_trend_prob = model.config['min_trend_prob']
print(f"  Trend prob: {trend_prob:.2%}")
print(f"  Threshold: {min_trend_prob:.2%}")
if trend_prob < min_trend_prob:
    print(f"  ❌ FILTERED: Trend prob too low ({trend_prob:.2%} < {min_trend_prob:.2%})")
else:
    print(f"  ✅ PASS")

# Filter 3: MTF Confirmation
print(f"\n[Filter 3] MTF Confirmation Check")
mtf_score = data['mtf_score'].iloc[latest_idx] if 'mtf_score' in data.columns else 0.5
min_mtf = model.config['min_mtf_score']
print(f"  MTF score: {mtf_score:.2%}")
print(f"  Threshold: {min_mtf:.2%}")

if model.config['require_mtf_confirm']:
    if latest_pred == 1 and mtf_score < min_mtf:
        print(f"  ❌ FILTERED: LONG needs MTF >= {min_mtf:.2%}, got {mtf_score:.2%}")
    elif latest_pred == 2 and mtf_score > (1 - min_mtf):
        print(f"  ❌ FILTERED: SHORT needs MTF <= {(1-min_mtf):.2%}, got {mtf_score:.2%}")
    else:
        print(f"  ✅ PASS")
else:
    print(f"  ⚠️  DISABLED")

# Filter 4: ADX
print(f"\n[Filter 4] ADX Check")
adx = data['adx'].iloc[latest_idx] if 'adx' in data.columns else 0
adx_min = model.config['adx_min']
print(f"  ADX: {adx:.2f}")
print(f"  Threshold: {adx_min}")
if pd.isna(adx):
    print(f"  ⚠️  ADX is NaN")
elif adx < adx_min:
    print(f"  ❌ FILTERED: ADX too low ({adx:.2f} < {adx_min})")
else:
    print(f"  ✅ PASS")

# Filter 5: Momentum Confirmation
print(f"\n[Filter 5] Momentum Confirmation Check")
if model.config.get('momentum_confirm', False):
    mtf_bull = data['mtf_bull'].iloc[latest_idx] if 'mtf_bull' in data.columns else 0.5
    print(f"  MTF bull: {mtf_bull:.2%}")
    if latest_pred == 1 and mtf_bull < 0.6:
        print(f"  ❌ FILTERED: LONG needs mtf_bull >= 60%, got {mtf_bull:.2%}")
    elif latest_pred == 2 and mtf_bull > 0.4:
        print(f"  ❌ FILTERED: SHORT needs mtf_bull <= 40%, got {mtf_bull:.2%}")
    else:
        print(f"  ✅ PASS")
else:
    print(f"  ⚠️  DISABLED")

# Filter 6: Confidence
print(f"\n[Filter 6] Confidence Check")
max_conf = np.max(latest_proba)
min_conf = model.config['min_confidence']
print(f"  Confidence: {max_conf:.2%}")
print(f"  Threshold: {min_conf:.2%}")
if max_conf < min_conf:
    print(f"  ❌ FILTERED: Confidence too low ({max_conf:.2%} < {min_conf:.2%})")
else:
    print(f"  ✅ PASS")

# Final signal
print("\n" + "=" * 80)
print("FINAL SIGNAL")
print("=" * 80)

signals, confidences, regimes, size_mult = model.predict(df)
final_signal = signals[latest_idx]
final_conf = confidences[latest_idx]

signal_names = {1: 'LONG 🟢', -1: 'SHORT 🔴', 0: 'HOLD ⚪️'}
print(f"\nSignal: {signal_names[final_signal]}")
print(f"Confidence: {final_conf:.1%}")
print(f"Regime: {regime_names[regimes[latest_idx]]}")

# Explanation
print("\n" + "=" * 80)
print("GIẢI THÍCH")
print("=" * 80)

if final_signal == 0:
    print("\n❓ TẠI SAO HOLD?")
    print("\nModel RẤT SELECTIVE - cần TẤT CẢ điều kiện sau:")
    print("1. ✅ Regime = TRENDING")
    print("2. ✅ Model predict LONG/SHORT (không phải HOLD)")
    print("3. ✅ Trend probability >= 50%")
    print("4. ✅ MTF alignment phù hợp (H1+H4+D1 cùng hướng)")
    print("5. ✅ ADX >= 15 (trend đủ mạnh)")
    print("6. ✅ Confidence >= 40%")
    print("\nNếu THIẾU 1 điều kiện → HOLD")
    print("\nĐây là TÍNH NĂNG, không phải bug!")
    print("Model chỉ trade khi setup HOÀN HẢO.")
    
    # Show what's missing
    print("\n🔍 ĐIỀU KIỆN THIẾU:")
    issues = []
    
    if latest_pred == 0:
        issues.append("- Model predict HOLD (không có xu hướng rõ ràng)")
    
    if trend_prob < min_trend_prob:
        issues.append(f"- Trend prob quá thấp ({trend_prob:.1%} < {min_trend_prob:.1%})")
    
    if model.config['require_mtf_confirm']:
        if latest_pred == 1 and mtf_score < min_mtf:
            issues.append(f"- MTF không align cho LONG ({mtf_score:.1%} < {min_mtf:.1%})")
        elif latest_pred == 2 and mtf_score > (1 - min_mtf):
            issues.append(f"- MTF không align cho SHORT ({mtf_score:.1%} > {(1-min_mtf):.1%})")
    
    if not pd.isna(adx) and adx < adx_min:
        issues.append(f"- ADX quá thấp ({adx:.1f} < {adx_min})")
    
    if max_conf < min_conf:
        issues.append(f"- Confidence quá thấp ({max_conf:.1%} < {min_conf:.1%})")
    
    if issues:
        for issue in issues:
            print(issue)
    else:
        print("- Không rõ (có thể do momentum confirmation)")
    
    print("\n💡 ĐỀ XUẤT:")
    print("1. Chờ thêm - model sẽ signal khi setup tốt")
    print("2. Hoặc giảm threshold trong config (trade nhiều hơn, WR thấp hơn)")
    print("3. Backtest cho thấy 223 trades/năm = ~15/tháng = ~4/tuần")
    print("   → 1 tuần không có signal là BÌNH THƯỜNG")

else:
    print(f"\n✅ CÓ SIGNAL: {signal_names[final_signal]}")
    print(f"Confidence: {final_conf:.1%}")
    print("\nTất cả điều kiện đã thỏa mãn!")

print("\n" + "=" * 80)
print("DEBUG COMPLETED")
print("=" * 80)
