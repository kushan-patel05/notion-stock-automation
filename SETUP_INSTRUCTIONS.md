# Setup Instructions — Notion Stock Portfolio Automation

## 1. Create your Notion integration

1. Go to https://www.notion.so/my-integrations
2. Click **New integration**, name it something like `Stock Portfolio Automation`.
3. Under **Capabilities**, make sure it has **Read content**, **Update content**,
   and **Insert content** (the last one is needed since the workflow creates
   new Holdings rows for new tickers).
4. Copy the **Internal Integration Secret** — this is your `NOTION_TOKEN`.
5. Open your **Stock Holdings** database and your **Stock Transactions** database
   in Notion, and for each: click **`•••`** → **Connections** → add your new
   integration. Without this step the integration can't see either database,
   even with a valid token.

## 2. Confirm your data source IDs

Notion's API separates a **database** (the container) from its **data
source** (the actual table of rows). You already have both:

```
Holdings Database ID:        e726a15ccb5d4c3c844c89fc75fe6ce2
Holdings Data Source ID:     afc6fbe1-3a78-4637-92ed-afcc1049da25

Transactions Database ID:    e097968e985549b2942cc7f3e7c6e6f2
Transactions Data Source ID: f4096a6d-d6ce-4b33-a724-5ef1175d73fe
```

The scripts in this project use the **data source IDs**, not the database IDs.

## 3. Create the repo (public)

Create a new **public** repository on your personal GitHub account. Public
means GitHub Actions minutes are free and unlimited — no usage math to worry
about. See the "Security notes" in the README for what that does and
doesn't expose.

## 4. Add GitHub Secrets

In the repo: **Settings → Secrets and variables → Actions → New repository secret**.
Add these three:

| Secret name | Value |
|---|---|
| `NOTION_TOKEN` | Your integration token from step 1 |
| `NOTION_HOLDINGS_DATA_SOURCE_ID` | `afc6fbe1-3a78-4637-92ed-afcc1049da25` |
| `NOTION_TRANSACTIONS_DATA_SOURCE_ID` | `f4096a6d-d6ce-4b33-a724-5ef1175d73fe` |

Secrets are encrypted and never appear in logs, diffs, or to anyone browsing
the public repo — only the workflow can read them, at runtime.

## 5. Enable Actions permissions

The workflow commits back to the repo (to update the transaction-processing
state file), so:

1. Go to **Settings → Actions → General → Workflow permissions**.
2. Select **Read and write permissions**.
3. Save.

Without this, the "Commit updated state file" step will fail with a
permissions error.

## 6. Add the files to your repo

Copy this whole folder structure into your repository and push it:

```
.github/workflows/daily-portfolio-update.yml
scripts/notion_utils.py
scripts/process_transactions.py
scripts/update_prices.py
requirements.txt
state/processed_transactions.json   (must exist, starting as [])
.gitignore
README.md
```

## 7. How the workflow behaves

`daily-portfolio-update.yml` runs **once a day**, on weekdays, right after
market close (~4:05 PM ET). It does two things in sequence:

1. **Process transactions** — checks Stock Transactions for anything not
   yet in `state/processed_transactions.json`, creates/updates Holdings
   rows accordingly, and commits the updated state file back to the repo.
2. **Update prices** — refreshes Current Price for every Holdings row
   (including any created in step 1 that same day) using `yfinance`.

Because "4 PM ET" isn't a fixed UTC time (Daylight Saving Time shifts it),
the workflow registers two cron triggers and has a step that checks the real
Eastern time and skips whichever one doesn't land on ~4:00 PM ET that day —
so you still get exactly one real run per day, not zero or two.

You can also trigger it manually anytime from the **Actions** tab → **Run
workflow** — manual runs skip the time-window check entirely.

## 8. A few behavior notes worth knowing

- **New ticker via Buy:** creates a Holdings row with Shares Owned, Entry
  Price (Avg), and Current Price all set from the transaction. **Stock Name**
  and **Sector** are left blank for you to fill in manually (Stock Name is
  copied over automatically only if it was also filled in on the
  transaction).
- **New ticker via Sell:** doesn't make sense (can't sell something you
  don't own), so the script logs a warning and skips it rather than creating
  a negative position.
- **Existing ticker via Buy:** recalculates the weighted average entry price:
  `(old_avg * old_shares + new_price * new_shares) / (old_shares + new_shares)`.
- **Existing ticker via Sell:** reduces Shares Owned, leaves Entry Price
  (Avg) unchanged (cost basis of remaining shares doesn't change on a
  partial sell — standard average-cost accounting). If a sell would take
  shares below zero, it's floored at 0 with a warning logged.
- **Sector auto-add:** Notion's API automatically creates a new Select
  option if you write a value that doesn't exist yet, so typing a new
  sector name manually into a Holdings row just works.
- **Errors are non-fatal per-item:** if one transaction or one ticker fails
  (bad data, API hiccup, unknown ticker), the workflow logs it and moves on
  rather than stopping entirely. A failed transaction stays unprocessed and
  gets retried the next day.
- **yfinance** pulls from Yahoo Finance's free/unofficial API — reliable for
  most tickers, but no uptime SLA. If it starts failing broadly rather than
  for a couple of tickers, it's usually a sign Yahoo changed something
  upstream.

## 9. Testing

See `TESTING_CHECKLIST.md` for a step-by-step checklist to validate
everything before relying on it.

## 10. Later: failure email notifications

Not set up yet by design — we're adding this as a follow-up once the core
workflow is confirmed working.
