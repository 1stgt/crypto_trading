import streamlit as st
import pandas as pd
import io
import os
import sqlite3
import plotly.graph_objects as go
from datetime import datetime
from dotenv import load_dotenv
from streamlit_autorefresh import st_autorefresh
from crypto_data import get_coins_list, get_historical_data, get_dex_price
from database_manager import init_db, log_trade, get_all_trades, get_wallet_balance, update_wallet_balance, get_open_positions, close_position
from ai_brain import get_trading_signal
from one_inch_wrapper import OneInchService
# from wallet_bridge import generate_trust_wallet_link
from trust_wallet_bridge import generate_buy_link

st.markdown("""
<style>
    .binance-card {
        background: linear-gradient(135deg, #1e2329 0%, #0b0e11 100%);
        border-radius: 12px;
        padding: 20px;
        border: 1px solid #30363d;
        color: #eaecef;
        font-family: 'Inter', sans-serif;
        box-shadow: 0 4px 20px rgba(0,0,0,0.5);
        margin-bottom: 20px;
    }
    .pnl-plus { color: #02c076; font-size: 2.2rem; font-weight: 800; }
    .pnl-minus { color: #f84960; font-size: 2.2rem; font-weight: 800; }
    .binance-label { color: #848e9c; font-size: 0.85rem; text-transform: uppercase; }
    .binance-value { color: #eaecef; font-size: 1.1rem; font-weight: 500; }
    .gold-text { color: #f0b90b; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# --- INITIALIZATION ---
load_dotenv()
init_db()

st.set_page_config(
    page_title="Gravity Pulse | Crypto Terminal",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- STYLING ---
st.markdown("""
<style>
    .main { background-color: #0d1117; color: #c9d1d9; }
    .stMetric { background-color: #1e2130; padding: 15px; border-radius: 10px; border: 1px solid #30363d; }
    div[data-testid="stExpander"] { border: 1px solid #30363d; border-radius: 10px; }
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { height: 50px; white-space: pre-wrap; background-color: transparent; border-radius: 4px 4px 0px 0px; gap: 1px; padding-top: 10px; padding-bottom: 10px; border: none; }
    .stTabs [aria-selected="true"] { background-color: #1e2130; border-bottom: 2px solid #00ff7f !important; }
</style>
""", unsafe_allow_html=True)

# --- SIDEBAR ---
st.sidebar.title("🔐 Terminal Access")
api_key = st.sidebar.text_input("Gemini API Key", value=os.getenv("GEMINI_API_KEY", ""), type="password")
if api_key: os.environ["GEMINI_API_KEY"] = api_key

mode = st.sidebar.toggle("Live Trading Mode", value=False)
mode_str = "Live" if mode else "Paper"

user_wallet = ""
if mode:
    user_wallet = st.sidebar.text_input("Public Wallet Address", placeholder="0x...")
    if not user_wallet: st.sidebar.warning("Live Mode requires a wallet address.")

st.sidebar.divider()
st.sidebar.info(f"Connected: **{mode_str} Mode**")
st.sidebar.caption(f"Last Sync: {datetime.now().strftime('%H:%M:%S')}")

# --- CACHED DATA FETCHING ---
@st.cache_data(ttl=60)
def fetch_pulse_history(coin_id, symbol):
    """Fetches high-density history from local DB combined with CoinGecko."""
    try:
        conn = sqlite3.connect("crypto_bot.db")
        # Query last 100 entries for the target symbol
        query = "SELECT timestamp, price_usd as price FROM price_history WHERE UPPER(coin_symbol) = ? ORDER BY timestamp DESC LIMIT 100"
        db_df = pd.read_sql_query(query, conn, params=(symbol.upper(),))
        conn.close()
        if not db_df.empty:
            db_df['timestamp'] = pd.to_datetime(db_df['timestamp'])
            return db_df.iloc[::-1]
    except: pass
    return get_historical_data(coin_id, days=1)

@st.cache_data(ttl=60)
def fetch_market_overview():
    """Cached overview list for the main table."""
    return get_coins_list(per_page=100)

# --- REFRESH TOKEN ---
st_autorefresh(interval=60000, key="datarefresh")

# --- MAIN DASHBOARD ---
tab1, tab2, tab3 = st.tabs(["⚡ Market Overview", "🤖 AI Trading Bot", "📊 Analytics"])

all_coins_raw = fetch_market_overview()

with tab1:
    st.title("Pulse Market Terminal")
    if all_coins_raw == "RATE_LIMIT":
        st.error("Rate Limited by API. Showing priority assets.")
        all_coins = [] # Fallback logic could go here
    else:
        all_coins = all_coins_raw

    if all_coins:
        df_market = pd.DataFrame(all_coins)
        highlight_coin = df_market.iloc[0]
        h_hist = fetch_pulse_history(highlight_coin['id'], highlight_coin['symbol'])
        
        # --- TOP ASSET HIGHLIGHT ---
        col_h1, col_h2 = st.columns([1, 2])
        with col_h1:
            st.metric(f"🔥 Top Asset: {highlight_coin['name']}", f"${highlight_coin['current_price']:,.2f}", f"{highlight_coin['price_change_percentage_24h']:.2f}%")
            chart_type = st.radio("Chart View", ["Line", "Bar", "Candle"], horizontal=True, key="market_chart_type")

        with col_h2:
            if not h_hist.empty:
                current_val = highlight_coin['current_price']
                fig_p = go.Figure()
                
                if chart_type == "Line":
                    fig_p.add_trace(go.Scatter(
                        x=h_hist['timestamp'], y=h_hist['price'],
                        mode='lines', line=dict(color='#00ff7f', width=2),
                        name="Price"
                    ))
                else:
                    ohlc = h_hist.set_index('timestamp')['price'].resample('5min').ohlc().dropna().reset_index()
                    if chart_type == "Candle":
                        fig_p.add_trace(go.Candlestick(
                            x=ohlc['timestamp'], open=ohlc['open'], high=ohlc['high'],
                            low=ohlc['low'], close=ohlc['close'],
                            increasing_line_color='#00ff7f', decreasing_line_color='#ff4b4b',
                            name="OHLC"
                        ))
                    else:
                        fig_p.add_trace(go.Ohlc(
                            x=ohlc['timestamp'], open=ohlc['open'], high=ohlc['high'],
                            low=ohlc['low'], close=ohlc['close'],
                            increasing_line_color='#00ff7f', decreasing_line_color='#ff4b4b',
                            name="OHLC"
                        ))

                # --- PRO TRADING INDICATORS ---
                fig_p.add_hline(
                    y=current_val, 
                    line_dash="dash", line_color="#00ff7f", line_width=2,
                    annotation_text=f" <b>LIVE: ${current_val:,.2f}</b> ", 
                    annotation_position="right",
                    annotation_font_size=18,
                    annotation_font_color="#00ff7f",
                    annotation_bgcolor="#1e2130",
                    annotation_bordercolor="#00ff7f",
                    annotation_borderwidth=2
                )

                # --- PROFESSIONAL X-AXIS PADDING (25% Offset) ---
                last_time = h_hist['timestamp'].max()
                first_time = h_hist['timestamp'].min()
                duration = last_time - first_time
                x_max = last_time + (duration * 0.25)
                
                fig_p.update_layout(
                    height=350, margin={"l": 0, "r": 120, "t": 10, "b": 0},
                    template="plotly_dark",
                    xaxis={
                        "visible": True,
                        "range": [first_time, x_max],
                        "showgrid": False,
                        "rangeslider": {"visible": False},
                        "tickfont": {"color": "#8b949e"}
                    },
                    yaxis={
                        "visible": True, "showgrid": True, "gridcolor": "#30363d",
                        "zeroline": False, "autorange": True, "side": "right",
                        "tickfont": {"color": "#8b949e"}, "tickformat": ",.0f", "fixedrange": False 
                    },
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    showlegend=False,
                    hovermode="x unified"
                )
                st.plotly_chart(fig_p, use_container_width=True, config={'displayModeBar': True, 'scrollZoom': True})

        st.divider()
        # --- TERMINAL FEED ---
        display_df = df_market[['market_cap_rank', 'name', 'symbol', 'current_price', 'price_change_percentage_24h']].copy()
        st.dataframe(
            display_df.head(20),
            column_config={
                "current_price": st.column_config.NumberColumn("Price (USD)", format="$%.2f"),
                "price_change_percentage_24h": st.column_config.NumberColumn("24h Pulse", format="%.2f%%"),
            },
            hide_index=True,
            use_container_width=True
        )

        st.subheader("📊 Market Sentiment Heatmap (24h %)")
        hm_data = display_df.head(15).copy()
        fig_hm = go.Figure(data=go.Heatmap(
            z=[hm_data['price_change_percentage_24h'].tolist()],
            x=hm_data['name'].tolist(),
            y=['24h Change'],
            colorscale=[[0, '#ff4b4b'], [0.5, '#1e2130'], [1, '#00ff7f']],
            zmin=-12, zmax=12,
            showscale=True,
            text=[[f"{v:.2f}%" for v in hm_data['price_change_percentage_24h']]],
            texttemplate="%{text}",
        ))
        fig_hm.update_layout(
            height=200, margin=dict(l=0, r=0, t=10, b=30),
            template="plotly_dark",
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(side="bottom")
        )
        st.plotly_chart(fig_hm, use_container_width=True, config={'displayModeBar': False})

# --- TAB 2: AI TRADING BOT ---
with tab2:
    st.title("🤖 Gravity AI Strategic Terminal")
    
    # --- ASSET SELECTION & QUICK STATS ---
    col_t2_head1, col_t2_head2 = st.columns([2, 1])
    with col_t2_head1:
        target_coin_name = st.selectbox("🎯 Target Asset Loop", [c['name'] for c in all_coins], index=0)
        selected_coin = next(c for c in all_coins if c['name'] == target_coin_name)
    
    with col_t2_head2:
        risk_level = st.radio("Risk Profile", ["Safe", "Aggressive", "Institutional"], horizontal=True)

    st.divider()
    
    # --- METRICS GRID ---
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Exchange Price", f"${selected_coin['current_price']:,.2f}")
    m2.metric("24h Change", f"{selected_coin['price_change_percentage_24h']:.2f}%", delta_color="normal")
    m3.metric("Market Cap Rank", f"#{selected_coin['market_cap_rank']}")
    
    # DEX PRICE CHECKING
    with st.spinner("Checking DEX Liquidity..."):
        # USDC address for price routing on Ethereum
        dex_price = get_dex_price("0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee") if selected_coin['symbol'] == 'eth' else 0
        if dex_price > 0:
            m4.metric("DEX Price (1inch)", f"${dex_price:,.2f}")
        else:
            m4.metric("DEX Price", "N/A", help="DEX price available for ETH and primary ERC20s.")

    col_t2_main1, col_t2_main2 = st.columns([1, 1])
    
    with col_t2_main1:
        st.subheader("📋 Fundamental Report")
        with st.expander("View Asset Metadata", expanded=True):
            st.write(f"**Asset ID:** {selected_coin['id']}")
            st.write(f"**Symbol:** {selected_coin['symbol'].upper()}")
            st.write(f"**Circulating Supply:** {selected_coin.get('circulating_supply', 0):,.0f}")
            st.write(f"**Total Volume:** ${selected_coin.get('total_volume', 0):,.0f}")
        
        if st.button("🚀 Run Gemini Strategic Analysis", use_container_width=True):
            st.session_state.pop('latest_signal', None) # Clear old signal
            with st.spinner(f"AI scanning {selected_coin['name']} pulse..."):
                signal = get_trading_signal(selected_coin['symbol'])
                st.session_state['latest_signal'] = signal
                st.session_state['signal_coin'] = target_coin_name

    with col_t2_main2:
        st.subheader("⚡ Execution Engine")
        
        # --- AI STRATEGY OVERLAY (Shows if analysis was run) ---
        if 'latest_signal' in st.session_state and st.session_state['signal_coin'] == target_coin_name:
            sig = st.session_state['latest_signal']
            
            if isinstance(sig, dict) and "error" in sig:
                st.error(sig["error"])
            elif hasattr(sig, 'action') or (isinstance(sig, dict) and "action" in sig):
                action = getattr(sig, "action", sig.get("action") if isinstance(sig, dict) else "HOLD")
                conf = getattr(sig, "confidence", sig.get("confidence") if isinstance(sig, dict) else 0)
                reason = getattr(sig, "reasoning", sig.get("reasoning") if isinstance(sig, dict) else "No reasoning provided.")
                
                color = "#00ff7f" if action == "BUY" else "#ff4b4b" if action == "SELL" else "#8b949e"
                st.markdown(f"""
                <div style="padding:15px; border-radius:10px; border:1px solid {color}; background-color:rgba(0, 255, 127, 0.05); margin-bottom: 20px;">
                    <h3 style="color:{color}; margin:0;">AI ADVICE: {action}</h3>
                    <p style="margin:5px 0;">Confidence Score: <b>{conf}%</b></p>
                    <small>{reason}</small>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.warning("AI returned a non-standard response. Check logs.")
                st.write(sig)
        else:
            st.caption("🤖 AI Brain: Idle. Analysis optional.")

        # --- PERMANENT TRADING TERMINAL ---
        current_price = selected_coin['current_price']
        wallet_bal = get_wallet_balance()
        
        # Move Leverage Slider here for easier access during trade
        leverage = st.select_slider("Live Leverage Simulation", options=[1, 5, 10, 20, 50, 100, 125], value=st.session_state.get('leverage', 1))
        st.session_state['leverage'] = leverage
        
        st.write(f"💼 Buying Power: **${wallet_bal:,.2f}**")
        
        # --- QUICK PERCENTAGE ACTIONS ---
        pct_col1, pct_col2, pct_col3, pct_col4 = st.columns(4)
        if pct_col1.button("25%"): st.session_state['trade_pct'] = 0.25
        if pct_col2.button("50%"): st.session_state['trade_pct'] = 0.50
        if pct_col3.button("75%"): st.session_state['trade_pct'] = 0.75
        if pct_col4.button("100%"): st.session_state['trade_pct'] = 1.0

        base_val = (wallet_bal * st.session_state.get('trade_pct', 0.1)) / current_price
        
        trade_amt = st.number_input(
            f"Order Amount ({selected_coin['symbol'].upper()})", 
            value=float(base_val), 
            step=0.01,
            format="%.4f"
        )
        
        total_usd = trade_amt * current_price
        st.write(f"💰 Estimated Value: **${total_usd:,.2f}**")

        if mode_str == "Paper":
            col_btn_buy, col_btn_sell = st.columns(2)
            current_lev = st.session_state.get('leverage', 1)
            if col_btn_buy.button("Direct BUY", use_container_width=True, type="primary"):
                if total_usd > wallet_bal:
                    st.error("Insufficient Funds!")
                else:
                    log_trade(target_coin_name, "BUY", current_price, trade_amt, "Manual Entry", "Paper", current_lev)
                    st.success(f"Successfully BUYed {trade_amt:.4f} {selected_coin['symbol'].upper()} at {current_lev}x!")
                    st.balloons()
                    
            if col_btn_sell.button("Direct SELL", use_container_width=True):
                log_trade(target_coin_name, "SELL", current_price, trade_amt, "Manual Exit", "Paper", current_lev)
                st.success(f"Successfully SELLed {trade_amt:.4f} {selected_coin['symbol'].upper()}!")
                st.rerun()
        else:
            st.warning("⚡ Trust Wallet Integration (1inch)")
            coin_addr = selected_coin.get('platforms', {}).get('ethereum', "0x...")
            trust_link = generate_buy_link(coin_addr, total_usd)
            st.link_button("Open 1inch in Trust Wallet", trust_link, use_container_width=True)

# --- TAB 3: ANALYTICS ---
with tab3:
    st.title("📊 Portfolio & Audit Trail")
    
    col_w1, col_w2, col_w3 = st.columns(3)
    with col_w1:
        if mode_str == "Paper":
            balance = get_wallet_balance()
            st.metric("Virtual Balance", f"${balance:,.2f}")
            if st.button("🔄 Reset to $1,000", help="Reset virtual funds to initial state"):
                update_wallet_balance(1000.0)
                st.rerun()
        else:
            st.metric("Live Wallet Balance", "$0.00", help="Wallet integration required for live balance")
            st.caption("Connect Trust Wallet/1inch to sync")
    
    with col_w2:
        mode_filter = st.radio("History Mode", ["All", "Live", "Paper"], horizontal=True)

    # --- OPEN POSITIONS TRACKER ---
    st.divider()
    st.subheader(f"📋 Active Open Positions ({mode_str})")
    open_pos_df = get_open_positions(mode=mode_str)
    
    if not open_pos_df.empty:
        total_pnl = 0
        total_entry_val = 0
        pos_cols = st.columns(len(open_pos_df) if len(open_pos_df) < 4 else 3)
        
        for idx, row in open_pos_df.iterrows():
            # Match current price from global market data (Try Name then Symbol fallback)
            current_coin = next((c for c in all_coins if c['name'].lower() == row['coin'].lower() or c['symbol'].lower() == row['coin'].lower()), None)
            cur_price = current_coin['current_price'] if current_coin else row['avg_price']
            
            pnl_abs = (cur_price - row['avg_price']) * row['amount']
            # Use specific leverage from this trade's database row
            lev = row.get('leverage', 1)
            pnl_pct = (((cur_price - row['avg_price']) / row['avg_price']) * 100 * lev) if row['avg_price'] > 0 else 0
            
            # Track totals for global metric
            total_pnl += pnl_abs
            total_entry_val += (row['avg_price'] * row['amount'])
            
            with pos_cols[idx % (len(pos_cols))]:
                pnl_class = "pnl-plus" if pnl_pct >= 0 else "pnl-minus"
                st.markdown(f"""
                <div class="binance-card">
                    <div style="display: flex; justify-content: space-between; align-items: start;">
                        <div>
                            <span class="gold-text">LONG</span> &nbsp; <span style="color:#848e9c;">|</span> &nbsp; <b>{lev}x</b> &nbsp; <span style="color:#848e9c;">|</span> &nbsp; <b>{row['coin'].upper()}USDT</b>
                        </div>
                    </div>
                    <div style="margin: 15px 0;">
                        <div class="{pnl_class}">{pnl_pct:+.2f}%</div>
                        <div style="color:{'#02c076' if pnl_abs >= 0 else '#f84960'}; font-size: 0.9rem;">${pnl_abs:+.2f}</div>
                    </div>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
                        <div>
                            <div class="binance-label">Entry Price</div>
                            <div class="binance-value">{row['avg_price']:,.2f}</div>
                        </div>
                        <div>
                            <div class="binance-label">Mark Price</div>
                            <div class="binance-value">{cur_price:,.2f}</div>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                if st.button(f"Close Position", key=f"close_{row['id']}", use_container_width=True):
                    close_position(row['id'], cur_price)
                    st.success(f"Position {row['coin']} Closed!")
                    st.rerun()
        
        with col_w3:
            total_pnl_pct = (total_pnl / total_entry_val * 100) if total_entry_val > 0 else 0
            st.metric("Unrealized P&L", f"${total_pnl:,.2f}", delta=f"{total_pnl_pct:+.2f}%")
    else:
        st.info("No active trades found. Tokens purchased in 'Paper' mode will appear here.")
        with col_w3:
            st.metric("Unrealized P&L", "$0.00")

    st.divider()
    st.subheader("📜 Complete Trade History")
    trades_df = get_all_trades()
    if not trades_df.empty:
        if mode_filter != "All":
            trades_df = trades_df[trades_df['mode'] == mode_filter]
        
        st.dataframe(trades_df, use_container_width=True, hide_index=True)
        
        csv = trades_df.to_csv(index=False).encode('utf-8')
        st.download_button("Export History (CSV)", csv, "trade_history.csv", "text/csv")
    else:
        st.info("No trade history found. Start trading in Tab 2 to build your portfolio.")

