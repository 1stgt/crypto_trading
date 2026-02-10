import requests
import pandas as pd
import time
from one_inch_wrapper import OneInchService

COINGECKO_BASE_URL = "https://api.coingecko.com/api/v3"

def get_coins_list(per_page=100):
    """Get list of coins with extended market data and rate limit handling."""
    url = f"{COINGECKO_BASE_URL}/coins/markets"
    params = {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": per_page,
        "page": 1,
        "sparkline": False,
        "price_change_percentage": "1h,24h,7d"
    }
    try:
        response = requests.get(url, params=params, timeout=15)
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 429:
            return "RATE_LIMIT"
        return []
    except Exception:
        return []

def get_coin_price(coin_id):
    """Get current price for UI display."""
    coins = get_coins_list(per_page=50)
    if isinstance(coins, list):
        coin_data = next((c for c in coins if c['id'] == coin_id), None)
        if coin_data:
            return coin_data.get("current_price", 0)
    return 0

def get_dex_price(token_address, chain_id=1):
    """Fetches real-time execution price from 1inch DEX."""
    try:
        service = OneInchService(chain_id=chain_id)
        usdc_address = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
        amount_to_quote = 10**18 
        result = service.get_quote(from_token=token_address, to_token=usdc_address, amount=amount_to_quote)
        if isinstance(result, dict) and "dstAmount" in result:
            return float(result['dstAmount']) / 10**6
    except Exception:
        pass
    return 0

def get_historical_data(coin_id, days=30):
    """Get historical market data with flexible range (1, 7, 30, 90, 365, max)."""
    url = f"{COINGECKO_BASE_URL}/coins/{coin_id}/market_chart"
    params = {
        "vs_currency": "usd",
        "days": days,
        "interval": "daily" if days > 1 else "hourly"
    }
    try:
        response = requests.get(url, params=params, timeout=15)
        if response.status_code == 200:
            data = response.json()
            prices = data.get("prices", [])
            df = pd.DataFrame(prices, columns=["timestamp", "price"])
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            return df
    except Exception:
        pass
    return pd.DataFrame()
