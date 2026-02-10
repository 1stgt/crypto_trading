import os
import sqlite3
import pandas as pd
from pydantic import BaseModel
from google import genai
from dotenv import load_dotenv

load_dotenv()

# Configuration
BOT_DB = "crypto_bot.db"

# Define Pydantic model for structured output
class TradingSignal(BaseModel):
    action: str
    confidence: int
    reasoning: str

def fetch_recent_history(coin_symbol):
    """
    Queries the SQLite price_history table and returns the last 12 entries (1 hour of data).
    """
    try:
        conn = sqlite3.connect(BOT_DB)
        # We assume coin_symbol is stored in uppercase as per data_collector.py
        query = """
            SELECT price_usd, timestamp 
            FROM price_history 
            WHERE coin_symbol = ? 
            ORDER BY timestamp DESC 
            LIMIT 12
        """
        df = pd.read_sql_query(query, conn, params=(coin_symbol.upper(),))
        conn.close()
        
        if df.empty:
            return []
            
        # Return in chronological order (oldest to newest)
        return df.iloc[::-1].to_dict('records')
    except Exception as e:
        print(f"Database error: {e}")
        return []

def get_trading_signal(coin_symbol):
    """
    Analyzes the last 1 hour of price data using Gemini.
    """
    history = fetch_recent_history(coin_symbol)
    
    if not history:
        return {"error": f"No recent price history found for {coin_symbol} in {BOT_DB}."}

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return {"error": "API Key not found in environment variables."}

    client = genai.Client(api_key=api_key)
    
    # Format history for the prompt
    history_str = "\n".join([f"{item['timestamp']}: ${item['price_usd']:,.2f}" for item in history])
    
    prompt = f"""
    Analyze the following 1-hour price trend for {coin_symbol}:
    {history_str}

    Is the price stabilizing, crashing, or pumping? 
    Return a trading decision.
    
    Strictly return a JSON object with:
    'action' (BUY/SELL/HOLD),
    'confidence' (0-100),
    'reasoning' (Brief explanation of the trend).
    """

    try:
        response = client.models.generate_content(
            model='gemini-flash-latest',
            contents=prompt,
            config={
                'response_mime_type': 'application/json',
                'response_schema': TradingSignal,
            }
        )
        return response.parsed
    except Exception as e:
        if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
            # Quota hit - return a local technical fallback
            return local_technical_fallback(history, coin_symbol)
        return {"error": f"AI Signal Error: {str(e)}"}

def local_technical_fallback(history, coin_symbol):
    """
    Standard technical analysis fallback for when AI quota is hit.
    """
    if len(history) < 2:
        return {"action": "HOLD", "confidence": 50, "reasoning": "Insufficient data for technical analysis fallback."}
    
    first_price = history[0]['price_usd']
    last_price = history[-1]['price_usd']
    pct_change = ((last_price - first_price) / first_price) * 100
    
    if pct_change > 1.5:
        action = "BUY"
        confidence = min(int(abs(pct_change) * 30), 85)
        reasoning = f"(AI Offline) Technical Pump: Price up {pct_change:.1f}% in the last hour. Strong upward momentum detected."
    elif pct_change < -1.5:
        action = "SELL"
        confidence = min(int(abs(pct_change) * 30), 85)
        reasoning = f"(AI Offline) Technical Drop: Price down {abs(pct_change):.1f}% in the last hour. Bearish pressure observed."
    else:
        action = "HOLD"
        confidence = 70
        reasoning = f"(AI Offline) Consolidation: Price variant within {pct_change:+.1f}%. Market is searching for clear direction."
        
    return {"action": action, "confidence": confidence, "reasoning": reasoning}

def analyze_market(price, change_24h, risk_tolerance):
    """
    Legacy function preserved for compatibility with existing app logic, 
    but now internally uses the structured TradingSignal schema.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    client = genai.Client(api_key=api_key)
    
    prompt = f"""
    Market Data:
    - Current Price: ${price:,.2f}
    - 24h Change: {change_24h:.2f}%
    - Risk Tolerance: {risk_tolerance}

    Provide action (BUY/SELL/HOLD), confidence (0-100), and reasoning.
    """

    try:
        response = client.models.generate_content(
            model='gemini-flash-latest',
            contents=prompt,
            config={
                'response_mime_type': 'application/json',
                'response_schema': TradingSignal,
            }
        )
        # Adapt matching for legacy 'decision' field if needed by the app
        res = response.parsed
        return res
    except Exception as e:
        return {"error": f"AI Brain Error: {str(e)}"}

if __name__ == "__main__":
    # Test block
    print("Testing Signal for BTC...")
    print(get_trading_signal("BTC"))
