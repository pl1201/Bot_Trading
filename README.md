# 🤖 BotTrade - H1 Enhanced Trading Bot

Bot trading tự động với Machine Learning, HMM Regime Detection, và Multi-Timeframe Confirmation.

## 📊 Performance

- **Win Rate**: 71.4%
- **Profit Factor**: 8.24
- **Monthly Return**: ~10.4%
- **Max Drawdown**: 1.2%
- **Trades/Month**: ~9

## ✨ Tính Năng

### 1. Machine Learning
- ✅ H1 Enhanced Model (GradientBoosting)
- ✅ 29 features (momentum, trend, volatility, volume)
- ✅ Trained on 64,452 bars (2017-2024)
- ✅ Tested on 10,757 bars (2025)

### 2. Regime Detection
- ✅ Hidden Markov Model (HMM) với 4 regimes
- ✅ TRENDING, RANGING, VOLATILE, CALM
- ✅ **Skip hoàn toàn RANGING market**
- ✅ Giảm 50% position size trong VOLATILE

### 3. Multi-Timeframe Confirmation
- ✅ H1 + H4 + D1 alignment
- ✅ MTF score > 60%
- ✅ Chỉ trade khi cả 3 timeframes đồng thuận

### 4. Strong Filters
- ✅ ADX > 20 (trend strength)
- ✅ Momentum confirmation (60%+ alignment)
- ✅ RSI (avoid overbought/oversold)
- ✅ Bollinger Bands position
- ✅ EMA alignment (9, 21, 50, 100, 200)
- ✅ Volume confirmation
- ✅ Min confidence 50%

### 5. Risk Management
- ✅ Stop Loss: 1.5%
- ✅ Take Profit: 3% (2:1 RR)
- ✅ Trailing Stop: 1.5%
- ✅ Position sizing: 2% risk per trade
- ✅ Max 10 contracts

### 6. Trading Platforms
- ✅ OKX Integration (Demo & Real)
- ✅ Telegram Bot (Auto trading)
- ✅ Real-time monitoring

---

## 🚀 Quick Start

### 1. Cài Đặt

```bash
# Clone repo
git clone <repo_url>
cd BotTrade

# Cài dependencies
pip install -r requirements.txt
```

### 2. Cấu Hình

Tạo file `.env`:

```bash
# OKX API
OKX_API_KEY=your_api_key
OKX_API_SECRET=your_api_secret
OKX_PASSPHRASE=your_passphrase

# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Trading Config
SYMBOL=BTC-USDT
INTERVAL=1H
USE_SIMULATED_TRADING=true
AUTO_TRADING=false
RISK_PER_TRADE=0.02
SL_PCT=0.015
TP_PCT=0.03
```

### 3. Chạy Bot

#### Option 1: Telegram Bot (Recommended)
```bash
python telegram_bot_okx.py
```

Sau đó trong Telegram:
```
/start   - Khởi động
/status  - Xem trạng thái
/signals - Xem signals
/trade   - BẬT/TẮT auto trading
```

#### Option 2: Standalone Bot
```bash
python trading_bot_complete.py
```

---

## 📁 Cấu Trúc Project

```
BotTrade/
├── algo_trading/              # Core trading modules
│   ├── ml/                    # Machine learning
│   │   ├── h1_enhanced_model.py
│   │   └── models/            # Trained models
│   ├── market_models/         # Regime detection
│   ├── indicators/            # Technical indicators
│   ├── core/                  # Backtest engine
│   └── live/                  # Live trading
│
├── telegram_bot_okx.py        # Telegram bot (auto trading)
├── trading_bot_complete.py    # Standalone bot
├── okx_client_simple.py       # OKX API client
├── backtest_6months.py        # Backtest script
│
├── .env                       # Configuration
├── requirements.txt           # Dependencies
│
└── Documentation/
    ├── README.md              # This file
    ├── INTEGRATION_CHECK.md   # Feature checklist
    ├── BACKTEST_SUMMARY_6MONTHS.md
    ├── SETUP_FROM_GIT.md
    ├── TELEGRAM_SETUP.md
    ├── RISK_MANAGEMENT.md
    ├── MATHEMATICAL_ARCHITECTURE.md
    ├── ML_INDICATORS_DETAILED.md
    └── WHY_XGBOOST.md
```

---

## 📖 Documentation

### Hướng Dẫn Chi Tiết
- **[SETUP_FROM_GIT.md](SETUP_FROM_GIT.md)** - Hướng dẫn setup từ đầu
- **[TELEGRAM_SETUP.md](TELEGRAM_SETUP.md)** - Setup Telegram bot
- **[INTEGRATION_CHECK.md](INTEGRATION_CHECK.md)** - Kiểm tra tính năng
- **[BACKTEST_SUMMARY_6MONTHS.md](BACKTEST_SUMMARY_6MONTHS.md)** - Kết quả backtest

### Technical Documentation
- **[MATHEMATICAL_ARCHITECTURE.md](MATHEMATICAL_ARCHITECTURE.md)** - Kiến trúc toán học
- **[ML_INDICATORS_DETAILED.md](ML_INDICATORS_DETAILED.md)** - Chi tiết indicators
- **[WHY_XGBOOST.md](WHY_XGBOOST.md)** - Tại sao dùng GradientBoosting
- **[RISK_MANAGEMENT.md](RISK_MANAGEMENT.md)** - Quản lý rủi ro

---

## 🧪 Testing

### Test Integration
```bash
python test_integration.py
```

### Backtest
```bash
python backtest_6months.py
```

---

## 📊 Telegram Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Khởi động bot |
| `/status` | Xem trạng thái bot |
| `/balance` | Xem số dư OKX |
| `/position` | Xem vị thế hiện tại |
| `/signals` | Xem signals (dữ liệu thật từ OKX) |
| `/trade` | **BẬT/TẮT auto trading** ⭐ |
| `/help` | Hướng dẫn |

---

## ⚙️ Configuration

### Trading Parameters

```python
# Risk Management
RISK_PER_TRADE = 0.02      # 2% per trade
MAX_POSITION_SIZE = 10     # Max 10 contracts

# Stop Loss & Take Profit
SL_PCT = 0.015             # 1.5% stop loss
TP_PCT = 0.03              # 3% take profit

# Model Config
MIN_CONFIDENCE = 0.50      # Min 50% confidence
MIN_ADX = 20               # Min ADX for trend
MIN_MTF_SCORE = 0.60       # Min 60% MTF alignment
```

### Model Config

```python
config = {
    'skip_ranging': True,           # Skip ranging market
    'skip_volatile': False,         # Trade in volatile (50% size)
    'require_mtf_confirm': True,    # Require MTF alignment
    'momentum_confirm': True,       # Require momentum
    'adx_min': 20,                  # Min ADX
    'min_confidence': 0.50,         # Min confidence
    'min_mtf_score': 0.6,           # Min MTF score
}
```

---

## 🔒 Security

### Demo Mode (Mặc định)
```python
USE_SIMULATED_TRADING=true
```
- Giao dịch giả lập
- Không mất tiền thật
- An toàn để test

### Real Mode (Cẩn thận!)
```python
USE_SIMULATED_TRADING=false
```
- Giao dịch thật
- Mất tiền thật nếu sai
- Chỉ dùng khi đã test kỹ

---

## 📈 Expected Performance

### Backtest Results (2025)
- **Period**: 15 months (Jan - Mar 2025)
- **Total Trades**: 140
- **Win Rate**: 71.4%
- **Profit Factor**: 8.24
- **Total Return**: +156.5%
- **Max Drawdown**: 1.2%
- **Avg Return/Trade**: 1.12%

### Live Trading (Expected)
- **Trades/Month**: 8-12
- **Win Rate**: 65-75%
- **Monthly Return**: 8-12%
- **Max Drawdown**: 2-5%

---

## ⚠️ Risk Warning

- **Past performance ≠ future results**
- Luôn bắt đầu với **demo mode**
- Chỉ trade với tiền bạn có thể mất
- Monitor bot thường xuyên
- Hiểu rõ rủi ro trước khi trade

---

## 🛠️ Troubleshooting

### Model Loading Error
```bash
# Nếu gặp lỗi numpy version
pip install numpy==1.23.5

# Hoặc retrain model
cd production_best_model
python train_h1_proper.py
```

### OKX Connection Error
```bash
# Check API keys trong .env
# Check internet connection
# Check OKX API status
```

### Telegram Bot Timeout
```bash
# Bot đã có extended timeout (30s)
# Nếu vẫn timeout, check VPN
# Hoặc check Telegram API status
```

---

## 📞 Support

### Logs
- `trading_bot_complete.log` - Standalone bot logs
- `telegram_bot_okx.log` - Telegram bot logs

### Check Status
```bash
# Test integration
python test_integration.py

# Check model
python -c "from algo_trading.ml import H1EnhancedModel; m = H1EnhancedModel(); print(m.load('h1_enhanced'))"
```

---

## 🎯 Roadmap

- [x] H1 Enhanced Model
- [x] HMM Regime Detection
- [x] Multi-Timeframe Confirmation
- [x] Telegram Bot
- [x] OKX Integration
- [x] Auto Trading
- [x] Risk Management
- [ ] Web Dashboard
- [ ] Multiple exchanges
- [ ] Portfolio management
- [ ] Advanced analytics

---

## 📄 License

Private - For personal use only

---

## 🙏 Credits

- **Model**: H1 Enhanced (GradientBoosting + HMM)
- **Exchange**: OKX
- **Framework**: Python, scikit-learn, hmmlearn
- **Bot**: python-telegram-bot

---

**Status**: ✅ Production Ready

**Last Updated**: 2026-04-16

**Version**: 1.0.0
