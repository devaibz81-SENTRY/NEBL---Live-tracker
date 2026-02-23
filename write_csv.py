import re
import csv
import sys
import os
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

if len(sys.argv) > 1:
    GAME_URL = sys.argv[1]
else:
    GAME_URL = ""

GAME_NUM = "1"

def fetch(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(2000)
        html = page.content()
        browser.close()
    return html

def get_value(elem):
    if not elem:
        return ""
    text = elem.get_text(strip=True)
    if text:
        return text
    for c in elem.get('class', []):
        if c.startswith('aj_') and len(c) > 2:
            val = c[3:]
            if val.replace(':', '').isdigit() or val.replace('-', '').replace(':', '').isdigit():
                return val
    return ""

def parse_leaders(html):
    soup = BeautifulSoup(html, 'html.parser')
    
    def get_leader_data(prefix, stat):
        leaders = []
        for rank in range(1, 6):
            name_elem = soup.find('span', {'class': f'id_{prefix}_{stat}_{rank}_name'})
            num_elem = soup.find('span', {'class': f'id_{prefix}_{stat}_{rank}_shirtNumber'})
            tot_elem = soup.find('span', {'class': f'id_{prefix}_{stat}_{rank}_tot'})
            
            if name_elem:
                leaders.append({
                    'name': name_elem.get_text(strip=True),
                    'num': num_elem.get_text(strip=True) if num_elem else "",
                    'val': tot_elem.get_text(strip=True) if tot_elem else ""
                })
        return leaders
    
    return {
        'home_points': get_leader_data('aj_1', 'sPoints'),
        'away_points': get_leader_data('aj_2', 'sPoints'),
        'home_rebounds': get_leader_data('aj_1', 'sReboundsTotal'),
        'away_rebounds': get_leader_data('aj_2', 'sReboundsTotal'),
        'home_assists': get_leader_data('aj_1', 'sAssists'),
        'away_assists': get_leader_data('aj_2', 'sAssists'),
    }

def parse_boxscore(html):
    soup = BeautifulSoup(html, 'html.parser')
    
    home = soup.find('span', id='aj_1_shortName')
    away = soup.find('span', id='aj_2_shortName')
    h_score = soup.find('span', id='aj_1_score')
    a_score = soup.find('span', id='aj_2_score')
    period = soup.find('span', id='aj_period')
    clock = soup.find('span', id='aj_clock')
    
    home = home.get_text(strip=True) if home else ""
    away = away.get_text(strip=True) if away else ""
    h_score = get_value(h_score) if h_score else "0"
    a_score = get_value(a_score) if a_score else "0"
    period = get_value(period) if period else ""
    clock = get_value(clock) if clock else ""
    
    def get_player_data(row, team_num):
        name_span = row.find('span', id=lambda x: x and x.endswith(f'_{team_num}_name'))
        if not name_span:
            return None
        
        row_id = row.get('id', '')
        pid_match = re.search(rf'aj_{team_num}_(\d+)_row', row_id)
        if not pid_match:
            return None
        pid = pid_match.group(1)
        
        name = name_span.get_text(strip=True)
        
        captain_span = row.find('span', id=f'aj_{team_num}_{pid}_captainString')
        captain = captain_span.get_text(strip=True) if captain_span else ""
        
        return {
            'num': get_value(row.find('span', id=f'aj_{team_num}_{pid}_shirtNumber')),
            'name': name + captain,
            'pos': get_value(row.find('span', id=f'aj_{team_num}_{pid}_playingPosition')),
            'mins': get_value(row.find('span', id=f'aj_{team_num}_{pid}_sMinutes')),
            'pts': get_value(row.find('span', id=f'aj_{team_num}_{pid}_sPoints')),
            'fg_m': get_value(row.find('span', id=f'aj_{team_num}_{pid}_sFieldGoalsMade')),
            'fg_a': get_value(row.find('span', id=f'aj_{team_num}_{pid}_sFieldGoalsAttempted')),
            'fg_pct': get_value(row.find('span', id=f'aj_{team_num}_{pid}_sFieldGoalsPercentage')),
            'two_p_m': get_value(row.find('span', id=f'aj_{team_num}_{pid}_sTwoPointersMade')),
            'two_p_a': get_value(row.find('span', id=f'aj_{team_num}_{pid}_sTwoPointersAttempted')),
            'two_p_pct': get_value(row.find('span', id=f'aj_{team_num}_{pid}_sTwoPointersPercentage')),
            'three_p_m': get_value(row.find('span', id=f'aj_{team_num}_{pid}_sThreePointersMade')),
            'three_p_a': get_value(row.find('span', id=f'aj_{team_num}_{pid}_sThreePointersAttempted')),
            'three_p_pct': get_value(row.find('span', id=f'aj_{team_num}_{pid}_sThreePointersPercentage')),
            'ft_m': get_value(row.find('span', id=f'aj_{team_num}_{pid}_sFreeThrowsMade')),
            'ft_a': get_value(row.find('span', id=f'aj_{team_num}_{pid}_sFreeThrowsAttempted')),
            'ft_pct': get_value(row.find('span', id=f'aj_{team_num}_{pid}_sFreeThrowsPercentage')),
            'off': get_value(row.find('span', id=f'aj_{team_num}_{pid}_sReboundsOffensive')),
            'def': get_value(row.find('span', id=f'aj_{team_num}_{pid}_sReboundsDefensive')),
            'reb': get_value(row.find('span', id=f'aj_{team_num}_{pid}_sReboundsTotal')),
            'ast': get_value(row.find('span', id=f'aj_{team_num}_{pid}_sAssists')),
            'to': get_value(row.find('span', id=f'aj_{team_num}_{pid}_sTurnovers')),
            'stl': get_value(row.find('span', id=f'aj_{team_num}_{pid}_sSteals')),
            'blk': get_value(row.find('span', id=f'aj_{team_num}_{pid}_sBlocks')),
            'blkr': get_value(row.find('span', id=f'aj_{team_num}_{pid}_sBlocksReceived')),
            'pf': get_value(row.find('span', id=f'aj_{team_num}_{pid}_sFoulsPersonal')),
            'fld_on': get_value(row.find('span', id=f'aj_{team_num}_{pid}_sFoulsOn')),
            'plus_minus': get_value(row.find('span', id=f'aj_{team_num}_{pid}_sPlusMinusPoints')),
            'eff': get_value(row.find('span', id=f'aj_{team_num}_{pid}_eff_1')),
            'is_starter': 'p_starter' in row.get('class', [])
        }
    
    home_starters, home_bench = [], []
    away_starters, away_bench = [], []
    
    for row in soup.select('tbody.team-0-person-container tr.player-row'):
        if 'row-not-used' in row.get('class', []):
            continue
        p = get_player_data(row, 1)
        if p:
            (home_starters if p['is_starter'] else home_bench).append(p)
    
    for row in soup.select('tbody.team-1-person-container tr.player-row'):
        if 'row-not-used' in row.get('class', []):
            continue
        p = get_player_data(row, 2)
        if p:
            (away_starters if p['is_starter'] else away_bench).append(p)
    
    for row in soup.select('tbody.bench tr.player-row'):
        if 'row-not-used' in row.get('class', []):
            continue
        p1 = get_player_data(row, 1)
        if p1:
            home_bench.append(p1)
        p2 = get_player_data(row, 2)
        if p2:
            away_bench.append(p2)
    
    home_all = home_starters + home_bench
    away_all = away_starters + away_bench
    
    def get_totals(team_num):
        return {
            'pts': get_value(soup.find('span', id=f'aj_{team_num}_tot_sPoints')),
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
            'off': get_value(soup.find('span', id=f'aj_{team_num}_tot_sReboundsOffensive')),
            'def': get_value(soup.find('span', id=f'aj_{team_num}_tot_sReboundsDefensive')),
            'reb': get_value(soup.find('span', id=f'aj_{team_num}_tot_sReboundsTotal')),
            'ast': get_value(soup.find('span', id=f'aj_{team_num}_tot_sAssists')),
            'to': get_value(soup.find('span', id=f'aj_{team_num}_tot_sTurnovers')),
            'stl': get_value(soup.find('span', id=f'aj_{team_num}_tot_sSteals')),
            'blk': get_value(soup.find('span', id=f'aj_{team_num}_tot_sBlocks')),
            'pf': get_value(soup.find('span', id=f'aj_{team_num}_tot_sFoulsTotal')),
            'eff': get_value(soup.find('span', id=f'aj_{team_num}_tot_eff_1')),
            'pts_turnovers': get_value(soup.find('span', id=f'aj_{team_num}_tot_sPointsFromTurnovers')),
            'pts_paint': get_value(soup.find('span', id=f'aj_{team_num}_tot_sPointsInThePaint')),
            'pts_second': get_value(soup.find('span', id=f'aj_{team_num}_tot_sPointsSecondChance')),
            'pts_fast': get_value(soup.find('span', id=f'aj_{team_num}_tot_sPointsFastBreak')),
            'bench_pts': get_value(soup.find('span', id=f'aj_{team_num}_tot_sBenchPoints')),
        }
    
    return {
        'home': home, 'away': away, 'h_score': h_score, 'a_score': a_score,
        'period': period, 'clock': clock,
        'home_starters': home_starters, 'home_bench': home_bench,
        'away_starters': away_starters, 'away_bench': away_bench,
        'home_totals': get_totals(1), 'away_totals': get_totals(2),
    }

def write_csv(data, game_num):
    os.makedirs("Game CSV", exist_ok=True)
    filename = f"Game CSV/Game {game_num}.csv"
    
    def wrow(writer, row):
        writer.writerow(row)
    
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        wrow(writer, [f'NEBL LIVE STATS - GAME {game_num}'])
        wrow(writer, [])
        wrow(writer, ['SCOREBOARD'])
        wrow(writer, ['Home', data['home'], data['h_score']])
        wrow(writer, ['Away', data['away'], data['a_score']])
        wrow(writer, ['Period', data['period']])
        wrow(writer, ['Clock', data['clock']])
        wrow(writer, [])
        
        wrow(writer, ['No.', 'Player', 'POS', 'Mins', 'Pts', 'FG', 'FG%', '2P', '2P%', '3P', '3P%', 'FT', 'FT%', 'OFF', 'DEF', 'REB', 'AST', 'TO', 'STL', 'BLK', 'BLKR', 'PF', 'Fls on', '+/-', 'Index'])
        wrow(writer, ['', 'STARTERS'])
        
        for p in data['home_starters']:
            fg = f"{p['fg_m']}-{p['fg_a']}" if p['fg_m'] else ""
            two_p = f"{p['two_p_m']}-{p['two_p_a']}" if p['two_p_m'] else ""
            three_p = f"{p['three_p_m']}-{p['three_p_a']}" if p['three_p_m'] else ""
            ft = f"{p['ft_m']}-{p['ft_a']}" if p['ft_m'] else ""
            wrow(writer, [p['num'], p['name'], p['pos'], p['mins'], p['pts'], fg, p['fg_pct'], two_p, p['two_p_pct'], three_p, p['three_p_pct'], ft, p['ft_pct'], p['off'], p['def'], p['reb'], p['ast'], p['to'], p['stl'], p['blk'], p['blkr'], p['pf'], p['fld_on'], p['plus_minus'], p['eff']])
        
        wrow(writer, ['', 'BENCH'])
        for p in data['home_bench']:
            fg = f"{p['fg_m']}-{p['fg_a']}" if p['fg_m'] else ""
            two_p = f"{p['two_p_m']}-{p['two_p_a']}" if p['two_p_m'] else ""
            three_p = f"{p['three_p_m']}-{p['three_p_a']}" if p['three_p_m'] else ""
            ft = f"{p['ft_m']}-{p['ft_a']}" if p['ft_m'] else ""
            wrow(writer, [p['num'], p['name'], p['pos'], p['mins'], p['pts'], fg, p['fg_pct'], two_p, p['two_p_pct'], three_p, p['three_p_pct'], ft, p['ft_pct'], p['off'], p['def'], p['reb'], p['ast'], p['to'], p['stl'], p['blk'], p['blkr'], p['pf'], p['fld_on'], p['plus_minus'], p['eff']])
        
        ht = data['home_totals']
        wrow(writer, ['', 'TEAM TOTALS'])
        fg = f"{ht['fg_m']}-{ht['fg_a']}" if ht.get('fg_m') else ""
        two_p = f"{ht['two_p_m']}-{ht['two_p_a']}" if ht.get('two_p_m') else ""
        three_p = f"{ht['three_p_m']}-{ht['three_p_a']}" if ht.get('three_p_m') else ""
        ft = f"{ht['ft_m']}-{ht['ft_a']}" if ht.get('ft_m') else ""
        wrow(writer, ['', 'TEAM TOTALS', '', '', ht.get('pts', ''), fg, ht.get('fg_pct', ''), two_p, ht.get('two_p_pct', ''), three_p, ht.get('three_p_pct', ''), ft, ht.get('ft_pct', ''), ht.get('off', ''), ht.get('def', ''), ht.get('reb', ''), ht.get('ast', ''), ht.get('to', ''), ht.get('stl', ''), ht.get('blk', ''), '', ht.get('pf', ''), '', '', ht.get('eff', '')])
        
        wrow(writer, [])
        wrow(writer, ['No.', 'Player', 'POS', 'Mins', 'Pts', 'FG', 'FG%', '2P', '2P%', '3P', '3P%', 'FT', 'FT%', 'OFF', 'DEF', 'REB', 'AST', 'TO', 'STL', 'BLK', 'BLKR', 'PF', 'Fls on', '+/-', 'Index'])
        wrow(writer, ['', 'STARTERS'])
        
        for p in data['away_starters']:
            fg = f"{p['fg_m']}-{p['fg_a']}" if p['fg_m'] else ""
            two_p = f"{p['two_p_m']}-{p['two_p_a']}" if p['two_p_m'] else ""
            three_p = f"{p['three_p_m']}-{p['three_p_a']}" if p['three_p_m'] else ""
            ft = f"{p['ft_m']}-{p['ft_a']}" if p['ft_m'] else ""
            wrow(writer, [p['num'], p['name'], p['pos'], p['mins'], p['pts'], fg, p['fg_pct'], two_p, p['two_p_pct'], three_p, p['three_p_pct'], ft, p['ft_pct'], p['off'], p['def'], p['reb'], p['ast'], p['to'], p['stl'], p['blk'], p['blkr'], p['pf'], p['fld_on'], p['plus_minus'], p['eff']])
        
        wrow(writer, ['', 'BENCH'])
        for p in data['away_bench']:
            fg = f"{p['fg_m']}-{p['fg_a']}" if p['fg_m'] else ""
            two_p = f"{p['two_p_m']}-{p['two_p_a']}" if p['two_p_m'] else ""
            three_p = f"{p['three_p_m']}-{p['three_p_a']}" if p['three_p_m'] else ""
            ft = f"{p['ft_m']}-{p['ft_a']}" if p['ft_m'] else ""
            wrow(writer, [p['num'], p['name'], p['pos'], p['mins'], p['pts'], fg, p['fg_pct'], two_p, p['two_p_pct'], three_p, p['three_p_pct'], ft, p['ft_pct'], p['off'], p['def'], p['reb'], p['ast'], p['to'], p['stl'], p['blk'], p['blkr'], p['pf'], p['fld_on'], p['plus_minus'], p['eff']])
        
        at = data['away_totals']
        wrow(writer, ['', 'TEAM TOTALS'])
        fg = f"{at['fg_m']}-{at['fg_a']}" if at.get('fg_m') else ""
        two_p = f"{at['two_p_m']}-{at['two_p_a']}" if at.get('two_p_m') else ""
        three_p = f"{at['three_p_m']}-{at['three_p_a']}" if at.get('three_p_m') else ""
        ft = f"{at['ft_m']}-{at['ft_a']}" if at.get('ft_m') else ""
        wrow(writer, ['', 'TEAM TOTALS', '', '', at.get('pts', ''), fg, at.get('fg_pct', ''), two_p, at.get('two_p_pct', ''), three_p, at.get('three_p_pct', ''), ft, at.get('ft_pct', ''), at.get('off', ''), at.get('def', ''), at.get('reb', ''), at.get('ast', ''), at.get('to', ''), at.get('stl', ''), at.get('blk', ''), '', at.get('pf', ''), '', '', at.get('eff', '')])
        
        wrow(writer, [])
        
        wrow(writer, ['Points', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', ''])
        wrow(writer, ['', data['home'], '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', ''])
        wrow(writer, ['', data['away'], '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', ''])
        
        wrow(writer, [])
        wrow(writer, ['Total Rebounds', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', ''])
        wrow(writer, [ht.get('reb', ''), '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', ''])
        wrow(writer, [at.get('reb', ''), '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', ''])
        
        wrow(writer, [])
        wrow(writer, ['Assists', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', ''])
        wrow(writer, [ht.get('ast', ''), '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', ''])
        wrow(writer, [at.get('ast', ''), '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', ''])
        
        wrow(writer, [])
        wrow(writer, ['Steals', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', ''])
        wrow(writer, [ht.get('stl', ''), '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', ''])
        wrow(writer, [at.get('stl', ''), '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', ''])
        
        wrow(writer, [])
        wrow(writer, ['Turnovers', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', ''])
        wrow(writer, [ht.get('to', ''), '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', ''])
        wrow(writer, [at.get('to', ''), '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', ''])
        
        wrow(writer, [])
        wrow(writer, ['Points from turnovers', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', ''])
        wrow(writer, [ht.get('pts_turnovers', ''), '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', ''])
        wrow(writer, [at.get('pts_turnovers', ''), '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', ''])
        
        wrow(writer, [])
        wrow(writer, ['Fast break points', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', ''])
        wrow(writer, [ht.get('pts_fast', ''), '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', ''])
        wrow(writer, [at.get('pts_fast', ''), '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', ''])
        
        wrow(writer, [])
        wrow(writer, ['Second chance points', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', ''])
        wrow(writer, [ht.get('pts_second', ''), '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', ''])
        wrow(writer, [at.get('pts_second', ''), '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', ''])
        
        wrow(writer, [])
        wrow(writer, ['Bench points', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', ''])
        wrow(writer, [ht.get('bench_pts', ''), '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', ''])
        wrow(writer, [at.get('bench_pts', ''), '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', ''])
        
        wrow(writer, [])
        wrow(writer, [data['home'], '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', ''])
        
        wrow(writer, ['2P', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', f"{ht.get('two_p_m', '')}/{ht.get('two_p_a', '')}"])
        wrow(writer, [f"{ht.get('two_p_pct', '')}%", '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', ''])
        
        wrow(writer, ['3P', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', f"{ht.get('three_p_m', '')}/{ht.get('three_p_a', '')}"])
        wrow(writer, [f"{ht.get('three_p_pct', '')}%", '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', ''])
        
        wrow(writer, ['FT', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', f"{ht.get('ft_m', '')}/{ht.get('ft_a', '')}"])
        wrow(writer, [f"{ht.get('ft_pct', '')}%", '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', ''])
        
        wrow(writer, [])
        wrow(writer, ['POINTS LEADERS', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', ''])
        wrow(writer, [data['home'], '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', ''])
        for p in data.get('home_leaders', []):
            wrow(writer, [p.get('num', ''), p.get('name', ''), '', '', p.get('pts', ''), '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', ''])
        wrow(writer, [data['away'], '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', ''])
        for p in data.get('away_leaders', []):
            wrow(writer, [p.get('num', ''), p.get('name', ''), '', '', p.get('pts', ''), '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', ''])
        
        wrow(writer, [])
        wrow(writer, ['REBOUNDS LEADERS', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', ''])
        wrow(writer, [data['home'], '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', ''])
        for p in data.get('home_reb_leaders', []):
            wrow(writer, [p.get('num', ''), p.get('name', ''), '', '', p.get('val', ''), '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', ''])
        wrow(writer, [data['away'], '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', ''])
        for p in data.get('away_reb_leaders', []):
            wrow(writer, [p.get('num', ''), p.get('name', ''), '', '', p.get('val', ''), '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', ''])
        
        wrow(writer, [])
        wrow(writer, ['ASSISTS LEADERS', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', ''])
        wrow(writer, [data['home'], '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', ''])
        for p in data.get('home_ast_leaders', []):
            wrow(writer, [p.get('num', ''), p.get('name', ''), '', '', p.get('val', ''), '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', ''])
        wrow(writer, [data['away'], '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', ''])
        for p in data.get('away_ast_leaders', []):
            wrow(writer, [p.get('num', ''), p.get('name', ''), '', '', p.get('val', ''), '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', ''])
    
    print(f"Written {filename}")

if __name__ == "__main__":
    if len(sys.argv) > 2:
        GAME_NUM = sys.argv[2]
    
    if not GAME_URL:
        GAME_URL = input("Enter game URL: ").strip()
    
    match = re.search(r'/u/BBF/(\d+)', GAME_URL)
    game_id = match.group(1) if match else "unknown"
    bs_url = f"https://fibalivestats.dcd.shared.geniussports.com/u/BBF/{game_id}/bs.html"
    
    print(f"Fetching: {bs_url}")
    html = fetch(bs_url)
    data = parse_boxscore(html)
    
    lds_url = f"https://fibalivestats.dcd.shared.geniussports.com/u/BBF/{game_id}/lds.html"
    print(f"Fetching: {lds_url}")
    leaders_html = fetch(lds_url)
    leaders_data = parse_leaders(leaders_html)
    data['home_leaders'] = leaders_data['home_points']
    data['away_leaders'] = leaders_data['away_points']
    data['home_reb_leaders'] = leaders_data['home_rebounds']
    data['away_reb_leaders'] = leaders_data['away_rebounds']
    data['home_ast_leaders'] = leaders_data['home_assists']
    data['away_ast_leaders'] = leaders_data['away_assists']
    
    print(f"Score: {data['home']} {data['h_score']} - {data['a_score']} {data['away']}")
    print(f"Home players: {len(data['home_starters'])+len(data['home_bench'])}, Away players: {len(data['away_starters'])+len(data['away_bench'])}")
    
    write_csv(data, GAME_NUM)
    print("DONE!")
