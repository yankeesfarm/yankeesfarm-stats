"""
YankeesFarm Multi-Affiliate INDIVIDUAL PLAYER Stats Scraper
-------------------------------------------------------------
Pulls current-season batting & pitching stats for every individual
player on these Yankees affiliates, and writes the result to
data/stats.json:
  - DSL Yankees
  - DSL Bombers
  - FCL Yankees
  - Tampa Tarpons
  - Hudson Valley Renegades
  - Somerset Patriots
  - SWB RailRiders

HOW IT WORKS (two-step, to get PLAYER rows, not team totals)
--------------------------------------------------------------
1. Fetch Baseball-Reference's org-wide affiliate register page. This
   page lists a summary row per team, and — importantly — each team
   name is a link to that team's own dedicated stats page.
2. Follow each of those 7 links and scrape the individual player
   batting/pitching tables from each team's own page. This is where
   real per-player stat lines live (the org-wide page only has team
   totals).

Doing it this way (rather than hardcoding each team's URL) means the
script keeps working next year even though Baseball-Reference gives
each team page a new random-looking ID every season.
"""

import json
import re
import sys
import time
from datetime import datetime, timezone
from io import StringIO
from urllib.parse import urljoin

import requests
import pandas as pd
from bs4 import BeautifulSoup

ORG_ID = "NYY"
YEAR = 2026
AFFILIATE_URL = f"https://www.baseball-reference.com/register/affiliate.cgi?id={ORG_ID}&year={YEAR}"
BASE_URL = "https://www.baseball-reference.com"

TEAM_MATCHERS = {
    "DSL Bombers": ["dsl yankees 2", "dsl yankees2", "dsl bombers"],
    "DSL Yankees": ["dsl yankees"],
    "FCL Yankees": ["fcl yankees"],
    "Tampa Tarpons": ["tampa"],
    "Hudson Valley Renegades": ["hudson valley"],
    "Somerset Patriots": ["somerset"],
    "SWB RailRiders": ["scranton", "wilkes-barre", "swb", "s-wb"],
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def match_team(team_val: str):
    if not team_val:
        return None
    tv = team_val.lower()
    for canonical, needles in TEAM_MATCHERS.items():
        if any(n in tv for n in needles):
            return canonical
    return None


def fetch_page(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    time.sleep(2)
    return resp.text


def uncomment_tables(html: str) -> str:
    return re.sub(r"<!--|-->", "", html)


def find_team_page_links(affiliate_html: str):
    soup = BeautifulSoup(uncomment_tables(affiliate_html), "lxml")
    links = {}
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/register/team.cgi" not in href:
            continue
        canonical = match_team(a.get_text(strip=True))
        if canonical and canonical not in links:
            links[canonical] = urljoin(BASE_URL, href)
    return links


def parse_player_tables(team_html: str):
    soup = BeautifulSoup(uncomment_tables(team_html), "lxml")
    batting_rows, pitching_rows = [], []

    for table in soup.find_all("table"):
        try:
            df = pd.read_html(StringIO(str(table)))[0]
        except ValueError:
            continue

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [" ".join(map(str, c)).strip() for c in df.columns]

        cols_lower = [str(c).lower() for c in df.columns]
        has_name = "name" in cols_lower or "player" in cols_lower
        is_batting = has_name and "ab" in cols_lower and "hr" in cols_lower
        is_pitching = has_name and "ip" in cols_lower and "era" in cols_lower
        if not (is_batting or is_pitching):
            continue

        for _, row in df.iterrows():
            record = row.to_dict()
            record = {str(k): (None if pd.isna(v) else v) for k, v in record.items()}
            name_val = str(record.get("Name") or record.get("Player") or "").strip()
            if not name_val or name_val.lower() in ("team totals", "nan"):
                continue
            if is_batting:
                batting_rows.append(record)
            else:
                pitching_rows.append(record)

    return batting_rows, pitching_rows


def build_dataset():
    affiliate_html = fetch_page(AFFILIATE_URL)
    team_links = find_team_page_links(affiliate_html)

    teams_data = {name: {"batting": [], "pitching": []} for name in TEAM_MATCHERS}

    for canonical, url in team_links.items():
        try:
            team_html = fetch_page(url)
        except requests.HTTPError as e:
            print(f"Couldn't fetch {canonical} page ({url}): {e}", file=sys.stderr)
            continue
        batting, pitching = parse_player_tables(team_html)
        teams_data[canonical]["batting"] = batting
        teams_data[canonical]["pitching"] = pitching

    missing = [name for name in TEAM_MATCHERS if name not in team_links]
    if missing:
        print(f"WARNING: couldn't find a page link for: {', '.join(missing)}.", file=sys.stderr)

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
