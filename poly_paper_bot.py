import requests
import time
import json
import os
from py_clob_client.client import ClobClient

class PaperPortfolio:
    def __init__(self, initial_balance=1000.0):
        self.balance = initial_balance
        self.positions = {}
        print(f"--- Portfolio Initialized: ${self.balance} ---")

    def paper_buy(self, token_id, price, amount_usd):
        if amount_usd > self.balance: return
        shares = amount_usd / price
        self.balance -= amount_usd
        self.positions[token_id] = self.positions.get(token_id, 0) + shares
        print(f"🚀 PAPER BUY: {round(shares, 2)} units at ${price}. Bal: ${round(self.balance, 2)}")

    def paper_sell(self, token_id, price):
        shares = self.positions.get(token_id, 0)
        if shares <= 0: return
        credit = shares * price
        self.balance += credit
        self.positions[token_id] = 0
        print(f"💰 PAPER SELL: All units at ${price}. Bal: ${round(self.balance, 2)}")

def get_tradable_market():
    """Finds an active market with CLOB token ids."""
    url = "https://gamma-api.polymarket.com/markets"
    params = {
        "active": "true",
        "closed": "false",
        "limit": 200,
    }
    response = requests.get(url, params=params, timeout=20)
    response.raise_for_status()
    resp = response.json()

    if isinstance(resp, dict):
        if isinstance(resp.get("data"), list):
            resp = resp["data"]
        else:
            return None

    if not isinstance(resp, list):
        return None

    preferred_market = os.getenv("POLYMARKET_MARKET", "").strip().lower()
    
    for m in resp:
        if not isinstance(m, dict):
            continue

        if preferred_market:
            question = str(m.get("question", "")).lower()
            slug = str(m.get("slug", "")).lower()
            if preferred_market not in question and preferred_market not in slug:
                continue

        if m.get('clobTokenIds') and len(m['clobTokenIds']) > 0:
            token_ids = m['clobTokenIds']
            if isinstance(token_ids, str):
                try:
                    token_ids = json.loads(token_ids)
                except json.JSONDecodeError:
                    continue
            if not isinstance(token_ids, list) or not token_ids:
                continue
            
            return {
                "question": m['question'],
                "yes_token": token_ids[0]
            }
    return None

def run_bot():
    client = ClobClient("https://clob.polymarket.com")
    portfolio = PaperPortfolio(initial_balance=1000.0)

    market = get_tradable_market()
    if not market:
        print("Could not find a tradable market. Check your connection.")
        return

    print(f"Targeting: {market['question']}")
    token_id = market['yes_token']
    print("Set POLYMARKET_MARKET to part of a slug/question to target a specific market.")
    
    prices = []
    while True:
        try:
            mid = client.get_midpoint(token_id)
            mid_value = None
            if isinstance(mid, dict):
                mid_value = mid.get("mid") or mid.get("midpoint")
            elif isinstance(mid, (int, float, str)):
                mid_value = mid

            if mid_value is None:
                raise ValueError(f"Unexpected midpoint payload: {mid}")

            current_price = float(mid_value)
            if current_price <= 0:
                raise ValueError(f"Invalid midpoint price: {current_price}")

            prices.append(current_price)
            if len(prices) > 20: prices.pop(0)

            avg = sum(prices) / len(prices)
            print(f"[{time.strftime('%H:%M:%S')}] Price: {current_price} | Avg: {round(avg, 4)}")

            # Very sensitive strategy for testing (1% moves)
            if current_price < (avg * 0.99) and portfolio.balance > 100:
                portfolio.paper_buy(token_id, current_price, 100)
            elif current_price > (avg * 1.01) and portfolio.positions.get(token_id, 0) > 0:
                portfolio.paper_sell(token_id, current_price)

        except Exception as e:
            print(f"Loop error: {e}")
        
        time.sleep(5)

if __name__ == "__main__":
    run_bot()