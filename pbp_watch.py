#!/usr/bin/env python3
"""
NEBL Play-by-Play Watch Mode
Targets aj_pbp div for live data
"""

import json
import os
import argparse
import time
from datetime import datetime

try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except Exception:
    HAS_PLAYWRIGHT = False

def fetch_with_playwright(url: str, wait_time: int = 5) -> str:
    if not HAS_PLAYWRIGHT:
        print("Playwright not installed.")
        return ""
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        page = context.new_page()
        page.goto(url, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(wait_time * 1000)
        content = page.content()
        browser.close()
        return content

def parse_pbp_from_aj_pbp(html: str):
    """Parse the aj_pbp div specifically"""
    from bs4 import BeautifulSoup
    import re
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # Target the aj_pbp div
    aj_pbp = soup.find('div', id='aj_pbp')
    
    if not aj_pbp:
        print("Could not find aj_pbp div, trying alternate selectors...")
        # Fallback to the pbpa class
        aj_pbp = soup
    
    events = []
    pbp_rows = aj_pbp.find_all('div', class_='pbpa') if aj_pbp else []
    
    # Get teams
    home_team = None
    away_team = None
    
    home_img = soup.find('img', class_='logo home-logo')
    away_img = soup.find('img', class_='logo away-logo')
    
    if home_img and home_img.get('alt'):
        home_team = home_img.get('alt')
    if away_img and away_img.get('alt'):
        away_team = away_img.get('alt')
    
    seq = 1
    home_score = 0
    away_score = 0
    
    for row in pbp_rows:
        team_class = None
        for cls in row.get('class', []):
            if cls.startswith('pbp-team'):
                team_class = cls
                break
        
        team = None
        if team_class == 'pbp-team1':
            team = 'home'
        elif team_class == 'pbp-team2':
            team = 'away'
        
        # Get period and time
        period = None
        time_str = None
        
        # Try multiple selectors for period
        period_elem = row.find('span', class_='pbp-period')
        if period_elem:
            period_text = period_elem.get_text(strip=True)
            m = re.search(r'P(\d+)', period_text)
            if m:
                period = int(m.group(1))
        
        # Get time
        time_elem = row.find('div', class_='pbp-time')
        if time_elem:
            time_full = time_elem.get_text(strip=True)
            m = re.search(r'(\d{1,2}:\d{2}):\d{2}', time_full)
            if m:
                time_str = m.group(1)
        
        # Get score
        score_elem = row.find('span', class_='pbpsc')
        if score_elem:
            score_text = score_elem.get_text(strip=True)
            m = re.search(r'(\d+)-(\d+)', score_text)
            if m:
                home_score = int(m.group(1))
                away_score = int(m.group(2))
        
        # Get action/description
        action_elem = row.find('div', class_='pbp-action')
        description = ""
        player = None
        event_type = "unknown"
        points = None
        
        if action_elem:
            description = action_elem.get_text(strip=True)
            
            # Extract player number and name
            m = re.search(r'<strong>(\d+),\s*([^<]+)</strong>', str(action_elem))
            if m:
                player = m.group(2).strip()
            
            desc_lower = description.lower()
            
            if 'made' in desc_lower or 'score' in desc_lower:
                event_type = "score"
                if '3pt' in desc_lower or 'three' in desc_lower:
                    points = 3
                elif '2pt' in desc_lower:
                    points = 2
                elif 'free throw' in desc_lower or ' ft ' in desc_lower:
                    points = 1
                else:
                    m_pts = re.search(r'(\d+)\s*pt', desc_lower)
                    if m_pts:
                        points = int(m_pts.group(1))
            elif 'rebound' in desc_lower:
                event_type = "rebound"
            elif 'assist' in desc_lower:
                event_type = "assist"
            elif 'foul' in desc_lower:
                event_type = "foul"
            elif 'turnover' in desc_lower:
                event_type = "turnover"
            elif 'steal' in desc_lower:
                event_type = "steal"
            elif 'block' in desc_lower:
                event_type = "block"
            elif 'timeout' in desc_lower:
                event_type = "timeout"
            elif 'substitution' in desc_lower or 'enters' in desc_lower or 'leaves' in desc_lower:
                event_type = "substitution"
            elif 'jump ball' in desc_lower:
                event_type = "jumpball"
            elif 'period start' in desc_lower or 'game start' in desc_lower:
                event_type = "period_start"
            elif 'possession arrow' in desc_lower:
                event_type = "possession"
        
        events.append({
            "sequence": seq,
            "period": period,
            "time": time_str,
            "team": team,
            "player": player,
            "event_type": event_type,
            "points": points,
            "home_score": home_score,
            "away_score": away_score,
            "description": description
        })
        
        seq += 1
    
    return events, home_team, away_team

def accumulate_player_stats(pbp_events):
    stats = {}
    
    for e in pbp_events:
        player = e.get("player")
        team = e.get("team", "Unknown")
        
        if not player:
            continue
            
        if player not in stats:
            stats[player] = {
                "Player": player,
                "Team": team,
                "Points": 0,
                "Assists": 0,
                "Rebounds": 0,
                "Steals": 0,
                "Blocks": 0,
                "Turnovers": 0,
                "Fouls": 0
            }
        
        etype = e.get("event_type")
        pts = e.get("points")
        
        if etype == "score" and pts:
            stats[player]["Points"] += pts
        elif etype == "assist":
            stats[player]["Assists"] += 1
        elif etype == "rebound":
            stats[player]["Rebounds"] += 1
        elif etype == "steal":
            stats[player]["Steals"] += 1
        elif etype == "block":
            stats[player]["Blocks"] += 1
        elif etype == "foul":
            stats[player]["Fouls"] += 1
        elif etype == "turnover":
            stats[player]["Turnovers"] += 1
            
    return stats

def main():
    parser = argparse.ArgumentParser(description="NEBL Play-by-Play Watch Mode - aj_pbp")
    parser.add_argument("--url", default="https://nebl.web.geniussports.com/competitions/?WHurl=%2Fcompetition%2F48108%2Fmatch%2F2799695%2Fplaybyplay%3F", 
                        help="PBp page URL")
    parser.add_argument("--game-id", default="2799695", help="Game ID")
    parser.add_argument("--out", default="data/debug_live.json", help="Output JSON path")
    parser.add_argument("--poll", type=float, default=0.5, help="Poll interval in seconds")
    parser.add_argument("--max", type=int, default=0, help="Max updates (0 = infinite)")
    args = parser.parse_args()
    
    print(f"Starting watch mode for game {args.game_id}")
    print(f"URL: {args.url}")
    print(f"Poll interval: {args.poll} seconds")
    print(f"Target: aj_pbp div")
    print("-" * 50)
    
    last_event_count = 0
    update_count = 0
    
    while True:
        try:
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Fetching latest data...")
            
            html = fetch_with_playwright(args.url)
            
            if not html:
                print("Failed to fetch, retrying...")
                time.sleep(args.poll)
                continue
            
            events, home_team, away_team = parse_pbp_from_aj_pbp(html)
            player_stats = accumulate_player_stats(events)
            
            # Get current score
            current_home_score = events[-1].get("home_score", 0) if events else 0
            current_away_score = events[-1].get("away_score", 0) if events else 0
            
            new_events = len(events) - last_event_count
            
            if new_events > 0 or last_event_count == 0:
                print(f"  Home: {home_team} | Away: {away_team}")
                print(f"  Score: {current_home_score} - {current_away_score}")
                print(f"  Events: {len(events)} (+{new_events})")
                print(f"  Players: {len(player_stats)}")
                
                # Show latest event
                if events:
                    latest = events[-1]
                    print(f"  Last: Q{latest.get('period')} {latest.get('time')} - {latest.get('player')}: {latest.get('event_type')}")
                
                # Save to file
                output = {
                    "game_id": args.game_id,
                    "url": args.url,
                    "home_team": home_team,
                    "away_team": away_team,
                    "current_score": {"home": current_home_score, "away": current_away_score},
                    "last_update": datetime.now().isoformat(),
                    "total_events": len(events),
                    "total_players": len(player_stats),
                    "pbp_events": events,
                    "player_stats": list(player_stats.values())
                }
                
                os.makedirs(os.path.dirname(args.out) if os.path.dirname(args.out) else ".", exist_ok=True)
                with open(args.out, "w", encoding="utf-8") as f:
                    json.dump(output, f, indent=2, ensure_ascii=False)
                
                last_event_count = len(events)
                update_count += 1
            else:
                print(f"  No new events. Score: {current_home_score} - {current_away_score}")
            
            # Check max updates
            if args.max > 0 and update_count >= args.max:
                print(f"\nReached max updates ({args.max}). Exiting.")
                break
                
        except KeyboardInterrupt:
            print("\n\nWatch mode stopped.")
            break
        except Exception as e:
            print(f"Error: {e}")
        
        time.sleep(args.poll)

if __name__ == "__main__":
    main()
