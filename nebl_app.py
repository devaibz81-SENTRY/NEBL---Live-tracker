#!/usr/bin/env python3
"""
NEBL Live Stats Desktop Application
- Paste URL
- See live data in UI
- JSON saved locally
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
        self.root.title("NEBL Live Stats")
        self.root.geometry("1100x700")
        self.root.configure(bg="#1a1a2e")
        
        self.is_watching = False
        self.watch_thread = None
        
        self.setup_ui()
        
    def setup_ui(self):
        # Header
        header = tk.Frame(self.root, bg="#043f8f", height=60)
        header.pack(fill=tk.X)
        tk.Label(header, text="NEBL Live Stats", font=("Arial", 20, "bold"), 
                bg="#043f8f", fg="white").pack(pady=15)
        
        # URL Input
        input_frame = tk.Frame(self.root, bg="#1a1a2e", pady=10)
        input_frame.pack(fill=tk.X, padx=20)
        
        tk.Label(input_frame, text="Game URL:", bg="#1a1a2e", fg="white", font=("Arial", 11)).pack(side=tk.LEFT)
        
        self.url_entry = tk.Entry(input_frame, font=("Arial", 11), width=70)
        self.url_entry.pack(side=tk.LEFT, padx=10)
        self.url_entry.insert(0, "https://nebl.web.geniussports.com/competitions/?WHurl=%2Fcompetition%2F48108%2Fmatch%2F2799695%2Fplaybyplay%3F")
        
        self.start_btn = tk.Button(input_frame, text="START", command=self.start_watching,
                                  bg="#28a745", fg="white", font=("Arial", 11, "bold"), padx=20)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        
        self.stop_btn = tk.Button(input_frame, text="STOP", command=self.stop_watching,
                                 bg="#dc3545", fg="white", font=("Arial", 11, "bold"), padx=20, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        
        # Status
        self.status = tk.Label(input_frame, text="Ready", bg="#1a1a2e", fg="#888", font=("Arial", 10))
        self.status.pack(side=tk.LEFT, padx=20)
        
        # Scoreboard
        score_frame = tk.Frame(self.root, bg="#16213e", pady=15)
        score_frame.pack(fill=tk.X, padx=20, pady=10)
        
        self.home_name = tk.Label(score_frame, text="Home Team", font=("Arial", 14, "bold"), bg="#16213e", fg="white")
        self.home_name.place(relx=0.15, rely=0.2, anchor=tk.CENTER)
        
        self.home_score = tk.Label(score_frame, text="0", font=("Arial", 40, "bold"), bg="#16213e", fg="#ffd700")
        self.home_score.place(relx=0.15, rely=0.7, anchor=tk.CENTER)
        
        tk.Label(score_frame, text="VS", font=("Arial", 18), bg="#16213e", fg="#666").place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        
        self.away_name = tk.Label(score_frame, text="Away Team", font=("Arial", 14, "bold"), bg="#16213e", fg="white")
        self.away_name.place(relx=0.85, rely=0.2, anchor=tk.CENTER)
        
        self.away_score = tk.Label(score_frame, text="0", font=("Arial", 40, "bold"), bg="#16213e", fg="#ffd700")
        self.away_score.place(relx=0.85, rely=0.7, anchor=tk.CENTER)
        
        # Main content - split view
        content = tk.Frame(self.root, bg="#1a1a2e")
        content.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Left - Player Stats
        left_frame = tk.LabelFrame(content, text="Player Statistics", font=("Arial", 11, "bold"), 
                                   bg="#16213e", fg="white", padx=10, pady=10)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        cols = ("Player", "PTS", "AST", "REB", "STL", "BLK")
        self.stats_tree = ttk.Treeview(left_frame, columns=cols, show="headings", height=12)
        
        for col in cols:
            self.stats_tree.heading(col, text=col)
            self.stats_tree.column(col, width=70)
        self.stats_tree.column("Player", width=150)
        self.stats_tree.pack(fill=tk.BOTH, expand=True)
        
        # Right - Events
        right_frame = tk.LabelFrame(content, text="Recent Events", font=("Arial", 11, "bold"),
                                    bg="#16213e", fg="white", padx=10, pady=10)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        self.events_list = tk.Listbox(right_frame, font=("Consolas", 9), bg="#0d1b2a", fg="white", height=12)
        self.events_list.pack(fill=tk.BOTH, expand=True)
        
        # Bottom - JSON path
        bottom = tk.Frame(self.root, bg="#1a1a2e", pady=5)
        bottom.pack(fill=tk.X, padx=20)
        
        tk.Label(bottom, text="JSON saved to:", bg="#1a1a2e", fg="#888", font=("Arial", 9)).pack(side=tk.LEFT)
        self.json_path = tk.Label(bottom, text="data/live_stats.json", bg="#1a1a2e", fg="#28a745", font=("Arial", 9))
        self.json_path.pack(side=tk.LEFT, padx=5)
        
        self.last_update = tk.Label(bottom, text="", bg="#1a1a2e", fg="#666", font=("Arial", 9))
        self.last_update.pack(side=tk.RIGHT)
        
    def start_watching(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("Warning", "Please enter a game URL")
            return
        
        # Extract game ID
        match = re.search(r'match/(\d+)', url)
        game_id = match.group(1) if match else "unknown"
        
        self.is_watching = True
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.url_entry.config(state=tk.DISABLED)
        self.status.config(text="Watching...", fg="#28a745")
        
        self.watch_thread = threading.Thread(target=self.watch_loop, args=(url, game_id), daemon=True)
        self.watch_thread.start()
        
    def stop_watching(self):
        self.is_watching = False
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.url_entry.config(state=tk.NORMAL)
        self.status.config(text="Stopped", fg="#dc3545")
        
    def watch_loop(self, url, game_id):
        last_count = 0
        
        while self.is_watching:
            try:
                self.status.config(text="Fetching...", fg="#ffc107")
                data = self.fetch_data(url)
                
                if data:
                    # Save JSON
                    json_file = "data/live_stats.json"
                    os.makedirs("data", exist_ok=True)
                    with open(json_file, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2)
                    self.json_path.config(text=json_file)
                    
                    # Update UI
                    self.root.after(0, lambda: self.update_ui(data))
                    
                    new_events = data.get("total_events", 0) - last_count
                    last_count = data.get("total_events", 0)
                    
                    if new_events > 0:
                        self.status.config(text=f"Live! +{new_events} events", fg="#28a745")
                    else:
                        self.status.config(text=f"Watching... ({data.get('total_events', 0)} events)", fg="#ffc107")
                else:
                    self.status.config(text="No data (game may not have started)", fg="#dc3545")
                    
            except Exception as e:
                self.status.config(text=f"Error: {str(e)}", fg="#dc3545")
            
            time.sleep(0.5)
            
    def fetch_data(self, url):
        if not HAS_PLAYWRIGHT:
            return None
            
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(user_agent='Mozilla/5.0')
                page = context.new_page()
                page.goto(url, wait_until="networkidle", timeout=60000)
                page.wait_for_timeout(2000)
                html = page.content()
                browser.close()
            
            return self.parse_html(html)
            
        except Exception as e:
            print(f"Error: {e}")
            return None
    
    def parse_html(self, html):
        soup = BeautifulSoup(html, 'html.parser')
        
        # Teams
        home_img = soup.find('img', class_='logo home-logo')
        away_img = soup.find('img', class_='logo away-logo')
        home_team = home_img.get('alt') if home_img else 'Home'
        away_team = away_img.get('alt') if away_img else 'Away'
        
        # Events
        pbp_rows = soup.find_all('div', class_='pbpa')
        events = []
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
            
            # Period & Time
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
            
            # Score
            score_elem = row.find('span', class_='pbpsc')
            if score_elem:
                m = re.search(r'(\d+)-(\d+)', score_elem.get_text())
                if m:
                    home_score = int(m.group(1))
                    away_score = int(m.group(2))
            
            # Action
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
                    if '3pt' in desc_lower or 'three' in desc_lower: points = 3
                    elif '2pt' in desc_lower: points = 2
                    elif 'free throw' in desc_lower: points = 1
                elif 'rebound' in desc_lower: event_type = 'rebound'
                elif 'assist' in desc_lower: event_type = 'assist'
                elif 'foul' in desc_lower: event_type = 'foul'
                elif 'turnover' in desc_lower: event_type = 'turnover'
            
            events.append({
                'sequence': seq, 'period': period, 'time': time_str, 'team': team,
                'player': player, 'event_type': event_type, 'points': points,
                'home_score': home_score, 'away_score': away_score, 'description': description
            })
            seq += 1
        
        # Player stats
        player_stats = {}
        for e in events:
            player = e.get('player')
            if not player: continue
            if player not in player_stats:
                player_stats[player] = {'Player': player, 'PTS': 0, 'AST': 0, 'REB': 0, 'STL': 0, 'BLK': 0}
            if e.get('event_type') == 'score' and e.get('points'):
                player_stats[player]['PTS'] += e['points']
            elif e.get('event_type') == 'assist': player_stats[player]['AST'] += 1
            elif e.get('event_type') == 'rebound': player_stats[player]['REB'] += 1
            elif e.get('event_type') == 'steal': player_stats[player]['STL'] += 1
            elif e.get('event_type') == 'block': player_stats[player]['BLK'] += 1
        
        return {
            'home_team': home_team,
            'away_team': away_team,
            'current_score': {'home': home_score, 'away': away_score},
            'total_events': len(events),
            'player_stats': list(player_stats.values()),
            'events': events,
            'last_update': datetime.now().isoformat()
        }
    
    def update_ui(self, data):
        # Scoreboard
        self.home_name.config(text=data.get('home_team', 'Home'))
        self.away_name.config(text=data.get('away_team', 'Away'))
        self.home_score.config(text=str(data.get('current_score', {}).get('home', 0)))
        self.away_score.config(text=str(data.get('current_score', {}).get('away', 0)))
        
        # Player stats
        for item in self.stats_tree.get_children():
            self.stats_tree.delete(item)
        
        sorted_players = sorted(data.get('player_stats', []), key=lambda x: x.get('PTS', 0), reverse=True)
        for p in sorted_players[:15]:
            self.stats_tree.insert("", tk.END, values=(
                p.get('Player', '')[:20],
                p.get('PTS', 0),
                p.get('AST', 0),
                p.get('REB', 0),
                p.get('STL', 0),
                p.get('BLK', 0)
            ))
        
        # Events
        self.events_list.delete(0, tk.END)
        recent = data.get('events', [])[-15:][::-1]
        for e in recent:
            period = e.get('period') or '-'
            time_str = e.get('time') or '-'
            player = (e.get('player') or '-')[:15]
            event_type = e.get('event_type') or '-'
            pts = e.get('points') or ''
            self.events_list.insert(tk.END, f"Q{period} {time_str} | {player:15} | {event_type:10} {pts}")
        
        # Last update
        self.last_update.config(text=f"Updated: {data.get('last_update', '')}")

def main():
    if not HAS_PLAYWRIGHT:
        messagebox.showerror("Error", "Playwright not installed.\nRun: pip install playwright")
        return
    
    root = tk.Tk()
    app = NEBLStatsApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
