import re
import csv
import sys
import os
import time
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

if len(sys.argv) > 1:
    GAME_URL = sys.argv[1]
else:
    GAME_URL = ""

GAME_NUM = "1"

def fetch(url, retries=3):
    for attempt in range(retries):
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    viewport={"width": 1920, "height": 1080}
                )
                page = context.new_page()
                
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                
                try:
                    page.wait_for_selector('#aj_1_score', timeout=30000)
                except:
                    pass
                
                try:
                    page.wait_for_selector('.team-0-person-container', timeout=30000)
                except:
                    pass
                
                page.wait_for_timeout(3000)
                
                html = page.content()
                browser.close()
            return html
        except Exception as e:
            print(f"Attempt {attempt+1} failed: {e}")
            if attempt < retries - 1:
                time.sleep(2)
            else:
                raise
    return ""

def get_value(elem):
    if not elem:
        return ""
    text = elem.get_text(strip=True)
    if text:
        return text
    classes = elem.get('class') or []
    for c in classes:
        if isinstance(c, str) and c.startswith('aj_') and len(c) > 2:
            val = c[3:]
            if val.replace(':', '').replace('-', '').isdigit():
                return val
    return ""

def parse_index_html(html):
    soup = BeautifulSoup(html, 'html.parser')
    
    home = soup.find('span', id='aj_1_shortName')
    away = soup.find('span', id='aj_2_shortName')
    h_score = soup.find('span', id='aj_1_score')
    a_score = soup.find('span', id='aj_2_score')
    period = soup.find('span', id='aj_period')
    clock = soup.find('span', id='aj_clock')
    
    home_team = home.get_text(strip=True) if home else ""
    away_team = away.get_text(strip=True) if away else ""
    home_score = get_value(h_score) if h_score else "0"
    away_score = get_value(a_score) if a_score else "0"
    game_period = get_value(period) if period else ""
    game_clock = get_value(clock) if clock else ""
    
    print(f"Debug - Home: {home_team}, Score: {home_score}-{away_score}")
    
    def get_player_data(row, team_num):
        row_id = row.get('id', '')
        pid_match = re.search(rf'aj_{team_num}_(\d+)_row', row_id)
        if not pid_match:
            return None
        pid = pid_match.group(1)
        
        name_elem = row.find('span', id=f'aj_{team_num}_{pid}_name')
        if not name_elem:
            return None
        
        name = name_elem.get_text(strip=True)
        if not name:
            return None
        
        return {
            'num': get_value(row.find('span', id=f'aj_{team_num}_{pid}_shirtNumber')),
            'name': name,
            'mins': get_value(row.find('span', id=f'aj_{team_num}_{pid}_sMinutes')),
            'pts': get_value(row.find('span', id=f'aj_{team_num}_{pid}_sPoints')),
            'reb': get_value(row.find('span', id=f'aj_{team_num}_{pid}_sReboundsTotal')),
            'ast': get_value(row.find('span', id=f'aj_{team_num}_{pid}_sAssists')),
            'pf': get_value(row.find('span', id=f'aj_{team_num}_{pid}_sFoulsPersonal')),
            'eff': get_value(row.find('span', id=f'aj_{team_num}_{pid}_eff_1')),
            'is_starter': 'p_starter' in (row.get('class') or [])
        }
    
    home_players, away_players = [], []
    
    for row in soup.select('tbody.team-0-person-container tr.player-row'):
        classes = row.get('class') or []
        if 'row-not-used' in classes:
            continue
        p = get_player_data(row, 1)
        if p:
            home_players.append(p)
    
    for row in soup.select('tbody.team-1-person-container tr.player-row'):
        classes = row.get('class') or []
        if 'row-not-used' in classes:
            continue
        p = get_player_data(row, 2)
        if p:
            away_players.append(p)
    
    print(f"Debug - Home players: {len(home_players)}, Away players: {len(away_players)}")
    
    def get_team_totals(team_num):
        return {
            'fg_m': get_value(soup.find('span', id=f'aj_{team_num}_tot_sFieldGoalsMade')),
            'fg_a': get_value(soup.find('span', id=f'aj_{team_num}_tot_sFieldGoalsAttempted')),
            'fg_pct': get_value(soup.find('span', id=f'aj_{team_num}_tot_sFieldGoalsPercentage')),
            'two_p_m': get_value(soup.find('span', id=f'aj_{team_num}_tot_sTwoPointersMade')),
            'two_p_a': get_value(soup.find('span', id=f'aj_{team_num}_tot_sTwoPointersAttempted')),
            'two_p_pct': get_value(soup.find('span', id=f'aj_{team_num}_tot_sTwoPointersPercentage')),
            'three_p_m': get_value(soup.find('span', id=f'aj_{team_num}_tot_sThreePointersMade')),
            'three_p_a': get_value(soup.find('span', id=f'aj_{team_num}_tot_sThreePointersAttempted')),
            'three_p_pct': get_value(soup.find('span', id=f'aj_{team_num}_tot_sThreePointersPercentage')),
            'ft_m': get_value(soup.find('span', id=f'aj_{team_num}_tot_sFreeThrowsMade')),
            'ft_a': get_value(soup.find('span', id=f'aj_{team_num}_tot_sFreeThrowsAttempted')),
            'ft_pct': get_value(soup.find('span', id=f'aj_{team_num}_tot_sFreeThrowsPercentage')),
            'reb': get_value(soup.find('span', id=f'aj_{team_num}_tot_sReboundsTotal')),
            'ast': get_value(soup.find('span', id=f'aj_{team_num}_tot_sAssists')),
            'stl': get_value(soup.find('span', id=f'aj_{team_num}_tot_sSteals')),
            'blk': get_value(soup.find('span', id=f'aj_{team_num}_tot_sBlocks')),
            'to': get_value(soup.find('span', id=f'aj_{team_num}_tot_sTurnovers')),
            'pf': get_value(soup.find('span', id=f'aj_{team_num}_tot_sFoulsPersonal')),
            'pts': get_value(soup.find('span', id=f'aj_{team_num}_tot_sPoints')),
            'pts_turnovers': get_value(soup.find('span', id=f'aj_{team_num}_tot_sPointsFromTurnovers')),
            'pts_paint': get_value(soup.find('span', id=f'aj_{team_num}_tot_sPointsInThePaint')),
            'pts_second': get_value(soup.find('span', id=f'aj_{team_num}_tot_sPointsSecondChance')),
            'pts_fast': get_value(soup.find('span', id=f'aj_{team_num}_tot_sPointsFastBreak')),
            'bench_pts': get_value(soup.find('span', id=f'aj_{team_num}_tot_sBenchPoints')),
        }
    
    home_totals = get_team_totals(1)
    away_totals = get_team_totals(2)
    
    def get_leaders(prefix, stat):
        leaders = []
        for rank in range(1, 6):
            name_elem = soup.find('span', class_=f'id_{prefix}_{stat}_{rank}_name')
            tot_elem = soup.find('span', class_=f'id_{prefix}_{stat}_{rank}_tot')
            if name_elem:
                leaders.append({
                    'name': name_elem.get_text(strip=True),
                    'val': get_value(tot_elem) if tot_elem else ""
                })
        return leaders
    
    home_pts_leaders = get_leaders('aj_1', 'sPoints')
    away_pts_leaders = get_leaders('aj_2', 'sPoints')
    home_reb_leaders = get_leaders('aj_1', 'sReboundsTotal')
    away_reb_leaders = get_leaders('aj_2', 'sReboundsTotal')
    home_ast_leaders = get_leaders('aj_1', 'sAssists')
    away_ast_leaders = get_leaders('aj_2', 'sAssists')
    
    return {
        'home': home_team, 'away': away_team,
        'h_score': home_score, 'a_score': away_score,
        'period': game_period, 'clock': game_clock,
        'home_players': home_players, 'away_players': away_players,
        'home_totals': home_totals, 'away_totals': away_totals,
        'home_pts_leaders': home_pts_leaders, 'away_pts_leaders': away_pts_leaders,
        'home_reb_leaders': home_reb_leaders, 'away_reb_leaders': away_reb_leaders,
        'home_ast_leaders': home_ast_leaders, 'away_ast_leaders': away_ast_leaders,
    }

def write_csv(data, game_num):
    os.makedirs("Game CSV", exist_ok=True)
    filename = f"Game CSV/Game {game_num}.csv"
    
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        writer.writerow(['NEBL LIVE STATS - GAME ' + game_num])
        writer.writerow([])
        writer.writerow(['SCOREBOARD'])
        writer.writerow(['Home', data['home'], data['h_score']])
        writer.writerow(['Away', data['away'], data['a_score']])
        writer.writerow(['Period', data['period']])
        writer.writerow(['Clock', data['clock']])
        writer.writerow([])
        
        writer.writerow(['HOME TEAM - ' + data['home']])
        writer.writerow(['No.', 'Player', 'Mins', 'Pts', 'REB', 'AST', 'PF', 'Index'])
        
        for p in data['home_players']:
            writer.writerow([p['num'], p['name'], p['mins'], p['pts'], p['reb'], p['ast'], p['pf'], p['eff']])
        
        ht = data['home_totals']
        writer.writerow(['', 'TEAM TOTALS', '', ht.get('pts', ''), ht.get('reb', ''), ht.get('ast', ''), ht.get('pf', ''), ''])
        
        writer.writerow([])
        writer.writerow(['AWAY TEAM - ' + data['away']])
        writer.writerow(['No.', 'Player', 'Mins', 'Pts', 'REB', 'AST', 'PF', 'Index'])
        
        for p in data['away_players']:
            writer.writerow([p['num'], p['name'], p['mins'], p['pts'], p['reb'], p['ast'], p['pf'], p['eff']])
        
        at = data['away_totals']
        writer.writerow(['', 'TEAM TOTALS', '', at.get('pts', ''), at.get('reb', ''), at.get('ast', ''), at.get('pf', ''), ''])
        
        writer.writerow([])
        writer.writerow(['TEAM STATS COMPARISON'])
        writer.writerow(['', data['home'], data['away']])
        
        fg_home = f"{ht.get('fg_m', '')}/{ht.get('fg_a', '')} ({ht.get('fg_pct', '')}%)"
        fg_away = f"{at.get('fg_m', '')}/{at.get('fg_a', '')} ({at.get('fg_pct', '')}%)"
        writer.writerow(['FG', fg_home, fg_away])
        
        two_home = f"{ht.get('two_p_m', '')}/{ht.get('two_p_a', '')} ({ht.get('two_p_pct', '')}%)"
        two_away = f"{at.get('two_p_m', '')}/{at.get('two_p_a', '')} ({at.get('two_p_pct', '')}%)"
        writer.writerow(['2P', two_home, two_away])
        
        three_home = f"{ht.get('three_p_m', '')}/{ht.get('three_p_a', '')} ({ht.get('three_p_pct', '')}%)"
        three_away = f"{at.get('three_p_m', '')}/{at.get('three_p_a', '')} ({at.get('three_p_pct', '')}%)"
        writer.writerow(['3P', three_home, three_away])
        
        ft_home = f"{ht.get('ft_m', '')}/{ht.get('ft_a', '')} ({ht.get('ft_pct', '')}%)"
        ft_away = f"{at.get('ft_m', '')}/{at.get('ft_a', '')} ({at.get('ft_pct', '')}%)"
        writer.writerow(['FT', ft_home, ft_away])
        
        writer.writerow(['REB', ht.get('reb', ''), at.get('reb', '')])
        writer.writerow(['AST', ht.get('ast', ''), at.get('ast', '')])
        writer.writerow(['STL', ht.get('stl', ''), at.get('stl', '')])
        writer.writerow(['BLK', ht.get('blk', ''), at.get('blk', '')])
        writer.writerow(['TO', ht.get('to', ''), at.get('to', '')])
        writer.writerow(['PF', ht.get('pf', ''), at.get('pf', '')])
        writer.writerow(['Points from TO', ht.get('pts_turnovers', ''), at.get('pts_turnovers', '')])
        writer.writerow(['Points in Paint', ht.get('pts_paint', ''), at.get('pts_paint', '')])
        writer.writerow(['2nd Chance Pts', ht.get('pts_second', ''), at.get('pts_second', '')])
        writer.writerow(['Fast Break Pts', ht.get('pts_fast', ''), at.get('pts_fast', '')])
        writer.writerow(['Bench Pts', ht.get('bench_pts', ''), at.get('bench_pts', '')])
        
        writer.writerow([])
        writer.writerow(['POINTS LEADERS'])
        writer.writerow([data['home']])
        for i, p in enumerate(data['home_pts_leaders'], 1):
            writer.writerow([i, p['name'], p['val']])
        writer.writerow([data['away']])
        for i, p in enumerate(data['away_pts_leaders'], 1):
            writer.writerow([i, p['name'], p['val']])
        
        writer.writerow([])
        writer.writerow(['REBOUNDS LEADERS'])
        writer.writerow([data['home']])
        for i, p in enumerate(data['home_reb_leaders'], 1):
            writer.writerow([i, p['name'], p['val']])
        writer.writerow([data['away']])
        for i, p in enumerate(data['away_reb_leaders'], 1):
            writer.writerow([i, p['name'], p['val']])
        
        writer.writerow([])
        writer.writerow(['ASSISTS LEADERS'])
        writer.writerow([data['home']])
        for i, p in enumerate(data['home_ast_leaders'], 1):
            writer.writerow([i, p['name'], p['val']])
        writer.writerow([data['away']])
        for i, p in enumerate(data['away_ast_leaders'], 1):
            writer.writerow([i, p['name'], p['val']])
    
    print(f"Written {filename}")

if __name__ == "__main__":
    if len(sys.argv) > 2:
        GAME_NUM = sys.argv[2]
    
    if not GAME_URL:
        GAME_URL = input("Enter game URL: ").strip()
    
    match = re.search(r'/u/BBF/(\d+)', GAME_URL)
    game_id = match.group(1) if match else "unknown"
    
    index_url = f"https://fibalivestats.dcd.shared.geniussports.com/u/BBF/{game_id}/index.html"
    
    print(f"Fetching: {index_url}")
    html = fetch(index_url)
    
    # Debug: save HTML
    with open('last_fetch.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"Saved HTML to last_fetch.html ({len(html)} bytes)")
    
    if not html:
        print("Failed to fetch HTML")
        sys.exit(1)
    
    data = parse_index_html(html)
    
    print(f"Score: {data['home']} {data['h_score']} - {data['a_score']} {data['away']}")
    print(f"Home players: {len(data['home_players'])}, Away players: {len(data['away_players'])}")
    
    write_csv(data, GAME_NUM)
    print("DONE!")
