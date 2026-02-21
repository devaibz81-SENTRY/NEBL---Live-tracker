#!/usr/bin/env python3
"""
NEBL Live Stats - All Pages Version
Shows: Index, Box Score, Leaders, Play-by-Play, Scoreboard, Periods
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import json
import os
import time
from datetime import datetime
import re
from bs4 import BeautifulSoup

try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except Exception:
    HAS_PLAYWRIGHT = False

class NEBLStatsApp:
    def __init__(self, root):
        self.root = root
        self.root.title("NEBL Live Stats - All Pages")
        self.root.geometry("1400x800")
        self.root.configure(bg="#1a1a2e")
        
        self.is_watching = False
        self.watch_thread = None
        
        self.setup_ui()
        
    def setup_ui(self):
        # Header
        header = tk.Frame(self.root, bg="#043f8f", height=60)
        header.pack(fill=tk.X)
        tk.Label(header, text="NEBL Live Stats - All Pages", font=("Arial", 18, "bold"), 
                bg="#043f8f", fg="white").pack(pady=15)
        
        # URL Input
        input_frame = tk.Frame(self.root, bg="#1a1a2e", pady=10)
        input_frame.pack(fill=tk.X, padx=20)
        
        tk.Label(input_frame, text="Game URL:", bg="#1a1a2e", fg="white", font=("Arial", 11)).pack(side=tk.LEFT)
        
        self.url_entry = tk.Entry(input_frame, font=("Arial", 11), width=70)
        self.url_entry.pack(side=tk.LEFT, padx=10)
        self.url_entry.insert(0, "https://fibalivestats.dcd.shared.geniussports.com/u/BBF/2799694/")
        
        self.start_btn = tk.Button(input_frame, text="START", command=self.start_watching,
                                  bg="#28a745", fg="white", font=("Arial", 11, "bold"), padx=20)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        
        self.stop_btn = tk.Button(input_frame, text="STOP", command=self.stop_watching,
                                 bg="#dc3545", fg="white", font=("Arial", 11, "bold"), padx=20, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        
        self.status = tk.Label(input_frame, text="Ready", bg="#1a1a2e", fg="#888", font=("Arial", 10))
        self.status.pack(side=tk.LEFT, padx=20)
        
        # Tabbed interface for different pages
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Tab 1: Scoreboard
        self.score_tab = tk.Frame(self.notebook, bg="#16213e")
        self.notebook.add(self.score_tab, text="Scoreboard")
        self.setup_scoreboard_tab()
        
        # Tab 2: Box Score
        self.box_tab = tk.Frame(self.notebook, bg="#16213e")
        self.notebook.add(self.box_tab, text="Box Score")
        self.setup_boxscore_tab()
        
        # Tab 3: Play-by-Play
        self.pbp_tab = tk.Frame(self.notebook, bg="#16213e")
        self.notebook.add(self.pbp_tab, text="Play-by-Play")
        self.setup_pbp_tab()
        
        # Tab 4: Leaders
        self.leaders_tab = tk.Frame(self.notebook, bg="#16213e")
        self.notebook.add(self.leaders_tab, text="Leaders")
        self.setup_leaders_tab()
        
        # Tab 5: Periods
        self.periods_tab = tk.Frame(self.notebook, bg="#16213e")
        self.notebook.add(self.periods_tab, text="Periods")
        self.setup_periods_tab()
        
        # Bottom - JSON path
        bottom = tk.Frame(self.root, bg="#1a1a2e", pady=5)
        bottom.pack(fill=tk.X, padx=20)
        
        tk.Label(bottom, text="JSON:", bg="#1a1a2e", fg="#888", font=("Arial", 9)).pack(side=tk.LEFT)
        self.json_path = tk.Label(bottom, text="data/all_pages.json", bg="#1a1a2e", fg="#28a745", font=("Arial", 9))
        self.json_path.pack(side=tk.LEFT, padx=5)
        
        self.last_update = tk.Label(bottom, text="", bg="#1a1a2e", fg="#666", font=("Arial", 9))
        self.last_update.pack(side=tk.RIGHT)
        
    def setup_scoreboard_tab(self):
        # Score display
        score_frame = tk.Frame(self.score_tab, bg="#16213e", pady=30)
        score_frame.pack(fill=tk.X, padx=20)
        
        self.home_name = tk.Label(score_frame, text="Home Team", font=("Arial", 16, "bold"), bg="#16213e", fg="white")
        self.home_name.place(relx=0.2, rely=0.3, anchor=tk.CENTER)
        
        self.home_score = tk.Label(score_frame, text="0", font=("Arial", 50, "bold"), bg="#16213e", fg="#ffd700")
        self.home_score.place(relx=0.2, rely=0.7, anchor=tk.CENTER)
        
        tk.Label(score_frame, text="VS", font=("Arial", 20), bg="#16213e", fg="#666").place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        
        self.away_name = tk.Label(score_frame, text="Away Team", font=("Arial", 16, "bold"), bg="#16213e", fg="white")
        self.away_name.place(relx=0.8, rely=0.3, anchor=tk.CENTER)
        
        self.away_score = tk.Label(score_frame, text="0", font=("Arial", 50, "bold"), bg="#16213e", fg="#ffd700")
        self.away_score.place(relx=0.8, rely=0.7, anchor=tk.CENTER)
        
        # Period scores
        self.periods_label = tk.Label(self.score_tab, text="", font=("Arial", 12), bg="#16213e", fg="#888")
        self.periods_label.pack(pady=10)
        
    def setup_boxscore_tab(self):
        # Home team players
        home_frame = tk.LabelFrame(self.box_tab, text="Home Team", font=("Arial", 11, "bold"), 
                                   bg="#16213e", fg="white", padx=10, pady=10)
        home_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0,5), pady=10)
        
        cols = ("Num", "Name", "MIN", "PTS", "FG", "3P", "FT", "REB", "AST", "STL", "BLK", "TO", "PF")
        self.home_tree = ttk.Treeview(home_frame, columns=cols, show="headings", height=15)
        
        for col in cols:
            self.home_tree.heading(col, text=col)
            self.home_tree.column(col, width=50)
        self.home_tree.column("Name", width=120)
        self.home_tree.pack(fill=tk.BOTH, expand=True)
        
        # Away team players
        away_frame = tk.LabelFrame(self.box_tab, text="Away Team", font=("Arial", 11, "bold"),
                                  bg="#16213e", fg="white", padx=10, pady=10)
        away_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5,0), pady=10)
        
        self.away_tree = ttk.Treeview(away_frame, columns=cols, show="headings", height=15)
        
        for col in cols:
            self.away_tree.heading(col, text=col)
            self.away_tree.column(col, width=50)
        self.away_tree.column("Name", width=120)
        self.away_tree.pack(fill=tk.BOTH, expand=True)
        
    def setup_pbp_tab(self):
        cols = ("Q", "Time", "Team", "Player", "Event", "Pts", "Score")
        self.pbp_tree = ttk.Treeview(self.pbp_tab, columns=cols, show="headings", height=20)
        
        for col in cols:
            self.pbp_tree.heading(col, text=col)
            self.pbp_tree.column(col, width=80)
        self.pbp_tree.column("Player", width=150)
        self.pbp_tree.column("Event", width=100)
        
        self.pbp_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
    def setup_leaders_tab(self):
        cols = ("Rank", "Player", "Stat", "Value")
        self.leaders_tree = ttk.Treeview(self.leaders_tab, columns=cols, show="headings", height=20)
        
        for col in cols:
            self.leaders_tree.heading(col, text=col)
            self.leaders_tree.column(col, width=150)
        
        self.leaders_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
    def setup_periods_tab(self):
        cols = ("Period", "Home", "Away", "Total")
        self.periods_tree = ttk.Treeview(self.periods_tab, columns=cols, show="headings", height=15)
        
        for col in cols:
            self.periods_tree.heading(col, text=col)
            self.periods_tree.column(col, width=150)
        
        self.periods_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
    def start_watching(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("Warning", "Please enter a game URL")
            return
        
        # Extract game ID
        match = re.search(r'/u/BBF/(\d+)', url)
        game_id = match.group(1) if match else "unknown"
        
        # Build base URL
        base_url = f"https://fibalivestats.dcd.shared.geniussports.com/u/BBF/{game_id}"
        
        self.is_watching = True
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.url_entry.config(state=tk.DISABLED)
        self.status.config(text="Watching...", fg="#28a745")
        
        self.watch_thread = threading.Thread(target=self.watch_loop, args=(base_url, game_id), daemon=True)
        self.watch_thread.start()
        
    def stop_watching(self):
        self.is_watching = False
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.url_entry.config(state=tk.NORMAL)
        self.status.config(text="Stopped", fg="#dc3545")
        
    def watch_loop(self, base_url, game_id):
        while self.is_watching:
            try:
                self.status.config(text="Fetching all pages...", fg="#ffc107")
                data = self.fetch_all_pages(base_url, game_id)
                
                if data:
                    # Save JSON
                    json_file = "data/all_pages.json"
                    os.makedirs("data", exist_ok=True)
                    with open(json_file, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2)
                    self.json_path.config(text=json_file)
                    
                    # Update UI
                    self.root.after(0, lambda: self.update_ui(data))
                    self.status.config(text=f"Live! ({data.get('total_events', 0)} events)", fg="#28a745")
                else:
                    self.status.config(text="No data", fg="#dc3545")
                    
            except Exception as e:
                self.status.config(text=f"Error: {str(e)}", fg="#dc3545")
            
            time.sleep(1)
            
    def fetch_all_pages(self, base_url, game_id):
        if not HAS_PLAYWRIGHT:
            return None
        
        pages = {
            'index': f"{base_url}/index.html",
            'boxscore': f"{base_url}/bs.html",
            'leaders': f"{base_url}/lds.html",
            'playbyplay': f"{base_url}/pbp.html",
            'scoreboard': f"{base_url}/sc.html",
            'periods': f"{base_url}/p.html"
        }
        
        result = {
            'game_id': game_id,
            'base_url': base_url,
            'fetched_at': datetime.now().isoformat(),
            'pages': {}
        }
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(user_agent='Mozilla/5.0')
                
                for page_name, url in pages.items():
                    try:
                        page = context.new_page()
                        page.goto(url, wait_until="networkidle", timeout=60000)
                        page.wait_for_timeout(2000)
                        html = page.content()
                        page.close()
                        
                        if page_name == 'index':
                            result['pages']['index'] = self.parse_index(html)
                        elif page_name == 'boxscore':
                            result['pages']['boxscore'] = self.parse_boxscore(html)
                        elif page_name == 'leaders':
                            result['pages']['leaders'] = self.parse_leaders(html)
                        elif page_name == 'playbyplay':
                            result['pages']['playbyplay'] = self.parse_pbp(html)
                        elif page_name == 'scoreboard':
                            result['pages']['scoreboard'] = self.parse_scoreboard(html)
                        elif page_name == 'periods':
                            result['pages']['periods'] = self.parse_periods(html)
                    except:
                        pass
                
                browser.close()
        except:
            pass
        
        return result
    
    def parse_index(self, html):
        soup = BeautifulSoup(html, 'html.parser')
        data = {'teams': {}, 'score': {'home': 0, 'away': 0}, 'period': None}
        
        home_img = soup.find('img', class_='logo home-logo')
        away_img = soup.find('img', class_='logo away-logo')
        
        if home_img and home_img.get('alt'):
            data['teams']['home'] = home_img.get('alt')
        if away_img and away_img.get('alt'):
            data['teams']['away'] = away_img.get('alt')
        
        score_elems = soup.find_all('span', class_='pbpsc')
        for elem in score_elems:
            text = elem.get_text(strip=True)
            m = re.search(r'(\d+)\s*-\s*(\d+)', text)
            if m:
                data['score']['home'] = int(m.group(1))
                data['score']['away'] = int(m.group(2))
        
        return data
    
    def parse_boxscore(self, html):
        soup = BeautifulSoup(html, 'html.parser')
        data = {'home_players': [], 'away_players': []}
        
        tables = soup.find_all('table')
        team_idx = 0
        
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cells = [c.get_text(strip=True) for c in row.find_all(['td', 'th'])]
                if len(cells) >= 10:
                    player = {
                        'num': cells[0], 'name': cells[1] if len(cells) > 1 else '',
                        'pts': cells[3] if len(cells) > 3 else '',
                        'reb': cells[12] if len(cells) > 12 else '',
                        'ast': cells[13] if len(cells) > 13 else ''
                    }
                    if team_idx == 0:
                        data['home_players'].append(player)
                    else:
                        data['away_players'].append(player)
            team_idx += 1
        
        return data
    
    def parse_leaders(self, html):
        soup = BeautifulSoup(html, 'html.parser')
        data = {'leaders': []}
        
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cells = [c.get_text(strip=True) for c in row.find_all(['td', 'th'])]
                if len(cells) >= 3:
                    data['leaders'].append({'rank': cells[0], 'player': cells[1], 'value': cells[2]})
        
        return data
    
    def parse_pbp(self, html):
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
            
            score_elem = row.find('span', class_='pbpsc')
            if score_elem:
                m = re.search(r'(\d+)-(\d+)', score_elem.get_text())
                if m:
                    home_score = int(m.group(1))
                    away_score = int(m.group(2))
            
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
            
            events.append({
                'seq': seq, 'period': period, 'time': time_str, 'team': team,
                'player': player, 'type': event_type, 'points': points,
                'score': f"{home_score}-{away_score}"
            })
            seq += 1
        
        return {'events': events, 'home_score': home_score, 'away_score': away_score, 'total': len(events)}
    
    def parse_scoreboard(self, html):
        return {'note': 'Scoreboard data'}
    
    def parse_periods(self, html):
        soup = BeautifulSoup(html, 'html.parser')
        data = {'quarters': []}
        
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cells = [c.get_text(strip=True) for c in row.find_all(['td', 'th'])]
                if len(cells) >= 3:
                    data['quarters'].append({'period': cells[0], 'home': cells[1], 'away': cells[2]})
        
        return data
    
    def update_ui(self, data):
        pages = data.get('pages', {})
        
        # Scoreboard
        if 'index' in pages:
            idx = pages['index']
            self.home_name.config(text=idx.get('teams', {}).get('home', 'Home'))
            self.away_name.config(text=idx.get('teams', {}).get('away', 'Away'))
            self.home_score.config(text=str(idx.get('score', {}).get('home', 0)))
            self.away_score.config(text=str(idx.get('score', {}).get('away', 0)))
        
        # Box Score
        if 'boxscore' in pages:
            bs = pages['boxscore']
            
            for item in self.home_tree.get_children():
                self.home_tree.delete(item)
            for p in bs.get('home_players', [])[:15]:
                self.home_tree.insert("", tk.END, values=(
                    p.get('num', ''), p.get('name', '')[:15], '',
                    p.get('pts', ''), '', '', '', p.get('reb', ''), p.get('ast', ''), '', '', '', ''
                ))
            
            for item in self.away_tree.get_children():
                self.away_tree.delete(item)
            for p in bs.get('away_players', [])[:15]:
                self.away_tree.insert("", tk.END, values=(
                    p.get('num', ''), p.get('name', '')[:15], '',
                    p.get('pts', ''), '', '', '', p.get('reb', ''), p.get('ast', ''), '', '', '', ''
                ))
        
        # PBP
        if 'playbyplay' in pages:
            pbp = pages['playbyplay']
            
            for item in self.pbp_tree.get_children():
                self.pbp_tree.delete(item)
            
            events = pbp.get('events', [])[-50:][::-1]
            for e in events:
                self.pbp_tree.insert("", tk.END, values=(
                    e.get('period', '-'), e.get('time', '-') or '-',
                    e.get('team', '-') or '-', (e.get('player') or '-')[:20],
                    e.get('type', '-'), e.get('points', ''), e.get('score', '')
                ))
        
        # Leaders
        if 'leaders' in pages:
            leaders = pages['leaders']
            
            for item in self.leaders_tree.get_children():
                self.leaders_tree.delete(item)
            for l in leaders.get('leaders', [])[:20]:
                self.leaders_tree.insert("", tk.END, values=(
                    l.get('rank', ''), l.get('player', ''), 'PTS', l.get('value', '')
                ))
        
        # Periods
        if 'periods' in pages:
            periods = pages['periods']
            
            for item in self.periods_tree.get_children():
                self.periods_tree.delete(item)
            for q in periods.get('quarters', []):
                self.periods_tree.insert("", tk.END, values=(
                    q.get('period', ''), q.get('home', ''), q.get('away', ''), ''
                ))
        
        self.last_update.config(text=f"Updated: {data.get('fetched_at', '')}")

def main():
    if not HAS_PLAYWRIGHT:
        messagebox.showerror("Error", "Playwright not installed.\nRun: pip install playwright")
        return
    
    root = tk.Tk()
    app = NEBLStatsApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
