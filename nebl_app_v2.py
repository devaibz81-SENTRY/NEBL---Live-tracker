#!/usr/bin/env python3
"""
NEBL Live Stats - Full Featured Desktop App
- Nice big tabs
- All stats from all pages
- Live JSON pushing
- Fast polling
"""

import tkinter as tk
from tkinter import ttk
import threading
import json
import os
import time
import re
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

class NEBLStatsApp:
    def __init__(self, root):
        self.root = root
        self.root.title("NEBL Live Stats")
        self.root.geometry("1400x900")
        self.root.configure(bg="#0d1b2a")
        
        self.is_watching = False
        self.watch_thread = None
        self.poll_interval = 0.5
        
        self.setup_ui()
        
    def setup_ui(self):
        # Header
        header = tk.Frame(self.root, bg="#1e3a5f", height=80)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        
        tk.Label(header, text="NEBL LIVE STATS", font=("Arial", 24, "bold"), 
                bg="#1e3a5f", fg="#ffd700").pack(pady=20)
        
        # URL Input
        input_frame = tk.Frame(self.root, bg="#0d1b2a", pady=10)
        input_frame.pack(fill=tk.X, padx=20)
        
        tk.Label(input_frame, text="Game URL:", bg="#0d1b2a", fg="white", font=("Arial", 12, "bold")).pack(side=tk.LEFT)
        
        self.url_entry = tk.Entry(input_frame, font=("Arial", 12), width=60)
        self.url_entry.pack(side=tk.LEFT, padx=10)
        self.url_entry.insert(0, "https://fibalivestats.dcd.shared.geniussports.com/u/BBF/2799697/index.html")
        
        # Poll interval
        tk.Label(input_frame, text="Interval (s):", bg="#0d1b2a", fg="white", font=("Arial", 10)).pack(side=tk.LEFT, padx=(20,5))
        self.poll_entry = tk.Entry(input_frame, font=("Arial", 10), width=8)
        self.poll_entry.pack(side=tk.LEFT)
        self.poll_entry.insert(0, "1")
        
        self.start_btn = tk.Button(input_frame, text="START WATCHING", command=self.start_watching,
                                  bg="#28a745", fg="white", font=("Arial", 12, "bold"), padx=20, pady=5)
        self.start_btn.pack(side=tk.LEFT, padx=10)
        
        self.stop_btn = tk.Button(input_frame, text="STOP", command=self.stop_watching,
                                 bg="#dc3545", fg="white", font=("Arial", 12, "bold"), padx=20, pady=5, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        
        # Game CSV selection (radio buttons)
        game_csv_frame = tk.Frame(input_frame, bg="#0d1b2a")
        game_csv_frame.pack(side=tk.LEFT, padx=10)
        
        tk.Label(game_csv_frame, text="Write to:", bg="#0d1b2a", fg="#ffd700", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=(10,5))
        
        self.selected_game = tk.StringVar(value="1")
        
        self.game1_btn = tk.Radiobutton(game_csv_frame, text="Game 1", variable=self.selected_game, value="1",
                                        bg="#0d1b2a", fg="white", font=("Arial", 10), selectcolor="#1e3a5f",
                                        activebackground="#0d1b2a", padx=10)
        self.game1_btn.pack(side=tk.LEFT, padx=2)
        
        self.game2_btn = tk.Radiobutton(game_csv_frame, text="Game 2", variable=self.selected_game, value="2",
                                        bg="#0d1b2a", fg="white", font=("Arial", 10), selectcolor="#1e3a5f",
                                        activebackground="#0d1b2a", padx=10)
        self.game2_btn.pack(side=tk.LEFT, padx=2)
        
        self.game3_btn = tk.Radiobutton(game_csv_frame, text="Game 3", variable=self.selected_game, value="3",
                                        bg="#0d1b2a", fg="white", font=("Arial", 10), selectcolor="#1e3a5f",
                                        activebackground="#0d1b2a", padx=10)
        self.game3_btn.pack(side=tk.LEFT, padx=2)

        # Read CSV button
        self.read_csv_btn = tk.Button(input_frame, text="📖 READ CSV", command=self.read_csv_data,
                                      bg="#17a2b8", fg="white", font=("Arial", 11, "bold"), padx=15, pady=5)
        self.read_csv_btn.pack(side=tk.LEFT, padx=10)
        
        # Status
        self.status = tk.Label(input_frame, text="Ready - Click START or use CSV files", bg="#0d1b2a", fg="#888", font=("Arial", 11))
        self.status.pack(side=tk.LEFT, padx=20)
        
        # Tab styling
        style = ttk.Style()
        style.theme_use('default')
        style.configure('TNotebook', background='#0d1b2a')
        style.configure('TNotebook.Tab', background='#1e3a5f', foreground='white', 
                      font=('Arial', 14, 'bold'), padding=[20, 10])
        style.map('TNotebook.Tab', background=[('selected', '#ffd700')], 
                 foreground=[('selected', '#0d1b2a')])
        
        # Main tabs - BIG AND BEAUTIFUL
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Tab 1: SCOREBOARD
        self.score_tab = tk.Frame(self.notebook, bg="#0d1b2a")
        self.notebook.add(self.score_tab, text="🏀 SCOREBOARD")
        self.setup_scoreboard()
        
        # Tab 2: BOX SCORE
        self.box_tab = tk.Frame(self.notebook, bg="#0d1b2a")
        self.notebook.add(self.box_tab, text="📊 BOX SCORE")
        self.setup_boxscore()
        
        # Tab 3: PLAY-BY-PLAY
        self.pbp_tab = tk.Frame(self.notebook, bg="#0d1b2a")
        self.notebook.add(self.pbp_tab, text="📈 PLAY-BY-PLAY")
        self.setup_pbp()
        
        # Tab 4: PERIODS
        self.periods_tab = tk.Frame(self.notebook, bg="#0d1b2a")
        self.notebook.add(self.periods_tab, text="⏱ PERIODS")
        self.setup_periods()
        
        # Tab 5: LEADERS
        self.leaders_tab = tk.Frame(self.notebook, bg="#0d1b2a")
        self.notebook.add(self.leaders_tab, text="⭐ LEADERS")
        self.setup_leaders()
        
        # Bottom bar
        bottom = tk.Frame(self.root, bg="#1e3a5f", pady=10)
        bottom.pack(fill=tk.X, side=tk.BOTTOM)
        
        tk.Label(bottom, text="JSON:", bg="#1e3a5f", fg="#888", font=("Arial", 10)).pack(side=tk.LEFT, padx=20)
        self.json_label = tk.Label(bottom, text="data/live_full.json", bg="#1e3a5f", fg="#28a745", font=("Arial", 10))
        self.json_label.pack(side=tk.LEFT)
        
        self.last_update = tk.Label(bottom, text="", bg="#1e3a5f", fg="#666", font=("Arial", 10))
        self.last_update.pack(side=tk.RIGHT, padx=20)
        
    def setup_scoreboard(self):
        # Big score display
        score_frame = tk.Frame(self.score_tab, bg="#0d1b2a", pady=40)
        score_frame.pack(fill=tk.X, padx=20)
        
        # Home
        home_panel = tk.Frame(score_frame, bg="#1e3a5f", pady=30, padx=40)
        home_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)
        
        self.home_logo = tk.Label(home_panel, text="🏀", font=("Arial", 40), bg="#1e3a5f")
        self.home_logo.pack()
        
        self.home_name = tk.Label(home_panel, text="HOME", font=("Arial", 16, "bold"), bg="#1e3a5f", fg="white")
        self.home_name.pack()
        
        self.home_score = tk.Label(home_panel, text="0", font=("Arial", 60, "bold"), bg="#1e3a5f", fg="#ffd700")
        self.home_score.pack()
        
        # VS
        tk.Label(score_frame, text="VS", font=("Arial", 30, "bold"), bg="#0d1b2a", fg="#666").pack(side=tk.LEFT, padx=20)
        
        # Away
        away_panel = tk.Frame(score_frame, bg="#1e3a5f", pady=30, padx=40)
        away_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10)
        
        self.away_logo = tk.Label(away_panel, text="🏀", font=("Arial", 40), bg="#1e3a5f")
        self.away_logo.pack()
        
        self.away_name = tk.Label(away_panel, text="AWAY", font=("Arial", 16, "bold"), bg="#1e3a5f", fg="white")
        self.away_name.pack()
        
        self.away_score = tk.Label(away_panel, text="0", font=("Arial", 60, "bold"), bg="#1e3a5f", fg="#ffd700")
        self.away_score.pack()
        
        # Game info
        info_frame = tk.Frame(self.score_tab, bg="#0d1b2a", pady=20)
        info_frame.pack(fill=tk.X, padx=20)
        
        self.period_label = tk.Label(info_frame, text="Period: -", font=("Arial", 18), bg="#0d1b2a", fg="#888")
        self.period_label.pack(side=tk.LEFT, padx=20)
        
        self.clock_label = tk.Label(info_frame, text="Clock: -", font=("Arial", 18), bg="#0d1b2a", fg="#888")
        self.clock_label.pack(side=tk.LEFT, padx=20)
        
    def setup_boxscore(self):
        # Two columns
        left = tk.Frame(self.box_tab, bg="#0d1b2a", padx=10, pady=10)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        right = tk.Frame(self.box_tab, bg="#0d1b2a", padx=10, pady=10)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Home
        tk.Label(left, text="HOME TEAM", font=("Arial", 16, "bold"), bg="#0d1b2a", fg="#ffd700").pack(pady=5)
        
        cols = ("#", "Name", "MIN", "PTS", "REB", "AST", "STL", "BLK", "TO", "PF")
        self.home_tree = ttk.Treeview(left, columns=cols, show="headings", height=18)
        
        for col in cols:
            self.home_tree.heading(col, text=col)
            self.home_tree.column(col, width=60)
        self.home_tree.column("Name", width=150)
        self.home_tree.pack(fill=tk.BOTH, expand=True)
        
        # Away
        tk.Label(right, text="AWAY TEAM", font=("Arial", 16, "bold"), bg="#0d1b2a", fg="#ffd700").pack(pady=5)
        
        self.away_tree = ttk.Treeview(right, columns=cols, show="headings", height=18)
        
        for col in cols:
            self.away_tree.heading(col, text=col)
            self.away_tree.column(col, width=60)
        self.away_tree.column("Name", width=150)
        self.away_tree.pack(fill=tk.BOTH, expand=True)
        
    def setup_pbp(self):
        cols = ("Q", "Clock", "Team", "Player", "Event", "Pts", "Score")
        self.pbp_tree = ttk.Treeview(self.pbp_tab, columns=cols, show="headings", height=25)
        
        for col in cols:
            self.pbp_tree.heading(col, text=col)
            self.pbp_tree.column(col, width=80)
        self.pbp_tree.column("Player", width=180)
        self.pbp_tree.column("Event", width=120)
        
        self.pbp_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
    def setup_periods(self):
        # Quarter scores
        quarter_frame = tk.Frame(self.periods_tab, bg="#0d1b2a", pady=20)
        quarter_frame.pack(fill=tk.X, padx=20)
        
        tk.Label(quarter_frame, text="QUARTER BY QUARTER", font=("Arial", 18, "bold"), bg="#0d1b2a", fg="#ffd700").pack()
        
        cols = ("Quarter", "Home", "Away", "Total")
        self.periods_tree = ttk.Treeview(quarter_frame, columns=cols, show="headings", height=10)
        
        for col in cols:
            self.periods_tree.heading(col, text=col)
            self.periods_tree.column(col, width=200, anchor="center")
        self.periods_tree.pack(pady=20)
        
        # Totals
        totals_frame = tk.Frame(self.periods_tab, bg="#0d1b2a", pady=20)
        totals_frame.pack(fill=tk.X, padx=20)
        
        tk.Label(totals_frame, text="FINAL SCORE", font=("Arial", 18, "bold"), bg="#0d1b2a", fg="#ffd700").pack()
        
        self.final_score = tk.Label(totals_frame, text="0 - 0", font=("Arial", 40, "bold"), bg="#0d1b2a", fg="#ffd700")
        self.final_score.pack(pady=10)
        
    def setup_leaders(self):
        cols = ("Stat", "Player", "Value")
        self.leaders_tree = ttk.Treeview(self.leaders_tab, columns=cols, show="headings", height=25)
        
        for col in cols:
            self.leaders_tree.heading(col, text=col)
            self.leaders_tree.column(col, width=250, anchor="center")
        
        self.leaders_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
    def start_watching(self):
        url = self.url_entry.get().strip()
        if not url:
            return
        
        # Extract game ID and build base URL
        import re
        match = re.search(r'/u/BBF/(\d+)', url)
        game_id = match.group(1) if match else "unknown"
        base_url = f"https://fibalivestats.dcd.shared.geniussports.com/u/BBF/{game_id}"
        
        # Get poll interval
        try:
            self.poll_interval = float(self.poll_entry.get())
        except:
            self.poll_interval = 0.5
        
        self.is_watching = True
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.status.config(text="Watching...", fg="#28a745")
        
        self.watch_thread = threading.Thread(target=self.watch_loop, args=(base_url,), daemon=False)
        self.watch_thread.start()
        
    def stop_watching(self):
        self.is_watching = False
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.status.config(text="Stopped", fg="#dc3545")
        
    def watch_loop(self, base_url):
        pages = {
            'index': f"{base_url}/index.html",
            'boxscore': f"{base_url}/bs.html",
            'boxscore_url': f"{base_url}/bs.html",
            'playbyplay': f"{base_url}/pbp.html",
            'periods': f"{base_url}/p.html",
            'leaders': f"{base_url}/lds.html"
        }
        
        while self.is_watching:
            try:
                self.status.config(text="Fetching...", fg="#ffc107")
                
                result = {'pages': {}, 'fetched_at': datetime.now().isoformat()}
                
                # Fetch index
                html = self.fetch_page(pages['index'])
                if html:
                    result['pages']['index'] = self.parse_index(html)
                
                # Fetch boxscore
                html = self.fetch_page(pages['boxscore'])
                if html:
                    result['pages']['boxscore'] = self.parse_boxscore(html)
                
                # Fetch pbp
                html = self.fetch_page(pages['playbyplay'])
                if html:
                    result['pages']['playbyplay'] = self.parse_pbp(html)
                
                # Fetch periods
                html = self.fetch_page(pages['periods'])
                if html:
                    result['pages']['periods'] = self.parse_periods(html)
                
                # Fetch leaders
                html = self.fetch_page(pages['leaders'])
                if html:
                    result['pages']['leaders'] = self.parse_leaders(html)
                
                # Save JSON
                json_file = "data/live_full.json"
                os.makedirs("data", exist_ok=True)
                with open(json_file, "w") as f:
                    json.dump(result, f, indent=2)
                
                # Write to CSV
                game_num = self.selected_game.get()
                self.write_game_csv(result, game_num)
                
                self.json_label.config(text=json_file)
                
                # Update UI
                self.root.after(0, lambda: self.update_ui(result))
                
                self.status.config(text=f"Live! ({result.get('pages', {}).get('playbyplay', {}).get('total_events', 0)} events)", fg="#28a745")
                
            except Exception as e:
                self.status.config(text=f"Error: {str(e)}", fg="#dc3545")
            
            time.sleep(self.poll_interval)
    
    def open_csv_files(self):
        import os
        import webbrowser
        base = os.path.dirname(os.path.abspath(__file__))
        webbrowser.open(f"file://{base}/scoreboard.csv")
        webbrowser.open(f"file://{base}/home_box.csv")
        webbrowser.open(f"file://{base}/away_box.csv")
    
    def open_game_csv(self, game_num):
        import os
        import subprocess
        base = os.path.dirname(os.path.abspath(__file__))
        game_folder = os.path.join(base, "Game CSV")
        
        if os.path.exists(game_folder):
            subprocess.Popen(["explorer", game_folder])
            self.status.config(text=f"Opened Game CSV folder", fg="#28a745")
        else:
            self.status.config(text="Game CSV folder not found", fg="red")
    
    def write_game_csv(self, result, game_num):
        import csv
        import os
        import re
        from bs4 import BeautifulSoup
        
        base_dir = os.path.dirname(os.path.abspath(__file__))
        game_csv_dir = os.path.join(base_dir, "Game CSV")
        os.makedirs(game_csv_dir, exist_ok=True)
        
        filename = os.path.join(game_csv_dir, f"Game {game_num}.csv")
        
        pages = result.get('pages', {})
        index_data = pages.get('index', {})
        
        home = index_data.get('home', 'HOME')
        away = index_data.get('away', 'AWAY')
        h_score = index_data.get('h_score', '0')
        a_score = index_data.get('a_score', '0')
        period = index_data.get('period', '')
        clock = index_data.get('clock', '')
        
        bs_html = self.fetch_page(pages.get('boxscore_url', ''))
        lds_html = self.fetch_page(pages.get('leaders', ''))
        
        def get_stat_value(elem):
            if not elem:
                return ""
            text = elem.get_text(strip=True)
            if text:
                return text
            for c in elem.get('class', []):
                if c.startswith('aj_') and len(c) > 2:
                    val = c[3:]
                    if val.replace(':', '').replace('-', '').isdigit():
                        return val
            return ""
        
        def get_player_stats(row, team_num):
            name_elem = row.find('span', id=re.compile(rf'aj_{team_num}_\d+_name'))
            if not name_elem or not name_elem.text.strip():
                return None
            player_id_match = re.search(rf'aj_{team_num}_(\d+)_', str(row))
            if not player_id_match:
                return None
            pid = player_id_match.group(1)
            
            return {
                'num': get_stat_value(row.find('span', id=f'aj_{team_num}_{pid}_shirtNumber')),
                'name': name_elem.text.strip(),
                'pos': get_stat_value(row.find('span', id=f'aj_{team_num}_{pid}_playingPosition')),
                'mins': get_stat_value(row.find('span', id=f'aj_{team_num}_{pid}_sMinutes')),
                'pts': get_stat_value(row.find('span', id=f'aj_{team_num}_{pid}_sPoints')),
                'fg': get_stat_value(row.find('span', id=f'aj_{team_num}_{pid}_sFieldGoalsMade')) + '-' + get_stat_value(row.find('span', id=f'aj_{team_num}_{pid}_sFieldGoalsAttempted')),
                'fg_pct': get_stat_value(row.find('span', id=f'aj_{team_num}_{pid}_sFieldGoalsPercentage')),
                'two_p': get_stat_value(row.find('span', id=f'aj_{team_num}_{pid}_sTwoPointersMade')) + '-' + get_stat_value(row.find('span', id=f'aj_{team_num}_{pid}_sTwoPointersAttempted')),
                'two_p_pct': get_stat_value(row.find('span', id=f'aj_{team_num}_{pid}_sTwoPointersPercentage')),
                'three_p': get_stat_value(row.find('span', id=f'aj_{team_num}_{pid}_sThreePointersMade')) + '-' + get_stat_value(row.find('span', id=f'aj_{team_num}_{pid}_sThreePointersAttempted')),
                'three_p_pct': get_stat_value(row.find('span', id=f'aj_{team_num}_{pid}_sThreePointersPercentage')),
                'ft': get_stat_value(row.find('span', id=f'aj_{team_num}_{pid}_sFreeThrowsMade')) + '-' + get_stat_value(row.find('span', id=f'aj_{team_num}_{pid}_sFreeThrowsAttempted')),
                'ft_pct': get_stat_value(row.find('span', id=f'aj_{team_num}_{pid}_sFreeThrowsPercentage')),
                'off': get_stat_value(row.find('span', id=f'aj_{team_num}_{pid}_sReboundsOffensive')),
                'def': get_stat_value(row.find('span', id=f'aj_{team_num}_{pid}_sReboundsDefensive')),
                'reb': get_stat_value(row.find('span', id=f'aj_{team_num}_{pid}_sReboundsTotal')),
                'ast': get_stat_value(row.find('span', id=f'aj_{team_num}_{pid}_sAssists')),
                'to': get_stat_value(row.find('span', id=f'aj_{team_num}_{pid}_sTurnovers')),
                'stl': get_stat_value(row.find('span', id=f'aj_{team_num}_{pid}_sSteals')),
                'blk': get_stat_value(row.find('span', id=f'aj_{team_num}_{pid}_sBlocks')),
                'blkr': get_stat_value(row.find('span', id=f'aj_{team_num}_{pid}_sBlocksReceived')),
                'pf': get_stat_value(row.find('span', id=f'aj_{team_num}_{pid}_sFoulsPersonal')),
                'fld_on': get_stat_value(row.find('span', id=f'aj_{team_num}_{pid}_sFoulsOn')),
                'plus_minus': get_stat_value(row.find('span', id=f'aj_{team_num}_{pid}_sPlusMinusPoints')),
                'eff': get_stat_value(row.find('span', id=f'aj_{team_num}_{pid}_eff_1'))
            }
        
        home_players = []
        away_players = []
        
        if bs_html:
            soup = BeautifulSoup(bs_html, 'html.parser')
            for row in soup.select('tbody.team-0-person-container tr.player-row, tbody.bench tr.player-row'):
                if 'row-not-used' in row.get('class', []): 
                    continue
                player = get_player_stats(row, 1)
                if player:
                    home_players.append(player)
            
            for row in soup.select('tbody.team-1-person-container tr.player-row, tbody.bench tr.player-row'):
                if 'row-not-used' in row.get('class', []): 
                    continue
                player = get_player_stats(row, 2)
                if player:
                    away_players.append(player)
        
        home_leaders = sorted([p for p in home_players if p.get('pts', '')], key=lambda x: int(x['pts']) if x.get('pts', '').isdigit() else 0, reverse=True)[:5]
        away_leaders = sorted([p for p in away_players if p.get('pts', '')], key=lambda x: int(x['pts']) if x.get('pts', '').isdigit() else 0, reverse=True)[:5]
        
        home_pts_leaders = []
        away_pts_leaders = []
        home_reb_leaders = []
        away_reb_leaders = []
        home_ast_leaders = []
        away_ast_leaders = []
        
        if lds_html:
            lds_soup = BeautifulSoup(lds_html, 'html.parser')
            
            def get_lds_leaders(prefix, stat):
                leaders = []
                for rank in range(1, 6):
                    name_elem = lds_soup.find('span', {'class': f'id_{prefix}_{stat}_{rank}_name'})
                    num_elem = lds_soup.find('span', {'class': f'id_{prefix}_{stat}_{rank}_shirtNumber'})
                    tot_elem = lds_soup.find('span', {'class': f'id_{prefix}_{stat}_{rank}_tot'})
                    if name_elem:
                        leaders.append({
                            'name': name_elem.get_text(strip=True),
                            'num': num_elem.get_text(strip=True) if num_elem else "",
                            'val': tot_elem.get_text(strip=True) if tot_elem else ""
                        })
                return leaders
            
            home_pts_leaders = get_lds_leaders('aj_1', 'sPoints')
            away_pts_leaders = get_lds_leaders('aj_2', 'sPoints')
            home_reb_leaders = get_lds_leaders('aj_1', 'sReboundsTotal')
            away_reb_leaders = get_lds_leaders('aj_2', 'sReboundsTotal')
            home_ast_leaders = get_lds_leaders('aj_1', 'sAssists')
            away_ast_leaders = get_lds_leaders('aj_2', 'sAssists')
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            writer.writerow(['NEBL LIVE STATS - GAME ' + game_num])
            writer.writerow([])
            
            writer.writerow(['SCOREBOARD'])
            writer.writerow(['Home', home, h_score])
            writer.writerow(['Away', away, a_score])
            writer.writerow(['Period', period])
            writer.writerow(['Clock', clock])
            writer.writerow([])
            
            writer.writerow([home + ' - BOX SCORE'])
            writer.writerow(['No.', 'Player', 'POS', 'Mins', 'Pts', 'FG', 'FG%', '2P', '2P%', '3P', '3P%', 'FT', 'FT%', 'OFF', 'DEF', 'REB', 'AST', 'TO', 'STL', 'BLK', 'BLKR', 'PF', 'Fls on', '+/-', 'Index'])
            for p in home_players:
                writer.writerow([
                    p['num'], p['name'], p['pos'], p['mins'], p['pts'], 
                    p['fg'], p['fg_pct'], p['two_p'], p['two_p_pct'], 
                    p['three_p'], p['three_p_pct'], p['ft'], p['ft_pct'],
                    p['off'], p['def'], p['reb'], p['ast'], p['to'],
                    p['stl'], p['blk'], p['blkr'], p['pf'], p['fld_on'],
                    p['plus_minus'], p['eff']
                ])
            writer.writerow([])
            
            writer.writerow([away + ' - BOX SCORE'])
            writer.writerow(['No.', 'Player', 'POS', 'Mins', 'Pts', 'FG', 'FG%', '2P', '2P%', '3P', '3P%', 'FT', 'FT%', 'OFF', 'DEF', 'REB', 'AST', 'TO', 'STL', 'BLK', 'BLKR', 'PF', 'Fls on', '+/-', 'Index'])
            for p in away_players:
                writer.writerow([
                    p['num'], p['name'], p['pos'], p['mins'], p['pts'], 
                    p['fg'], p['fg_pct'], p['two_p'], p['two_p_pct'], 
                    p['three_p'], p['three_p_pct'], p['ft'], p['ft_pct'],
                    p['off'], p['def'], p['reb'], p['ast'], p['to'],
                    p['stl'], p['blk'], p['blkr'], p['pf'], p['fld_on'],
                    p['plus_minus'], p['eff']
                ])
            writer.writerow([])
            
            writer.writerow([home + ' LEADERS'])
            writer.writerow(['#', 'Name', 'PTS', 'REB', 'AST'])
            for p in home_leaders:
                writer.writerow([p['num'], p['name'], p['pts'], p['reb'], p['ast']])
            writer.writerow([])
            
            writer.writerow([away + ' LEADERS'])
            writer.writerow(['#', 'Name', 'PTS', 'REB', 'AST'])
            for p in away_leaders:
                writer.writerow([p['num'], p['name'], p['pts'], p['reb'], p['ast']])
            writer.writerow([])
            writer.writerow([away + ' LEADERS'])
            writer.writerow(['#', 'Name', 'PTS', 'REB', 'AST'])
            for p in away_leaders[:5]:
                writer.writerow([p.get('num', ''), p.get('name', ''), p.get('pts', ''), 
                               p.get('reb', ''), p.get('ast', '')])
    
    def read_csv_data(self):
        import csv
        import os
        import subprocess
        
        base_dir = os.path.dirname(os.path.abspath(__file__))
        game_num = self.selected_game.get()
        csv_file = os.path.join(base_dir, "Game CSV", f"Game {game_num}.csv")
        
        if os.path.exists(csv_file):
            subprocess.Popen(["start", "", csv_file], shell=True)
            self.status.config(text=f"Opened Game {game_num}.csv", fg="#28a745")
        else:
            self.status.config(text=f"Game {game_num}.csv not found - start fetching first", fg="orange")
    
    def open_sheets(self):
        import webbrowser
        webbrowser.open("https://docs.google.com/spreadsheets/d/1B5y_9uVwHfC_9Gw1sKC6YJesaOG_xe3ACWPJTra8K14/edit")
        
    def fetch_page(self, url):
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(user_agent='Mozilla/5.0')
                page = context.new_page()
                page.goto(url, wait_until="networkidle", timeout=60000)
                page.wait_for_timeout(1000)
                html = page.content()
                browser.close()
                return html
        except:
            return ""
    
    def parse_index(self, html):
        soup = BeautifulSoup(html, 'html.parser')
        data = {'teams': {'home': None, 'away': None}, 'score': {'home': 0, 'away': 0}, 'period': None, 'clock': None}
        
        home_img = soup.find('img', class_='logo home-logo')
        away_img = soup.find('img', class_='logo away-logo')
        
        if home_img and home_img.get('alt'):
            data['teams']['home'] = home_img.get('alt')
        if away_img and away_img.get('alt'):
            data['teams']['away'] = away_img.get('alt')
        
        for elem in soup.find_all('span', class_='pbpsc'):
            m = re.search(r'(\d+)\s*-\s*(\d+)', elem.get_text())
            if m:
                data['score']['home'] = int(m.group(1))
                data['score']['away'] = int(m.group(2))
        
        for elem in soup.find_all('span', class_='pbp-period'):
            m = re.search(r'P(\d+)', elem.get_text())
            if m:
                data['period'] = int(m.group(1))
        
        for elem in soup.find_all('div', class_='pbp-time'):
            m = re.search(r'(\d{1,2}:\d{2})', elem.get_text())
            if m:
                data['clock'] = m.group(1)
        
        return data
    
    def parse_boxscore(self, html):
        """Parse box score using ID-based extraction"""
        soup = BeautifulSoup(html, 'html.parser')
        data = {'home_players': [], 'away_players': [], 'home_totals': {}, 'away_totals': {}}
        
        for team_num, key in [(1, 'home_players'), (2, 'away_players')]:
            rows = soup.find_all('tr', id=re.compile(f'^aj_{team_num}_\\d+_row$'))
            for row in rows:
                classes = row.get('class', [])
                if isinstance(classes, str):
                    classes = classes.split()
                if 'row-not-used' in classes:
                    continue
                
                player = {'num': '', 'name': '', 'pos': '', 'is_starter': False}
                
                num_span = row.find('span', id=re.compile(f'^aj_{team_num}_\\d+_shirtNumber$'))
                if num_span:
                    player['num'] = num_span.get_text(strip=True) or self._get_class_value(num_span)
                
                name_span = row.find('span', id=re.compile(f'^aj_{team_num}_\\d+_name$'))
                if name_span:
                    player['name'] = name_span.get_text(strip=True) or self._get_class_value(name_span)
                
                pos_span = row.find('span', id=re.compile(f'^aj_{team_num}_\\d+_playingPosition$'))
                if pos_span:
                    player['pos'] = pos_span.get_text(strip=True) or self._get_class_value(pos_span)
                
                if isinstance(classes, str):
                    classes = classes.split()
                if 'p_starter' in classes:
                    player['is_starter'] = True
                
                stat_ids = {
                    'min': f'aj_{team_num}_\\d+_sMinutes',
                    'pts': f'aj_{team_num}_\\d+_sPoints',
                    'fgm': f'aj_{team_num}_\\d+_sFieldGoalsMade',
                    'fga': f'aj_{team_num}_\\d+_sFieldGoalsAttempted',
                    'fg_pct': f'aj_{team_num}_\\d+_sFieldGoalsPercentage',
                    '3pm': f'aj_{team_num}_\\d+_sThreePointersMade',
                    '3pa': f'aj_{team_num}_\\d+_sThreePointersAttempted',
                    '3p_pct': f'aj_{team_num}_\\d+_sThreePointersPercentage',
                    'ftm': f'aj_{team_num}_\\d+_sFreeThrowsMade',
                    'fta': f'aj_{team_num}_\\d+_sFreeThrowsAttempted',
                    'ft_pct': f'aj_{team_num}_\\d+_sFreeThrowsPercentage',
                    'reb': f'aj_{team_num}_\\d+_sReboundsTotal',
                    'ast': f'aj_{team_num}_\\d+_sAssists',
                    'stl': f'aj_{team_num}_\\d+_sSteals',
                    'blk': f'aj_{team_num}_\\d+_sBlocks',
                    'to': f'aj_{team_num}_\\d+_sTurnovers',
                    'pf': f'aj_{team_num}_\\d+_sFoulsPersonal',
                }
                
                for stat, pattern in stat_ids.items():
                    span = row.find('span', id=re.compile(pattern))
                    if span:
                        player[stat] = span.get_text(strip=True) or self._get_class_value(span)
                
                if player.get('name'):
                    data[key].append(player)
        
        return data
    
    def _get_class_value(self, span):
        """Get value from span class attribute"""
        if not span:
            return ''
        cls = span.get('class', [])
        for c in cls:
            if c.startswith('aj_'):
                val = c[3:]
                if val:
                    return val
        return ''
    
    def parse_pbp(self, html):
        soup = BeautifulSoup(html, 'html.parser')
        events = []
        rows = soup.find_all('div', class_='pbpa')
        
        home_score = 0
        away_score = 0
        
        for row in rows:
            team = None
            for cls in row.get('class', []):
                if cls.startswith('pbp-team'):
                    team = 'home' if cls == 'pbp-team1' else 'away' if cls == 'pbp-team2' else None
                    break
            
            period = None
            for elem in row.find_all('span', class_='pbp-period'):
                m = re.search(r'P(\d+)', elem.get_text())
                if m: period = int(m.group(1))
            
            clock = None
            for elem in row.find_all('div', class_='pbp-time'):
                m = re.search(r'(\d{1,2}:\d{2})', elem.get_text())
                if m: clock = m.group(1)
            
            for elem in row.find_all('span', class_='pbpsc'):
                m = re.search(r'(\d+)\s*-\s*(\d+)', elem.get_text())
                if m:
                    home_score = int(m.group(1))
                    away_score = int(m.group(2))
            
            player = None
            for elem in row.find_all('div', class_='pbp-action'):
                m = re.search(r'<strong>\d+,\s*([^<]+)</strong>', str(elem))
                if m: player = m.group(1).strip()
            
            event_type = "unknown"
            pts = None
            for elem in row.find_all('div', class_='pbp-action'):
                text = elem.get_text().lower()
                if 'made' in text:
                    event_type = "score"
                    if '3pt' in text: pts = 3
                    elif '2pt' in text: pts = 2
                    elif 'free throw' in text: pts = 1
                elif 'rebound' in text: event_type = "rebound"
                elif 'assist' in text: event_type = "assist"
                elif 'foul' in text: event_type = "foul"
                elif 'turnover' in text: event_type = "turnover"
                elif 'steal' in text: event_type = "steal"
                elif 'block' in text: event_type = "block"
            
            events.append({
                'period': period, 'clock': clock, 'team': team, 'player': player,
                'event': event_type, 'points': pts,
                'home_score': home_score, 'away_score': away_score
            })
        
        return {'events': events, 'total_events': len(events)}
    
    def parse_periods(self, html):
        soup = BeautifulSoup(html, 'html.parser')
        data = {'quarters': [], 'totals': {'home': 0, 'away': 0}}
        
        for elem in soup.find_all('span', class_='pbpsc'):
            m = re.search(r'(\d+)\s*-\s*(\d+)', elem.get_text())
            if m:
                data['totals']['home'] = int(m.group(1))
                data['totals']['away'] = int(m.group(2))
        
        return data
    
    def parse_leaders(self, html):
        soup = BeautifulSoup(html, 'html.parser')
        data = {'leaders': []}
        
        for row in soup.find_all('tr'):
            cells = [c.get_text(strip=True) for c in row.find_all(['td', 'th'])]
            if len(cells) >= 3:
                data['leaders'].append({'rank': cells[0], 'player': cells[1], 'value': cells[2]})
        
        return data
    
    def update_ui(self, data):
        pages = data.get('pages', {})
        
        # Scoreboard
        if 'index' in pages:
            idx = pages['index']
            self.home_name.config(text=idx.get('teams', {}).get('home', 'HOME'))
            self.away_name.config(text=idx.get('teams', {}).get('away', 'AWAY'))
            self.home_score.config(text=str(idx.get('score', {}).get('home', 0)))
            self.away_score.config(text=str(idx.get('score', {}).get('away', 0)))
            self.period_label.config(text=f"Period: {idx.get('period', '-')}")
            self.clock_label.config(text=f"Clock: {idx.get('clock', '-')}")
        
        # Box Score
        if 'boxscore' in pages:
            bs = pages['boxscore']
            
            for item in self.home_tree.get_children():
                self.home_tree.delete(item)
            for p in bs.get('home_players', [])[:15]:
                self.home_tree.insert("", tk.END, values=(
                    p.get('num', ''), p.get('name', '')[:20], p.get('min', ''),
                    p.get('pts', ''), p.get('reb', ''), p.get('ast', ''),
                    p.get('stl', ''), p.get('blk', ''), p.get('to', ''), p.get('pf', '')
                ))
            
            for item in self.away_tree.get_children():
                self.away_tree.delete(item)
            for p in bs.get('away_players', [])[:15]:
                self.away_tree.insert("", tk.END, values=(
                    p.get('num', ''), p.get('name', '')[:20], p.get('min', ''),
                    p.get('pts', ''), p.get('reb', ''), p.get('ast', ''),
                    p.get('stl', ''), p.get('blk', ''), p.get('to', ''), p.get('pf', '')
                ))
        
        # PBP
        if 'playbyplay' in pages:
            pbp = pages['playbyplay']
            
            for item in self.pbp_tree.get_children():
                self.pbp_tree.delete(item)
            
            events = pbp.get('events', [])[-50:][::-1]
            for e in events:
                self.pbp_tree.insert("", tk.END, values=(
                    e.get('period', '-'), e.get('clock', '-') or '-', e.get('team', '-') or '-',
                    (e.get('player') or '-')[:25], e.get('event', '-'), e.get('points', ''),
                    f"{e.get('home_score', 0)}-{e.get('away_score', 0)}"
                ))
        
        # Periods
        if 'periods' in pages:
            per = pages['periods']
            
            for item in self.periods_tree.get_children():
                self.periods_tree.delete(item)
            
            for i, q in enumerate(per.get('quarters', [])):
                self.periods_tree.insert("", tk.END, values=(
                    f"Q{i+1}", q.get('home', 0), q.get('away', 0),
                    f"{q.get('home', 0) + q.get('away', 0)}"
                ))
            
            totals = per.get('totals', {})
            self.final_score.config(text=f"{totals.get('home', 0)} - {totals.get('away', 0)}")
        
        # Leaders
        if 'leaders' in pages:
            leaders = pages['leaders']
            
            for item in self.leaders_tree.get_children():
                self.leaders_tree.delete(item)
            
            # Use overall_leaders if available, otherwise fall back to categories
            overall = leaders.get('overall_leaders', {})
            
            if overall:
                # Show top 5 for each stat category
                for stat in ['Points', 'Assists', 'Total Rebounds', 'Steals']:
                    if stat in overall:
                        for i, p in enumerate(overall[stat], 1):
                            self.leaders_tree.insert("", tk.END, values=(
                                f"{stat} #{i}", p.get('player', ''), f"{p.get('value', 0)} ({p.get('team', '')})"
                            ))
            elif 'categories' in leaders:
                # Fall back to categories format
                for stat, players in leaders.get('categories', {}).items():
                    for p in players[:5]:
                        self.leaders_tree.insert("", tk.END, values=(
                            stat, p.get('player', ''), p.get('value', '')
                        ))
        
        self.last_update.config(text=f"Updated: {data.get('fetched_at', '')}")

    def write_to_sheets(self):
        """Write current data to Google Sheets"""
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
            
            # Load credentials
            creds_file = os.environ.get('GOOGLE_CREDS_FILE', 'credentials.json')
            if not os.path.exists(creds_file):
                self.status.config(text="No credentials.json file!", fg="red")
                return
            
            credentials = service_account.Credentials.from_service_account_file(
                creds_file, scopes=['https://www.googleapis.com/auth/spreadsheets']
            )
            service = build('sheets', 'v4', credentials=credentials)
            
            # Get data from current display
            sb = self.score_data
            if not sb:
                self.status.config(text="No data to write!", fg="red")
                return
            
            spreadsheet_id = "1B5y_9uVwHfC_9Gw1sKC6YJesaOG_xe3ACWPJTra8K14"
            
            # Scoreboard
            sb_values = [
                ['NEBL LIVE STATS'],
                [sb.get('teams', {}).get('home', 'Home'), sb.get('score', {}).get('home', 0)],
                [sb.get('teams', {}).get('away', 'Away'), sb.get('score', {}).get('away', 0)],
                ['Period', sb.get('period', '')],
                ['Clock', sb.get('clock', '')]
            ]
            
            # Home players
            home_vals = [['#', 'Name', 'POS', 'PTS', 'REB', 'AST']]
            for p in self.home_players:
                home_vals.append([p.get('num',''), p.get('name',''), p.get('pos',''), 
                                p.get('pts',''), p.get('reb',''), p.get('ast','')])
            
            # Away players
            away_vals = [['#', 'Name', 'POS', 'PTS', 'REB', 'AST']]
            for p in self.away_players:
                away_vals.append([p.get('num',''), p.get('name',''), p.get('pos',''),
                                p.get('pts',''), p.get('reb',''), p.get('ast','')])
            
            # Write to sheets
            for name, vals in [('Scoreboard', sb_values), ('Home', home_vals), ('Away', away_vals)]:
                service.spreadsheets().values().update(
                    spreadsheetId=spreadsheet_id, range=f"{name}!A1",
                    valueInputOption='USER_ENTERED', body={'values': vals}
                ).execute()
            
            self.status.config(text="Written to Google Sheets!", fg="#28a745")
        except Exception as e:
            self.status.config(text=f"Sheet error: {str(e)}", fg="red")

def main():
    try:
        print("Starting NEBL Live Stats...")
        root = tk.Tk()
        print("Tk window created")
        app = NEBLStatsApp(root)
        print("App initialized")
        
        # Start fresh - no old data loaded
        
        print("Starting mainloop...")
        root.mainloop()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        input("Press Enter to exit...")

if __name__ == "__main__":
    main()
