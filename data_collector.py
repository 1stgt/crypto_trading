import sqlite3
import time
import requests
from datetime import datetime

# Configuration
DB_NAME = "crypto_bot.db"
COINGECKO_BASE_URL = "https://api.coingecko.com/api/v3"
TRACKED_COINS = ["bitcoin", "ethereum", "binancecoin", "solana", "cardano"]

def init_db():
    """Initializes the SQLite database and creates the price_history table."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            coin_symbol TEXT,
            price_usd REAL,
            volume REAL DEFAULT 0,
            change_24h REAL
        )
    ''')
    # Schema Migration: Add volume if it hasn't been added yet
    try:
        cursor.execute("ALTER TABLE price_history ADD COLUMN volume REAL DEFAULT 0")
    except:
        pass
        
    conn.commit()
    conn.close()

def fetch_and_store_data():
    """Fetches market data from CoinGecko and stores it in the database."""
    url = f"{COINGECKO_BASE_URL}/coins/markets"
    params = {
        "vs_currency": "usd",
        "ids": ",".join(TRACKED_COINS),
        "order": "market_cap_desc",
        "sparkline": False,
        "price_change_percentage": "24h"
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            for coin in data:
                symbol = coin['symbol'].upper()
                price = coin['current_price']
                change = coin['price_change_percentage_24h']
                volume = coin.get('total_volume', 0)
                
                cursor.execute('''
                    INSERT INTO price_history (timestamp, coin_symbol, price_usd, volume, change_24h)
                    VALUES (?, ?, ?, ?, ?)
                ''', (timestamp, symbol, price, volume, change))
            
            conn.commit()
            conn.close()
            print(f"Data saved for {timestamp}")
            return True
        elif response.status_code == 429:
            print("Rate limit hit. Waiting for retry...")
            return False
        else:
            print(f"API Error: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"Error during data collection: {str(e)}")
        return False

def backfill_data():
    """Fetches 24h of historical data for tracked coins to initialize the DB."""
    init_db()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    print("Checking for existing data...")
    for coin_id in TRACKED_COINS:
        cursor.execute("SELECT COUNT(*) FROM price_history WHERE coin_symbol = ?", (coin_id.upper()[:3],))
        if cursor.fetchone()[0] > 0:
            print(f"Skipping backfill for {coin_id} (data exists)")
            continue
            
        print(f"Backfilling 24h history for {coin_id}...")
        url = f"{COINGECKO_BASE_URL}/coins/{coin_id}/market_chart"
        params = {"vs_currency": "usd", "days": "1"}
        
        try:
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                hist_data = resp.json().get("prices", [])
                symbol = coin_id.upper()[:3]
                for timestamp, price in hist_data:
                    dt = datetime.fromtimestamp(timestamp/1000.0).strftime("%Y-%m-%d %H:%M:%S")
                    cursor.execute('''
                        INSERT INTO price_history (timestamp, coin_symbol, price_usd, change_24h)
                        VALUES (?, ?, ?, ?)
                    ''', (dt, symbol, price, 0.0))
                print(f"Inserted {len(hist_data)} points for {coin_id}")
            time.sleep(2) # Avoid immediate rate limit
        except Exception as e:
            print(f"Backfill error for {coin_id}: {e}")
            
    conn.commit()
    conn.close()

def main():
    print("Initializing background data collector...")
    backfill_data()
    
    print("Starting 1-minute live tracking loop...")
    while True:
        success = fetch_and_store_data()
        
        if success:
            # Wait for 1 minute (60 seconds) as requested
            time.sleep(60)
        else:
            # If failed (API error or connection), wait 20 seconds before retrying
            print("Retrying in 20 seconds...")
            time.sleep(20)

if __name__ == "__main__":
    main()
