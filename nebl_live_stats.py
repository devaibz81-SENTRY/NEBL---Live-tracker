#!/usr/bin/env python3
"""
NEBL Live Stats Desktop Application
GUI for watching basketball games in real-time
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import json
import os
import time
from datetime import datetime
from urllib.parse import urlparse

try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except Exception:
    HAS_PLAYWRIGHT = False

import re
from bs4 import BeautifulSoup

class NEBLStatsApp:
    def __init__(self, root):
        self.root = root
        self.root.title("NEBL Live Stats")
        self.root.geometry("1200x800")
        self.root.configure(bg="#1a1a2e")
        
        self.is_watching = False
        self.watch_thread = None
        self.current_url = ""
        self.game_id = ""
        
        self.setup_ui()
        
    def setup_ui(self):
        # Header
        header_frame = tk.Frame(self.root, bg="#043f8f", height=80)
        header_frame.pack(fill=tk.X)
        header_frame.pack_propagate(False)
        
        title_label = tk.Label(header_frame, text="🏀 NEBL Live Stats", 
                              font=("Arial", 24, "bold"), bg="#043f8f", fg="white")
        title_label.pack(pady=20)
        
        # URL Input Frame
        input_frame = tk.Frame(self.root, bg="#1a1a2e", pady=10)
        input_frame.pack(fill=tk.X, padx=20)
        
        tk.Label(input_frame, text="Game URL:", bg="#1a1a2e", fg="white", font=("Arial", 12)).pack(side=tk.LEFT)
        
        self.url_entry = tk.Entry(input_frame, font=("Arial", 11), width=60)
        self.url_entry.pack(side=tk.LEFT, padx=10, fill=tk.X, expand=True)
        
        self.watch_btn = tk.Button(input_frame, text="▶ Start Watching", 
                                   command=self.start_watching,
                                   bg="#28a745", fg="white", font=("Arial", 11, "bold"),
                                   padx=20, pady=5)
        self.watch_btn.pack(side=tk.LEFT, padx=5)
        
        self.stop_btn = tk.Button(input_frame, text="⏹ Stop", 
                                  command=self.stop_watching,
                                  bg="#dc3545", fg="white", font=("Arial", 11, "bold"),
                                  padx=20, pady=5, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        
        # Status Bar
        self.status_label = tk.Label(input_frame, text="Ready", 
                                     bg="#1a1a2e", fg="#888", font=("Arial", 10))
        self.status_label.pack(side=tk.LEFT, padx=20)
        
        # Main Content
        content_frame = tk.Frame(self.root, bg="#1a1a2e")
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Scoreboard
        score_frame = tk.Frame(content_frame, bg="#16213e", pady=20, padx=20)
        score_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Home Team
        self.home_team_label = tk.Label(score_frame, text="Home Team", 
                                        font=("Arial", 14, "bold"), bg="#16213e", fg="white")
        self.home_team_label.place(relx=0.15, rely=0.3, anchor=tk.CENTER)
        
        self.home_score_label = tk.Label(score_frame, text="0", 
                                         font=("Arial", 48, "bold"), bg="#16213e", fg="#ffd700")
        self.home_score_label.place(relx=0.15, rely=0.7, anchor=tk.CENTER)
        
        # VS
        tk.Label(score_frame, text="VS", font=("Arial", 20), bg="#16213e", fg="#666").place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        
        # Away Team
        self.away_team_label = tk.Label(score_frame, text="Away Team", 
                                        font=("Arial", 14, "bold"), bg="#16213e", fg="white")
        self.away_team_label.place(relx=0.85, rely=0.3, anchor=tk.CENTER)
        
        self.away_score_label = tk.Label(score_frame, text="0", 
                                         font=("Arial", 48, "bold"), bg="#16213e", fg="#ffd700")
        self.away_score_label.place(relx=0.85, rely=0.7, anchor=tk.CENTER)
        
        # Bottom Panes
        paned = ttk.PanedWindow(content_frame, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)
        
        # Player Stats
        stats_frame = tk.LabelFrame(paned, text="Player Statistics", 
                                    font=("Arial", 12, "bold"))
        paned.add(stats_frame, weight=2)
        
        # Treeview for stats
        columns = ("Player", "Team", "PTS", "AST", "REB", "STL", "BLK")
        self.stats_tree = ttk.Treeview(stats_frame, columns=columns, show="headings", height=15)
        
        for col in columns:
            self.stats_tree.heading(col, text=col)
            self.stats_tree.column(col, width=80)
        
        self.stats_tree.column("Player", width=150)
        self.stats_tree.column("Team", width=100)
        
        self.stats_tree.pack(fill=tk.BOTH, expand=True)
        
        # Recent Events
        events_frame = tk.LabelFrame(paned, text="Recent Events", 
                                     font=("Arial", 12, "bold"))
        paned.add(events_frame, weight=1)
        
        self.events_text = scrolledtext.ScrolledText(events_frame, font=("Consolas", 10), 
                                                    bg="#16213e", fg="white", height=15)
        self.events_text.pack(fill=tk.BOTH, expand=True)
        
        # Last Update
        self.last_update_label = tk.Label(content_frame, text="", 
                                          bg="#1a1a2e", fg="#666", font=("Arial", 9))
        self.last_update_label.pack(pady=5)
        
        # Debug Console
        debug_frame = tk.LabelFrame(content_frame, text="Debug Console", font=("Arial", 10))
        debug_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.debug_text = scrolledtext.ScrolledText(debug_frame, font=("Consolas", 9), 
                                                    bg="#000", fg="#0f0", height=6)
        self.debug_text.pack(fill=tk.X, padx=5, pady=5)
        
    def log_to_console(self, msg):
        """Log message to debug console"""
        self.debug_text.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
        self.debug_text.see(tk.END)
        self.root.update()
        
    def start_watching(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("Warning", "Please enter a game URL")
            return
        
        # Extract game ID from URL
        match = re.search(r'match/(\d+)', url)
        if match:
            self.game_id = match.group(1)
        else:
            # Try to extract from the fibalivestats URL
            match = re.search(r'/u/BBF/(\d+)', url)
            if match:
                self.game_id = match.group(1)
            else:
                self.game_id = "unknown"
        
        self.current_url = url
        self.is_watching = True
        
        self.watch_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.url_entry.config(state=tk.DISABLED)
        self.status_label.config(text="Watching...", fg="#28a745")
        
        # Start watch thread
        self.watch_thread = threading.Thread(target=self.watch_loop, daemon=True)
        self.watch_thread.start()
        
    def stop_watching(self):
        self.is_watching = False
        self.watch_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.url_entry.config(state=tk.NORMAL)
        self.status_label.config(text="Stopped", fg="#dc3545")
        
    def watch_loop(self):
        last_event_count = 0
        
        while self.is_watching:
            try:
                self.status_label.config(text="Fetching data...", fg="#ffc107")
                self.log_to_console("Fetching data from: " + self.current_url)
                data = self.fetch_game_data(self.current_url)
                
                self.log_to_console(f"Got data: {data is not None}")
                if data:
                    self.log_to_console(f"Events: {data.get('total_events', 0)}, Players: {len(data.get('player_stats', []))}")
                    
                    # Save JSON for debugging
                    with open("data/debug_live.json", "w") as f:
                        json.dump(data, f, indent=2)
                    self.log_to_console("Saved to data/debug_live.json")
                    
                    self.update_ui(data)
                    new_events = data.get("total_events", 0) - last_event_count
                    last_event_count = data.get("total_events", 0)
                    
                    if new_events > 0:
                        self.status_label.config(text=f"Live! +{new_events} events", fg="#28a745")
                    else:
                        self.status_label.config(text=f"Watching... ({data.get('total_events', 0)} events)", fg="#ffc107")
                else:
                    self.status_label.config(text="No data (game may not have started)", fg="#dc3545")
                    self.log_to_console("No data returned from fetch")
                    
            except Exception as e:
                self.status_label.config(text=f"Error: {str(e)}", fg="#dc3545")
            
            # Poll every 15 seconds
            for _ in range(15):
                if not self.is_watching:
                    break
                time.sleep(1)
                
        self.status_label.config(text="Stopped", fg="#dc3545")
        
    def fetch_game_data(self, url):
        """Fetch and parse game data"""
        if not HAS_PLAYWRIGHT:
            self.log_to_console("ERROR: Playwright not installed")
            return None
            
        try:
            self.log_to_console("Launching browser...")
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                )
                page = context.new_page()
                self.log_to_console(f"Loading URL: {url[:50]}...")
                page.goto(url, wait_until="networkidle", timeout=60000)
                page.wait_for_timeout(3000)
                html = page.content()
                self.log_to_console(f"Page loaded, HTML length: {len(html)}")
                browser.close()
            
            self.log_to_console("Parsing HTML...")
            data = self.parse_html(html)
            self.log_to_console(f"Parsed: {data.get('total_events', 0) if data else 0} events")
            return data
            
        except Exception as e:
            self.log_to_console(f"ERROR: {str(e)}")
            import traceback
            self.log_to_console(traceback.format_exc())
            return None
    
    def parse_html(self, html):
        """Parse the HTML to extract game data"""
        soup = BeautifulSoup(html, 'html.parser')
        
        # Get teams
        home_team = "Home"
        away_team = "Away"
        
        home_img = soup.find('img', class_='logo home-logo')
        away_img = soup.find('img', class_='logo away-logo')
        
        if home_img and home_img.get('alt'):
            home_team = home_img.get('alt')
        if away_img and away_img.get('alt'):
            away_team = away_img.get('alt')
        
        # Get pbp events
        events = []
        pbp_rows = soup.find_all('div', class_='pbpa')
        
        seq = 1
        home_score = 0
        away_score = 0
        
        for row in pbp_rows:
            team_class = None
            for cls in row.get('class', []):
                if cls.startswith('pbp-team'):
                    team_class = cls
                    break
            
            team = None
            if team_class == 'pbp-team1':
                team = 'home'
            elif team_class == 'pbp-team2':
                team = 'away'
            
            # Get time
            period = None
            time_str = None
            
            period_elem = row.find('span', class_='pbp-period')
            if period_elem:
                m = re.search(r'P(\d+)', period_elem.get_text())
                if m:
                    period = int(m.group(1))
            
            time_elem = row.find('div', class_='pbp-time')
            if time_elem:
                m = re.search(r'(\d{1,2}:\d{2}):\d{2}', time_elem.get_text())
                if m:
                    time_str = m.group(1)
            
            # Get score
            score_elem = row.find('span', class_='pbpsc')
            if score_elem:
                m = re.search(r'(\d+)-(\d+)', score_elem.get_text())
                if m:
                    home_score = int(m.group(1))
                    away_score = int(m.group(2))
            
            # Get action
            action_elem = row.find('div', class_='pbp-action')
            description = ""
            player = None
            event_type = "unknown"
            points = None
            
            if action_elem:
                description = action_elem.get_text(strip=True)
                m = re.search(r'<strong>(\d+),\s*([^<]+)</strong>', str(action_elem))
                if m:
                    player = m.group(2).strip()
                
                desc_lower = description.lower()
                
                if 'made' in desc_lower or 'score' in desc_lower:
                    event_type = "score"
                    if '3pt' in desc_lower or 'three' in desc_lower:
                        points = 3
                    elif '2pt' in desc_lower:
                        points = 2
                    elif 'free throw' in desc_lower:
                        points = 1
                elif 'rebound' in desc_lower:
                    event_type = "rebound"
                elif 'assist' in desc_lower:
                    event_type = "assist"
                elif 'foul' in desc_lower:
                    event_type = "foul"
                elif 'turnover' in desc_lower:
                    event_type = "turnover"
            
            events.append({
                "sequence": seq,
                "period": period,
                "time": time_str,
                "team": team,
                "player": player,
                "event_type": event_type,
                "points": points,
                "home_score": home_score,
                "away_score": away_score,
                "description": description
            })
            seq += 1
        
        # Calculate player stats
        player_stats = {}
        for e in events:
            player = e.get("player")
            if not player:
                continue
            if player not in player_stats:
                player_stats[player] = {
                    "Player": player,
                    "Team": e.get("team", "Unknown"),
                    "PTS": 0, "AST": 0, "REB": 0, "STL": 0, "BLK": 0
                }
            
            if e.get("event_type") == "score" and e.get("points"):
                player_stats[player]["PTS"] += e["points"]
            elif e.get("event_type") == "assist":
                player_stats[player]["AST"] += 1
            elif e.get("event_type") == "rebound":
                player_stats[player]["REB"] += 1
            elif e.get("event_type") == "steal":
                player_stats[player]["STL"] += 1
            elif e.get("event_type") == "block":
                player_stats[player]["BLK"] += 1
        
        return {
            "game_id": self.game_id,
            "home_team": home_team,
            "away_team": away_team,
            "current_score": {"home": home_score, "away": away_score},
            "total_events": len(events),
            "player_stats": list(player_stats.values()),
            "events": events
        }
    
    def update_ui(self, data):
        """Update the UI with new data"""
        # Update scoreboard
        self.home_team_label.config(text=data.get("home_team", "Home"))
        self.away_team_label.config(text=data.get("away_team", "Away"))
        
        score = data.get("current_score", {})
        self.home_score_label.config(text=str(score.get("home", 0)))
        self.away_score_label.config(text=str(score.get("away", 0)))
        
        # Update player stats
        for item in self.stats_tree.get_children():
            self.stats_tree.delete(item)
        
        players = data.get("player_stats", [])
        sorted_players = sorted(players, key=lambda x: x.get("PTS", 0), reverse=True)
        
        for p in sorted_players[:20]:
            self.stats_tree.insert("", tk.END, values=(
                p.get("Player", ""),
                p.get("Team", ""),
                p.get("PTS", 0),
                p.get("AST", 0),
                p.get("REB", 0),
                p.get("STL", 0),
                p.get("BLK", 0)
            ))
        
        # Update recent events
        events = data.get("events", [])
        recent = events[-20:] if len(events) > 20 else events
        
        self.events_text.delete(1.0, tk.END)
        for e in reversed(recent):
            period = e.get("period") or "-"
            time_str = e.get("time") or "-"
            player = e.get("player") or "-"
            event_type = e.get("event_type") or "-"
            pts = e.get("points") or ""
            
            line = f"Q{period} {time_str} | {player} | {event_type} {pts}\n"
            self.events_text.insert(tk.END, line)
        
        # Update last update time
        self.last_update_label.config(text=f"Last updated: {datetime.now().strftime('%H:%M:%S')}")

def main():
    if not HAS_PLAYWRIGHT:
        messagebox.showerror("Error", "Playwright not installed. Run: pip install playwright")
        return
        
    root = tk.Tk()
    app = NEBLStatsApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
