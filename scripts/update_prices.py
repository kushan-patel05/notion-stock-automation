"""
Workflow 2: Daily price update.

Reads every ticker in the Stock Holdings data source, fetches a current
price for each via yfinance, and writes it back to the "Current Price"
property.
"""

import os
import sys
import time

import yfinance as yf

from notion_utils import (
    query_all_pages,
    update_page,
    get_title,
    number_prop,
)

HOLDINGS_DATA_SOURCE_ID = os.environ.get("NOTION_HOLDINGS_DATA_SOURCE_ID")


def get_current_price(ticker):
    """
    Fetch a current price for a ticker. Tries fast_info first (cheap, live),
    falls back to the most recent close from history if that's unavailable.
    """
    t = yf.Ticker(ticker)

    try:
        price = t.fast_info.get("last_price")
        if price:
            return float(price)
    except Exception:
        pass

    try:
        hist = t.history(period="5d")
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
    except Exception:
        pass

    return None


def main():
    if not HOLDINGS_DATA_SOURCE_ID:
        print("ERROR: NOTION_HOLDINGS_DATA_SOURCE_ID must be set as an environment variable.")
        sys.exit(1)

    holdings = query_all_pages(HOLDINGS_DATA_SOURCE_ID)
    print(f"Found {len(holdings)} holdings to update.")

    updated = 0
    failed = []

    for page in holdings:
        ticker = get_title(page, "Ticker").upper().strip()
        if not ticker:
            continue

        print(f"Fetching price for {ticker}...")
        price = get_current_price(ticker)

        if price is None:
            print(f"  Could not fetch a price for {ticker}")
            failed.append(ticker)
            continue

        try:
            update_page(page["id"], {"Current Price": number_prop(round(price, 2))})
            print(f"  {ticker}: ${price:.2f}")
            updated += 1
        except Exception as e:
            print(f"  Failed to update {ticker} in Notion: {e}")
            failed.append(ticker)

        # Be polite to Yahoo Finance's unofficial API
        time.sleep(0.5)

    print(f"\nUpdated {updated}/{len(holdings)} holdings.")
    if failed:
        print(f"Failed tickers: {', '.join(failed)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
