# Testing Checklist

Work through these in order. Each builds on the previous one working. All
tests here use manual **Run workflow** triggers from the Actions tab, which
skip the 4 PM ET time-window check — so you can test anytime, not just at
market close.

## Before you start
- [ ] Integration created in Notion, capabilities include Read + Update + Insert content
- [ ] Integration connected to **both** the Holdings and Transactions databases
      (`•••` → Connections → your integration, on each database)
- [ ] All three GitHub Secrets added (`NOTION_TOKEN`,
      `NOTION_HOLDINGS_DATA_SOURCE_ID`, `NOTION_TRANSACTIONS_DATA_SOURCE_ID`)
- [ ] Repo → Settings → Actions → General → Workflow permissions set to
      **Read and write**
- [ ] All files committed and pushed, including `state/processed_transactions.json`
      containing `[]`

## Test 1 — Manual trigger, no data changes
- [ ] Go to **Actions** tab → **Daily Portfolio Update** → **Run workflow**
- [ ] It should complete green. Check the logs: "Process transactions" step
      should say `Found 0 previously processed transaction IDs` (first run)
      and list however many transactions currently exist in your database.
- [ ] The "Update current prices" step should update Current Price for
      whatever holdings already exist.

If this fails, check the error in the logs first — most first-run failures
are either (a) integration not connected to the database, or (b) a typo'd
secret name/value.

## Test 2 — New ticker via Buy
- [ ] In Stock Transactions, add a row: pick a ticker you don't currently
      hold (e.g. `AAPL` if you don't own it yet), Type = Buy, Shares = 10,
      Price per Share = 150, Date = today.
- [ ] Manually run **Daily Portfolio Update**.
- [ ] Confirm: a new row appears in Stock Holdings with Ticker = AAPL,
      Shares Owned = 10, Entry Price (Avg) = 150, and Current Price updated
      to today's actual close (not 150, since the price-update step ran
      right after and overwrote it).
- [ ] Confirm: `state/processed_transactions.json` in your repo now contains
      the transaction's page ID (check the file on GitHub after the run).

## Test 3 — Existing ticker via Buy (average price recalculation)
- [ ] Add another transaction for the same ticker (AAPL): Type = Buy,
      Shares = 10, Price per Share = 170.
- [ ] Run the workflow again.
- [ ] Confirm: Holdings now shows Shares Owned = 20, Entry Price (Avg) = 160
      (the weighted average of 150 and 170 across 10 shares each).

## Test 4 — Existing ticker via Sell
- [ ] Add a transaction: Type = Sell, Shares = 5, Price per Share = 180.
- [ ] Run the workflow again.
- [ ] Confirm: Shares Owned drops to 15, Entry Price (Avg) stays at 160
      (unchanged — cost basis of remaining shares doesn't move on a sell).

## Test 5 — Sell with no existing holding (should be skipped, not crash)
- [ ] Add a transaction for a ticker you've never bought: Type = Sell,
      Shares = 5, Price per Share = 100.
- [ ] Run the workflow.
- [ ] Confirm: the workflow logs a warning about this and completes
      successfully rather than erroring out. No Holdings row is created.
      This transaction should remain unprocessed (not yet in the state
      file) so you can fix it and it'll pick it up on a future run.

## Test 6 — No duplicate processing
- [ ] Run **Daily Portfolio Update** again immediately with no new
      transactions added.
- [ ] Confirm in the logs: `0 transaction(s) not yet processed` — i.e. it
      doesn't re-apply the same transactions and inflate your share counts.

## Test 7 — New sector value
- [ ] On any Holdings row, manually type a brand-new value into the Sector
      field that doesn't exist as an option yet (e.g. "Quantum Computing").
- [ ] Confirm Notion lets you save it — this is native Notion behavior (new
      Select options are created automatically), not something the scripts
      need to handle, but worth confirming it works in your setup.

## Test 8 — Daily price update accuracy
- [ ] Spot-check 2-3 tickers' Current Price against a live source (e.g.
      Google Finance) to confirm they're reasonably close (yfinance prices
      can lag real-time by a few minutes, which is expected).
- [ ] Try including one deliberately invalid ticker (e.g. `ZZZZZZ`) in
      Holdings temporarily — confirm the workflow logs it as failed but
      still updates all the valid tickers, and the job exits with a
      non-zero status (visible as a red X in Actions) so you notice.

## Test 9 — Scheduled run actually fires on its own
- [ ] On a weekday, check that the workflow fires automatically around
      4:05 PM ET without you clicking anything, and that the logs show it
      did real work (not the "Not the correct seasonal firing" skip
      message) — and that the *other* seasonal cron trigger that same day
      logged the skip message instead of doing a second run.

## Ongoing sanity checks
- [ ] Periodically peek at the **Actions** tab for red (failed) runs —
      GitHub does not email you by default unless you opt into failure
      notifications (this is the follow-up we're adding next).
- [ ] If yfinance starts failing broadly (not just for a couple of tickers),
      it's usually a sign Yahoo changed something upstream — check for a
      `yfinance` package update.
