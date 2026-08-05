import streamlit as st
import pandas as pd
import json
from sqlalchemy import create_engine
import folium
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster
from geopy.geocoders import Nominatim 

st.set_page_config(page_title="Shipsonic Radar", layout="wide")

DB_URI = "postgresql://postgres.ntbhkrfwibgmulwbotts:%40CasadaBouca3@aws-0-eu-central-1.pooler.supabase.com:5432/postgres?sslmode=require"
engine = create_engine(DB_URI)

PORT_COORDS = {
    'Matosinhos': [41.18, -8.70],
    'Aveiro': [40.64, -8.74],
    'Lisboa': [38.70, -9.16],
    'Setúbal': [38.52, -8.89],
    'Sines': [37.95, -8.87]
}

# Initialize the map reader
geolocator = Nominatim(user_agent="shipsonic_radar")

# Cache the city lookups so the dashboard loads instantly!
@st.cache_data(max_entries=200)
def get_city_country(lat, lon):
    try:
        location = geolocator.reverse((lat, lon), exactly_one=True, language='en')
        if location:
            address = location.raw.get('address', {})
            # Geocoders are weird, sometimes it's a city, town, municipality, or village
            city = address.get('city', address.get('town', address.get('municipality', address.get('village', 'Unknown City'))))
            country = address.get('country', 'Unknown Country')
            
            if city != 'Unknown City' and country != 'Unknown Country':
                return f"{city}, {country}"
            elif country != 'Unknown Country':
                return country
        return f"{lat:.2f}, {lon:.2f}"
    except Exception:
        return f"{lat:.2f}, {lon:.2f}"

@st.cache_data(ttl=60)
def load_data():
    query = "SELECT * FROM risk_assessments ORDER BY assessed_at DESC LIMIT 200"
    try:
        df = pd.read_sql(query, engine)
        if 'residency_hours' in df.columns:
            df['residency_hours'] = df['residency_hours'].fillna(0).round().astype(int)
        return df
    except Exception:
        return pd.DataFrame()

df = load_data()

st.markdown("""
<div style="text-align: center; margin-bottom: 20px;">
    <h1>🚢 Shipsonic Radar</h1>
    <p style="font-size: 1.1rem; color: #a1a1aa;">Live biosecurity monitoring and voyage trajectory intelligence.</p>
</div>
""", unsafe_allow_html=True)

col1, col2, col3 = st.columns([1, 1, 1])
with col2:
    if st.button("Refresh Radar", use_container_width=True):
        # THE FIX: Only clear the database cache! 
        # This keeps the translated cities in memory so they load instantly.
        load_data.clear() 
        df = load_data()

m = folium.Map(location=[39.5, -8.0], zoom_start=6, tiles="CartoDB dark_matter")

zero_cluster_html = """
<div style="
    background-color: rgba(241, 211, 87, 0.6);
    width: 40px; height: 40px;
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    ">
    <div style="
        background-color: rgba(240, 194, 12, 0.9);
        width: 30px; height: 30px;
        border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        color: #333; font-weight: bold; font-family: sans-serif; font-size: 14px;
        ">
        0
    </div>
</div>
"""

active_ports = df['host_port_name'].unique() if not df.empty else []

for port_name, coords in PORT_COORDS.items():
    if port_name not in active_ports:
        folium.Marker(
            location=coords,
            icon=folium.DivIcon(html=zero_cluster_html, icon_anchor=(20, 20)),
            popup=f"⚓ Port of {port_name} (0 Ships)"
        ).add_to(m)

marker_cluster = MarkerCluster().add_to(m)

if not df.empty:
    for _, row in df.iterrows():
        vessel_id = row.get('vessel_id', 'Unknown')
        port_name = row.get('host_port_name', 'Unknown')
        
        # Removed the default '0' so we can accurately detect missing data (NaN)
        risk_score = row.get('final_risk_score')
        
        host_latlon = PORT_COORDS.get(port_name, [39.5, -8.0])
        
        # --- ROBUST COLOR CHECK ---
        if pd.isna(risk_score) or risk_score == "None":
            marker_color = "lightgray"
            popup_text = f"MMSI: {vessel_id}<br>Score: Data Unavailable"
        else:
            try:
                numeric_score = float(risk_score)
                marker_color = "red" if numeric_score > 70 else "blue"
                popup_text = f"MMSI: {vessel_id}<br>Score: {numeric_score:.1f}"
            except (ValueError, TypeError):
                marker_color = "gray"
                popup_text = f"MMSI: {vessel_id}<br>Score: Data Error"
        # --------------------------
        
        folium.Marker(
            location=host_latlon,
            popup=popup_text,
            icon=folium.Icon(color=marker_color, icon="ship", prefix='fa')
        ).add_to(marker_cluster)

st_folium(m, use_container_width=True, height=550)

def clean_threat_names(threats_json):
    if pd.isna(threats_json): return "None"
    try:
        threat_list = json.loads(threats_json)
        cleaned_list = [threat.replace('_', ' ').title() for threat in threat_list]
        return ", ".join(cleaned_list)
    except Exception:
        return str(threats_json)

KNOWN_PORTS = {
    (51.68, 6.47): "Rotterdam, Netherlands",
    (45.17, 29.11): "Constanta, Romania",
    (42.50, -8.86): "Vigo, Spain",
    (42.46, -8.92): "Marín, Spain",
    (36.54, -6.28): "Cadiz, Spain",
    (63.86, 23.03): "Raahe, Finland",
    (41.18, -8.71): "Matosinhos, Portugal",
    (38.70, -9.16): "Lisboa, Portugal"
}

def get_origin_city_name(history_json):
    if pd.isna(history_json) or history_json is None or history_json == '[]':
        return "Not found"
    try:
        history = json.loads(history_json)
        if isinstance(history, list) and len(history) > 0:
            lat = history[0].get('lat')
            lon = history[0].get('lon')
            if lat is not None and lon is not None:
                # 1. Check our fast demo dictionary first
                for (k_lat, k_lon), name in KNOWN_PORTS.items():
                    if abs(lat - k_lat) < 0.1 and abs(lon - k_lon) < 0.1:
                        return name
                
                # 2. Fallback to geocoder if it's a new coordinate
                return get_city_country(lat, lon)
    except Exception:
        pass
    return "Not found"

st.subheader("View Raw Assessment Logs")

if not df.empty:
    if 'triggered_threats' in df.columns:
        df['triggered_threats'] = df['triggered_threats'].apply(clean_threat_names)

    if 'voyage_history' in df.columns:
        df['origin_location'] = df['voyage_history'].apply(get_origin_city_name)
    else:
        df['origin_location'] = "Not found"

    display_df = df.rename(columns={
        'id': 'ID',
        'vessel_id': 'Vessel ID',
        'origin_location': 'Last Port Visited', # <--- Change the display name here!
        'host_port_name': 'Host Port',
        'arrival_month': 'Arrival Month',
        'residency_hours': 'Residency Hours',
        'environmental_similarity': 'Environmental Similarity',
        'biological_multiplier': 'Biological Multiplier',
        'triggered_threats': 'Triggered Threats',
        'final_risk_score': 'Final Risk Score',
        'voyage_history': 'Voyage History',
        'assessed_at': 'Assessment Time'
    })

    # Make sure to update the expected_cols list below it too!
    expected_cols = [
        'ID', 'Vessel ID', 'Last Port Visited', 'Host Port', 'Arrival Month', 
        'Residency Hours', 'Environmental Similarity', 'Biological Multiplier', 
        'Triggered Threats', 'Final Risk Score', 'Assessment Time'
    ]
    
    final_cols = [col for col in expected_cols if col in display_df.columns]
    display_df = display_df[final_cols]
    
    st.dataframe(display_df, use_container_width=True)
else:
    st.info("Awaiting live satellite data... Run your radar script to begin tracking.")

st.markdown("---")
st.subheader("🧮 How We Assess Biosecurity Risk")
st.info("""
**The Shipsonic engine calculates the threat of marine invasive species using a localized mathematical model:**

1. **Environmental Suitability:** The system cross-references NetCDF marine climate datasets (temperature and salinity) between the vessel's previous global ports and the current Portuguese host port. A high climate match means invasive species are more likely to survive the transition.
2. **Biological Multipliers:** Using the Global Fishing Watch API, we pull the true residency time (hours spent loitering or docked). The longer a vessel sits idle in a foreign port, the higher the mathematical probability of biofouling attachment on the hull.
3. **Final Computation:** `(Base Climate Suitability) x (Residency Duration Multiplier) x (Traffic Volume) = Final Risk Score (0-100)`. Vessels scoring above 70 are flagged for high-priority physical inspection.
""")