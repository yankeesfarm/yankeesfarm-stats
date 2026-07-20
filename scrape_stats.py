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

That JSON file is what your Wix site will fetch from (via the raw
GitHub URL) to display "automatically updated" stats.

HOW IT WORKS
------------
1. Baseball-Reference's affiliate register page lists every org player,
   split into tables by affiliate/level (AAA, AA, A+, A, Rk).
2. Baseball-Reference hides most of these tables inside HTML comments
   to make casual scraping harder. We strip the comments before parsing.
3. We filter down to rows whose level/team looks like DSL / FCL / Rookie.
4. We write tidy JSON grouped by team, with batting and pitching split out.

RUN LOCALLY (to test):
    pip install requests beautifulsoup4 pandas lxml
    python scrape_stats.py

NOTE ON BOT BLOCKING:
Baseball-Reference allows automated requests under ~20/min (see
sports-reference.com/bot-traffic.html), but their edge protection
(Cloudflare) can still challenge requests from datacenter IPs like
GitHub Actions runners, independent of rate. If this script starts
returning 0 players when run in GitHub Actions, that's almost
certainly what's happening — see SETUP-GUIDE.md for the fallback
(running the script from your own computer's Task Scheduler/cron
instead of GitHub Actions).
"""

import json
import re
import sys
import time
from datetime import datetime, timezone

import requests
import pandas as pd
from bs4 import BeautifulSoup

ORG_ID = "NYY"
YEAR = 2026
URL = f"https://www.baseball-reference.com/register/affiliate.cgi?id={ORG_ID}&year={YEAR}"

# Which affiliates to include, and what substrings (lowercase) to match
# against the "Team" column to identify each one. Baseball-Reference's
# exact team-name text can vary (e.g. "DSL Yankees1" vs "DSL Yankees"),
# so each affiliate lists a few possible matches. If a team comes back
# missing from your data, open your stats.json, find how BR actually
# labeled it, and add that exact string to the matching list below.
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
    """Return the canonical affiliate name if team_val matches one of
    our tracked teams, else None."""
    if not team_val:
        return None
    tv = team_val.lower()
    for canonical, needles in TEAM_MATCHERS.items():
        if any(n in tv for n in needles):
            return canonical
    return None

HEADERS = {
    # A realistic desktop browser UA. Reduces (but does not guarantee
    # avoiding) bot-detection challenges.
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
    """Baseball-Reference wraps most stat tables in HTML comments.
    Strip the comment markers so BeautifulSoup/pandas can see them."""
    return re.sub(r"<!--|-->", "", html)


def parse_tables(html: str):
    """Return a list of (table_id, DataFrame) for every table on the page."""
    soup = BeautifulSoup(html, "lxml")
    tables = soup.find_all("table")
    results = []
    for t in tables:
        table_id = t.get("id", "unknown")
        try:
            df = pd.read_html(str(t))[0]
        except ValueError:
            continue
        results.append((table_id, df))
    return results


def build_dataset():
    html = fetch_page(URL)
    html = uncomment_tables(html)
    tables = parse_tables(html)

    # Start with an empty bucket for each tracked affiliate so the
    # output JSON always has a consistent shape, even for teams with
    # 0 matches.
    teams_data = {
        name: {"batting": [], "pitching": []} for name in TEAM_MATCHERS
    }

    for table_id, df in tables:
        # Flatten multi-index columns if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [" ".join(map(str, c)).strip() for c in df.columns]

        # Identify batting vs pitching tables by column signature
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
        print(
            "WARNING: 0 players found across all teams. This usually means "
            "Baseball-Reference served a bot-detection page instead of real "
            "data. See SETUP-GUIDE.md.",
            file=sys.stderr,
        )
    else:
        for name, t in dataset["teams"].items():
            if not t["batting"] and not t["pitching"]:
                print(
                    f"WARNING: 0 players found for '{name}'. Check that its "
                    f"entry in TEAM_MATCHERS matches how Baseball-Reference "
                    f"actually labels this team (see data/stats.json for raw "
                    f"team name text on other rows).",
                    file=sys.stderr,
                )

    with open("data/stats.json", "w") as f:
        json.dump(dataset, f, indent=2)

    print(f"Wrote {total_batting} batting rows, {total_pitching} pitching "
          f"rows across {len(dataset['teams'])} teams to data/stats.json")


if __name__ == "__main__":
    main()
