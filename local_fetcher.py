#!/usr/bin/env python3
"""
NEBL Live Stats - Read from LOCAL HTML files and write to Google Sheets
Place your saved HTML files in a folder and run this script
"""

import os
import re
import json
from bs4 import BeautifulSoup

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    HAS_GOOGLE = True
except ImportError:
    HAS_GOOGLE = False

def read_local_html(folder_path, filename):
    """Read HTML from local file"""
    filepath = os.path.join(folder_path, filename)
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    return ""

def parse_scoreboard(html):
    if not html:
        return {'home_team': 'Home', 'away_team': 'Away', 'home_score': 0, 'away_score': 0, 'period': '', 'clock': ''}
    
    soup = BeautifulSoup(html, 'html.parser')
    
    data = {
        'home_team': soup.find('span', id='aj_1_shortName')?.text?.strip() or 'Home',
        'away_team': soup.find('span', id='aj_2_shortName')?.text?.strip() or 'Away',
        'home_score': soup.find('span', id='aj_1_score')?.text?.strip() or '0',
        'away_score': soup.find('span', id='aj_2_score')?.text?.strip() or '0',
        'period': soup.find('span', id='aj_period')?.text?.strip() or '',
        'clock': soup.find('span', id='aj_clock')?.text?.strip() or ''
    }
    return data

def parse_boxscore(html):
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
            
            # Get player number
            num_span = row.find('span', id=re.compile(f'^aj_{team_num}_\\d+_shirtNumber$'))
            if num_span:
                player['num'] = num_span.get_text(strip=True) or ''
            
            # Get player name
            name_span = row.find('span', id=re.compile(f'^aj_{team_num}_\\d+_name$'))
            if name_span:
                player['name'] = name_span.get_text(strip=True) or ''
            
            # Get position
            pos_span = row.find('span', id=re.compile(f'^aj_{team_num}_\\d+_playingPosition$'))
            if pos_span:
                player['pos'] = pos_span.get_text(strip=True) or ''
            
            # Get stats
            for stat_key, stat_id in [
                ('min', 'sMinutes'), ('pts', 'sPoints'), ('reb', 'sReboundsTotal'),
                ('ast', 'sAssists'), ('stl', 'sSteals'), ('blk', 'sBlocks'),
                ('to', 'sTurnovers'), ('pf', 'sFoulsPersonal')
            ]:
                span = row.find('span', id=re.compile(f'^aj_{team_num}_\\d+_{stat_id}$'))
                if span:
                    player[stat_key] = span.get_text(strip=True) or '0'
            
            if player.get('name'):
                data[key].append(player)
    
    return data

def write_to_sheets(credentials, data, spreadsheet_id):
    service = build('sheets', 'v4', credentials=credentials)
    
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
    
    home_players = data.get('boxscore', {}).get('home_players', [])
    home_values = [['#', 'Name', 'POS', 'MIN', 'PTS', 'REB', 'AST', 'STL', 'BLK', 'TO', 'PF']]
    for p in home_players:
        home_values.append([
            p.get('num', ''), p.get('name', ''), p.get('pos', ''),
            p.get('min', ''), p.get('pts', ''), p.get('reb', ''),
            p.get('ast', ''), p.get('stl', ''), p.get('blk', ''),
            p.get('to', ''), p.get('pf', '')
        ])
    
    away_players = data.get('boxscore', {}).get('away_players', [])
    away_values = [['#', 'Name', 'POS', 'MIN', 'PTS', 'REB', 'AST', 'STL', 'BLK', 'TO', 'PF']]
    for p in away_players:
        away_values.append([
            p.get('num', ''), p.get('name', ''), p.get('pos', ''),
            p.get('min', ''), p.get('pts', ''), p.get('reb', ''),
            p.get('ast', ''), p.get('stl', ''), p.get('blk', ''),
            p.get('to', ''), p.get('pf', '')
        ])
    
    sheets = {
        'Scoreboard': scoreboard_values,
        'Home Box': home_values,
        'Away Box': away_values
    }
    
    for sheet_name, values in sheets.items():
        try:
            result = service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=f"{sheet_name}!A1",
                valueInputOption='USER_ENTERED',
                body={'values': values}
            ).execute()
            print(f"✓ Updated {sheet_name}: {result.get('updatedCells', 0)} cells")
        except Exception as e:
            print(f"✗ Error updating {sheet_name}: {e}")

def main():
    print("=" * 50)
    print("NEBL Live Stats - Local HTML to Google Sheets")
    print("=" * 50)
    
    # Get folder path
    folder = input("\nEnter folder path with HTML files: ").strip()
    if not folder:
        folder = "."
    
    # Check files exist
    index_path = os.path.join(folder, "index.html")
    bs_path = os.path.join(folder, "bs.html")
    
    if not os.path.exists(index_path):
        print(f"✗ Error: index.html not found in {folder}")
        return
    if not os.path.exists(bs_path):
        print(f"✗ Error: bs.html not found in {folder}")
        return
    
    print(f"\nReading HTML files from: {folder}")
    
    # Read HTML files
    print("Reading index.html...")
    html_index = read_local_html(folder, "index.html")
    scoreboard = parse_scoreboard(html_index)
    print(f"  Score: {scoreboard['home_team']} {scoreboard['home_score']} - {scoreboard['away_score']} {scoreboard['away_team']}")
    print(f"  Period: {scoreboard['period']}, Clock: {scoreboard['clock']}")
    
    print("Reading bs.html...")
    html_box = read_local_html(folder, "bs.html")
    boxscore = parse_boxscore(html_box)
    print(f"  Home players: {len(boxscore['home_players'])}")
    print(f"  Away players: {len(boxscore['away_players'])}")
    
    data = {'scoreboard': scoreboard, 'boxscore': boxscore}
    
    # Ask about Google Sheets
    update_sheets = input("\nUpdate Google Sheets? (y/n): ").strip().lower()
    
    if update_sheets == 'y' and HAS_GOOGLE:
        spreadsheet_id = input("Enter Spreadsheet ID: ").strip()
        
        # Try to get credentials
        import os
        creds_json = os.environ.get('GOOGLE_CREDENTIALS_JSON')
        
        if creds_json:
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                f.write(creds_json)
                creds_file = f.name
            
            credentials = service_account.Credentials.from_service_account_file(
                creds_file,
                scopes=['https://www.googleapis.com/auth/spreadsheets']
            )
            
            print("\nWriting to Google Sheets...")
            write_to_sheets(credentials, data, spreadsheet_id)
            print("\n✓ Done! Check your Google Sheet.")
        else:
            print("✗ No GOOGLE_CREDENTIALS_JSON environment variable set")
            print("Set it with: set GOOGLE_CREDENTIALS_JSON={'...json content...'}")
    else:
        print("\nData fetched:")
        print(json.dumps(data, indent=2))

if __name__ == '__main__':
    main()
