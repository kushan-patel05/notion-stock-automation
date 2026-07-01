"""
Workflow 1: Process new Stock Transactions and keep Stock Holdings in sync.

Since GitHub Actions has no native "new Notion page" trigger, this script
runs on a schedule (every 10 minutes by default) and:

  1. Reads a small state file (state/processed_transactions.json) listing
     transaction page IDs already handled.
  2. Queries the Transactions data source for all pages, skips ones already
     processed.
  3. For each new transaction, creates or updates the matching row in
     Holdings, then marks the transaction as processed.

The state file is committed back to the repo by the GitHub Actions workflow
step (not by this script) so it persists between runs.
"""

import json
import os
import sys

from notion_utils import (
    query_all_pages,
    create_page,
    update_page,
    get_title,
    get_rich_text,
    get_number,
    get_select,
    get_date,
    title_prop,
    rich_text_prop,
    number_prop,
    date_prop,
)

HOLDINGS_DATA_SOURCE_ID = os.environ.get("NOTION_HOLDINGS_DATA_SOURCE_ID")
TRANSACTIONS_DATA_SOURCE_ID = os.environ.get("NOTION_TRANSACTIONS_DATA_SOURCE_ID")
STATE_FILE = os.path.join(os.path.dirname(__file__), "..", "state", "processed_transactions.json")


def load_processed_ids():
    if not os.path.exists(STATE_FILE):
        return set()
    with open(STATE_FILE, "r") as f:
        try:
            return set(json.load(f))
        except json.JSONDecodeError:
            return set()


def save_processed_ids(ids):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(sorted(ids), f, indent=2)


def find_holding(ticker):
    """Return the Holdings page for a ticker, or None if it doesn't exist yet."""
    filter_obj = {
        "property": "Ticker",
        "title": {"equals": ticker},
    }
    results = query_all_pages(HOLDINGS_DATA_SOURCE_ID, filter_obj=filter_obj)
    return results[0] if results else None


def process_transaction(txn):
    ticker = get_title(txn, "Ticker").upper().strip()
    if not ticker:
        print(f"  Skipping transaction {txn['id']}: no Ticker set")
        return False

    stock_name = get_rich_text(txn, "Stock Name")
    txn_date = get_date(txn, "Date")
    txn_type = (get_select(txn, "Type") or "Buy").strip()
    shares = get_number(txn, "Shares")
    price = get_number(txn, "Price per Share")

    if shares is None or price is None:
        print(f"  Skipping transaction {txn['id']} ({ticker}): missing Shares or Price per Share")
        return False

    holding = find_holding(ticker)

    if holding is None:
        if txn_type.lower() == "sell":
            print(f"  WARNING: Sell transaction for {ticker} but no existing holding. Skipping.")
            return False

        print(f"  Creating new Holdings row for {ticker} ({shares} shares @ ${price})")
        properties = {
            "Ticker": title_prop(ticker),
            "Shares Owned": number_prop(shares),
            "Entry Price (Avg)": number_prop(price),
            "Current Price": number_prop(price),
        }
        if stock_name:
            properties["Stock Name"] = rich_text_prop(stock_name)
        if txn_date:
            properties["Purchase Date"] = date_prop(txn_date)
        create_page(HOLDINGS_DATA_SOURCE_ID, properties)
        return True

    old_shares = get_number(holding, "Shares Owned") or 0
    old_avg = get_number(holding, "Entry Price (Avg)") or 0

    if txn_type.lower() == "sell":
        new_shares = old_shares - shares
        if new_shares < 0:
            print(f"  WARNING: Selling {shares} shares of {ticker} but only {old_shares} owned. "
                  f"Setting to 0 instead of going negative.")
            new_shares = 0
        new_avg = old_avg  # cost basis of remaining shares is unchanged on a sell
        print(f"  Updating {ticker}: {old_shares} -> {new_shares} shares (sell)")
    else:
        new_shares = old_shares + shares
        if new_shares > 0:
            new_avg = ((old_avg * old_shares) + (price * shares)) / new_shares
        else:
            new_avg = old_avg
        print(f"  Updating {ticker}: {old_shares} -> {new_shares} shares, "
              f"avg price ${old_avg:.2f} -> ${new_avg:.2f} (buy)")

    update_page(holding["id"], {
        "Shares Owned": number_prop(new_shares),
        "Entry Price (Avg)": number_prop(round(new_avg, 4)),
    })
    return True


def main():
    if not HOLDINGS_DATA_SOURCE_ID or not TRANSACTIONS_DATA_SOURCE_ID:
        print("ERROR: NOTION_HOLDINGS_DATA_SOURCE_ID and NOTION_TRANSACTIONS_DATA_SOURCE_ID "
              "must be set as environment variables.")
        sys.exit(1)

    processed_ids = load_processed_ids()
    print(f"Loaded {len(processed_ids)} previously processed transaction IDs.")

    all_transactions = query_all_pages(
        TRANSACTIONS_DATA_SOURCE_ID,
        sorts=[{"timestamp": "created_time", "direction": "ascending"}],
    )
    print(f"Found {len(all_transactions)} total transactions.")

    new_transactions = [t for t in all_transactions if t["id"] not in processed_ids]
    print(f"{len(new_transactions)} transaction(s) not yet processed.")

    errors = 0
    for txn in new_transactions:
        ticker = get_title(txn, "Ticker")
        print(f"Processing transaction {txn['id']} ({ticker})...")
        try:
            handled = process_transaction(txn)
            if handled:
                processed_ids.add(txn["id"])
            # If handled is False, we intentionally leave it unprocessed so
            # it gets retried next run (e.g. missing data that might be
            # filled in later) rather than silently dropping it.
        except Exception as e:
            errors += 1
            print(f"  ERROR processing transaction {txn['id']}: {e}")

    save_processed_ids(processed_ids)
    print(f"Done. {len(processed_ids)} total transactions marked processed.")

    if errors:
        print(f"Completed with {errors} error(s).")
        sys.exit(1)


if __name__ == "__main__":
    main()
