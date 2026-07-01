# Notion Stock Portfolio Automation

Keeps a Notion **Stock Holdings** database in sync with a **Stock
Transactions** database, and refreshes current prices daily — all via
GitHub Actions, for free.

## What it does

Once a day, right after US market close (~4:05 PM ET on weekdays), a single
GitHub Actions workflow:

1. **Processes new/updated transactions** — for each transaction not yet
   handled, creates a new Holdings row (on a first Buy) or updates an
   existing one (recalculating the weighted average entry price on a Buy,
   reducing share count on a Sell).
2. **Refreshes Current Price** for every holding, using `yfinance`.

See [`SETUP_INSTRUCTIONS.md`](./SETUP_INSTRUCTIONS.md) for how to configure
this from scratch, and [`TESTING_CHECKLIST.md`](./TESTING_CHECKLIST.md) for
a step-by-step way to validate it before trusting it with real data.

## Project layout

```
.github/workflows/daily-portfolio-update.yml   # the single scheduled workflow
scripts/notion_utils.py                        # shared Notion API helpers
scripts/process_transactions.py                # Workflow step 1
scripts/update_prices.py                       # Workflow step 2
state/processed_transactions.json              # tracks which transactions are already applied
requirements.txt                                # Python dependencies
```

## Why once a day instead of real-time

GitHub Actions has no native "new Notion page created" trigger — it can
only run on a schedule or be triggered manually. Since transactions don't
need to be reflected in Holdings faster than end-of-day pricing anyway,
this runs both steps together once daily rather than polling every few
minutes, which keeps the commit history clean and Actions usage minimal.

## Security notes

- `NOTION_TOKEN` and the data source IDs are stored as **GitHub Secrets**
  and are never written to any file in this repo or exposed in logs.
- This repo is public. GitHub Actions minutes are free and unlimited for
  public repositories, and no financial data (tickers, share counts,
  dollar amounts) is ever written back into the repo — only anonymous
  Notion page IDs in `state/processed_transactions.json`, used purely to
  avoid double-processing.
- The workflow only runs on a `schedule` or manual `workflow_dispatch` —
  never on external pull requests — so secrets are never exposed to
  content from outside contributors.
