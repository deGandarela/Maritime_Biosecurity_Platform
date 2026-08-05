import json
import websocket
import pandas as pd
from sqlalchemy import create_engine
from datetime import datetime, timedelta, timezone
import math
import os
import threading
import time
from flask import Flask
import requests 
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Import the brain of your project
from scoring_engine import calculate_final_risk

# --- 1. CONFIGURATION ---
API_KEY = "e0c478006d151032c0ea83cdfdf47bea79d32f9f"

# Your Supabase Database URI
DB_URI = "postgresql://postgres.ntbhkrfwibgmulwbotts:%40CasadaBouca3@aws-0-eu-central-1.pooler.supabase.com:5432/postgres?sslmode=require"
engine = create_engine(DB_URI)

# GFW API Token 
GFW_TOKEN = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6ImtpZEtleSJ9.eyJkYXRhIjp7Im5hbWUiOiJNYXJpdGltZV9CaW9zZWN1cml0eV9QbGF0Zm9ybSIsInVzZXJJZCI6Njc0MzEsImFwcGxpY2F0aW9uTmFtZSI6Ik1hcml0aW1lX0Jpb3NlY3VyaXR5X1BsYXRmb3JtIiwiaWQiOjEyODg2LCJ0eXBlIjoidXNlci1hcHBsaWNhdGlvbiJ9LCJpYXQiOjE3ODU1MTAzNTksImV4cCI6MjEwMDg3MDM1OSwiYXVkIjoiZ2Z3IiwiaXNzIjoiZ2Z3In0.HoIeFR_CWr64L4gdRwDriTj5tTjnkTBG0vjAkWYujnwSlE4P6MA73UoF9WzS9ObnKheyWHE1Wvjfync-TCy4nd2953rQvf6C4lzLbHk_PNmyI2fP4iRsqbiGAABobPmBLDAW_ZHrzs8APzMgc5cjKZj6WCEoB6gRzD70jvNFKYNN83Ur08hjZkLrpZEb_cWnJGLjwW2M4BCKW1zA1jz1GedbBMZYptuGOU-TUHlu8HJTGI2mU1SbMhbkf1rJH-H_2SG6P_dSdOymM3mIbay6qMkF-bJToKpQL9VfOum9TFARAabh9cpMpUyMSkZvaspfSWamxoKGR28mIMCquWSyu5jPazAvlVYMDdxgMpucK4CwPvGJJRWtFH9cMA3QUeTWXwV5IqAzy74H1wlN9gIs_9oZYYV5_Sh5FqolDCLOnrW4E43ebT_sd9K5qhqWa6YoorWpMaP1A6koRbFFO5tn2KUk6bLtMDSfoozEqWUVBOSFEU4lIRG6TpQwvj0Cqm06"

# --- PORT COORDINATES ---
PORT_COORDS = {
    'Matosinhos': [41.18, -8.70],
    'Aveiro': [40.64, -8.74],
    'Lisboa': [38.70, -9.16],
    'Setúbal': [38.52, -8.89],
    'Sines': [37.95, -8.87]
}

# --- UPGRADE: Robust network session that auto-retries on dropped connections ---
session = requests.Session()
retry_strategy = Retry(
    total=5,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
)
adapter = HTTPAdapter(max_retries=retry_strategy)
session.mount("https://", adapter)
session.mount("http://", adapter)

# --- Helper function to find the closest port ---
def get_nearest_port(lat, lon):
    nearest_port = "Unknown"
    min_dist = float('inf')
    for port, (p_lat, p_lon) in PORT_COORDS.items():
        dist = math.sqrt((lat - p_lat)**2 + (lon - p_lon)**2)
        if dist < min_dist:
            min_dist = dist
            nearest_port = port
    return nearest_port, PORT_COORDS[nearest_port]

# --- GLOBAL FISHING WATCH LOOKUP ---
def get_gfw_origin_data(mmsi):
    """Fetches the last known port of call for a given MMSI using the GFW API."""
    
    headers = {
        "Authorization": f"Bearer {GFW_TOKEN}", 
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Shipsonic-Risk-Engine/1.0"
    }

    try:
        time.sleep(1.0)
        
        # STEP 1: Get Identity (Manual string format to prevent url-encoding errors)
        search_url = f"https://gateway.api.globalfishingwatch.org/v3/vessels/search?query={mmsi}&datasets[0]=public-global-vessel-identity:latest"
        
        identity_response = session.get(search_url, headers=headers, timeout=15)
        identity_response.raise_for_status()
        
        identity_data = identity_response.json()
        
        if not identity_data.get('entries'):
            print(f"ℹ️ MMSI {mmsi} not found in GFW identity database.")
            return [], None, None
            
        # --- NEW API V3 EXTRACTION LOGIC ---
        entry = identity_data['entries'][0]
        gfw_vessel_id = None
        
        for key in ['combinedSourcesInfo', 'selfReportedInfo']:
            if key in entry and entry[key]:
                info = entry[key]
                if isinstance(info, list) and len(info) > 0:
                    gfw_vessel_id = info[0].get('vesselId') or info[0].get('id')
                elif isinstance(info, dict):
                    gfw_vessel_id = info.get('vesselId') or info.get('id')
                
                if gfw_vessel_id:
                    break
                    
        if not gfw_vessel_id:
            print(f"⚠️ Could not find internal vessel ID for MMSI {mmsi}.")
            return [], None, None
            
        time.sleep(1.0)
        
      # STEP 2: Get Last Port Visit
        # (Fixing dates to the strict ISO 8601 format required by the API)
        end_date = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')
        start_date = (datetime.now(timezone.utc) - timedelta(days=180)).strftime('%Y-%m-%dT%H:%M:%S.000Z')
        
        events_url = "https://gateway.api.globalfishingwatch.org/v3/events"
        
       # Letting Python handle the URL encoding natively using the params dictionary
        events_params = {
            # THE FIX: Pointing back to the true dataset now that dates/offsets are fixed
            "datasets[0]": "public-global-port-visits-c2-events:latest",
            "vessels[0]": gfw_vessel_id,
            "start-date": start_date,
            "end-date": end_date,
            "limit": 1,
            "offset": 0
        }
        
        events_response = session.get(events_url, headers=headers, params=events_params, timeout=15)
        
        # --- THE DIAGNOSTIC SAFETY NET ---
        # If the API still complains, this forces it to reveal EXACTLY what is wrong!
        if not events_response.ok:
            print(f"🔥 GFW SERVER ERROR MESSAGE: {events_response.text}")
            
        events_response.raise_for_status()
        
        events_data = events_response.json()
        
        if not events_data.get('entries'):
            print(f"ℹ️ No recent port visits found for {mmsi}.")
            return [], None, None
            
        last_port_event = events_data['entries'][0]
        
        # Added safety check in case a port visit record is missing position data
        if 'position' not in last_port_event:
            print(f"ℹ️ Port visit found, but missing GPS coordinates for MMSI {mmsi}.")
            return [], None, None
            
        lat = last_port_event['position']['lat']
        lon = last_port_event['position']['lon']
        
        start_time = datetime.strptime(last_port_event['start'][:19], '%Y-%m-%dT%H:%M:%S')
        end_time = datetime.strptime(last_port_event['end'][:19], '%Y-%m-%dT%H:%M:%S')
        residency_hours = (end_time - start_time).total_seconds() / 3600.0
        
        voyage_history = [{"lat": lat, "lon": lon, "residency_hours": residency_hours}]
        origin_coords = (lat, lon)
        
        print(f"✅ Traced MMSI {mmsi} to previous port: {lat}, {lon}")
        return voyage_history, origin_coords, residency_hours

    except requests.exceptions.RequestException as e:
        print(f"⚠️ GFW API Network Error for MMSI {mmsi}: {e}")
        return [], None, None
    except Exception as e:
        print(f"⚠️ GFW Data Parsing Error for MMSI {mmsi}: {e}")
        return [], None, None

# --- 3. WEBSOCKET LOGIC ---
def on_message(ws, message):
    data = json.loads(message)
    if data["MessageType"] == "PositionReport":
        ship_data = data["Message"]["PositionReport"]
        vessel_id = str(ship_data["UserID"])
        current_lat = ship_data["Latitude"]
        current_lon = ship_data["Longitude"]
        
        port_name, port_coords = get_nearest_port(current_lat, current_lon)
        
        voyage_history, origin_coords, residency_hours = get_gfw_origin_data(vessel_id)
        
        # GATEKEEPER: If no GFW data is found, skip saving to DB
        if origin_coords is None:
            print(f"⏭️ Skipping MMSI {vessel_id}: No verifiable port history to score.")
            return

        current_month = datetime.now().month
        print(f"🚢 Intercepted Vessel MMSI: {vessel_id} near {port_name}...")

        risk_report = calculate_final_risk(
            residency_time_hours=residency_hours,
            origin_coords=origin_coords,
            host_coords=port_coords,
            month=current_month,
            traffic_volume_multiplier=1.2
        )
        
        env_sim = risk_report['environmental_similarity']
        bio_mult = risk_report['biological_multiplier_applied']
        threats = json.dumps(risk_report['triggered_threats'])
        final_score = risk_report['final_risk_score']

        result_df = pd.DataFrame([{
            'vessel_id': vessel_id,
            'host_port_name': port_name,
            'arrival_month': current_month,
            'residency_hours': residency_hours if residency_hours else 0,
            'environmental_similarity': env_sim,
            'biological_multiplier': bio_mult,
            'triggered_threats': threats,
            'final_risk_score': final_score,
            'voyage_history': json.dumps(voyage_history),
            'assessed_at': datetime.now()
        }])
        
        try:
            result_df.to_sql('risk_assessments', engine, if_exists='append', index=False)
            print(f"✅ Risk Score {final_score:.1f} saved to database!")
        except Exception as e:
            print(f"❌ Database error: {e}")

def on_error(ws, error):
    print(f"Error: {error}")

def on_open(ws):
    print("🌐 Connected to Satellite Feed! Listening for ships near Portugal...")
    subscription_message = {
        "APIKey": API_KEY,
        # Locked strictly to the regional coastal bounding box
        "BoundingBoxes": [[ [42.5, -10.5], [36.5, -7.0] ]], 
        "FilterMessageTypes": ["PositionReport"]
    }
    ws.send(json.dumps(subscription_message))

# --- 2. DUMMY WEB SERVER ---
app = Flask(__name__) 

@app.route('/')
def keep_alive():
    return "Shipsonic Radar is live and listening to satellites!"

def run_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    # Start the background web server
    server_thread = threading.Thread(target=run_server)
    server_thread.daemon = True
    server_thread.start()
    
    # THE AUTO-RECONNECT LOOP
    while True:
        try:
            print("🚀 Booting up Shipsonic Radar engine...")
            ws = websocket.WebSocketApp("wss://stream.aisstream.io/v0/stream",
                                        on_open=on_open,
                                        on_message=on_message,
                                        on_error=on_error)
            ws.run_forever()
        except Exception as e:
            print(f"❌ Radar crashed: {e}")
            
        print("⚠️ Satellite feed disconnected. Reconnecting in 5 seconds...")
        time.sleep(5)