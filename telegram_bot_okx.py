"""
Telegram Trading Bot - Với OKX Demo Trading
Dùng requests thay vì ccxt
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import os
import time
import logging
import threading
from datetime import datetime
from typing import Optional
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('telegram_bot_okx.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

from algo_trading.ml import H1EnhancedModel
from okx_client_simple import OKXClient

try:
    from telegram import Update
    from telegram.ext import Application, CommandHandler, ContextTypes
    HAS_TELEGRAM = True
except ImportError:
    HAS_TELEGRAM = False
    logger.error("python-telegram-bot not installed")


class TradingBotOKX:
    """Trading bot với OKX Demo - MULTIPLE POSITIONS + AUTO TP/SL"""
    
    def __init__(self, symbol: str = 'BTC-USDT', position_size_pct: float = 0.02):
        # Load model
        logger.info("Loading model...")
        self.model = H1EnhancedModel()
        if not self.model.load('h1_enhanced'):
            raise ValueError("Model not found!")
        
        # OKX client
        logger.info("Initializing OKX client...")
        self.okx = OKXClient(
            api_key=os.getenv('OKX_API_KEY'),
            api_secret=os.getenv('OKX_API_SECRET'),
            passphrase=os.getenv('OKX_PASSPHRASE'),
            demo_mode=True  # Demo trading
        )
        
        self.symbol = symbol
        self.position_size_pct = position_size_pct
        
        # Trading config
        self.risk_per_trade = float(os.getenv('RISK_PER_TRADE', '0.02'))
        self.sl_pct = float(os.getenv('SL_PCT', '0.015'))
        self.tp_pct = float(os.getenv('TP_PCT', '0.03'))
        self.max_position_size = int(os.getenv('MAX_POSITION_SIZE', '10'))  # Max contracts
        self.max_positions = int(os.getenv('MAX_POSITIONS', '3'))  # Max concurrent positions
        
        # State - MULTIPLE POSITIONS
        self.auto_trading = False
        self.positions = []  # List of active positions
        
        self.last_signal = None
        self.last_check_time = None
        self.last_trade_time = None
        
        # Telegram
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
        
        # Trading thread
        self.running = False
        self.trading_thread = None
        
        logger.info(f"Bot initialized - Symbol: {symbol}")
        logger.info(f"Risk per trade: {self.risk_per_trade * 100}%")
        logger.info(f"SL: {self.sl_pct * 100}% | TP: {self.tp_pct * 100}%")
        logger.info(f"Max concurrent positions: {self.max_positions}")
        
        # Sync positions from OKX on startup
        self.sync_positions_from_okx()
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        balance = self.okx.fetch_balance()
        usdt = balance.get('USDT', {}).get('free', 0)
        
        message = f"""
🤖 <b>H1 Enhanced Trading Bot - OKX DEMO</b>

✅ Kết nối OKX thành công!

<b>Commands:</b>
/status - Xem trạng thái bot
/balance - Xem số dư
/position - Xem vị thế
/signals - Xem signals
/trade - Bật/tắt auto trading
/help - Hướng dẫn

<b>Symbol:</b> {self.symbol}
<b>Balance:</b> {usdt:,.2f} USDT
<b>Auto Trading:</b> {'✅ BẬT' if self.auto_trading else '❌ TẮT'}

⚠️ <b>DEMO MODE</b> - Giao dịch giả lập
"""
        await update.message.reply_text(message, parse_mode='HTML')
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            balance = self.okx.fetch_balance()
            usdt = balance.get('USDT', {}).get('free', 0)
            
            # Get OKX position
            okx_position = self.okx.get_position(self.symbol)
            
            message = f"""
📊 <b>BOT STATUS - OKX DEMO</b>

<b>Symbol:</b> {self.symbol}
<b>Balance:</b> {usdt:,.2f} USDT
<b>Auto Trading:</b> {'✅ BẬT' if self.auto_trading else '❌ TẮT'}
<b>Active Positions:</b> {len(self.positions)}/{self.max_positions}
<b>OKX Position Size:</b> {okx_position['size']} contracts

<b>Last Check:</b> {self.last_check_time or 'Never'}
<b>Last Signal:</b> {self.last_signal or 'None'}

<b>Model Config:</b>
- Min Confidence: {self.model.config['min_confidence']:.0%}
- Min ADX: {self.model.config['adx_min']}
- Holding Period: {self.model.config['holding_period']}h

⚠️ Demo mode - OKX simulated trading
"""
            await update.message.reply_text(message, parse_mode='HTML')
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    async def balance_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            balance = self.okx.fetch_balance()
            
            message = "💰 <b>OKX DEMO BALANCE</b>\n\n"
            
            for coin in ['USDT', 'BTC', 'ETH', 'OKB']:
                if coin in balance:
                    b = balance[coin]
                    message += f"<b>{coin}:</b>\n"
                    message += f"  Total: {b['total']:.8f}\n"
                    message += f"  Free: {b['free']:.8f}\n"
                    message += f"  Used: {b['used']:.8f}\n\n"
            
            message += "⚠️ Demo balance - Not real money"
            
            await update.message.reply_text(message, parse_mode='HTML')
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    async def position_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.positions:
            await update.message.reply_text("📭 Không có vị thế nào đang mở")
            return
        
        try:
            ticker = self.okx.fetch_ticker(self.symbol)
            current_price = ticker['last']
            
            message = f"📈 <b>ACTIVE POSITIONS ({len(self.positions)})</b>\n\n"
            
            for i, pos in enumerate(self.positions, 1):
                if pos['direction'] == 'LONG':
                    pnl_pct = (current_price / pos['entry_price'] - 1) * 100
                else:
                    pnl_pct = (pos['entry_price'] / current_price - 1) * 100
                
                holding_hours = (datetime.now() - pos['entry_time']).total_seconds() / 3600
                
                message += f"""
<b>Position #{i} - {pos['direction']}</b>
Entry: ${pos['entry_price']:,.2f}
Size: {abs(pos['size'])} contracts
PnL: {pnl_pct:+.2f}%
Holding: {holding_hours:.1f}h
SL: ${pos['sl_price']:,.2f} ({self.sl_pct * 100}%)
TP: ${pos['tp_price']:,.2f} ({self.tp_pct * 100}%)
Order ID: {pos['order_id'][:8]}...

"""
            
            message += f"<b>Current Price:</b> ${current_price:,.2f}\n"
            message += "⚠️ TP/SL tự động chốt trên OKX"
            
            await update.message.reply_text(message, parse_mode='HTML')
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    async def signals_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            await update.message.reply_text("🔍 Đang phân tích thị trường...")
            
            # Fetch real data from OKX
            df = self.okx.fetch_ohlcv(self.symbol, "1H", 1000)
            
            # Generate signals
            signals, confidences, regimes, size_mult = self.model.predict(df)
            
            latest_signal = signals[-1]
            latest_confidence = confidences[-1]
            latest_regime = regimes[-1]
            latest_price = df['close'].iloc[-1]
            
            regime_names = ['TRENDING', 'RANGING', 'VOLATILE', 'CALM']
            signal_names = {1: 'LONG 🟢', -1: 'SHORT 🔴', 0: 'HOLD ⚪'}
            
            # Get recent signals
            recent_signals = []
            for i in range(max(0, len(signals)-5), len(signals)):
                if signals[i] != 0:
                    recent_signals.append({
                        'time': df.index[i].strftime('%m-%d %H:%M'),
                        'signal': signal_names[signals[i]],
                        'conf': confidences[i],
                        'regime': regime_names[regimes[i]]
                    })
            
            message = f"""
📊 <b>MARKET SIGNALS - OKX REAL DATA</b>

<b>Current Signal:</b> {signal_names[latest_signal]}
<b>Confidence:</b> {latest_confidence:.1%}
<b>Regime:</b> {regime_names[latest_regime]}
<b>Price:</b> ${latest_price:,.2f}

<b>Recent Signals (last 5):</b>
"""
            if recent_signals:
                for s in recent_signals[-5:]:
                    message += f"\n{s['time']} - {s['signal']} ({s['conf']:.0%}) [{s['regime']}]"
            else:
                message += "\nKhông có signal gần đây"
            
            message += "\n\n✅ Dữ liệu thật từ OKX"
            
            await update.message.reply_text(message, parse_mode='HTML')
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    async def trade_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self.auto_trading = not self.auto_trading
        
        status = "✅ BẬT" if self.auto_trading else "❌ TẮT"
        
        message = f"""
🤖 <b>AUTO TRADING: {status}</b>

"""
        if self.auto_trading:
            message += """
✅ Bot sẽ tự động trade khi có signal.

⚠️ <b>Lưu ý:</b>
- Đây là DEMO MODE (OKX simulated)
- Giao dịch giả lập, không mất tiền thật
- Bot rất selective, có thể vài giờ mới có signal

Dùng /status để theo dõi.
"""
        else:
            message += """
❌ Bot sẽ KHÔNG tự động trade.

Dùng /trade lại để bật.
"""
        
        await update.message.reply_text(message, parse_mode='HTML')
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        message = """
📖 <b>HƯỚNG DẪN - OKX DEMO BOT</b>

<b>Commands:</b>
/start - Khởi động bot
/status - Xem trạng thái
/balance - Xem số dư OKX demo
/position - Xem vị thế
/signals - Xem signals (dữ liệu thật từ OKX)
/trade - Bật/tắt auto trading
/sync - Đồng bộ vị thế từ OKX
/help - Hướng dẫn

<b>Tính Năng:</b>
✅ Kết nối OKX thật
✅ Dữ liệu thị trường real-time
✅ Model H1 Enhanced
✅ HMM Regime Detection
✅ Multi-Timeframe Confirmation
✅ Multiple Positions (max 3)
✅ Auto TP/SL trên OKX

<b>Demo Mode:</b>
- Giao dịch giả lập (x-simulated-trading: 1)
- Không mất tiền thật
- Test bot an toàn

<b>Hiệu Suất Kỳ Vọng:</b>
- Win Rate: ~70%
- Trades/Tháng: 8-12
- Return/Tháng: ~10%
"""
        await update.message.reply_text(message, parse_mode='HTML')
    
    async def sync_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Sync positions from OKX"""
        try:
            await update.message.reply_text("🔄 Đang đồng bộ vị thế từ OKX...")
            
            # Get OKX position
            okx_position = self.okx.get_position(self.symbol)
            okx_size = okx_position['size']
            
            if okx_size == 0:
                self.positions = []
                await update.message.reply_text("✅ OKX không có vị thế nào\n📭 Bot tracking đã được xóa")
                return
            
            # Force sync
            direction = 'LONG' if okx_size > 0 else 'SHORT'
            entry_price = okx_position['entry_price']
            unrealized_pnl = okx_position['unrealized_pnl']
            unrealized_pnl_pct = okx_position['unrealized_pnl_pct']
            
            # Calculate SL/TP
            sl_price, tp_price = self.calculate_sl_tp_prices(entry_price, direction)
            
            # Clear and create new tracking
            self.positions = [{
                'order_id': 'synced_from_okx',
                'direction': direction,
                'entry_price': entry_price,
                'entry_time': datetime.now(),
                'size': int(abs(okx_size)),
                'sl_price': sl_price,
                'tp_price': tp_price,
            }]
            
            message = f"""
✅ <b>ĐÃ ĐỒNG BỘ VỊ THẾ TỪ OKX</b>

<b>Direction:</b> {direction}
<b>Size:</b> {abs(okx_size)} contracts ({abs(okx_size) * 0.01:.4f} BTC)
<b>Entry Price:</b> ${entry_price:,.2f}
<b>Unrealized PnL:</b> ${unrealized_pnl:,.2f} ({unrealized_pnl_pct:+.2f}%)

<b>Calculated SL/TP:</b>
- SL: ${sl_price:,.2f} ({self.sl_pct * 100}%)
- TP: ${tp_price:,.2f} ({self.tp_pct * 100}%)

⚠️ Nếu OKX đã có TP/SL orders, chúng sẽ được ưu tiên
"""
            await update.message.reply_text(message, parse_mode='HTML')
            
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    def calculate_position_size(self, current_price: float) -> int:
        """
        Tính position size dựa trên risk management
        
        Returns:
            int: Số contracts (1 contract = 0.01 BTC = ~$100)
        """
        balance = self.okx.fetch_balance()
        usdt_balance = balance.get('USDT', {}).get('free', 0)
        
        if usdt_balance <= 0:
            return 0
        
        risk_amount = usdt_balance * self.risk_per_trade
        sl_distance = current_price * self.sl_pct
        
        # Calculate BTC quantity
        qty_btc = risk_amount / sl_distance if sl_distance > 0 else 0
        
        # Convert to contracts (1 contract = 0.01 BTC)
        contracts = int(qty_btc / 0.01)
        
        # Limit max position
        if self.max_position_size:
            contracts = min(contracts, self.max_position_size)
        
        return max(contracts, 1)  # Minimum 1 contract
    
    def calculate_sl_tp_prices(self, entry_price: float, direction: str):
        """Tính SL/TP prices"""
        if direction == 'LONG':
            sl_price = entry_price * (1 - self.sl_pct)
            tp_price = entry_price * (1 + self.tp_pct)
        else:  # SHORT
            sl_price = entry_price * (1 + self.sl_pct)
            tp_price = entry_price * (1 - self.tp_pct)
        
        return sl_price, tp_price
    
    def enter_position(self, direction: str, current_price: float):
        """Vào position với AUTO TP/SL trên OKX"""
        try:
            # Check max positions
            if len(self.positions) >= self.max_positions:
                logger.warning(f"Max positions reached ({self.max_positions}), skip")
                return
            
            contracts = self.calculate_position_size(current_price)
            if contracts <= 0:
                logger.warning("Position size <= 0, skip")
                return
            
            # Calculate SL/TP
            sl_price, tp_price = self.calculate_sl_tp_prices(current_price, direction)
            
            side = "buy" if direction == 'LONG' else "sell"
            
            logger.info(f"🎯 Entering {direction} position...")
            logger.info(f"   Price: ${current_price:,.2f}, Size: {contracts} contracts ({contracts * 0.01:.4f} BTC)")
            logger.info(f"   SL: ${sl_price:,.2f} | TP: ${tp_price:,.2f}")
            
            # Create order with AUTO SL/TP on OKX
            order = self.okx.create_order_with_sl_tp(
                self.symbol, 
                side, 
                contracts,
                sl_price=sl_price,
                tp_price=tp_price
            )
            
            if order and order.get('orderId'):
                # Add to positions list
                position = {
                    'order_id': order['orderId'],
                    'direction': direction,
                    'entry_price': current_price,
                    'entry_time': datetime.now(),
                    'size': contracts if direction == 'LONG' else -contracts,
                    'sl_price': sl_price,
                    'tp_price': tp_price,
                }
                self.positions.append(position)
                self.last_trade_time = datetime.now()
                
                logger.info(f"✅ Entered {direction} position!")
                logger.info(f"   Order ID: {order['orderId']}")
                logger.info(f"   Active positions: {len(self.positions)}/{self.max_positions}")
                logger.info(f"   ⚡ TP/SL sẽ TỰ ĐỘNG chốt trên OKX!")
        except Exception as e:
            logger.error(f"❌ Error entering position: {e}", exc_info=True)
    
    def check_positions_status(self):
        """Check if positions are still active on OKX"""
        try:
            okx_position = self.okx.get_position(self.symbol)
            okx_size = okx_position['size']
            
            # If OKX position is 0, clear all positions (TP/SL hit)
            if okx_size == 0 and len(self.positions) > 0:
                logger.info(f"🎯 All positions closed on OKX (TP/SL hit)")
                logger.info(f"   Cleared {len(self.positions)} positions from tracking")
                self.positions = []
        except Exception as e:
            logger.error(f"Error checking positions: {e}")
    
    def sync_positions_from_okx(self):
        """Sync positions from OKX to bot tracking"""
        try:
            okx_position = self.okx.get_position(self.symbol)
            okx_size = okx_position['size']
            
            if okx_size == 0:
                # No position on OKX
                if len(self.positions) > 0:
                    logger.info("🔄 OKX has no position, clearing bot tracking")
                    self.positions = []
                return
            
            # OKX has position
            direction = 'LONG' if okx_size > 0 else 'SHORT'
            entry_price = okx_position['entry_price']
            
            # Check if we already track this position
            if len(self.positions) == 0:
                # Create tracking entry
                sl_price, tp_price = self.calculate_sl_tp_prices(entry_price, direction)
                
                position = {
                    'order_id': 'synced_from_okx',
                    'direction': direction,
                    'entry_price': entry_price,
                    'entry_time': datetime.now(),  # Approximate
                    'size': int(abs(okx_size)),
                    'sl_price': sl_price,
                    'tp_price': tp_price,
                }
                self.positions.append(position)
                
                logger.info(f"🔄 Synced position from OKX:")
                logger.info(f"   Direction: {direction}")
                logger.info(f"   Size: {abs(okx_size)} contracts")
                logger.info(f"   Entry: ${entry_price:,.2f}")
                logger.info(f"   SL: ${sl_price:,.2f} | TP: ${tp_price:,.2f}")
            else:
                # Update existing position size if different
                total_tracked = sum(abs(p['size']) for p in self.positions)
                if abs(total_tracked - abs(okx_size)) > 0.1:
                    logger.warning(f"⚠️ Position size mismatch!")
                    logger.warning(f"   OKX: {abs(okx_size)} contracts")
                    logger.warning(f"   Bot: {total_tracked} contracts")
                    logger.warning(f"   Use /sync to force sync")
        
        except Exception as e:
            logger.error(f"Error syncing positions: {e}", exc_info=True)
    
    def trading_loop(self):
        """Main trading loop với AUTO TP/SL trên OKX"""
        logger.info("Trading loop started with AUTO TP/SL on OKX")
        logger.info(f"Max concurrent positions: {self.max_positions}")
        
        while self.running:
            try:
                self.last_check_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                # Fetch data from OKX
                df = self.okx.fetch_ohlcv(self.symbol, "1H", 1000)
                ticker = self.okx.fetch_ticker(self.symbol)
                current_price = ticker['last']
                
                # Check positions status (TP/SL hit?)
                self.check_positions_status()
                
                # Sync positions from OKX (in case of manual trades or restarts)
                if len(self.positions) == 0:
                    self.sync_positions_from_okx()
                
                # Generate signals
                signals, confidences, regimes, size_mult = self.model.predict(df)
                
                latest_signal = signals[-1]
                latest_confidence = confidences[-1]
                latest_regime = regimes[-1]
                
                regime_names = ['TRENDING', 'RANGING', 'VOLATILE', 'CALM']
                signal_names = {1: 'LONG', -1: 'SHORT', 0: 'HOLD'}
                
                self.last_signal = f"{signal_names[latest_signal]} ({latest_confidence:.0%})"
                
                logger.info(f"Signal: {self.last_signal}, Regime: {regime_names[latest_regime]}, Price: ${current_price:,.2f}")
                logger.info(f"Active positions: {len(self.positions)}/{self.max_positions}")
                
                # Auto trading logic - MULTIPLE POSITIONS
                if self.auto_trading:
                    if latest_signal == 1:  # LONG signal
                        self.enter_position('LONG', current_price)
                    elif latest_signal == -1:  # SHORT signal
                        self.enter_position('SHORT', current_price)
                
                # Sleep 1 hour
                time.sleep(3600)
                
            except Exception as e:
                logger.error(f"Error in trading loop: {e}", exc_info=True)
                time.sleep(60)
    
    def run(self):
        if not HAS_TELEGRAM:
            logger.error("python-telegram-bot not installed!")
            return
        
        logger.info("=" * 70)
        logger.info("TELEGRAM TRADING BOT - OKX DEMO")
        logger.info("=" * 70)
        
        # Start trading thread
        self.running = True
        self.trading_thread = threading.Thread(target=self.trading_loop, daemon=True)
        self.trading_thread.start()
        
        # Start Telegram bot with longer timeout
        from telegram.request import HTTPXRequest
        
        # Custom request with longer timeout
        request = HTTPXRequest(
            connection_pool_size=8,
            connect_timeout=30.0,  # 30 seconds
            read_timeout=30.0,
            write_timeout=30.0,
            pool_timeout=30.0
        )
        
        app = Application.builder().token(self.telegram_token).request(request).build()
        
        app.add_handler(CommandHandler("start", self.start_command))
        app.add_handler(CommandHandler("status", self.status_command))
        app.add_handler(CommandHandler("balance", self.balance_command))
        app.add_handler(CommandHandler("position", self.position_command))
        app.add_handler(CommandHandler("signals", self.signals_command))
        app.add_handler(CommandHandler("trade", self.trade_command))
        app.add_handler(CommandHandler("sync", self.sync_command))
        app.add_handler(CommandHandler("help", self.help_command))
        
        logger.info("Telegram bot started with OKX connection")
        logger.info("Send /start to begin")
        logger.info("Using extended timeout (30s) for slow connections")
        
        try:
            app.run_polling(allowed_updates=Update.ALL_TYPES)
        except Exception as e:
            logger.error(f"Bot stopped: {e}")
            logger.info("Tip: Check internet connection or try VPN if Telegram is blocked")


def main():
    bot = TradingBotOKX(symbol='BTC-USDT', position_size_pct=0.02)
    bot.run()


if __name__ == '__main__':
    main()
