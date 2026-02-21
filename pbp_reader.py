#!/usr/bin/env python3
"""
NEBL/BEBL Play-by-Play Reader
Parses the actual pbp data from the NEBL/Genius Sports HTML pages.
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

def fetch_with_playwright(url: str, wait_time: int = 5) -> str:
    """Fetch HTML using Playwright to handle JS-rendered content"""
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

def parse_pbp_from_nebl_html(html: str):
    """Parse the actual NEBL/Genius Sports pbp structure"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    
    events = []
    
    # Find all pbp action rows
    pbp_rows = soup.find_all('div', class_='pbpa')
    
    home_team = None
    away_team = None
    
    # Try to get team names
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
        # Get team - pbp-team0, pbp-team1, pbp-team2
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
        
        # Get time
        time_elem = row.find('span', class_='pbp-period')
        time_elem2 = row.find('div', class_='pbp-time')
        
        period = None
        time_str = None
        
        if time_elem:
            period_text = time_elem.get_text(strip=True)
            m = re.search(r'P(\d+)', period_text)
            if m:
                period = int(m.group(1))
        
        if time_elem2:
            time_full = time_elem2.get_text(strip=True)
            # Extract time like 09:58:00
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
                player_num = m.group(1)
                player = m.group(2).strip()
            
            # Determine event type
            desc_lower = description.lower()
            
            if 'made' in desc_lower or 'score' in desc_lower:
                event_type = "score"
                # Check for points
                if '3pt' in desc_lower or 'three' in desc_lower:
                    points = 3
                elif '2pt' in desc_lower:
                    points = 2
                elif 'free throw' in desc_lower or 'ft' in desc_lower:
                    points = 1
                else:
                    # Try to find point value
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
    """Accumulate per-player statistics from pbp events"""
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
    parser = argparse.ArgumentParser(description="NEBL Play-by-Play Reader")
    parser.add_argument("--url", default="https://nebl.web.geniussports.com/competitions/?WHurl=%2Fcompetition%2F48108%2Fmatch%2F2799695%2Fplaybyplay%3F", 
                        help="PBp page URL")
    parser.add_argument("--game-id", default="2799694", help="Game ID")
    parser.add_argument("--out", default="data/pbp_output.json", help="Output JSON path")
    args = parser.parse_args()
    
    print(f"Fetching: {args.url}")
    
    html = fetch_with_playwright(args.url)
    
    if not html:
        print("Failed to fetch page")
        return
    
    print("Parsing pbp data...")
    events, home_team, away_team = parse_pbp_from_nebl_html(html)
    
    player_stats = accumulate_player_stats(events)
    
    # Build output
    output = {
        "game_id": args.game_id,
        "url": args.url,
        "home_team": home_team,
        "away_team": away_team,
        "total_events": len(events),
        "total_players": len(player_stats),
        "pbp_events": events,
        "player_stats": list(player_stats.values())
    }
    
    # Save output
    os.makedirs(os.path.dirname(args.out) if os.path.dirname(args.out) else ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"\nOutput saved to {args.out}")
    print(f"Total events: {len(events)}")
    print(f"Total players: {len(player_stats)}")
    
    # Print sample
    if events:
        print("\nSample events:")
        for e in events[:10]:
            print(f"  Q{e.get('period')} {e.get('time')} - {e.get('team')} - {e.get('player')}: {e.get('event_type')} ({e.get('points')}) - Score: {e.get('home_score')}-{e.get('away_score')}")
    
    if player_stats:
        print("\nTop players by points:")
        sorted_players = sorted(player_stats.values(), key=lambda x: x.get('Points', 0), reverse=True)
        for p in sorted_players[:10]:
            print(f"  {p['Player']}: {p['Points']} pts, {p['Assists']} ast, {p['Rebounds']} reb")

if __name__ == "__main__":
    main()
