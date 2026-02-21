#!/usr/bin/env python3
"""
NEBL/BEBL Play-by-Play Batch Reader with Playwright
Fetches multiple pages from Genius Sports stats site, renders JS,
extracts pbp data, and outputs a JSON snapshot.
"""

import json
import re
import os
import argparse

try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except Exception:
    HAS_PLAYWRIGHT = False

def fetch_with_playwright(url: str, wait_time: int = 3) -> str:
    """Fetch HTML using Playwright to handle JS-rendered content"""
    if not HAS_PLAYWRIGHT:
        print("Playwright not installed. Run: pip install playwright && python -m playwright install")
        return ""
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=30000)
        # Wait for content to load
        page.wait_for_timeout(wait_time * 1000)
        content = page.content()
        browser.close()
        return content

def fetch_html_fallback(url: str) -> str:
    """Try requests first, fall back to Playwright if needed"""
    try:
        import requests
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        r = requests.get(url, timeout=15, headers=headers)
        r.raise_for_status()
        return r.text
    except Exception:
        # Fall back to Playwright
        return fetch_with_playwright(url)

def extract_teams_from_html(html: str):
    """Extract home and away team names from HTML"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)
    
    patterns = [
        r'([A-Z][A-Za-z\s&\-\']+)\s+(?:vs|v\.?|–|-|—|×|versus)\s+([A-Z][A-Za-z\s&\-\']+)',
        r'([A-Z][A-Za-z\s&\-\']+)\s*-\s*([A-Z][A-Za-z\s&\-\']+)',
    ]
    
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            return m.group(1).strip(), m.group(2).strip()
    
    return None, None

def parse_pbp_table(html: str, home: str = None, away: str = None):
    """Parse play-by-play data from HTML table"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    events = []
    
    tables = soup.find_all("table")
    
    for table in tables:
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue
            
        header_row = rows[0]
        headers = [th.get_text(strip=True).lower() for th in header_row.find_all(["th", "td"])]
        
        if not any('time' in h or 'period' in h or 'quarter' in h for h in headers):
            continue
            
        seq = 1
        for row in rows[1:]:
            cells = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
            if not cells or len(cells) < 2:
                continue
                
            line = " ".join(cells)
            
            # Extract period
            period = None
            m_p = re.search(r'(?:Q|Quarter|Period|P)\s*[:.]?\s*(\d+)', line, re.IGNORECASE)
            if m_p:
                try:
                    period = int(m_p.group(1))
                except:
                    pass
                    
            # Extract time
            time = None
            m_t = re.search(r'(\d{1,2}:\d{2})', line)
            if m_t:
                time = m_t.group(1)
                
            # Determine event type
            etype = "unknown"
            l = line.lower()
            
            if any(k in l for k in ["foul", "personal", "shooting", "technical"]):
                etype = "foul"
            elif any(k in l for k in ["rebound", "defensive", "offensive"]):
                etype = "rebound"
            elif "assist" in l:
                etype = "assist"
            elif "steal" in l:
                etype = "steal"
            elif "block" in l:
                etype = "block"
            elif "timeout" in l:
                etype = "timeout"
            elif "substitution" in l or "enters" in l or "leaves" in l:
                etype = "substitution"
            elif any(k in l for k in ["score", "points", "layup", "dunk", "jump ball", "three", "free throw", "ft", "fg"]):
                etype = "score"
            elif "turnover" in l:
                etype = "turnover"
                
            # Extract points
            pts = None
            m_pts = re.search(r'(\d+)\s*(?:pts?|points?)', line, re.IGNORECASE)
            if m_pts:
                try:
                    pts = int(m_pts.group(1))
                except:
                    pass
                    
            # Extract player name
            player = None
            for c in cells:
                if c and not c.isdigit() and len(c) > 1:
                    skip_words = ['period', 'quarter', 'score', 'team', 'home', 'away', 'q1', 'q2', 'q3', 'q4']
                    if not any(s in c.lower() for s in skip_words):
                        player = c
                        break
                        
            # Determine team
            team = None
            if home and away:
                if home.lower() in line.lower():
                    team = "home"
                elif away.lower() in line.lower():
                    team = "away"
                    
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
            
    return events

def parse_scoreboard(html: str):
    """Parse scoreboard data"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    data = {}
    
    text = soup.get_text()
    score_pattern = r'(\d+)\s*-\s*(\d+)'
    matches = re.findall(score_pattern, text)
    if matches:
        data['scores'] = matches
        
    return data

def parse_boxscore(html: str):
    """Parse box score data"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    data = {"players": [], "teams": []}
    
    tables = soup.find_all("table")
    for table in tables:
        rows = table.find_all("tr")
        for row in rows:
            cells = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
            if cells and len(cells) >= 5:
                # Likely a player row
                if any(c.isdigit() for c in cells):
                    data["players"].append(cells)
                    
    return data

def parse_leaders(html: str):
    """Parse statistical leaders"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    leaders = []
    
    tables = soup.find_all("table")
    for table in tables:
        rows = table.find_all("tr")
        for row in rows:
            cells = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
            if cells and len(cells) >= 2:
                leaders.append(cells)
                
    return leaders

def parse_standings(html: str):
    """Parse standings/team stats"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    teams = []
    
    tables = soup.find_all("table")
    for table in tables:
        rows = table.find_all("tr")
        for row in rows:
            cells = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
            if cells and len(cells) >= 2:
                teams.append(cells)
                
    return teams

def accumulate_player_stats(pbp_events):
    """Accumulate per-player statistics from pbp events"""
    stats = {}
    
    for e in pbp_events:
        player = e.get("player")
        if not player or player == "unknown":
            continue
            
        if player not in stats:
            stats[player] = {
                "Player": player,
                "Team": e.get("team", "Unknown"),
                "Points": 0,
                "Assists": 0,
                "Rebounds": 0,
                "Steals": 0,
                "Blocks": 0,
                "Turnovers": 0,
                "Fouls": 0,
                "Minutes": 0
            }
            
        if e.get("event_type") == "score" and e.get("points"):
            stats[player]["Points"] += int(e["points"])
        elif e.get("event_type") == "assist":
            stats[player]["Assists"] += 1
        elif e.get("event_type") == "rebound":
            stats[player]["Rebounds"] += 1
        elif e.get("event_type") == "steal":
            stats[player]["Steals"] += 1
        elif e.get("event_type") == "block":
            stats[player]["Blocks"] += 1
        elif e.get("event_type") == "foul":
            stats[player]["Fouls"] += 1
        elif e.get("event_type") == "turnover":
            stats[player]["Turnovers"] += 1
            
    return stats

def process_url(url: str, use_playwright: bool = True):
    """Process a single URL and extract data"""
    print(f"Fetching: {url}")
    
    try:
        if use_playwright:
            html = fetch_with_playwright(url)
        else:
            html = fetch_html_fallback(url)
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None
        
    # Determine page type from URL
    page_type = "unknown"
    if "index" in url:
        page_type = "index"
    elif "pbp" in url:
        page_type = "playbyplay"
    elif "bs" in url:
        page_type = "boxscore"
    elif "lds" in url:
        page_type = "leaders"
    elif "sc" in url:
        page_type = "scoreboard"
    elif "st" in url:
        page_type = "standings"
    elif "p.html" in url:
        page_type = "periods"
        
    # Extract teams
    home, away = extract_teams_from_html(html)
    
    result = {
        "url": url,
        "page_type": page_type,
        "home_team": home,
        "away_team": away,
        "pbp_events": [],
        "player_stats": {},
        "raw_data": {}
    }
    
    # Parse based on page type
    if page_type in ["playbyplay", "index"]:
        events = parse_pbp_table(html, home, away)
        result["pbp_events"] = events
        result["player_stats"] = accumulate_player_stats(events)
        
    elif page_type == "boxscore":
        result["raw_data"]["boxscore"] = parse_boxscore(html)
        
    elif page_type == "leaders":
        result["raw_data"]["leaders"] = parse_leaders(html)
        
    elif page_type == "scoreboard":
        result["raw_data"]["scoreboard"] = parse_scoreboard(html)
        
    elif page_type == "standings":
        result["raw_data"]["standings"] = parse_standings(html)
        
    elif page_type == "periods":
        result["raw_data"]["periods"] = parse_scoreboard(html)
        
    print(f"  Found {len(result['pbp_events'])} pbp events, {len(result['player_stats'])} players")
    
    return result

def main():
    parser = argparse.ArgumentParser(description="NEBL Play-by-Play Batch Reader with Playwright")
    parser.add_argument("--base", default="https://fibalivestats.dcd.shared.geniussports.com/u/BBF/2799694", 
                        help="Base URL for the game")
    parser.add_argument("--game-id", default="2799694", help="Game ID")
    parser.add_argument("--out", default="data/pbp_output.json", help="Output JSON path")
    parser.add_argument("--no-playwright", action="store_true", help="Disable Playwright, use requests only")
    parser.add_argument("--urls", help="Comma-separated URLs to fetch (overrides --base)")
    args = parser.parse_args()
    
    # Build list of URLs to fetch
    if args.urls:
        urls = [u.strip() for u in args.urls.split(",")]
    else:
        base = args.base
        urls = [
            f"{base}/index.html",
            f"{base}/bs.html",
            f"{base}/lds.html",
            f"{base}/pbp.html",
            f"{base}/sc.html",
            f"{base}/st.html",
            f"{base}/p.html",
        ]
    
    print(f"Processing {len(urls)} URLs with Playwright...")
    
    results = []
    for url in urls:
        result = process_url(url, use_playwright=not args.no_playwright)
        if result:
            results.append(result)
    
    # Combine all pbp events
    all_pbp = []
    all_player_stats = {}
    
    for r in results:
        if r.get("pbp_events"):
            all_pbp.extend(r["pbp_events"])
        if r.get("player_stats"):
            for player, stats in r["player_stats"].items():
                if player not in all_player_stats:
                    all_player_stats[player] = stats
                else:
                    for key in ["Points", "Assists", "Rebounds", "Steals", "Blocks", "Turnovers", "Fouls"]:
                        if key in stats:
                            all_player_stats[player][key] = all_player_stats[player].get(key, 0) + stats[key]
    
    # Build output
    output = {
        "game_id": args.game_id,
        "base_url": args.base,
        "urls_processed": urls,
        "home_team": results[0].get("home_team") if results else None,
        "away_team": results[0].get("away_team") if results else None,
        "total_pbp_events": len(all_pbp),
        "total_players": len(all_player_stats),
        "pbp_events": all_pbp,
        "player_stats": list(all_player_stats.values()),
        "page_details": results
    }
    
    # Save output
    os.makedirs(os.path.dirname(args.out) if os.path.dirname(args.out) else ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"\nOutput saved to {args.out}")
    print(f"Total pbp events: {len(all_pbp)}")
    print(f"Total players: {len(all_player_stats)}")
    
    # Print sample
    if all_pbp:
        print("\nSample pbp events:")
        for e in all_pbp[:5]:
            print(f"  {e.get('period')} {e.get('time')} - {e.get('player')}: {e.get('event_type')} ({e.get('points')})")
    
    if all_player_stats:
        print("\nTop players by points:")
        sorted_players = sorted(all_player_stats.values(), key=lambda x: x.get('Points', 0), reverse=True)
        for p in sorted_players[:5]:
            print(f"  {p['Player']}: {p['Points']} pts")

if __name__ == "__main__":
    main()
