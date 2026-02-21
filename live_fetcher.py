#!/usr/bin/env python3
"""
NEBL Live Multi-Page Fetcher
- Fast polling (0.1s)
- Error handling
- State saving
- All available data from all pages
"""

import json
import os
import re
import argparse
import time
from datetime import datetime

try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except Exception:
    HAS_PLAYWRIGHT = False
    print("WARNING: Playwright not installed")

# State file for saving progress
STATE_FILE = "data/fetcher_state.json"

def save_state(state):
    """Save current state to file"""
    os.makedirs("data", exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def load_state():
    """Load saved state"""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {}

def fetch_page(url, timeout=30000):
    """Fetch a single page with error handling"""
    if not HAS_PLAYWRIGHT:
        return ""
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            page = context.new_page()
            page.goto(url, wait_until="networkidle", timeout=timeout)
            page.wait_for_timeout(1500)  # Wait for JS
            content = page.content()
            browser.close()
            return content
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return ""

def parse_index(html):
    """Parse main index page - scoreboard, clock, teams"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    
    data = {
        'teams': {'home': None, 'away': None},
        'score': {'home': 0, 'away': 0},
        'period': None,
        'clock': None,
        'status': 'unknown',
        'venue': None,
        'date': None
    }
    
    # Teams
    home_img = soup.find('img', class_='logo home-logo')
    away_img = soup.find('img', class_='logo away-logo')
    
    if home_img and home_img.get('alt'):
        data['teams']['home'] = home_img.get('alt')
    if away_img and away_img.get('alt'):
        data['teams']['away'] = away_img.get('alt')
    
    # Score - multiple selectors
    for cls in ['pbpsc', 'score', 'home-score', 'away-score']:
        score_elems = soup.find_all('span', class_=cls)
        for elem in score_elems:
            text = elem.get_text(strip=True)
            m = re.search(r'(\d+)\s*[-–]\s*(\d+)', text)
            if m:
                data['score']['home'] = int(m.group(1))
                data['score']['away'] = int(m.group(2))
                break
    
    # Period
    for cls in ['pbp-period', 'period', 'quarter']:
        period_elems = soup.find_all('span', class_=cls)
        for elem in period_elems:
            text = elem.get_text(strip=True)
            m = re.search(r'P(\d+)', text, re.IGNORECASE)
            if m:
                data['period'] = int(m.group(1))
                break
    
    # Game clock
    for cls in ['pbp-time', 'game-clock', 'clock', 'timer']:
        time_elems = soup.find_all('div', class_=cls)
        for elem in time_elems:
            text = elem.get_text(strip=True)
            m = re.search(r'(\d{1,2}:\d{2})', text)
            if m:
                data['clock'] = m.group(1)
                break
    
    # Status
    status_elem = soup.find('div', class_=re.compile('status', re.I))
    if status_elem:
        data['status'] = status_elem.get_text(strip=True)
    
    return data

def parse_boxscore(html):
    """Parse box score - full player stats"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    
    data = {
        'home_team': None,
        'away_team': None,
        'home_players': [],
        'away_players': [],
        'home_totals': {},
        'away_totals': {}
    }
    
    # Get team names
    home_img = soup.find('img', class_='logo home-logo')
    away_img = soup.find('img', class_='logo away-logo')
    
    if home_img and home_img.get('alt'):
        data['home_team'] = home_img.get('alt')
    if away_img and away_img.get('alt'):
        data['away_team'] = away_img.get('alt')
    
    tables = soup.find_all('table')
    
    for table_idx, table in enumerate(tables):
        rows = table.find_all('tr')
        
        # Header row
        headers = []
        header_row = rows[0] if rows else None
        if header_row:
            headers = [th.get_text(strip=True) for th in header_row.find_all(['th', 'td'])]
        
        # Data rows
        for row_idx, row in enumerate(rows[1:], 1):
            cells = [td.get_text(strip=True) for td in row.find_all(['td', 'th'])]
            
            if len(cells) < 3:
                continue
            
            # Skip totals row
            if 'totals' in ' '.join(cells).lower():
                if table_idx == 0:
                    data['home_totals'] = {f'col_{i}': v for i, v in enumerate(cells)}
                else:
                    data['away_totals'] = {f'col_{i}': v for i, v in enumerate(cells)}
                continue
            
            # Player row
            player = {
                'num': cells[0] if len(cells) > 0 else '',
                'name': cells[1] if len(cells) > 1 else '',
                'min': cells[2] if len(cells) > 2 else '',
                'pts': cells[3] if len(cells) > 3 else '',
                'fgm': cells[4] if len(cells) > 4 else '',
                'fga': cells[5] if len(cells) > 5 else '',
                'fg_pct': cells[6] if len(cells) > 6 else '',
                '3pm': cells[7] if len(cells) > 7 else '',
                '3pa': cells[8] if len(cells) > 8 else '',
                '3p_pct': cells[9] if len(cells) > 9 else '',
                'ftm': cells[10] if len(cells) > 10 else '',
                'fta': cells[11] if len(cells) > 11 else '',
                'ft_pct': cells[12] if len(cells) > 12 else '',
                'oreb': cells[13] if len(cells) > 13 else '',
                'dreb': cells[14] if len(cells) > 14 else '',
                'reb': cells[15] if len(cells) > 15 else '',
                'ast': cells[16] if len(cells) > 16 else '',
                'stl': cells[17] if len(cells) > 17 else '',
                'blk': cells[18] if len(cells) > 18 else '',
                'to': cells[19] if len(cells) > 19 else '',
                'pf': cells[20] if len(cells) > 20 else '',
                'pm': cells[21] if len(cells) > 21 else ''
            }
            
            if table_idx == 0:
                data['home_players'].append(player)
            else:
                data['away_players'].append(player)
    
    return data

def parse_pbp(html):
    """Parse play-by-play - all events"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    
    events = []
    pbp_rows = soup.find_all('div', class_='pbpa')
    
    home_score = 0
    away_score = 0
    seq = 1
    
    for row in pbp_rows:
        # Team
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
        
        # Period
        period = None
        period_elem = row.find('span', class_='pbp-period')
        if period_elem:
            m = re.search(r'P(\d+)', period_elem.get_text())
            if m:
                period = int(m.group(1))
        
        # Clock/Time
        clock = None
        time_elem = row.find('div', class_='pbp-time')
        if time_elem:
            m = re.search(r'(\d{1,2}:\d{2}):\d{2}', time_elem.get_text())
            if m:
                clock = m.group(1)
            else:
                m = re.search(r'(\d{1,2}:\d{2})', time_elem.get_text())
                if m:
                    clock = m.group(1)
        
        # Score
        score_elem = row.find('span', class_='pbpsc')
        if score_elem:
            m = re.search(r'(\d+)\s*[-–]\s*(\d+)', score_elem.get_text())
            if m:
                home_score = int(m.group(1))
                away_score = int(m.group(2))
        
        # Action/Event
        action_elem = row.find('div', class_='pbp-action')
        description = action_elem.get_text(strip=True) if action_elem else ''
        
        player_num = None
        player_name = None
        event_type = 'unknown'
        points = None
        
        if action_elem:
            # Extract player number and name
            m = re.search(r'<strong>(\d+),\s*([^<]+)</strong>', str(action_elem))
            if m:
                player_num = m.group(1)
                player_name = m.group(2).strip()
            
            desc_lower = description.lower()
            
            # Determine event type
            if 'made' in desc_lower or ('score' in desc_lower and 'miss' not in desc_lower):
                event_type = 'score'
                if '3pt' in desc_lower or 'three' in desc_lower:
                    points = 3
                elif '2pt' in desc_lower:
                    points = 2
                elif 'free throw' in desc_lower or ' ft ' in desc_lower or 'ftm' in desc_lower:
                    points = 1
                else:
                    m_pts = re.search(r'(\d+)\s*pt', desc_lower)
                    if m_pts:
                        points = int(m_pts.group(1))
            elif 'miss' in desc_lower:
                event_type = 'miss'
                if '3pt' in desc_lower: points = 3
                elif '2pt' in desc_lower: points = 2
                elif 'free throw' in desc_lower: points = 1
            elif 'rebound' in desc_lower:
                event_type = 'rebound'
                if 'offensive' in desc_lower:
                    event_type = 'offensive_rebound'
                elif 'defensive' in desc_lower:
                    event_type = 'defensive_rebound'
            elif 'assist' in desc_lower:
                event_type = 'assist'
            elif 'foul' in desc_lower:
                event_type = 'foul'
                if 'personal' in desc_lower:
                    event_type = 'personal_foul'
                elif 'shooting' in desc_lower:
                    event_type = 'shooting_foul'
                elif 'technical' in desc_lower:
                    event_type = 'technical_foul'
            elif 'turnover' in desc_lower:
                event_type = 'turnover'
            elif 'steal' in desc_lower:
                event_type = 'steal'
            elif 'block' in desc_lower:
                event_type = 'block'
            elif 'timeout' in desc_lower:
                event_type = 'timeout'
            elif 'substitution' in desc_lower or 'enters' in desc_lower or 'leaves' in desc_lower:
                event_type = 'substitution'
            elif 'jump ball' in desc_lower:
                event_type = 'jumpball'
            elif 'period start' in desc_lower or 'game start' in desc_lower:
                event_type = 'period_start'
            elif 'possession' in desc_lower:
                event_type = 'possession'
        
        events.append({
            'seq': seq,
            'period': period,
            'clock': clock,
            'team': team,
            'player_num': player_num,
            'player': player_name,
            'event': event_type,
            'points': points,
            'home_score': home_score,
            'away_score': away_score,
            'score_diff': home_score - away_score,
            'description': description
        })
        
        seq += 1
    
    return {
        'events': events,
        'home_score': home_score,
        'away_score': away_score,
        'total_events': len(events),
        'last_clock': clock,
        'last_period': period
    }

def parse_periods(html):
    """Parse periods page - quarter by quarter scores"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    
    data = {
        'quarters': [],
        'totals': {'home': 0, 'away': 0}
    }
    
    # Try to find period scores
    tables = soup.find_all('table')
    
    for table in tables:
        rows = table.find_all('tr')
        
        for row in rows:
            cells = [c.get_text(strip=True) for c in row.find_all(['td', 'th'])]
            
            if len(cells) >= 3:
                # Check if it's a period row
                period_name = cells[0]
                home_pts = cells[1] if len(cells) > 1 else ''
                away_pts = cells[2] if len(cells) > 2 else ''
                
                # Try to extract numbers
                try:
                    home_num = int(re.search(r'\d+', home_pts).group()) if re.search(r'\d+', home_pts) else 0
                    away_num = int(re.search(r'\d+', away_pts).group()) if re.search(r'\d+', away_pts) else 0
                    
                    data['quarters'].append({
                        'period': period_name,
                        'home': home_num,
                        'away': away_num
                    })
                    
                    data['totals']['home'] += home_num
                    data['totals']['away'] += away_num
                except:
                    pass
    
    # Also try to get from score elements
    score_elems = soup.find_all('span', class_='pbpsc')
    for elem in score_elems:
        text = elem.get_text(strip=True)
        m = re.search(r'(\d+)\s*[-–]\s*(\d+)', text)
        if m:
            data['totals']['home'] = int(m.group(1))
            data['totals']['away'] = int(m.group(2))
    
    return data

def parse_leaders(html):
    """Parse leaders page"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    
    data = {'leaders': []}
    
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

def parse_scoreboard(html):
    """Parse scoreboard page"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    
    data = {
        'period_scores': [],
        'current_period': None,
        'home_total': 0,
        'away_total': 0
    }
    
    # Try to find all scores
    score_elems = soup.find_all('span', class_='pbpsc')
    
    for elem in score_elems:
        text = elem.get_text(strip=True)
        m = re.search(r'(\d+)\]\s*(\s*[-–d+)', text)
        if m:
            data['home_total'] = int(m.group(1))
            data['away_total'] = int(m.group(2))
    
    return data

def fetch_all_pages(base_url, game_id, poll_interval=0.1, max_iterations=None):
    """Main loop - fetch all pages continuously"""
    
    pages = {
        'index': f"{base_url}/index.html",
        'boxscore': f"{base_url}/bs.html",
        'leaders': f"{base_url}/lds.html",
        'playbyplay': f"{base_url}/pbp.html",
        'scoreboard': f"{base_url}/sc.html",
        'periods': f"{base_url}/p.html"
    }
    
    iteration = 0
    last_pbp_count = 0
    
    print(f"Starting live fetcher for game {game_id}")
    print(f"Base URL: {base_url}")
    print(f"Poll interval: {poll_interval}s")
    print("-" * 50)
    
    while True:
        try:
            iteration += 1
            start_time = time.time()
            
            # Check max iterations
            if max_iterations and iteration > max_iterations:
                print(f"\nReached max iterations ({max_iterations}). Stopping.")
                break
            
            result = {
                'game_id': game_id,
                'base_url': base_url,
                'iteration': iteration,
                'fetched_at': datetime.now().isoformat(),
                'pages': {}
            }
            
            # Fetch index first (has current score)
            print(f"\n[{iteration}] Fetching index...")
            html = fetch_page(pages['index'])
            if html:
                result['pages']['index'] = parse_index(html)
                idx = result['pages']['index']
                print(f"  Score: {idx.get('score', {}).get('home', 0)}-{idx.get('score', {}).get('away', 0)} | Period: {idx.get('period')} | Clock: {idx.get('clock')}")
            
            # Fetch boxscore
            print(f"  Fetching boxscore...")
            html = fetch_page(pages['boxscore'])
            if html:
                result['pages']['boxscore'] = parse_boxscore(html)
                bs = result['pages']['boxscore']
                print(f"  Players: {len(bs.get('home_players', []))} home, {len(bs.get('away_players', []))} away")
            
            # Fetch pbp (most important - check for changes)
            print(f"  Fetching pbp...")
            html = fetch_page(pages['playbyplay'])
            if html:
                result['pages']['playbyplay'] = parse_pbp(html)
                pbp = result['pages']['playbyplay']
                new_events = pbp.get('total_events', 0) - last_pbp_count
                print(f"  Events: {pbp.get('total_events', 0)} (+{new_events})")
                last_pbp_count = pbp.get('total_events', 0)
            
            # Fetch periods
            print(f"  Fetching periods...")
            html = fetch_page(pages['periods'])
            if html:
                result['pages']['periods'] = parse_periods(html)
            
            # Fetch leaders
            print(f"  Fetching leaders...")
            html = fetch_page(pages['leaders'])
            if html:
                result['pages']['leaders'] = parse_leaders(html)
            
            # Save to file
            json_file = "data/live_full.json"
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2)
            
            # Save state
            save_state({
                'iteration': iteration,
                'game_id': game_id,
                'last_fetch': datetime.now().isoformat(),
                'last_events': last_pbp_count
            })
            
            elapsed = time.time() - start_time
            print(f"  Saved to {json_file} ({elapsed:.2f}s)")
            
            # Wait for poll interval
            wait_time = max(0, poll_interval - elapsed)
            if wait_time > 0:
                time.sleep(wait_time)
                
        except KeyboardInterrupt:
            print("\n\nStopped by user")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(1)  # Wait before retry

def main():
    parser = argparse.ArgumentParser(description="NEBL Live Multi-Page Fetcher")
    parser.add_argument("--game-id", default="2799694", help="Game ID")
    parser.add_argument("--base", default="https://fibalivestats.dcd.shared.geniussports.com/u/BBF/{game_id}", 
                       help="Base URL template")
    parser.add_argument("--poll", type=float, default=0.5, help="Poll interval in seconds (0.1 = fastest)")
    parser.add_argument("--max", type=int, default=None, help="Max iterations (None = infinite)")
    parser.add_argument("--out", default="data/live_full.json", help="Output file")
    args = parser.parse_args()
    
    base_url = args.base.format(game_id=args.game_id)
    
    fetch_all_pages(base_url, args.game_id, args.poll, args.max)

if __name__ == "__main__":
    main()
