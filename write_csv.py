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
        return "--"
    text = elem.get_text(strip=True)
    if text:
        return text
    classes = elem.get('class') or []
    for c in classes:
        if isinstance(c, str) and c.startswith('aj_') and len(c) > 2:
            val = c[3:]
            if val.replace(':', '').replace('-', '').isdigit():
                return val
    return "--"

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

def parse_index_players(html):
    soup = BeautifulSoup(html, 'html.parser')
    
    home_players = []
    away_players = []
    home_names = set()
    away_names = set()
    
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
            'stl': '',
            'blk': '',
            'to': '',
            'pf': get_value(row.find('span', id=f'aj_{team_num}_{pid}_sFoulsPersonal')),
        }
    
    for row in soup.select('tbody.team-0-person-container tr.player-row'):
        if 'row-not-used' in (row.get('class') or []):
            continue
        p = get_player_data(row, 1)
        if p and p['name'] not in home_names:
            home_players.append(p)
            home_names.add(p['name'])
    
    for row in soup.select('tbody.team-1-person-container tr.player-row'):
        if 'row-not-used' in (row.get('class') or []):
            continue
        p = get_player_data(row, 2)
        if p and p['name'] not in away_names:
            away_players.append(p)
            away_names.add(p['name'])
    
    return {'home': home_players, 'away': away_players}

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
        
        writer.writerow([])
        writer.writerow([data['away'], 'BOX SCORE'])
        writer.writerow(['#', 'Name', 'MIN', 'PTS', 'REB', 'AST', 'STL', 'BLK', 'TO', 'PF'])
        
        for p in data['away_players']:
            writer.writerow([p['num'], p['name'], p['mins'], p['pts'], p['reb'], p['ast'], p['stl'], p['blk'], p['to'], p['pf']])
        
        writer.writerow([])
        writer.writerow(['SCOREBOARD'])
        writer.writerow([data['home'], data['h_score']])
        writer.writerow([data['away'], data['a_score']])
        writer.writerow(['Period', data['period']])
        writer.writerow(['Clock', data['clock']])
        
        # Leaders - Points
        writer.writerow([])
        writer.writerow(['POINTS LEADERS'])
        writer.writerow([data['home']])
        for i, p in enumerate(data.get('home_pts_leaders', []), 1):
            writer.writerow([i, p.get('name', ''), p.get('val', '')])
        writer.writerow([data['away']])
        for i, p in enumerate(data.get('away_pts_leaders', []), 1):
            writer.writerow([i, p.get('name', ''), p.get('val', '')])
        
        # Leaders - Rebounds
        writer.writerow([])
        writer.writerow(['REBOUNDS LEADERS'])
        writer.writerow([data['home']])
        for i, p in enumerate(data.get('home_reb_leaders', []), 1):
            writer.writerow([i, p.get('name', ''), p.get('val', '')])
        writer.writerow([data['away']])
        for i, p in enumerate(data.get('away_reb_leaders', []), 1):
            writer.writerow([i, p.get('name', ''), p.get('val', '')])
        
        # Leaders - Assists
        writer.writerow([])
        writer.writerow(['ASSISTS LEADERS'])
        writer.writerow([data['home']])
        for i, p in enumerate(data.get('home_ast_leaders', []), 1):
            writer.writerow([i, p.get('name', ''), p.get('val', '')])
        writer.writerow([data['away']])
        for i, p in enumerate(data.get('away_ast_leaders', []), 1):
            writer.writerow([i, p.get('name', ''), p.get('val', '')])
        
        # Team Stats
        writer.writerow([])
        writer.writerow(['TEAM STATS'])
        ts = data.get('team_stats', {})
        for key, val in ts.items():
            if val:
                writer.writerow([key, val])
        
        # Team Totals from bs.html
        writer.writerow([])
        writer.writerow(['TEAM TOTALS'])
        writer.writerow(['Team', 'Points', 'REB', 'AST', 'STL', 'BLK', 'TO', 'PF', 'PIP*', '2CP*', 'BP*'])
        writer.writerow([data['home'], data.get('home_totals', {}).get('pts', ''), data.get('home_totals', {}).get('reb', ''), data.get('home_totals', {}).get('ast', ''), data.get('home_totals', {}).get('stl', ''), data.get('home_totals', {}).get('blk', ''), data.get('home_totals', {}).get('to', ''), data.get('home_totals', {}).get('pf', ''), data.get('home_totals', {}).get('pts_paint', ''), data.get('home_totals', {}).get('pts_second', ''), data.get('home_totals', {}).get('bench_pts', '')])
        writer.writerow([data['away'], data.get('away_totals', {}).get('pts', ''), data.get('away_totals', {}).get('reb', ''), data.get('away_totals', {}).get('ast', ''), data.get('away_totals', {}).get('stl', ''), data.get('away_totals', {}).get('blk', ''), data.get('away_totals', {}).get('to', ''), data.get('away_totals', {}).get('pf', ''), data.get('away_totals', {}).get('pts_paint', ''), data.get('away_totals', {}).get('pts_second', ''), data.get('away_totals', {}).get('bench_pts', '')])
        
        # Advanced stats from bs.html
        writer.writerow([])
        writer.writerow(['ADVANCED STATS'])
        writer.writerow(['Team', 'Player', 'FG', 'FG%', '3PT', '3PT%', 'FT', 'FT%', '+/-', 'EFF'])
        
        for p in data.get('home_players', []):
            writer.writerow([data['home'], p.get('name', ''), f"{p.get('fg_m', '')}/{p.get('fg_a', '')}", p.get('fg_pct', ''), f"{p.get('three_p_m', '')}/{p.get('three_p_a', '')}", p.get('three_p_pct', ''), f"{p.get('ft_m', '')}/{p.get('ft_a', '')}", p.get('ft_pct', ''), p.get('plus_minus', ''), p.get('eff', '')])
        
        for p in data.get('away_players', []):
            writer.writerow([data['away'], p.get('name', ''), f"{p.get('fg_m', '')}/{p.get('fg_a', '')}", p.get('fg_pct', ''), f"{p.get('three_p_m', '')}/{p.get('three_p_a', '')}", p.get('three_p_pct', ''), f"{p.get('ft_m', '')}/{p.get('ft_a', '')}", p.get('ft_pct', ''), p.get('plus_minus', ''), p.get('eff', '')])
        
        # Four Factors from st.html
        writer.writerow([])
        writer.writerow(['FOUR FACTORS'])
        writer.writerow(['Metric', data['home'], data['away']])
        
        ht = data.get('home_totals', {})
        at = data.get('away_totals', {})
        
        writer.writerow(['Field Goal %', f"{ht.get('fg_pct', '')}%", f"{at.get('fg_pct', '')}%"])
        writer.writerow(['2-Point %', f"{ht.get('two_p_pct', '')}%", f"{at.get('two_p_pct', '')}%"])
        writer.writerow(['3-Point %', f"{ht.get('three_p_pct', '')}%", f"{at.get('three_p_pct', '')}%"])
        writer.writerow(['Free Throw %', f"{ht.get('ft_pct', '')}%", f"{at.get('ft_pct', '')}%"])
        writer.writerow(['Points in Paint', ht.get('pts_paint', ''), at.get('pts_paint', '')])
        writer.writerow(['Points from TO', ht.get('pts_turnovers', ''), at.get('pts_turnovers', '')])
        writer.writerow(['2nd Chance Points', ht.get('pts_second', ''), at.get('pts_second', '')])
        writer.writerow(['Fast Break Points', ht.get('pts_fast', ''), at.get('pts_fast', '')])
        writer.writerow(['Bench Points', ht.get('bench_pts', ''), at.get('bench_pts', '')])
    
    print(f"Written {filename}")

def write_text(data, game_num):
    os.makedirs("Game CSV", exist_ok=True)
    filename = f"Game CSV/Game {game_num}.txt"
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(f"NEBL LIVE STATS - GAME {game_num}\n")
        f.write("=" * 50 + "\n\n")
        f.write(f"SCOREBOARD\n")
        f.write(f"{data['home']}: {data['h_score']}\n")
        f.write(f"{data['away']}: {data['a_score']}\n")
        f.write(f"Period: {data['period']}, Clock: {data['clock']}\n\n")
        
        f.write(f"{data['home']} - BOX SCORE\n")
        f.write("-" * 30 + "\n")
        f.write(f"{'#':<4} {'Name':<20} {'MIN':<6} {'PTS':<5} {'REB':<5} {'AST':<5} {'STL':<5} {'BLK':<5} {'TO':<5} {'PF':<5}\n")
        for p in data['home_players']:
            f.write(f"{p['num']:<4} {p['name']:<20} {p['mins']:<6} {p['pts']:<5} {p['reb']:<5} {p['ast']:<5} {p['stl']:<5} {p['blk']:<5} {p['to']:<5} {p['pf']:<5}\n")
        
        f.write(f"\n{data['away']} - BOX SCORE\n")
        f.write("-" * 30 + "\n")
        f.write(f"{'#':<4} {'Name':<20} {'MIN':<6} {'PTS':<5} {'REB':<5} {'AST':<5} {'STL':<5} {'BLK':<5} {'TO':<5} {'PF':<5}\n")
        for p in data['away_players']:
            f.write(f"{p['num']:<4} {p['name']:<20} {p['mins']:<6} {p['pts']:<5} {p['reb']:<5} {p['ast']:<5} {p['stl']:<5} {p['blk']:<5} {p['to']:<5} {p['pf']:<5}\n")
        
        # Team Stats
        f.write(f"\nTEAM STATS\n")
        ts = data.get('team_stats', {})
        for key, val in ts.items():
            if val:
                f.write(f"{key}: {val}\n")
        
        # Team Totals
        f.write(f"\nTEAM TOTALS\n")
        f.write(f"{data['home']}: Pts={data.get('home_totals', {}).get('pts', '')} REB={data.get('home_totals', {}).get('reb', '')} AST={data.get('home_totals', {}).get('ast', '')} STL={data.get('home_totals', {}).get('stl', '')} BLK={data.get('home_totals', {}).get('blk', '')} TO={data.get('home_totals', {}).get('to', '')} PF={data.get('home_totals', {}).get('pf', '')} PIP={data.get('home_totals', {}).get('pts_paint', '')} 2CP={data.get('home_totals', {}).get('pts_second', '')} BP={data.get('home_totals', {}).get('bench_pts', '')}\n")
        f.write(f"{data['away']}: Pts={data.get('away_totals', {}).get('pts', '')} REB={data.get('away_totals', {}).get('reb', '')} AST={data.get('away_totals', {}).get('ast', '')} STL={data.get('away_totals', {}).get('stl', '')} BLK={data.get('away_totals', {}).get('blk', '')} TO={data.get('away_totals', {}).get('to', '')} PF={data.get('away_totals', {}).get('pf', '')} PIP={data.get('away_totals', {}).get('pts_paint', '')} 2CP={data.get('away_totals', {}).get('pts_second', '')} BP={data.get('away_totals', {}).get('bench_pts', '')}\n")
    
    print(f"Written {filename}")

def write_xml(data, game_num):
    os.makedirs("Game CSV", exist_ok=True)
    filename = f"Game CSV/Game {game_num}.xml"
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write(f"<game number='{game_num}'>\n")
        
        f.write("  <scoreboard>\n")
        f.write(f"    <home team='{data['home']}' score='{data['h_score']}'/>\n")
        f.write(f"    <away team='{data['away']}' score='{data['a_score']}'/>\n")
        f.write(f"    <period>{data['period']}</period>\n")
        f.write(f"    <clock>{data['clock']}</clock>\n")
        f.write("  </scoreboard>\n")
        
        f.write(f"  <home_team name='{data['home']}'>\n")
        for p in data['home_players']:
            f.write(f"    <player number='{p['num']}' name='{p['name']}' min='{p['mins']}' pts='{p['pts']}' reb='{p['reb']}' ast='{p['ast']}' stl='{p['stl']}' blk='{p['blk']}' to='{p['to']}' pf='{p['pf']}'/>\n")
        f.write("  </home_team>\n")
        
        f.write(f"  <away_team name='{data['away']}'>\n")
        for p in data['away_players']:
            f.write(f"    <player number='{p['num']}' name='{p['name']}' min='{p['mins']}' pts='{p['pts']}' reb='{p['reb']}' ast='{p['ast']}' stl='{p['stl']}' blk='{p['blk']}' to='{p['to']}' pf='{p['pf']}'/>\n")
        f.write("  </away_team>\n")
        
        f.write("  <team_totals>\n")
        f.write(f"    <team name='{data['home']}' pts='{data.get('home_totals', {}).get('pts', '')}' reb='{data.get('home_totals', {}).get('reb', '')}' ast='{data.get('home_totals', {}).get('ast', '')}' stl='{data.get('home_totals', {}).get('stl', '')}' blk='{data.get('home_totals', {}).get('blk', '')}' to='{data.get('home_totals', {}).get('to', '')}' pf='{data.get('home_totals', {}).get('pf', '')}' pip='{data.get('home_totals', {}).get('pts_paint', '')}' tcp='{data.get('home_totals', {}).get('pts_second', '')}' bp='{data.get('home_totals', {}).get('bench_pts', '')}'/>\n")
        f.write(f"    <team name='{data['away']}' pts='{data.get('away_totals', {}).get('pts', '')}' reb='{data.get('away_totals', {}).get('reb', '')}' ast='{data.get('away_totals', {}).get('ast', '')}' stl='{data.get('away_totals', {}).get('stl', '')}' blk='{data.get('away_totals', {}).get('blk', '')}' to='{data.get('away_totals', {}).get('to', '')}' pf='{data.get('away_totals', {}).get('pf', '')}' pip='{data.get('away_totals', {}).get('pts_paint', '')}' tcp='{data.get('away_totals', {}).get('pts_second', '')}' bp='{data.get('away_totals', {}).get('bench_pts', '')}'/>\n")
        f.write("  </team_totals>\n")
        
        f.write("</game>\n")
    
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
    data_players = parse_index_players(index_html)
    data_st = parse_st_html(st_html)
    data_lds = parse_lds_html(lds_html)
    
    # Combine data - use index players for box score (has all players)
    data['home_players'] = data_players.get('home', data.get('home_players', []))
    data['away_players'] = data_players.get('away', data.get('away_players', []))
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
            data_players = parse_index_players(index_html)
            data_st = parse_st_html(st_html)
            data_lds = parse_lds_html(lds_html)
            
            # Use index players for box score (has all players)
            data['home_players'] = data_players.get('home', [])
            data['away_players'] = data_players.get('away', [])
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
            
            # Merge advanced stats from bs.html into players
            bs_data = parse_bs_html(bs_html)
            if 'home_totals' in bs_data:
                data['home_totals'] = bs_data.get('home_totals', {})
            if 'away_totals' in bs_data:
                data['away_totals'] = bs_data.get('away_totals', {})
            
            # Merge player advanced stats
            for hp in data.get('home_players', []):
                for bsp in bs_data.get('home_players', []):
                    if hp.get('name') == bsp.get('name'):
                        hp.update(bsp)
                        break
            
            for ap in data.get('away_players', []):
                for bsp in bs_data.get('away_players', []):
                    if ap.get('name') == bsp.get('name'):
                        ap.update(bsp)
                        break
            
            write_csv(data, GAME_NUM)
            write_text(data, GAME_NUM)
            write_xml(data, GAME_NUM)
            print(f"Updated at {time.strftime('%H:%M:%S')} - Score: {data['home']} {data['h_score']} - {data['a_score']} {data['away']}")
            time.sleep(5)
        except KeyboardInterrupt:
            print("Stopped.")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)
