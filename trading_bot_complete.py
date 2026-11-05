"""
Complete Trading Bot với TP/SL và Risk Management
Tích hợp đầy đủ chức năng từ h1_enhanced_production
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import os
import time
import logging
from datetime import datetime
from typing import Optional, Tuple
import pandas as pd
import numpy as np
from dotenv import load_dotenv
from dataclasses import dataclass

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trading_bot_complete.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

from algo_trading.ml import H1EnhancedModel
from okx_client_simple import OKXClient


@dataclass
class TradingConfig:
    """Cấu hình trading"""
    symbol: str = 'BTC-USDT'  # Sẽ tự động thêm -SWAP trong okx_client
    timeframe: str = '1H'
    
    # Risk Management
    risk_per_trade: float = 0.02  # 2% per trade
    max_position_size: int = 10  # Max 10 contracts (1 contract = 0.01 BTC = ~$100)
    
    # Stop Loss
    sl_pct: Optional[float] = 0.015  # 1.5% SL
    sl_atr_k: Optional[float] = None  # hoặc 2.0 * ATR
    
    # Take Profit
    tp_pct: Optional[float] = 0.03  # 3% TP
    tp_atr_k: Optional[float] = None  # hoặc 3.0 * ATR
    
    # Trailing Stop
    trailing_pct: Optional[float] = None  # 1% trailing
    
    # Bot behavior
    check_interval_sec: int = 3600  # Check mỗi 1 giờ
    cooldown_sec: int = 300  # 5 phút cooldown
    
    # Mode
    demo_mode: bool = True  # Demo trading
    auto_trading: bool = False  # Tự động trade


class CompleteTradingBot:
    """Bot trading hoàn chỉnh với TP/SL"""
    
    def __init__(self, config: TradingConfig):
        self.config = config
        
        # Load model
        logger.info("Loading H1 Enhanced Model...")
        self.model = H1EnhancedModel()
        if not self.model.load('h1_enhanced'):
            raise ValueError("Model not found!")
        
        # OKX client
        logger.info("Initializing OKX client...")
        self.okx = OKXClient(
            api_key=os.getenv('OKX_API_KEY'),
            api_secret=os.getenv('OKX_API_SECRET'),
            passphrase=os.getenv('OKX_PASSPHRASE'),
            demo_mode=config.demo_mode
        )
        
        # State
        self.position = None  # None, 'LONG', 'SHORT'
        self.entry_price = None
        self.entry_time = None
        self.position_size = 0.0
        self.stop_loss_price = None
        self.take_profit_price = None
        self.trailing_stop_price = None
        
        self.last_check_time = None
        self.last_trade_time = None
        
        logger.info(f"Bot initialized - Symbol: {config.symbol}")
        logger.info(f"Demo Mode: {config.demo_mode}")
        logger.info(f"Auto Trading: {config.auto_trading}")
    
    def calculate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """Tính ATR"""
        if len(df) < period:
            return 0.0
        
        high = df['high']
        low = df['low']
        close = df['close'].shift(1)
        
        tr1 = high - low
        tr2 = (high - close).abs()
        tr3 = (low - close).abs()
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        
        return atr.iloc[-1] if len(atr) > 0 else 0.0
    
    def calculate_position_size(self, current_price: float, df: pd.DataFrame) -> int:
        """
        Tính position size dựa trên risk management
        
        Returns:
            int: Số contracts (1 contract = 0.01 BTC = ~$100)
        """
        # Get balance
        balance = self.okx.fetch_balance()
        usdt_balance = balance.get('USDT', {}).get('free', 0)
        
        if usdt_balance <= 0:
            logger.warning("No USDT balance")
            return 0
        
        # Risk amount
        risk_amount = usdt_balance * self.config.risk_per_trade
        
        # Calculate SL distance
        sl_distance = None
        if self.config.sl_pct:
            sl_distance = current_price * self.config.sl_pct
        elif self.config.sl_atr_k:
            atr = self.calculate_atr(df)
            if atr > 0:
                sl_distance = self.config.sl_atr_k * atr
        
        # Calculate position size in BTC
        if sl_distance and sl_distance > 0:
            qty_btc = risk_amount / sl_distance
        else:
            qty_btc = risk_amount / current_price
        
        # Convert to contracts (1 contract = 0.01 BTC)
        contracts = int(qty_btc / 0.01)
        
        # Limit max position size
        if self.config.max_position_size:
            contracts = min(contracts, self.config.max_position_size)
        
        return max(contracts, 1)  # Minimum 1 contract
    
    def calculate_sl_tp(self, entry_price: float, direction: str, df: pd.DataFrame) -> Tuple[Optional[float], Optional[float]]:
        """Tính Stop Loss và Take Profit"""
        sl_price = None
        tp_price = None
        
        # Calculate ATR if needed
        atr = None
        if self.config.sl_atr_k or self.config.tp_atr_k:
            atr = self.calculate_atr(df)
        
        if direction == 'LONG':
            # Stop Loss
            if self.config.sl_pct:
                sl_price = entry_price * (1 - self.config.sl_pct)
            elif self.config.sl_atr_k and atr:
                sl_price = entry_price - self.config.sl_atr_k * atr
            
            # Take Profit
            if self.config.tp_pct:
                tp_price = entry_price * (1 + self.config.tp_pct)
            elif self.config.tp_atr_k and atr:
                tp_price = entry_price + self.config.tp_atr_k * atr
        
        elif direction == 'SHORT':
            # Stop Loss
            if self.config.sl_pct:
                sl_price = entry_price * (1 + self.config.sl_pct)
            elif self.config.sl_atr_k and atr:
                sl_price = entry_price + self.config.sl_atr_k * atr
            
            # Take Profit
            if self.config.tp_pct:
                tp_price = entry_price * (1 - self.config.tp_pct)
            elif self.config.tp_atr_k and atr:
                tp_price = entry_price - self.config.tp_atr_k * atr
        
        return sl_price, tp_price
    
    def check_sl_tp(self, current_price: float) -> Optional[str]:
        """Kiểm tra SL/TP có bị hit không"""
        if not self.position or not self.entry_price:
            return None
        
        if self.position == 'LONG':
            # Check SL
            if self.stop_loss_price and current_price <= self.stop_loss_price:
                return 'sl'
            # Check TP
            if self.take_profit_price and current_price >= self.take_profit_price:
                return 'tp'
            # Check Trailing Stop
            if self.trailing_stop_price and current_price <= self.trailing_stop_price:
                return 'trailing'
        
        elif self.position == 'SHORT':
            # Check SL
            if self.stop_loss_price and current_price >= self.stop_loss_price:
                return 'sl'
            # Check TP
            if self.take_profit_price and current_price <= self.take_profit_price:
                return 'tp'
            # Check Trailing Stop
            if self.trailing_stop_price and current_price >= self.trailing_stop_price:
                return 'trailing'
        
        return None
    
    def update_trailing_stop(self, current_price: float):
        """Cập nhật trailing stop"""
        if not self.config.trailing_pct or not self.position:
            return
        
        if self.position == 'LONG':
            new_trailing = current_price * (1 - self.config.trailing_pct)
            if self.trailing_stop_price is None or new_trailing > self.trailing_stop_price:
                self.trailing_stop_price = new_trailing
                logger.info(f"📈 Updated trailing stop: ${new_trailing:,.2f}")
        
        elif self.position == 'SHORT':
            new_trailing = current_price * (1 + self.config.trailing_pct)
            if self.trailing_stop_price is None or new_trailing < self.trailing_stop_price:
                self.trailing_stop_price = new_trailing
                logger.info(f"📉 Updated trailing stop: ${new_trailing:,.2f}")
    
    def enter_position(self, direction: str, df: pd.DataFrame):
        """Vào position mới"""
        if self.position:
            logger.warning(f"Already in {self.position} position")
            return
        
        # Get current price
        ticker = self.okx.fetch_ticker(self.config.symbol)
        current_price = ticker['last']
        
        # Calculate position size (contracts)
        contracts = self.calculate_position_size(current_price, df)
        if contracts <= 0:
            logger.warning("Position size <= 0, skip")
            return
        
        # Calculate SL/TP
        sl_price, tp_price = self.calculate_sl_tp(current_price, direction, df)
        
        # Place order
        try:
            side = "buy" if direction == 'LONG' else "sell"
            
            logger.info(f"🎯 Entering {direction} position...")
            logger.info(f"   Price: ${current_price:,.2f}")
            logger.info(f"   Size: {contracts} contracts ({contracts * 0.01:.4f} BTC)")
            if sl_price:
                logger.info(f"   SL: ${sl_price:,.2f} ({abs(current_price - sl_price) / current_price * 100:.2f}%)")
            if tp_price:
                logger.info(f"   TP: ${tp_price:,.2f} ({abs(tp_price - current_price) / current_price * 100:.2f}%)")
            
            order = self.okx.create_market_order(self.config.symbol, side, contracts)
            
            if order:
                self.position = direction
                self.entry_price = current_price
                self.entry_time = datetime.now()
                self.position_size = contracts if direction == 'LONG' else -contracts
                self.stop_loss_price = sl_price
                self.take_profit_price = tp_price
                self.trailing_stop_price = None
                self.last_trade_time = datetime.now()
                
                logger.info(f"✅ Entered {direction} position successfully!")
                logger.info(f"   Order ID: {order.get('orderId')}")
            else:
                logger.error("❌ Failed to enter position")
        
        except Exception as e:
            logger.error(f"❌ Error entering position: {e}")
    
    def exit_position(self, reason: str = "signal"):
        """Thoát position"""
        if not self.position:
            logger.warning("No position to exit")
            return
        
        try:
            # Get current price
            ticker = self.okx.fetch_ticker(self.config.symbol)
            current_price = ticker['last']
            
            # Calculate P&L
            if self.position == 'LONG':
                pnl_pct = (current_price / self.entry_price - 1) * 100
            else:
                pnl_pct = (self.entry_price / current_price - 1) * 100
            
            # Place exit order
            side = "sell" if self.position == 'LONG' else "buy"
            contracts = abs(self.position_size)
            
            logger.info(f"🚪 Exiting {self.position} position ({reason})...")
            logger.info(f"   Entry: ${self.entry_price:,.2f}")
            logger.info(f"   Exit: ${current_price:,.2f}")
            logger.info(f"   Size: {contracts} contracts")
            logger.info(f"   P&L: {pnl_pct:+.2f}%")
            
            order = self.okx.create_market_order(self.config.symbol, side, contracts)
            
            if order:
                logger.info(f"✅ Exited {self.position} position successfully!")
                logger.info(f"   Order ID: {order.get('orderId')}")
                
                # Reset state
                self.position = None
                self.entry_price = None
                self.entry_time = None
                self.position_size = 0
                self.stop_loss_price = None
                self.take_profit_price = None
                self.trailing_stop_price = None
                self.last_trade_time = datetime.now()
            else:
                logger.error("❌ Failed to exit position")
        
        except Exception as e:
            logger.error(f"❌ Error exiting position: {e}")
    
    def check_cooldown(self) -> bool:
        """Kiểm tra cooldown"""
        if not self.last_trade_time:
            return True
        
        elapsed = (datetime.now() - self.last_trade_time).total_seconds()
        return elapsed >= self.config.cooldown_sec
    
    def run_once(self):
        """Chạy một vòng kiểm tra"""
        try:
            self.last_check_time = datetime.now()
            
            logger.info("=" * 70)
            logger.info(f"Checking at {self.last_check_time.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Fetch data
            df = self.okx.fetch_ohlcv(self.config.symbol, self.config.timeframe, 1000)
            
            if df.empty:
                logger.warning("No data fetched")
                return
            
            # Get current price
            ticker = self.okx.fetch_ticker(self.config.symbol)
            current_price = ticker['last']
            
            logger.info(f"Current price: ${current_price:,.2f}")
            
            # Check SL/TP if in position
            if self.position:
                logger.info(f"Current position: {self.position}")
                logger.info(f"Entry price: ${self.entry_price:,.2f}")
                
                # Calculate current P&L
                if self.position == 'LONG':
                    pnl_pct = (current_price / self.entry_price - 1) * 100
                else:
                    pnl_pct = (self.entry_price / current_price - 1) * 100
                
                logger.info(f"Current P&L: {pnl_pct:+.2f}%")
                
                # Update trailing stop
                self.update_trailing_stop(current_price)
                
                # Check SL/TP
                exit_reason = self.check_sl_tp(current_price)
                if exit_reason:
                    logger.info(f"🎯 {exit_reason.upper()} hit!")
                    self.exit_position(exit_reason)
                    return
            
            # Generate signals
            signals, confidences, regimes, size_mult = self.model.predict(df)
            
            latest_signal = signals[-1]
            latest_confidence = confidences[-1]
            latest_regime = regimes[-1]
            
            regime_names = ['TRENDING', 'RANGING', 'VOLATILE', 'CALM']
            signal_names = {1: 'LONG', -1: 'SHORT', 0: 'HOLD'}
            
            logger.info(f"Signal: {signal_names[latest_signal]} ({latest_confidence:.1%})")
            logger.info(f"Regime: {regime_names[latest_regime]}")
            
            # Auto trading logic
            if self.config.auto_trading and self.check_cooldown():
                if latest_signal == 1 and not self.position:
                    # Enter LONG
                    self.enter_position('LONG', df)
                
                elif latest_signal == -1 and not self.position:
                    # Enter SHORT
                    self.enter_position('SHORT', df)
                
                elif latest_signal == 0 and self.position:
                    # Exit position
                    self.exit_position('signal_exit')
                
                elif latest_signal == 1 and self.position == 'SHORT':
                    # Reverse: Exit SHORT, Enter LONG
                    self.exit_position('reverse')
                    time.sleep(2)  # Wait a bit
                    self.enter_position('LONG', df)
                
                elif latest_signal == -1 and self.position == 'LONG':
                    # Reverse: Exit LONG, Enter SHORT
                    self.exit_position('reverse')
                    time.sleep(2)
                    self.enter_position('SHORT', df)
            
            logger.info("=" * 70)
        
        except Exception as e:
            logger.error(f"Error in run_once: {e}", exc_info=True)
    
    def run(self):
        """Chạy bot loop"""
        logger.info("=" * 70)
        logger.info("COMPLETE TRADING BOT - WITH TP/SL")
        logger.info("=" * 70)
        logger.info(f"Symbol: {self.config.symbol}")
        logger.info(f"Timeframe: {self.config.timeframe}")
        logger.info(f"Risk per trade: {self.config.risk_per_trade * 100}%")
        logger.info(f"SL: {self.config.sl_pct * 100 if self.config.sl_pct else 'ATR'}%")
        logger.info(f"TP: {self.config.tp_pct * 100 if self.config.tp_pct else 'ATR'}%")
        logger.info(f"Demo mode: {self.config.demo_mode}")
        logger.info(f"Auto trading: {self.config.auto_trading}")
        logger.info(f"Check interval: {self.config.check_interval_sec}s")
        logger.info("=" * 70)
        logger.info("Press Ctrl+C to stop")
        logger.info("")
        
        try:
            while True:
                self.run_once()
                
                logger.info(f"💤 Sleeping {self.config.check_interval_sec}s...")
                time.sleep(self.config.check_interval_sec)
        
        except KeyboardInterrupt:
            logger.info("\n⚠️ Stopping bot...")
            
            if self.position:
                logger.warning(f"⚠️ Still in {self.position} position!")
                logger.warning("Please close position manually if needed")
        
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
        
        finally:
            logger.info("Bot stopped")


def main():
    # Load config from env
    config = TradingConfig(
        symbol=os.getenv('SYMBOL', 'BTC-USDT'),
        timeframe=os.getenv('INTERVAL', '1H'),
        risk_per_trade=float(os.getenv('RISK_PER_TRADE', '0.02')),
        sl_pct=float(os.getenv('SL_PCT', '0.015')) if os.getenv('SL_PCT') else None,
        tp_pct=float(os.getenv('TP_PCT', '0.03')) if os.getenv('TP_PCT') else None,
        demo_mode=os.getenv('USE_SIMULATED_TRADING', 'true').lower() == 'true',
        auto_trading=os.getenv('AUTO_TRADING', 'false').lower() == 'true',
        check_interval_sec=int(os.getenv('CHECK_INTERVAL_SEC', '3600')),
    )
    
    bot = CompleteTradingBot(config)
    bot.run()


if __name__ == '__main__':
    main()
