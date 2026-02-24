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
    
    return {
        'home': home_team, 'away': away_team,
        'h_score': home_score, 'a_score': away_score,
        'period': game_period, 'clock': game_clock,
    }

def parse_lds_html(html):
    soup = BeautifulSoup(html, 'html.parser')
    
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
    
    return {
        'home_pts_leaders': get_leaders('aj_1', 'sPoints'),
        'away_pts_leaders': get_leaders('aj_2', 'sPoints'),
        'home_reb_leaders': get_leaders('aj_1', 'sReboundsTotal'),
        'away_reb_leaders': get_leaders('aj_2', 'sReboundsTotal'),
        'home_ast_leaders': get_leaders('aj_1', 'sAssists'),
        'away_ast_leaders': get_leaders('aj_2', 'sAssists'),
    }

def parse_st_html(html):
    soup = BeautifulSoup(html, 'html.parser')
    all_data = {}
    
    for span in soup.find_all('span'):
        sid = span.get('id', '') or ''
        if sid.startswith('aj_') or sid.startswith('id_aj_'):
            val = get_value(span)
            if val:
                all_data[sid] = val
    
    return all_data

def parse_bs_html(html):
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
            'stl': get_value(row.find('span', id=f'aj_{team_num}_{pid}_sSteals')),
            'blk': get_value(row.find('span', id=f'aj_{team_num}_{pid}_sBlocks')),
            'to': get_value(row.find('span', id=f'aj_{team_num}_{pid}_sTurnovers')),
            'pf': get_value(row.find('span', id=f'aj_{team_num}_{pid}_sFoulsPersonal')),
            'eff': get_value(row.find('span', id=f'aj_{team_num}_{pid}_eff_1')),
            'is_starter': 'p_starter' in (row.get('class') or [])
        }
    
    home_players, away_players = [], []
    home_names = set()
    away_names = set()
    
    # Get all players from team-0-person-container
    for row in soup.select('tbody.team-0-person-container tr.player-row'):
        classes = row.get('class') or []
        if 'row-not-used' in classes:
            continue
        p = get_player_data(row, 1)
        if p and p['name'] not in home_names:
            home_players.append(p)
            home_names.add(p['name'])
    
    # Get all players from team-1-person-container
    for row in soup.select('tbody.team-1-person-container tr.player-row'):
        classes = row.get('class') or []
        if 'row-not-used' in classes:
            continue
        p = get_player_data(row, 2)
        if p and p['name'] not in away_names:
            away_players.append(p)
            away_names.add(p['name'])
    
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
        
        writer.writerow([data['home'], 'BOX SCORE'])
        writer.writerow(['#', 'Name', 'MIN', 'PTS', 'REB', 'AST', 'STL', 'BLK', 'TO', 'PF'])
        
        for p in data['home_players']:
            writer.writerow([p['num'], p['name'], p['mins'], p['pts'], p['reb'], p['ast'], p['stl'], p['blk'], p['to'], p['pf']])
        
        ht = data['home_totals']
        
        writer.writerow([])
        writer.writerow([data['away'], 'BOX SCORE'])
        writer.writerow(['#', 'Name', 'MIN', 'PTS', 'REB', 'AST', 'STL', 'BLK', 'TO', 'PF'])
        
        for p in data['away_players']:
            writer.writerow([p['num'], p['name'], p['mins'], p['pts'], p['reb'], p['ast'], p['stl'], p['blk'], p['to'], p['pf']])
        
        at = data['away_totals']
        
        writer.writerow([])
        writer.writerow(['SCOREBOARD'])
        writer.writerow([data['home'], data['h_score']])
        writer.writerow([data['away'], data['a_score']])
        writer.writerow(['Period', data['period']])
        writer.writerow(['Clock', data['clock']])
    
    print(f"Written {filename}")

if __name__ == "__main__":
    if len(sys.argv) > 2:
        GAME_NUM = sys.argv[2]
    
    if not GAME_URL:
        GAME_URL = input("Enter game URL: ").strip()
    
    match = re.search(r'/u/BBF/(\d+)', GAME_URL)
    game_id = match.group(1) if match else "unknown"
    
    # Fetch from index.html for scoreboard
    index_url = f"https://fibalivestats.dcd.shared.geniussports.com/u/BBF/{game_id}/index.html"
    print(f"Fetching: {index_url}")
    index_html = fetch(index_url)
    
    # Fetch from bs.html for full box score
    bs_url = f"https://fibalivestats.dcd.shared.geniussports.com/u/BBF/{game_id}/bs.html"
    print(f"Fetching: {bs_url}")
    bs_html = fetch(bs_url)
    
    # Fetch from lds.html for leaders
    lds_url = f"https://fibalivestats.dcd.shared.geniussports.com/u/BBF/{game_id}/lds.html"
    print(f"Fetching: {lds_url}")
    lds_html = fetch(lds_url)
    
    # Fetch from st.html for statistics
    st_url = f"https://fibalivestats.dcd.shared.geniussports.com/u/BBF/{game_id}/st.html"
    print(f"Fetching: {st_url}")
    st_html = fetch(st_url)
    
    # Debug: save HTMLs
    with open('last_fetch.html', 'w', encoding='utf-8') as f:
        f.write(bs_html)
    print(f"Saved HTML to last_fetch.html ({len(bs_html)} bytes)")
    
    if not bs_html:
        print("Failed to fetch HTML")
        sys.exit(1)
    
    data = parse_bs_html(bs_html)
    data_index = parse_index_html(index_html)
    data_st = parse_st_html(st_html)
    data_lds = parse_lds_html(lds_html)
    
    # Combine data
    data['h_score'] = data_index.get('h_score', data.get('h_score'))
    data['a_score'] = data_index.get('a_score', data.get('a_score'))
    data['period'] = data_index.get('period', data.get('period'))
    data['clock'] = data_index.get('clock', data.get('clock'))
    data['home_pts_leaders'] = data_lds.get('home_pts_leaders', [])
    data['away_pts_leaders'] = data_lds.get('away_pts_leaders', [])
    data['home_reb_leaders'] = data_lds.get('home_reb_leaders', [])
    data['away_reb_leaders'] = data_lds.get('away_reb_leaders', [])
    data['home_ast_leaders'] = data_lds.get('home_ast_leaders', [])
    data['away_ast_leaders'] = data_lds.get('away_ast_leaders', [])
    data['team_stats'] = data_st
    
    print(f"Score: {data['home']} {data['h_score']} - {data['a_score']} {data['away']}")
    print(f"Home players: {len(data['home_players'])}, Away players: {len(data['away_players'])}")
    
    # Write CSV and refresh every 10 seconds
    while True:
        try:
            # Refetch data
            index_html = fetch(index_url)
            bs_html = fetch(bs_url)
            lds_html = fetch(lds_url)
            st_html = fetch(st_url)
            
            data = parse_bs_html(bs_html)
            data_index = parse_index_html(index_html)
            data_st = parse_st_html(st_html)
            data_lds = parse_lds_html(lds_html)
            
            data['h_score'] = data_index.get('h_score', data.get('h_score'))
            data['a_score'] = data_index.get('a_score', data.get('a_score'))
            data['period'] = data_index.get('period', data.get('period'))
            data['clock'] = data_index.get('clock', data.get('clock'))
            data['home_pts_leaders'] = data_lds.get('home_pts_leaders', [])
            data['away_pts_leaders'] = data_lds.get('away_pts_leaders', [])
            data['home_reb_leaders'] = data_lds.get('home_reb_leaders', [])
            data['away_reb_leaders'] = data_lds.get('away_reb_leaders', [])
            data['home_ast_leaders'] = data_lds.get('home_ast_leaders', [])
            data['away_ast_leaders'] = data_lds.get('away_ast_leaders', [])
            data['team_stats'] = data_st
            
            write_csv(data, GAME_NUM)
            print(f"Updated at {time.strftime('%H:%M:%S')} - Score: {data['home']} {data['h_score']} - {data['a_score']} {data['away']}")
            time.sleep(10)
        except KeyboardInterrupt:
            print("Stopped.")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(10)
