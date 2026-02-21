#!/usr/bin/env python3
"""
NEBL Multi-Page Data Fetcher
Fetches all sub-pages: index, bs, lds, pbp, sc, p
"""

import json
import os
import re
import argparse
from datetime import datetime

try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except Exception:
    HAS_PLAYWRIGHT = False

def fetch_page(url):
    if not HAS_PLAYWRIGHT:
        print("Playwright not installed")
        return ""
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        page = context.new_page()
        page.goto(url, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(3000)
        content = page.content()
        browser.close()
        return content

def parse_index(html):
    """Parse main index page"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    
    data = {
        'teams': {},
        'score': {'home': 0, 'away': 0},
        'period': None,
        'game_time': None,
        'status': 'unknown'
    }
    
    # Get teams
    home_img = soup.find('img', class_='logo home-logo')
    away_img = soup.find('img', class_='logo away-logo')
    
    if home_img and home_img.get('alt'):
        data['teams']['home'] = home_img.get('alt')
    if away_img and away_img.get('alt'):
        data['teams']['away'] = away_img.get('alt')
    
    # Get score - try multiple selectors
    score_elems = soup.find_all('span', class_='pbpsc')
    for elem in score_elems:
        text = elem.get_text(strip=True)
        m = re.search(r'(\d+)\s*-\s*(\d+)', text)
        if m:
            data['score']['home'] = int(m.group(1))
            data['score']['away'] = int(m.group(2))
    
    # Get period/time
    time_elems = soup.find_all('div', class_='pbp-time')
    for elem in time_elems:
        text = elem.get_text(strip=True)
        m = re.search(r'P(\d+)', text)
        if m:
            data['period'] = int(m.group(1))
    
    return data

def parse_boxscore(html):
    """Parse box score page"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    
    data = {
        'home_players': [],
        'away_players': [],
        'home_totals': {},
        'away_totals': {}
    }
    
    tables = soup.find_all('table')
    
    for table in tables:
        rows = table.find_all('tr')
        for row in rows:
            cells = [c.get_text(strip=True) for c in row.find_all(['td', 'th'])]
            if len(cells) < 3:
                continue
            
            # Try to identify player rows (have numbers)
            if cells[0].isdigit() or '#' in cells[0]:
                player_data = {
                    'num': cells[0].replace('#', ''),
                    'name': cells[1] if len(cells) > 1 else '',
                    'mins': cells[2] if len(cells) > 2 else '',
                    'pts': cells[3] if len(cells) > 3 else '',
                    'fgm': cells[4] if len(cells) > 4 else '',
                    'fga': cells[5] if len(cells) > 5 else '',
                    '3pm': cells[6] if len(cells) > 6 else '',
                    '3pa': cells[7] if len(cells) > 7 else '',
                    'ftm': cells[8] if len(cells) > 8 else '',
                    'fta': cells[9] if len(cells) > 9 else '',
                    'oreb': cells[10] if len(cells) > 10 else '',
                    'dreb': cells[11] if len(cells) > 11 else '',
                    'reb': cells[12] if len(cells) > 12 else '',
                    'ast': cells[13] if len(cells) > 13 else '',
                    'stl': cells[14] if len(cells) > 14 else '',
                    'blk': cells[15] if len(cells) > 15 else '',
                    'to': cells[16] if len(cells) > 16 else '',
                    'pf': cells[17] if len(cells) > 17 else '',
                    '+/-': cells[18] if len(cells) > 18 else '',
                }
                # Determine team (first team table = home, second = away)
                if 'home_players' not in data or len(data['home_players']) < len(data.get('away_players', [])):
                    data['home_players'].append(player_data)
                else:
                    data['away_players'].append(player_data)
    
    return data

def parse_leaders(html):
    """Parse leaders page"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    
    data = {
        'leaders': []
    }
    
    tables = soup.find_all('table')
    
    for table in tables:
        rows = table.find_all('tr')
        for row in rows:
            cells = [c.get_text(strip=True) for c in row.find_all(['td', 'th'])]
            if len(cells) >= 3:
                data['leaders'].append({
                    'rank': cells[0],
                    'player': cells[1],
                    'value': cells[2]
                })
    
    return data

def parse_pbp(html):
    """Parse play-by-play page"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    
    events = []
    pbp_rows = soup.find_all('div', class_='pbpa')
    
    home_score = 0
    away_score = 0
    seq = 1
    
    for row in pbp_rows:
        team_class = None
        for cls in row.get('class', []):
            if cls.startswith('pbp-team'):
                team_class = cls
                break
        
        team = 'home' if team_class == 'pbp-team1' else 'away' if team_class == 'pbp-team2' else None
        
        # Period & Time
        period = None
        time_str = None
        period_elem = row.find('span', class_='pbp-period')
        if period_elem:
            m = re.search(r'P(\d+)', period_elem.get_text())
            if m: period = int(m.group(1))
        
        time_elem = row.find('div', class_='pbp-time')
        if time_elem:
            m = re.search(r'(\d{1,2}:\d{2}):\d{2}', time_elem.get_text())
            if m: time_str = m.group(1)
        
        # Score
        score_elem = row.find('span', class_='pbpsc')
        if score_elem:
            m = re.search(r'(\d+)-(\d+)', score_elem.get_text())
            if m:
                home_score = int(m.group(1))
                away_score = int(m.group(2))
        
        # Action
        action_elem = row.find('div', class_='pbp-action')
        description = action_elem.get_text(strip=True) if action_elem else ''
        player = None
        event_type = 'unknown'
        points = None
        
        if action_elem:
            m = re.search(r'<strong>(\d+),\s*([^<]+)</strong>', str(action_elem))
            if m: player = m.group(2).strip()
            
            desc_lower = description.lower()
            if 'made' in desc_lower or 'score' in desc_lower:
                event_type = 'score'
                if '3pt' in desc_lower: points = 3
                elif '2pt' in desc_lower: points = 2
                elif 'free throw' in desc_lower: points = 1
            elif 'rebound' in desc_lower: event_type = 'rebound'
            elif 'assist' in desc_lower: event_type = 'assist'
            elif 'foul' in desc_lower: event_type = 'foul'
            elif 'turnover' in desc_lower: event_type = 'turnover'
            elif 'steal' in desc_lower: event_type = 'steal'
            elif 'block' in desc_lower: event_type = 'block'
        
        events.append({
            'seq': seq, 'period': period, 'time': time_str, 'team': team,
            'player': player, 'type': event_type, 'points': points,
            'score': f"{home_score}-{away_score}"
        })
        seq += 1
    
    return {'events': events, 'home_score': home_score, 'away_score': away_score}

def parse_scoreboard(html):
    """Parse scoreboard page"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    
    data = {
        'periods': {},
        'final': {'home': 0, 'away': 0}
    }
    
    # Try to find period scores
    tables = soup.find_all('table')
    for table in tables:
        rows = table.find_all('tr')
        for row in rows:
            cells = [c.get_text(strip=True) for c in row.find_all(['td', 'th'])]
            # Look for patterns like "20-15" (period scores)
            for i, cell in enumerate(cells):
                m = re.search(r'(\d+)\s*-\s*(\d+)', cell)
                if m:
                    period_name = f"period_{i+1}"
                    data['periods'][period_name] = {
                        'home': int(m.group(1)),
                        'away': int(m.group(2))
                    }
    
    # Final score
    score_elems = soup.find_all('span', class_='pbpsc')
    for elem in score_elems:
        text = elem.get_text(strip=True)
        m = re.search(r'(\d+)\s*-\s*(\d+)', text)
        if m:
            data['final'] = {'home': int(m.group(1)), 'away': int(m.group(2))}
    
    return data

def parse_periods(html):
    """Parse periods page"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    
    data = {
        'quarters': []
    }
    
    # Look for period data
    tables = soup.find_all('table')
    for table in tables:
        rows = table.find_all('tr')
        for row in rows:
            cells = [c.get_text(strip=True) for c in row.find_all(['td', 'th'])]
            if len(cells) >= 3:
                data['quarters'].append({
                    'period': cells[0],
                    'home': cells[1] if len(cells) > 1 else '',
                    'away': cells[2] if len(cells) > 2 else ''
                })
    
    return data

def main():
    parser = argparse.ArgumentParser(description="NEBL Multi-Page Fetcher")
    parser.add_argument("--game-id", default="2799694", help="Game ID")
    parser.add_argument("--base", default="https://fibalivestats.dcd.shared.geniussports.com/u/BBF/{game_id}", 
                        help="Base URL template")
    parser.add_argument("--out", default="data/full_game.json", help="Output file")
    args = parser.parse_args()
    
    base_url = args.base.format(game_id=args.game_id)
    
    pages = {
        'index': f"{base_url}/index.html",
        'boxscore': f"{base_url}/bs.html", 
        'leaders': f"{base_url}/lds.html",
        'playbyplay': f"{base_url}/pbp.html",
        'scoreboard': f"{base_url}/sc.html",
        'periods': f"{base_url}/p.html"
    }
    
    print(f"Fetching all pages for game {args.game_id}...")
    
    result = {
        'game_id': args.game_id,
        'base_url': base_url,
        'fetched_at': datetime.now().isoformat(),
        'pages': {}
    }
    
    for page_name, url in pages.items():
        print(f"  Fetching {page_name}...")
        try:
            html = fetch_page(url)
            if not html:
                print(f"    Failed to fetch {page_name}")
                continue
            
            if page_name == 'index':
                result['pages']['index'] = parse_index(html)
            elif page_name == 'boxscore':
                result['pages']['boxscore'] = parse_boxscore(html)
            elif page_name == 'leaders':
                result['pages']['leaders'] = parse_leaders(html)
            elif page_name == 'playbyplay':
                result['pages']['playbyplay'] = parse_pbp(html)
            elif page_name == 'scoreboard':
                result['pages']['scoreboard'] = parse_scoreboard(html)
            elif page_name == 'periods':
                result['pages']['periods'] = parse_periods(html)
            
            print(f"    OK: {page_name}")
            
        except Exception as e:
            print(f"    Error: {e}")
    
    # Save
    os.makedirs(os.path.dirname(args.out) if os.path.dirname(args.out) else ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    
    print(f"\nSaved to {args.out}")
    
    # Summary
    print("\nSummary:")
    if 'index' in result['pages']:
        idx = result['pages']['index']
        print(f"  Teams: {idx.get('teams', {}).get('home')} vs {idx.get('teams', {}).get('away')}")
        print(f"  Score: {idx.get('score', {}).get('home')} - {idx.get('score', {}).get('away')}")
    
    if 'playbyplay' in result['pages']:
        pbp = result['pages']['playbyplay']
        print(f"  PBP Events: {len(pbp.get('events', []))}")
    
    if 'boxscore' in result['pages']:
        bs = result['pages']['boxscore']
        print(f"  Home Players: {len(bs.get('home_players', []))}")
        print(f"  Away Players: {len(bs.get('away_players', []))}")

if __name__ == "__main__":
    main()
