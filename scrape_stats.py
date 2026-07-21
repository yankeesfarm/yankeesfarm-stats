"""
YankeesFarm Multi-Affiliate Stats Scraper
-------------------------------------------
Pulls current-season batting & pitching stats for these Yankees
affiliates from Baseball-Reference's organization register page, and
writes the result to data/stats.json:
  - DSL Yankees
  - DSL Bombers
  - FCL Yankees
  - Tampa Tarpons
  - Hudson Valley Renegades
  - Somerset Patriots
  - SWB RailRiders
"""

import json
import re
import sys
from datetime import datetime, timezone
from io import StringIO

import requests
import pandas as pd
from bs4 import BeautifulSoup

ORG_ID = "NYY"
YEAR = 2026
URL = f"https://www.baseball-reference.com/register/affiliate.cgi?id={ORG_ID}&year={YEAR}"

TEAM_MATCHERS = {
    "DSL Yankees": ["dsl yankees1", "dsl yankees 1"],
    "DSL Bombers": ["dsl bombers", "dsl yankees2", "dsl yankees 2"],
    "FCL Yankees": ["fcl yankees"],
    "Tampa Tarpons": ["tampa"],
    "Hudson Valley Renegades": ["hudson valley"],
    "Somerset Patriots": ["somerset"],
    "SWB RailRiders": ["scranton", "wilkes-barre", "swb", "s-wb"],
}


def match_team(team_val: str):
    if not team_val:
        return None
    tv = team_val.lower()
    for canonical, needles in TEAM_MATCHERS.items():
        if any(n in tv for n in needles):
            return canonical
    return None


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def fetch_page(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.text


def uncomment_tables(html: str) -> str:
    return re.sub(r"<!--|-->", "", html)


def parse_tables(html: str):
    soup = BeautifulSoup(html, "lxml")
    tables = soup.find_all("table")
    results = []
    for t in tables:
        table_id = t.get("id", "unknown")
        try:
            df = pd.read_html(StringIO(str(t)))[0]
        except ValueError:
            continue
        results.append((table_id, df))
    return results


def build_dataset():
    html = fetch_page(URL)
    html = uncomment_tables(html)
    tables = parse_tables(html)

    teams_data = {
        name: {"batting": [], "pitching": []} for name in TEAM_MATCHERS
    }

    for table_id, df in tables:
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [" ".join(map(str, c)).strip() for c in df.columns]

        cols_lower = [str(c).lower() for c in df.columns]
        is_batting = "ab" in cols_lower and "hr" in cols_lower
        is_pitching = "ip" in cols_lower and "era" in cols_lower
        if not (is_batting or is_pitching):
            continue

        team_col = next((c for c in df.columns if str(c).lower() in ("tm", "team")), None)
        if team_col is None:
            continue

        for _, row in df.iterrows():
            team_val = str(row.get(team_col, ""))
            canonical = match_team(team_val)
            if canonical is None:
                continue
            record = row.to_dict()
            record = {str(k): (None if pd.isna(v) else v) for k, v in record.items()}
            if is_batting:
                teams_data[canonical]["batting"].append(record)
            else:
                teams_data[canonical]["pitching"].append(record)

    return {
        "org": ORG_ID,
        "season": YEAR,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "teams": teams_data,
    }


def main():
    try:
        dataset = build_dataset()
    except requests.HTTPError as e:
        print(f"HTTP error fetching page: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)

    total_batting = sum(len(t["batting"]) for t in dataset["teams"].values())
    total_pitching = sum(len(t["pitching"]) for t in dataset["teams"].values())

    if total_batting == 0 and total_pitching == 0:
        print("WARNING: 0 players found across all teams.", file=sys.stderr)
    else:
        for name, t in dataset["teams"].items():
            if not t["batting"] and not t["pitching"]:
                print(f"WARNING: 0 players found for '{name}'.", file=sys.stderr)

    with open("data/stats.json", "w") as f:
        json.dump(dataset, f, indent=2)

    print(f"Wrote {total_batting} batting rows, {total_pitching} pitching "
          f"rows across {len(dataset['teams'])} teams to data/stats.json")


if __name__ == "__main__":
    main()
