/*
  PASTE THIS INTO YOUR WIX PAGE CODE (Velo)
  ------------------------------------------
  1. In the Wix Editor, turn on Dev Mode (top toolbar).
  2. Add these elements to your page:
       - A Dropdown, ID "teamDropdown" (lets visitors pick which
         of the 7 teams to view)
       - A Table, ID "statsTable"
       - (Optional) A Text element, ID "lastUpdatedText"
  3. Click the page in the left panel, open its code panel, and
     paste this in.
  4. Replace YOUR_USERNAME and YOUR_REPO below with your actual
     GitHub username and repo name.
  5. Publish the site.

  Data comes from data/stats.json, grouped by team like:
  { "teams": { "DSL Yankees": { "batting": [...], "pitching": [...] }, ... } }
*/

import { fetch } from 'wix-fetch';

const STATS_URL =
  "https://raw.githubusercontent.com/YOUR_USERNAME/YOUR_REPO/main/data/stats.json";

const TEAM_NAMES = [
  "DSL Yankees",
  "DSL Bombers",
  "FCL Yankees",
  "Tampa Tarpons",
  "Hudson Valley Renegades",
  "Somerset Patriots",
  "SWB RailRiders",
];

let statsData = null;

$w.onReady(async function () {
  $w("#teamDropdown").options = TEAM_NAMES.map((name) => ({
    label: name,
    value: name,
  }));
  $w("#teamDropdown").selectedIndex = 0;

  $w("#teamDropdown").onChange(() => {
    showTeam($w("#teamDropdown").value);
  });

  await loadStats();
  showTeam(TEAM_NAMES[0]);
});

async function loadStats() {
  try {
    const response = await fetch(STATS_URL, { method: "get" });
    statsData = await response.json();

    if (statsData.updated_at && $w("#lastUpdatedText")) {
      const updated = new Date(statsData.updated_at).toLocaleDateString();
      $w("#lastUpdatedText").text = `Stats last updated: ${updated}`;
    }
  } catch (err) {
    console.error("Couldn't load stats:", err);
  }
}

function showTeam(teamName) {
  if (!statsData || !statsData.teams || !statsData.teams[teamName]) return;

  const battingRows = statsData.teams[teamName].batting.map((p) => ({
    name: p["Name"] || p["Player"] || "",
    avg: p["BA"] || "",
    hr: p["HR"] || "",
    rbi: p["RBI"] || "",
    ops: p["OPS"] || "",
  }));

  // Adjust the field names above/below to match whatever columns
  // actually come through in stats.json (open the raw file in your
  // browser to check exact keys once real data is populated).
  $w("#statsTable").rows = battingRows;
}
