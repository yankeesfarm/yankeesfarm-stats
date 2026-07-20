# YankeesFarm Auto-Updating Stats — Setup Guide

This gets stats updating automatically on yankeesfarmreport.com for:
DSL Yankees, DSL Bombers, FCL Yankees, Tampa Tarpons, Hudson Valley
Renegades, Somerset Patriots, and SWB RailRiders — with zero ongoing
maintenance once it's set up. You don't need to write or understand
the code — just follow these steps.

## What you're setting up
1. A script that pulls stats from Baseball-Reference (the same source
   you already use for game logs).
2. GitHub Actions runs that script once a day automatically, for free.
3. Your Wix site reads the latest results and displays them — updated
   every time a visitor loads the page.

---

## Step 1: Create a free GitHub account
Go to github.com and sign up (skip if you already have one).

## Step 2: Create a new repository
1. Click the "+" in the top right → "New repository."
2. Name it something like `yankeesfarm-stats`.
3. Set it to **Public** (required for the free raw-file link Wix will use).
4. Click "Create repository."

## Step 3: Upload these files
Upload the whole folder structure exactly as provided:
- `scrape_stats.py`
- `.github/workflows/update-stats.yml`
- `data/stats.json`

Easiest way: on your new repo's GitHub page, click "Add file" →
"Upload files," then drag in everything (make sure the `.github` and
`data` folders keep their structure — GitHub preserves folder paths
when you drag a whole folder in).

## Step 4: Turn on GitHub Actions
1. Go to the "Actions" tab of your repo.
2. GitHub will detect the workflow file automatically — click "I
   understand my workflows, go ahead and enable them" if prompted.
3. To test it immediately rather than waiting for the daily schedule:
   Actions tab → "Update DSL/Lower-Level Stats" → "Run workflow" → Run.
4. Wait ~1 minute, refresh, and check whether it succeeded (green
   checkmark) or failed (red X). Click into it to see logs either way.

**If it fails with 0 players found:** this means Baseball-Reference's
bot protection blocked GitHub's servers specifically. This is a real
possibility — see the "If GitHub Actions gets blocked" section below.

## Step 5: Find your data URL
Once Step 4 succeeds, your live stats file lives at:
```
https://raw.githubusercontent.com/YOUR_USERNAME/YOUR_REPO/main/data/stats.json
```
Replace YOUR_USERNAME and YOUR_REPO with your actual details. Open
that URL in a browser to confirm you see real player data.

## Step 6: Wire it up in Wix
1. In the Wix Editor, enable Dev Mode (Velo) from the top toolbar.
2. Add these elements to the page:
   - A **Dropdown**, ID `teamDropdown` (so visitors can pick which of
     the 7 teams to view)
   - A **Table**, ID `statsTable`
   - Optionally, a **Text** element, ID `lastUpdatedText`
3. Open the page's code panel and paste in `wix-velo-page-code.js`
   (provided separately), updating the URL from Step 5.
4. Publish the site.

That's it — visitors pick a team from the dropdown and the table
updates instantly, all pulling from data that refreshes daily with no
further action needed from you.

---

## If GitHub Actions gets blocked
Baseball-Reference is fine with automated requests at a low rate, but
their Cloudflare protection sometimes blocks traffic from cloud
providers (like GitHub's servers) regardless of rate. If Step 4 keeps
failing:

**Fallback: run it from your own computer instead of GitHub Actions.**
- Same `scrape_stats.py` script, just run manually or on a schedule
  from your own machine (Mac: `cron`, Windows: Task Scheduler) instead
  of GitHub Actions doing it in the cloud.
- Have that scheduled task also run `git add`, `git commit`, `git push`
  to update the same GitHub repo.
- Everything downstream (Wix reading the raw URL) stays identical —
  only where the script physically runs changes.

If you hit this and want help setting up the local scheduled version
instead, just let me know and I'll write the exact scheduler
configuration for your OS.

---

## Maintenance
- If Baseball-Reference changes their page layout, the scraper may
  need small updates. You'll see this as the Actions tab showing a
  red X — that's your signal something needs a look, not you needing
  to check in on it proactively.
- If one specific team comes back empty while others work, it's
  usually because Baseball-Reference labels that team slightly
  differently than expected. Open `data/stats.json`, find how that
  team's name actually appears in the raw data, and add it to the
  matching list for that team near the top of `scrape_stats.py`
  (the `TEAM_MATCHERS` section).
- To track a different organization/year, only two lines in
  `scrape_stats.py` need changing (`ORG_ID` and `YEAR` near the top).
