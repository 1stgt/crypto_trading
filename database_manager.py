import sqlite3
import pandas as pd
from datetime import datetime

DB_NAME = "trades.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Create trade_history table with leverage
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trade_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            coin TEXT NOT NULL,
            action TEXT NOT NULL,
            price REAL NOT NULL,
            amount REAL NOT NULL,
            leverage INTEGER DEFAULT 1,
            reasoning TEXT,
            mode TEXT DEFAULT 'Paper'
        )
    ''')
    
    # Create open_positions table with leverage
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS open_positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            coin TEXT NOT NULL,
            avg_price REAL NOT NULL,
            amount REAL NOT NULL,
            leverage INTEGER DEFAULT 1,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            mode TEXT DEFAULT 'Paper'
        )
    ''')
    
    # Simple Migration: Add leverage column if table exists without it
    try:
        cursor.execute("ALTER TABLE trade_history ADD COLUMN leverage INTEGER DEFAULT 1")
        cursor.execute("ALTER TABLE open_positions ADD COLUMN leverage INTEGER DEFAULT 1")
    except:
        pass # Columns already exist
    
    # Initialize wallet with $10,000 if it's empty
    cursor.execute("SELECT COUNT(*) FROM wallet")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO wallet (id, balance) VALUES (1, 10000.0)")
    
    conn.commit()
    conn.close()

def log_trade(coin, action, price, amount, reasoning="", mode="Paper", leverage=1):
    """Saves a new trade to the trade_history table."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO trade_history (coin, action, price, amount, leverage, reasoning, mode)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (coin, action, price, amount, leverage, reasoning, mode))
    
    # If it's a paper trade, update the virtual wallet and positions
    if mode == "Paper":
        total_cost = price * amount
        if action.upper() == "BUY":
            cursor.execute("UPDATE wallet SET balance = balance - ? WHERE id = 1", (total_cost,))
            # Update open positions with specific leverage
            cursor.execute('''
                INSERT INTO open_positions (coin, avg_price, amount, leverage, mode)
                VALUES (?, ?, ?, ?, ?)
            ''', (coin, price, amount, leverage, mode))
        elif action.upper() == "SELL":
            cursor.execute("UPDATE wallet SET balance = balance + ? WHERE id = 1", (total_cost,))
            
    conn.commit()
    conn.close()

def get_all_trades():
    """Returns all trade history as a Pandas DataFrame."""
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM trade_history ORDER BY timestamp DESC", conn)
    conn.close()
    return df

def get_wallet_balance():
    """Gets the current virtual wallet balance."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM wallet WHERE id = 1")
    balance = cursor.fetchone()[0]
    conn.close()
    return balance

def update_wallet_balance(new_balance):
    """Manually update the virtual wallet balance."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE wallet SET balance = ? WHERE id = 1", (new_balance,))
    conn.commit()
    conn.close()

def get_open_positions(mode="Paper"):
    """Returns all currently open positions."""
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM open_positions WHERE mode = ?", conn, params=(mode,))
    conn.close()
    return df

def close_position(pos_id, current_price):
    """Closes an open position and logs the profit."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Get position details
    cursor.execute("SELECT coin, amount, avg_price, mode, leverage FROM open_positions WHERE id = ?", (pos_id,))
    pos = cursor.fetchone()
    if pos:
        coin, amount, buy_price, mode, leverage = pos
        # Log the SELL trade with the original leverage
        log_trade(coin, "SELL", current_price, amount, f"Closed Position ID: {pos_id}", mode, leverage)
        # Remove from open positions
        cursor.execute("DELETE FROM open_positions WHERE id = ?", (pos_id,))
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print(f"Database initialized. Current Balance: ${get_wallet_balance():,.2f}")
