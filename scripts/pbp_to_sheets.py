#!/usr/bin/env python3
"""
Local NEBL PBp to Sheets (testable locally).
Fetches a NEBL pbp page, extracts per-event play-by-play and per-player stats.
Writes a local snapshot to data/pbp_to_sheets.json and optionally pushes to Google Sheets via a service account.
"""
import argparse
import json
import os
import re
import requests
try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except Exception:
    BeautifulSoup = None
    HAS_BS4 = False

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    HAS_SHEETS = True
except Exception:
    HAS_SHEETS = False

# Headers for a CSV-like view in Sheets (if you later enable it)
DEF_HEADERS_PBP = ["Sequence","Period","Time","Team","Player","Event","Points","ScoreBefore","ScoreAfter","Description"]
DEF_HEADERS_STATS = ["Player","Team","Points","Assists","Rebounds","Steals","Blocks","Turnovers","Fouls","Minutes"]

def fetch_html(url: str) -> str:
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    return resp.text

def extract_teams_from_header(html: str):
    if not HAS_BS4 or BeautifulSoup is None:
        return None, None
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    m = re.search(r'([A-Z][A-Za-z\s&\-]+)\s*(?:vs|vs\.|–|-|—|×|versus)\s*([A-Z][A-Za-z\s&\-]+)', text)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    m = re.search(r'([A-Za-z\s]+)\s+vs\s+([A-Za-z\s]+)', text)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return None, None

def parse_pbp_from_html(html, home=None, away=None):
    if not HAS_BS4 or BeautifulSoup is None:
        return [], home, away, 0, 0
    soup = BeautifulSoup(html, "html.parser")
    table = None
    for tbl in soup.find_all("table"):
        if tbl.find("tbody"):
            table = tbl
            break
    events = []
    home_score, away_score = 0, 0
    seq = 1
    if not table:
        return events, home, away, home_score, away_score
    rows = table.find_all("tr")
    for row in rows[1:]:
        cells = [c.get_text(strip=True) for c in row.find_all(["td","th"])]
        if not cells:
            continue
        line = " ".join(cells)
        period = None
        m_period = re.search(r'Q\s*(\d+)|Period\s*(\d+)|P\s*(\d+)', line, re.IGNORECASE)
        if m_period:
            for g in m_period.groups():
                if g:
                    try:
                        period = int(g)
                        break
                    except:
                        pass
        time = None
        m_time = re.search(r'(\d{1,2}:\d{2})', line)
        if m_time:
            time = m_time.group(1)
        etype = "unknown"
        if any(k in line.lower() for k in ["score","points","layup","dunk","free throw","ft","three","pt"]):
            etype = "score"
        if "foul" in line.lower():
            etype = "foul"
        if "rebound" in line.lower():
            etype = "rebound"
        if "assist" in line.lower():
            etype = "assist"
        if "steal" in line.lower():
            etype = "steal"
        if "block" in line.lower():
            etype = "block"
        if "timeout" in line.lower():
            etype = "timeout"
        if "substitution" in line.lower():
            etype = "substitution"
        pts = None
        m_pts = re.search(r'(\d+)\s*(?:pts|points|pt|pg)?', line, re.IGNORECASE)
        if m_pts:
            try:
                pts = int(m_pts.group(1))
            except:
                pts = None
        player = None
        for t in cells:
            if t and not t.isdigit() and not re.fullmatch(r'\d+', t):
                if home and away:
                    if home.lower() in t.lower() or away.lower() in t.lower():
                        continue
                if len(t) > 2:
                    player = t
                    break
        team = None
        if home and away:
            if home.lower() in line.lower():
                team = "home"
            elif away.lower() in line.lower():
                team = "away"
        if not player and cells:
            for t in cells:
                if t:
                    player = t
                    break
        events.append({
            "sequence": seq,
            "period": period,
            "time": time,
            "team": team,
            "player": player,
            "event_type": etype,
            "points": pts,
            "score_before": None,
            "score_after": None,
            "description": line
        })
        seq += 1
    return events, home, away, home_score, away_score

def accumulate_player_stats(pbp_events):
    stats = {}
    for ev in pbp_events:
        player = ev.get("player")
        if not player:
            continue
        if player not in stats:
            stats[player] = {"Player": player, "Team": ev.get("team", "Unknown"), "Points":0, "Assists":0, "Rebounds":0, "Steals":0, "Blocks":0, "Turnovers":0, "Fouls":0, "Minutes":0}
        if ev.get("event_type") == "score" and ev.get("points"):
            stats[player]["Points"] += int(ev["points"])
        if ev.get("event_type") == "assist":
            stats[player]["Assists"] += 1
        if ev.get("event_type") == "rebound":
            stats[player]["Rebounds"] += 1
        if ev.get("event_type") == "steal":
            stats[player]["Steals"] += 1
        if ev.get("event_type") == "block":
            stats[player]["Blocks"] += 1
        if ev.get("event_type") == "foul":
            stats[player]["Fouls"] += 1
        if ev.get("event_type") == "turnover" or ev.get("event_type") == "Turnover":
            stats[player]["Turnovers"] += 1
    return stats

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--out", default="data/pbp_to_sheets.json")
    parser.add_argument("--dry-run", action="store_true", dest="dry_run", help="Dry run: do not write to Sheets")
    parser.add_argument("--creds", default=None, help="Credentials for Sheets (optional)")
    parser.add_argument("--sheet", default=None, help="Spreadsheet ID (optional)")
    parser.add_argument("--pbp-sheet", default="PBp")
    parser.add_argument("--stats-sheet", default="PlayerStats")
    parser.add_argument("--watch", action="store_true", help="Watch mode (not yet implemented)")
    parser.add_argument("--poll", type=int, default=15, help="Poll interval seconds (if watch)")
    args = parser.parse_args()

    html = fetch_html(args.url)
    home, away = extract_teams_from_header(html)
    pbp_events, home, away, score_h, score_a = parse_pbp_from_html(html, home, away)
    player_stats = accumulate_player_stats(pbp_events)
    data = {"game_url": args.url, "pbp_events": pbp_events, "player_stats": player_stats}
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Wrote pbp snapshot to {args.out} with {len(pbp_events)} events.")

    if args.dry_run or not args.creds or not args.sheet:
        print("Dry-run: Sheets export skipped.")
        return
    if not HAS_SHEETS:
        print("Google Sheets libs not installed. Install google-api-python-client and google-auth to enable Sheets export.")
        return
    print("Sheets export path configured but not implemented in this offline test.")

if __name__ == "__main__":
    main()
