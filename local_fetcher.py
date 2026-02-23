#!/usr/bin/env python3
"""
NEBL Live Stats - Local Fetcher
Run this on your computer to fetch data and write to Google Sheets
"""

import os
import re
import json
import sys
import time
from bs4 import BeautifulSoup

try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    HAS_GOOGLE = True
except ImportError:
    HAS_GOOGLE = False

def fetch_page(url):
    """Fetch page using playwright"""
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
    
    # Fallback to requests
    try:
        import requests
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            return response.text
    except:
        pass
    
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
            
            # Get stats
            for stat_key, stat_id in [('pts', 'sPoints'), ('reb', 'sReboundsTotal'), ('ast', 'sAssists'), ('min', 'sMinutes')]:
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
        ['Period', scoreboard.get('period', '')],
        ['Clock', scoreboard.get('clock', '')]
    ]
    
    home_players = data.get('boxscore', {}).get('home_players', [])
    home_values = [['#', 'Name', 'MIN', 'PTS', 'REB', 'AST']]
    for p in home_players:
        home_values.append([p.get('num', ''), p.get('name', ''), p.get('min', ''), p.get('pts', ''), p.get('reb', ''), p.get('ast', '')])
    
    away_players = data.get('boxscore', {}).get('away_players', [])
    away_values = [['#', 'Name', 'MIN', 'PTS', 'REB', 'AST']]
    for p in away_players:
        away_values.append([p.get('num', ''), p.get('name', ''), p.get('min', ''), p.get('pts', ''), p.get('reb', ''), p.get('ast', '')])
    
    sheets = {
        'Scoreboard': scoreboard_values,
        'Home': home_values,
        'Away': away_values
    }
    
    for sheet_name, values in sheets.items():
        try:
            result = service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=f"{sheet_name}!A1",
                valueInputOption='USER_ENTERED',
                body={'values': values}
            ).execute()
            print(f"Updated {sheet_name}")
        except Exception as e:
            print(f"Error updating {sheet_name}: {e}")

def main():
    # Get inputs
    game_url = input("Enter game URL (e.g., https://fibalivestats.dcd.shared.geniussports.com/u/BBF/2799697): ").strip()
    spreadsheet_id = input("Enter Spreadsheet ID: ").strip()
    
    # Parse game ID from URL
    match = re.search(r'/u/BBF/(\d+)', game_url)
    if not match:
        print("Invalid URL - could not find game ID")
        return
    
    game_id = match.group(1)
    base_url = f"https://fibalivestats.dcd.shared.geniussports.com/u/BBF/{game_id}"
    
    print(f"Fetching game {game_id}...")
    
    # Fetch data
    print("Fetching scoreboard...")
    html_index = fetch_page(f"{base_url}/index.html")
    scoreboard = parse_scoreboard(html_index)
    print(f"Score: {scoreboard['home_score']} - {scoreboard['away_score']}")
    
    print("Fetching boxscore...")
    html_box = fetch_page(f"{base_url}/bs.html")
    boxscore = parse_boxscore(html_box)
    print(f"Players: {len(boxscore['home_players'])} home, {len(boxscore['away_players'])} away")
    
    data = {'scoreboard': scoreboard, 'boxscore': boxscore}
    
    # Write to sheets
    if HAS_GOOGLE:
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
            write_to_sheets(credentials, data, spreadsheet_id)
            print("Sheets updated!")
        else:
            print("No GOOGLE_CREDENTIALS_JSON - run locally without sheet update")
            print(json.dumps(data, indent=2))
    else:
        print("Google libraries not installed")
        print(json.dumps(data, indent=2))

if __name__ == '__main__':
    main()
