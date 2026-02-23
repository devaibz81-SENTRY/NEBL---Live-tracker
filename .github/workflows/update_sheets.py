#!/usr/bin/env python3
"""
NEBL Live Stats - Fetch from Genius Sports and Write to Google Sheets
Runs on GitHub Actions
"""

import os
import re
import json
from bs4 import BeautifulSoup

# Try to import playwright - for GitHub Actions
try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

# Try to import Google libraries - only if credentials available
try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    HAS_GOOGLE = True
except ImportError:
    HAS_GOOGLE = False

# Configuration
GAME_ID = os.environ.get('GAME_ID', '')
SPREADSHEET_ID = os.environ.get('SPREADSHEET_ID', '')
BASE_URL = f"https://fibalivestats.dcd.shared.geniussports.com/u/BBF/{GAME_ID}" if GAME_ID else ''

def fetch_page(url):
    """Fetch a page - tries requests first, then playwright"""
    # Try with requests first (faster)
    try:
        import requests
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200 and len(response.text) > 5000:
            return response.text
    except:
        pass
    
    # Fall back to playwright
    if HAS_PLAYWRIGHT:
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(url, wait_until="networkidle", timeout=30000)
                page.wait_for_timeout(2000)
                content = page.content()
                browser.close()
                return content
        except Exception as e:
            print(f"Playwright error: {e}")
    
    return ""

def parse_index(html):
    """Parse scoreboard from index page"""
    if not html:
        return {'home_team': '', 'away_team': '', 'home_score': 0, 'away_score': 0, 'period': '', 'clock': ''}
    
    soup = BeautifulSoup(html, 'html.parser')
    
    data = {
        'home_team': '',
        'away_team': '',
        'home_score': 0,
        'away_score': 0,
        'period': '',
        'clock': ''
    }
    
    # Team names - try multiple selectors
    home_elem = soup.find('span', id='aj_1_shortName')
    if not home_elem:
        home_elem = soup.find('div', class_='team-0')
        if home_elem:
            name_elem = home_elem.find('span', class_='id_aj_1_code')
            if name_elem:
                data['home_team'] = name_elem.get_text(strip=True)
    
    if home_elem:
        data['home_team'] = home_elem.get_text(strip=True)
    
    away_elem = soup.find('span', id='aj_2_shortName')
    if away_elem:
        data['away_team'] = away_elem.get_text(strip=True)
    
    # Scores
    home_score = soup.find('span', id='aj_1_score')
    if home_score:
        data['home_score'] = home_score.get_text(strip=True)
    
    away_score = soup.find('span', id='aj_2_score')
    if away_score:
        data['away_score'] = away_score.get_text(strip=True)
    
    # Period and Clock
    period = soup.find('span', id='aj_period')
    if period:
        data['period'] = period.get_text(strip=True)
    
    clock = soup.find('span', id='aj_clock')
    if clock:
        data['clock'] = clock.get_text(strip=True)
    
    return data

def parse_boxscore(html):
    """Parse box score from bs page"""
    if not html:
        return {'home_players': [], 'away_players': []}
    
    soup = BeautifulSoup(html, 'html.parser')
    data = {'home_players': [], 'away_players': []}
    
    for team_num, key in [(1, 'home_players'), (2, 'away_players')]:
        rows = soup.find_all('tr', id=re.compile(f'^aj_{team_num}_\\d+_row$'))
        
        for row in rows:
            classes = row.get('class', [])
            if isinstance(classes, str):
                classes = classes.split()
            if 'row-not-used' in classes:
                continue
            
            player = {}
            
            # Get player number - check text first, then class
            num_span = row.find('span', id=re.compile(f'^aj_{team_num}_\\d+_shirtNumber$'))
            if num_span:
                txt = num_span.get_text(strip=True)
                if txt:
                    player['num'] = txt
                else:
                    for c in num_span.get('class', []):
                        if c.startswith('aj_') and len(c) > 3:
                            player['num'] = c[3:]
                            break
            
            # Get player name
            name_span = row.find('span', id=re.compile(f'^aj_{team_num}_\\d+_name$'))
            if name_span:
                txt = name_span.get_text(strip=True)
                if txt:
                    player['name'] = txt
                else:
                    for c in name_span.get('class', []):
                        if c.startswith('aj_') and len(c) > 3:
                            player['name'] = c[3:]
                            break
            
            # Get position
            pos_span = row.find('span', id=re.compile(f'^aj_{team_num}_\\d+_playingPosition$'))
            if pos_span:
                txt = pos_span.get_text(strip=True)
                if txt:
                    player['pos'] = txt
                else:
                    for c in pos_span.get('class', []):
                        if c.startswith('aj_'):
                            player['pos'] = c[3:]
                            break
            
            # Get stats
            stats = {}
            stat_ids = {
                'min': 'sMinutes', 'pts': 'sPoints', 'reb': 'sReboundsTotal',
                'ast': 'sAssists', 'stl': 'sSteals', 'blk': 'sBlocks',
                'to': 'sTurnovers', 'pf': 'sFoulsPersonal'
            }
            
            for stat_key, stat_id in stat_ids.items():
                span = row.find('span', id=re.compile(f'^aj_{team_num}_\\d+_{stat_id}$'))
                if span:
                    txt = span.get_text(strip=True)
                    if txt:
                        stats[stat_key] = txt
                    else:
                        for c in span.get('class', []):
                            if c.startswith('aj_') and c[3:].isdigit():
                                stats[stat_key] = c[3:]
                                break
            
            player.update(stats)
            
            if player.get('name'):
                data[key].append(player)
    
    return data

def parse_leaders(html):
    """Parse leaders from lds page"""
    if not html:
        return {'Points': [], 'Assists': [], 'Total Rebounds': [], 'Steals': []}
    
    soup = BeautifulSoup(html, 'html.parser')
    
    leaders = {
        'Points': [],
        'Assists': [],
        'Total Rebounds': [],
        'Steals': []
    }
    
    stat_map = {
        'sPoints': 'Points',
        'sAssists': 'Assists',
        'sReboundsTotal': 'Total Rebounds',
        'sSteals': 'Steals'
    }
    
    for team_num in [1, 2]:
        for stat_id, stat_name in stat_map.items():
            for rank in range(1, 6):
                name_elem = soup.find('span', id=f'aj_{team_num}_{stat_id}_{rank}_name')
                tot_elem = soup.find('span', id=f'aj_{team_num}_{stat_id}_{rank}_tot')
                
                if name_elem and tot_elem:
                    name = name_elem.get_text(strip=True)
                    value = tot_elem.get_text(strip=True)
                    
                    if name and value and not name.isdigit():
                        leaders[stat_name].append({
                            'rank': rank,
                            'player': name,
                            'value': value,
                            'team': 'home' if team_num == 1 else 'away'
                        })
    
    return leaders

def write_to_sheets(credentials, data):
    """Write data to Google Sheets"""
    service = build('sheets', 'v4', credentials=credentials)
    
    # Prepare Scoreboard data
    scoreboard = data.get('scoreboard', {})
    scoreboard_values = [
        ['NEBL LIVE STATS'],
        ['', ''],
        [scoreboard.get('home_team', 'Home'), scoreboard.get('home_score', 0)],
        [scoreboard.get('away_team', 'Away'), scoreboard.get('away_score', 0)],
        ['', ''],
        ['Period', scoreboard.get('period', '')],
        ['Clock', scoreboard.get('clock', '')]
    ]
    
    # Prepare Box Score Home
    home_players = data.get('boxscore', {}).get('home_players', [])
    home_values = [['#', 'Name', 'POS', 'MIN', 'PTS', 'REB', 'AST', 'STL', 'BLK', 'TO', 'PF']]
    for p in home_players:
        home_values.append([
            p.get('num', ''),
            p.get('name', ''),
            p.get('pos', ''),
            p.get('min', ''),
            p.get('pts', ''),
            p.get('reb', ''),
            p.get('ast', ''),
            p.get('stl', ''),
            p.get('blk', ''),
            p.get('to', ''),
            p.get('pf', '')
        ])
    
    # Prepare Box Score Away
    away_players = data.get('boxscore', {}).get('away_players', [])
    away_values = [['#', 'Name', 'POS', 'MIN', 'PTS', 'REB', 'AST', 'STL', 'BLK', 'TO', 'PF']]
    for p in away_players:
        away_values.append([
            p.get('num', ''),
            p.get('name', ''),
            p.get('pos', ''),
            p.get('min', ''),
            p.get('pts', ''),
            p.get('reb', ''),
            p.get('ast', ''),
            p.get('stl', ''),
            p.get('blk', ''),
            p.get('to', ''),
            p.get('pf', '')
        ])
    
    # Prepare Leaders
    leaders = data.get('leaders', {})
    leader_values = [['Category', 'Rank', 'Player', 'Value', 'Team']]
    for stat, players in leaders.items():
        for p in players[:5]:
            leader_values.append([
                stat,
                p.get('rank', ''),
                p.get('player', ''),
                p.get('value', ''),
                p.get('team', '')
            ])
    
    # Write to sheets
    sheets = {
        'Scoreboard': scoreboard_values,
        'Home Box': home_values,
        'Away Box': away_values,
        'Leaders': leader_values
    }
    
    for sheet_name, values in sheets.items():
        body = {'values': values}
        
        result = service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{sheet_name}!A1",
            valueInputOption='USER_ENTERED',
            body=body
        ).execute()
        
        print(f"Updated {sheet_name}: {result.get('updatedCells', 0)} cells")

def main():
    if not GAME_ID:
        print("ERROR: No GAME_ID provided. Set GAME_ID environment variable.")
        return
    
    print(f"Fetching game {GAME_ID} from {BASE_URL}")
    
    # Fetch data
    print("Fetching index...")
    html_index = fetch_page(f"{BASE_URL}/index.html")
    scoreboard = parse_index(html_index)
    print(f"Score: {scoreboard['home_score']} - {scoreboard['away_score']}")
    print(f"Period: {scoreboard['period']}, Clock: {scoreboard['clock']}")
    
    print("Fetching boxscore...")
    html_box = fetch_page(f"{BASE_URL}/bs.html")
    boxscore = parse_boxscore(html_box)
    print(f"Players: {len(boxscore['home_players'])} home, {len(boxscore['away_players'])} away")
    
    print("Fetching leaders...")
    html_leaders = fetch_page(f"{BASE_URL}/lds.html")
    leaders = parse_leaders(html_leaders)
    print(f"Leaders: {list(leaders.keys())}")
    
    # Prepare data
    data = {
        'scoreboard': scoreboard,
        'boxscore': boxscore,
        'leaders': leaders
    }
    
    # Write to Google Sheets
    print("Writing to Google Sheets...")
    creds_json = os.environ.get('GOOGLE_CREDENTIALS_JSON')
    print(f"GOOGLE_CREDENTIALS_JSON present: {bool(creds_json)}")
    print(f"HAS_GOOGLE: {HAS_GOOGLE}")
    
    if creds_json and HAS_GOOGLE:
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write(creds_json)
            creds_file = f.name
        
        credentials = service_account.Credentials.from_service_account_file(
            creds_file,
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        
        write_to_sheets(credentials, data)
        print("Sheets updated successfully!")
    else:
        print("No credentials found - running in test mode")
        print("Data fetched:")
        print(json.dumps(data, indent=2))

if __name__ == '__main__':
    main()
