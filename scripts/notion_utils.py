"""
Shared helper functions for talking to the Notion API.

Uses Notion-Version: 2025-09-03, which requires querying/creating pages
against a *data source ID* rather than a database ID. Your database IDs
still work for reference/lookups, but reads/writes to rows go through
the data source endpoints.

Docs: https://developers.notion.com/docs/upgrade-guide-2025-09-03
"""

import os
import time
import requests

NOTION_VERSION = "2025-09-03"
NOTION_BASE = "https://api.notion.com/v1"


def _headers():
    token = os.environ.get("NOTION_TOKEN")
    if not token:
        raise RuntimeError("NOTION_TOKEN environment variable is not set")
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def _request(method, url, json_body=None, max_retries=3):
    """Make a request to the Notion API with basic retry/backoff on 429/5xx."""
    for attempt in range(max_retries):
        resp = requests.request(method, url, headers=_headers(), json=json_body, timeout=30)
        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", "2"))
            print(f"  Rate limited, waiting {retry_after}s...")
            time.sleep(retry_after)
            continue
        if resp.status_code >= 500:
            print(f"  Server error {resp.status_code}, retrying...")
            time.sleep(2 * (attempt + 1))
            continue
        if resp.status_code >= 400:
            raise RuntimeError(
                f"Notion API error {resp.status_code} on {method} {url}: {resp.text}"
            )
        return resp.json()
    raise RuntimeError(f"Notion API request failed after {max_retries} retries: {method} {url}")


def query_all_pages(data_source_id, filter_obj=None, sorts=None):
    """
    Query every page in a data source, following pagination.
    Returns a list of raw Notion page objects.
    """
    url = f"{NOTION_BASE}/data_sources/{data_source_id}/query"
    all_results = []
    body = {}
    if filter_obj:
        body["filter"] = filter_obj
    if sorts:
        body["sorts"] = sorts

    while True:
        data = _request("POST", url, json_body=body)
        all_results.extend(data.get("results", []))
        if data.get("has_more") and data.get("next_cursor"):
            body["start_cursor"] = data["next_cursor"]
        else:
            break

    return all_results


def create_page(data_source_id, properties):
    """Create a new page (row) in a data source."""
    url = f"{NOTION_BASE}/pages"
    body = {
        "parent": {"type": "data_source_id", "data_source_id": data_source_id},
        "properties": properties,
    }
    return _request("POST", url, json_body=body)


def update_page(page_id, properties):
    """Update properties on an existing page."""
    url = f"{NOTION_BASE}/pages/{page_id}"
    body = {"properties": properties}
    return _request("PATCH", url, json_body=body)


# ---- Property extraction helpers -----------------------------------------
# Notion property values are nested by type. These helpers pull out plain
# Python values and are defensive about missing/empty properties.

def get_title(page, prop_name):
    prop = page.get("properties", {}).get(prop_name, {})
    items = prop.get("title", [])
    if not items:
        return ""
    return "".join(i.get("plain_text", "") for i in items).strip()


def get_rich_text(page, prop_name):
    prop = page.get("properties", {}).get(prop_name, {})
    items = prop.get("rich_text", [])
    if not items:
        return ""
    return "".join(i.get("plain_text", "") for i in items).strip()


def get_number(page, prop_name):
    prop = page.get("properties", {}).get(prop_name, {})
    return prop.get("number")


def get_select(page, prop_name):
    prop = page.get("properties", {}).get(prop_name, {})
    sel = prop.get("select")
    return sel.get("name") if sel else None


def get_date(page, prop_name):
    prop = page.get("properties", {}).get(prop_name, {})
    date_obj = prop.get("date")
    return date_obj.get("start") if date_obj else None


# ---- Property construction helpers ----------------------------------------
# Building the property payloads Notion expects when creating/updating pages.

def title_prop(text):
    return {"title": [{"text": {"content": str(text)}}]}


def rich_text_prop(text):
    return {"rich_text": [{"text": {"content": str(text)}}]}


def number_prop(value):
    return {"number": value}


def select_prop(name):
    # Notion auto-creates a new Select option if `name` doesn't already
    # exist on the property, so new sectors don't need to be pre-created.
    return {"select": {"name": name}}


def date_prop(iso_date):
    return {"date": {"start": iso_date}}
