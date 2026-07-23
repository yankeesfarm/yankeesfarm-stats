"""
YankeesFarm Transactions Scraper
-----------------------------------
Pulls recent transactions (promotions, assignments, releases, IL moves,
etc.) for these Yankees affiliates from MLB's official Stats API, and
writes the result to data/transactions.json:
  - DSL Yankees
  - DSL Bombers
  - FCL Yankees
  - Tampa Tarpons
  - Hudson Valley Renegades
  - Somerset Patriots
  - SWB RailRiders
"""

import json
import sys
from datetime import datetime, timezone

import requests

YANKEES_MLB_TEAM_ID = 147
YEAR = 2026
SEASON_START = f"{YEAR}-01-01"
SEASON_END = datetime.now(timezone.utc).strftime("%Y-%m-%d")

API_BASE = "https://statsapi.mlb.com/api/v1"

TEAM_MATCHERS = {
    "DSL Bombers": ["bombers"],
    "DSL Yankees": ["dsl yankees", "dsl nyy"],
    "FCL Yankees": ["fcl yankees"],
    "Tampa Tarpons": ["tampa"],
    "Hudson Valley Renegades": ["hudson valley"],
    "Somerset Patriots": ["somerset"],
    "SWB RailRiders": ["scranton", "railriders", "swb"],
}

HEADERS = {
    "User-Agent": "yankeesfarm-report-transactions-script/1.0",
}


def match_team(name_val: str, extra_val: str = ""):
    combined = f"{name_val} {extra_val}".lower()
    for canonical, needles in TEAM_MATCHERS.items():
        if any(n in combined for n in needles):
            return canonical
    return None


def get_affiliate_team_ids():
    url = f"{API_BASE}/teams/{YANKEES_MLB_TEAM_ID}"
    params = {"hydrate": "affiliates", "season": YEAR}
    resp = requests.get(url, params=params, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    teams_data = data.get("teams", [])
    if not teams_data:
        return {}

    affiliates = teams_data[0].get("affiliates", [])
    ids = {}
    for aff in affiliates:
        canonical = match_team(aff.get("name", ""), aff.get("teamName", ""))
        if canonical and canonical not in ids:
            ids[canonical] = aff.get("id")
    return ids


def get_transactions_for_team(team_id):
    url = f"{API_BASE}/transactions"
    params = {
        "teamId": team_id,
        "startDate": SEASON_START,
        "endDate": SEASON_END,
    }
    resp = requests.get(url, params=params, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("transactions", [])


def build_dataset():
    team_ids = get_affiliate_team_ids()

    teams_data = {name: [] for name in TEAM_MATCHERS}

    for canonical, team_id in team_ids.items():
        if not team_id:
            continue
        try:
            raw_txns = get_transactions_for_team(team_id)
        except requests.HTTPError as e:
            print(f"Couldn't fetch transactions for {canonical}: {e}", file=sys.stderr)
            continue

        cleaned = []
        for t in raw_txns:
            cleaned.append({
                "date": t.get("date"),
                "player": t.get("person", {}).get("fullName", ""),
                "type": t.get("typeDesc", ""),
                "description": t.get("description", ""),
            })
        cleaned.sort(key=lambda x: x["date"] or "", reverse=True)
        teams_data[canonical] = cleaned

    missing = [name for name in TEAM_MATCHERS if name not in team_ids]
    if missing:
        print(f"WARNING: couldn't find a team ID match for: {', '.join(missing)}.", file=sys.stderr)

    return {
        "org": "NYY",
        "season": YEAR,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "teams": teams_data,
    }


def main():
    try:
        dataset = build_dataset()
    except requests.HTTPError as e:
        print(f"HTTP error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)

    total = sum(len(v) for v in dataset["teams"].values())
    if total == 0:
        print("WARNING: 0 transactions found across all teams.", file=sys.stderr)

    with open("data/transactions.json", "w") as f:
        json.dump(dataset, f, indent=2)

    print(f"Wrote {total} transactions across {len(dataset['teams'])} teams "
          f"to data/transactions.json")


if __name__ == "__main__":
    main()
