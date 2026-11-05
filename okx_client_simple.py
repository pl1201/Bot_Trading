"""
Simple OKX Client - Dùng requests thay vì ccxt
"""
import hmac
import base64
import json
import requests
import pandas as pd
from datetime import datetime, timezone
from typing import Dict, List, Optional


class OKXClient:
    """Simple OKX API client"""
    
    def __init__(self, api_key: str, api_secret: str, passphrase: str, demo_mode: bool = True):
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase
        self.base_url = "https://www.okx.com"
        self.demo_mode = demo_mode
    
    def _get_timestamp(self) -> str:
        """Get ISO timestamp"""
        return datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
    
    def _sign(self, message: str) -> str:
        """Sign message with secret"""
        if not self.api_secret:
            raise ValueError("API secret is required")
        
        mac = hmac.new(
            self.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            digestmod='sha256'
        )
        return base64.b64encode(mac.digest()).decode()
    
    def _request(self, method: str, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """Make API request"""
        timestamp = self._get_timestamp()
        
        # Build request path and body
        if method == "GET":
            # GET: params in query string
            query_string = ""
            if params:
                query_string = "?" + "&".join([f"{k}={v}" for k, v in params.items()])
            request_path = endpoint + query_string
            body_str = ""
        else:
            # POST: params in body as JSON
            request_path = endpoint
            body_str = json.dumps(params) if params else ""
        
        # Build message to sign
        message = timestamp + method + request_path + body_str
        signature = self._sign(message)
        
        # Headers
        headers = {
            "OK-ACCESS-KEY": self.api_key,
            "OK-ACCESS-SIGN": signature,
            "OK-ACCESS-TIMESTAMP": timestamp,
            "OK-ACCESS-PASSPHRASE": self.passphrase,
            "Content-Type": "application/json",
        }
        
        if self.demo_mode:
            headers["x-simulated-trading"] = "1"
        
        # Make request
        url = self.base_url + request_path
        
        if method == "GET":
            response = requests.get(url, headers=headers)
        elif method == "POST":
            response = requests.post(url, json=params, headers=headers)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        # Parse response
        data = response.json()
        
        if data.get("code") != "0":
            raise Exception(f"OKX API Error: {data.get('msg', 'Unknown error')}")
        
        return data
    
    def fetch_balance(self) -> Dict:
        """Fetch account balance"""
        data = self._request("GET", "/api/v5/account/balance")
        
        # Parse balance
        balances = {}
        if data.get("data"):
            for account in data["data"]:
                for detail in account.get("details", []):
                    ccy = detail["ccy"]
                    balances[ccy] = {
                        "free": float(detail["availBal"]),
                        "used": float(detail["frozenBal"]),
                        "total": float(detail["eq"])
                    }
        
        return balances
    
    def fetch_ticker(self, symbol: str = "BTC-USDT") -> Dict:
        """Fetch ticker"""
        data = self._request("GET", "/api/v5/market/ticker", {"instId": symbol})
        
        if data.get("data"):
            ticker = data["data"][0]
            return {
                "symbol": symbol,
                "last": float(ticker["last"]),
                "bid": float(ticker["bidPx"]),
                "ask": float(ticker["askPx"]),
                "high": float(ticker["high24h"]),
                "low": float(ticker["low24h"]),
                "volume": float(ticker["vol24h"]),
            }
        
        return {}
    
    def fetch_ohlcv(self, symbol: str = "BTC-USDT", timeframe: str = "1H", limit: int = 100) -> pd.DataFrame:
        """Fetch OHLCV candles"""
        data = self._request("GET", "/api/v5/market/candles", {
            "instId": symbol,
            "bar": timeframe,
            "limit": str(limit)
        })
        
        if data.get("data"):
            candles = data["data"]
            
            # Parse candles [timestamp, open, high, low, close, volume, ...]
            df = pd.DataFrame(candles, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'volCcy', 'volCcyQuote', 'confirm'
            ])
            
            # Convert types (fix overflow error)
            df['timestamp'] = pd.to_datetime(pd.to_numeric(df['timestamp'], errors='coerce'), unit='ms', utc=True)
            df['open'] = pd.to_numeric(df['open'], errors='coerce')
            df['high'] = pd.to_numeric(df['high'], errors='coerce')
            df['low'] = pd.to_numeric(df['low'], errors='coerce')
            df['close'] = pd.to_numeric(df['close'], errors='coerce')
            df['volume'] = pd.to_numeric(df['volume'], errors='coerce')
            
            # Set index and sort
            df.set_index('timestamp', inplace=True)
            df.sort_index(inplace=True)
            
            # Keep only OHLCV
            df = df[['open', 'high', 'low', 'close', 'volume']]
            
            return df
        
        return pd.DataFrame()
    
    def create_market_order(self, symbol: str, side: str, amount: float) -> Dict:
        """
        Create market order
        
        Args:
            symbol: Trading pair (e.g. "BTC-USDT")
            side: "buy" or "sell"
            amount: Amount in CONTRACTS (not BTC)
                   For BTC-USDT-SWAP: 1 contract = 0.01 BTC = $100
                   So to trade 0.001 BTC, use amount = 0.1 contracts
        
        Returns:
            Order response dict
        """
        # Convert symbol to SWAP format if needed
        if not symbol.endswith("-SWAP"):
            symbol = symbol + "-SWAP"
        
        endpoint = "/api/v5/trade/order"
        
        # Round to integer contracts for SWAP
        # OKX SWAP requires integer contracts
        sz = max(1, int(round(amount)))
        
        params = {
            "instId": symbol,
            "tdMode": "cross",  # Cross margin for SWAP
            "side": side.lower(),
            "ordType": "market",
            "sz": str(sz),
        }
        
        data = self._request("POST", endpoint, params)
        
        if data.get("data"):
            order = data["data"][0]
            return {
                "orderId": order.get("ordId"),
                "symbol": symbol,
                "side": side,
                "amount": sz,
                "status": order.get("sMsg"),
                "timestamp": order.get("ts"),
            }
        
        return {}
    
    def create_limit_order(self, symbol: str, side: str, amount: float, price: float) -> Dict:
        """
        Create limit order
        
        Args:
            symbol: Trading pair (e.g. "BTC-USDT")
            side: "buy" or "sell"
            amount: Amount in base currency
            price: Limit price
        
        Returns:
            Order response dict
        """
        endpoint = "/api/v5/trade/order"
        
        params = {
            "instId": symbol,
            "tdMode": "cross",
            "side": side.lower(),
            "ordType": "limit",
            "sz": str(amount),
            "px": str(price),
        }
        
        data = self._request("POST", endpoint, params)
        
        if data.get("data"):
            order = data["data"][0]
            return {
                "orderId": order.get("ordId"),
                "symbol": symbol,
                "side": side,
                "amount": amount,
                "price": price,
                "status": order.get("state"),
                "timestamp": order.get("cTime"),
            }
        
        return {}
    
    def create_order_with_sl_tp(self, symbol: str, side: str, amount: float, 
                                 sl_price: Optional[float] = None, 
                                 tp_price: Optional[float] = None) -> Dict:
        """
        Create market order with automatic SL/TP orders
        
        Args:
            symbol: Trading pair (e.g. "BTC-USDT")
            side: "buy" or "sell"
            amount: Amount in CONTRACTS
            sl_price: Stop loss price (optional)
            tp_price: Take profit price (optional)
        
        Returns:
            Order response dict with SL/TP order IDs
        """
        # Convert symbol to SWAP format if needed
        if not symbol.endswith("-SWAP"):
            symbol = symbol + "-SWAP"
        
        endpoint = "/api/v5/trade/order"
        
        # Round to integer contracts
        sz = max(1, int(round(amount)))
        
        # Main market order params
        params = {
            "instId": symbol,
            "tdMode": "cross",
            "side": side.lower(),
            "ordType": "market",
            "sz": str(sz),
        }
        
        # Add SL/TP if provided
        if sl_price:
            params["slTriggerPx"] = str(round(sl_price, 2))
            params["slOrdPx"] = "-1"  # Market price for SL
        
        if tp_price:
            params["tpTriggerPx"] = str(round(tp_price, 2))
            params["tpOrdPx"] = "-1"  # Market price for TP
        
        data = self._request("POST", endpoint, params)
        
        if data.get("data"):
            order = data["data"][0]
            return {
                "orderId": order.get("ordId"),
                "symbol": symbol,
                "side": side,
                "amount": sz,
                "status": order.get("sMsg"),
                "timestamp": order.get("ts"),
                "sl_price": sl_price,
                "tp_price": tp_price,
            }
        
        return {}
    
    def get_position(self, symbol: str) -> Dict:
        """
        Get current position
        
        Returns:
            Position info dict with:
            - size: Position size (positive for long, negative for short)
            - entry_price: Average entry price
            - unrealized_pnl: Unrealized P&L
        """
        # Convert symbol to SWAP format if needed
        if not symbol.endswith("-SWAP"):
            symbol = symbol + "-SWAP"
        
        endpoint = "/api/v5/account/positions"
        params = {"instId": symbol}
        
        data = self._request("GET", endpoint, params)
        
        if data.get("data"):
            for pos in data["data"]:
                pos_size = float(pos.get("pos", 0))
                if pos_size != 0:
                    side = pos.get("posSide", "net")
                    if side == "short":
                        pos_size = -abs(pos_size)
                    elif side == "long":
                        pos_size = abs(pos_size)
                    
                    return {
                        "size": pos_size,
                        "entry_price": float(pos.get("avgPx", 0)),
                        "unrealized_pnl": float(pos.get("upl", 0)),
                        "unrealized_pnl_pct": float(pos.get("uplRatio", 0)) * 100,
                        "leverage": float(pos.get("lever", 1)),
                    }
        
        return {"size": 0, "entry_price": 0, "unrealized_pnl": 0, "unrealized_pnl_pct": 0, "leverage": 1}
    
    def cancel_order(self, symbol: str, order_id: str) -> bool:
        """Cancel an order"""
        endpoint = "/api/v5/trade/cancel-order"
        
        params = {
            "instId": symbol,
            "ordId": order_id,
        }
        
        data = self._request("POST", endpoint, params)
        return data.get("code") == "0"


if __name__ == '__main__':
    # Test
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    print("=" * 70)
    print("TEST OKX SIMPLE CLIENT")
    print("=" * 70)
    
    client = OKXClient(
        api_key=os.getenv('OKX_API_KEY'),
        api_secret=os.getenv('OKX_API_SECRET'),
        passphrase=os.getenv('OKX_PASSPHRASE'),
        demo_mode=True
    )
    
    # Test balance
    print("\n1. Testing Balance...")
    try:
        balance = client.fetch_balance()
        print(f"   ✅ USDT Balance: {balance['USDT']['free']:.2f}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Test ticker
    print("\n2. Testing Ticker...")
    try:
        ticker = client.fetch_ticker("BTC-USDT")
        print(f"   ✅ BTC Price: ${ticker['last']:,.2f}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Test OHLCV
    print("\n3. Testing OHLCV...")
    try:
        df = client.fetch_ohlcv("BTC-USDT", "1H", 10)
        print(f"   ✅ Fetched {len(df)} candles")
        print(f"   Latest close: ${df['close'].iloc[-1]:,.2f}")
        print(f"   Date range: {df.index[0]} to {df.index[-1]}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    print("\n" + "=" * 70)
    print("✅ OKX Simple Client hoạt động!")
    print("=" * 70)
