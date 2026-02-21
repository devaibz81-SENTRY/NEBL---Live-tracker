#!/usr/bin/env python3
"""
NEBL Play-by-Play to Google Sheets Exporter
"""

import json
import os
import argparse

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    HAS_SHEETS = True
except Exception:
    HAS_SHEETS = False
    print("Google Sheets libraries not installed. Run: pip install google-api-python-client google-auth")

def export_to_sheets(json_file, credentials_file, spreadsheet_id, pbp_sheet="PBp", stats_sheet="PlayerStats"):
    """Export pbp data to Google Sheets"""
    
    if not HAS_SHEETS:
        print("ERROR: Google Sheets libraries not installed")
        return False
    
    # Load JSON data
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Build credentials
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    credentials = service_account.Credentials.from_service_account_file(
        credentials_file, 
        scopes=scopes
    )
    service = build("sheets", "v4", credentials=credentials, cache_discovery=False)
    
    # Prepare PBp data
    pbp_headers = ["Sequence", "Period", "Time", "Team", "Player", "Event", "Points", "HomeScore", "AwayScore", "Description"]
    pbp_rows = [pbp_headers]
    
    for event in data.get("pbp_events", []):
        pbp_rows.append([
            event.get("sequence", ""),
            event.get("period", ""),
            event.get("time", ""),
            event.get("team", ""),
            event.get("player", ""),
            event.get("event_type", ""),
            event.get("points", ""),
            event.get("home_score", ""),
            event.get("away_score", ""),
            event.get("description", "")
        ])
    
    # Prepare Player Stats data
    stats_headers = ["Player", "Team", "Points", "Assists", "Rebounds", "Steals", "Blocks", "Turnovers", "Fouls"]
    stats_rows = [stats_headers]
    
    for player in data.get("player_stats", []):
        stats_rows.append([
            player.get("Player", ""),
            player.get("Team", ""),
            player.get("Points", ""),
            player.get("Assists", ""),
            player.get("Rebounds", ""),
            player.get("Steals", ""),
            player.get("Blocks", ""),
            player.get("Turnovers", ""),
            player.get("Fouls", "")
        ])
    
    try:
        # Clear and write PBp sheet
        print(f"Writing {len(pbp_rows)-1} events to PBp sheet...")
        body = {"values": pbp_rows}
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"{pbp_sheet}!A1",
            valueInputOption="RAW",
            body=body
        ).execute()
        
        # Clear and write Player Stats sheet
        print(f"Writing {len(stats_rows)-1} players to PlayerStats sheet...")
        body = {"values": stats_rows}
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"{stats_sheet}!A1",
            valueInputOption="RAW",
            body=body
        ).execute()
        
        print("Successfully exported to Google Sheets!")
        return True
        
    except Exception as e:
        print(f"Error exporting to Sheets: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Export NEBL PBp to Google Sheets")
    parser.add_argument("--json", default="data/pbp_output.json", help="Input JSON file")
    parser.add_argument("--creds", default="credentials.json", help="Google service account credentials")
    parser.add_argument("--sheet", required=True, help="Spreadsheet ID")
    parser.add_argument("--pbp-sheet", default="PBp", help="PBp sheet name")
    parser.add_argument("--stats-sheet", default="PlayerStats", help="PlayerStats sheet name")
    args = parser.parse_args()
    
    if not os.path.exists(args.json):
        print(f"ERROR: JSON file not found: {args.json}")
        return
    
    if not os.path.exists(args.creds):
        print(f"ERROR: Credentials file not found: {args.creds}")
        print("You need to download a service account JSON file from Google Cloud Console")
        return
    
    export_to_sheets(args.json, args.creds, args.sheet, args.pbp_sheet, args.stats_sheet)

if __name__ == "__main__":
    main()
