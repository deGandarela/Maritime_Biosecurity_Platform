import requests
import pandas as pd
import geopandas as gpd
from sqlalchemy import create_engine
from shapely.geometry import Point

# 1. Configuration
DB_URI = "postgresql://postgres:%40CasadaBouca3@db.ntbhkrfwibgmulwbotts.supabase.co:5432/postgres"
GFW_API_TOKEN = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6ImtpZEtleSJ9.eyJkYXRhIjp7Im5hbWUiOiJNYXJpdGltZV9CaW9zZWN1cml0eV9QbGF0Zm9ybSIsInVzZXJJZCI6Njc0MzEsImFwcGxpY2F0aW9uTmFtZSI6Ik1hcml0aW1lX0Jpb3NlY3VyaXR5X1BsYXRmb3JtIiwiaWQiOjEyODg2LCJ0eXBlIjoidXNlci1hcHBsaWNhdGlvbiJ9LCJpYXQiOjE3ODU1MTAzNTksImV4cCI6MjEwMDg3MDM1OSwiYXVkIjoiZ2Z3IiwiaXNzIjoiZ2Z3In0.HoIeFR_CWr64L4gdRwDriTj5tTjnkTBG0vjAkWYujnwSlE4P6MA73UoF9WzS9ObnKheyWHE1Wvjfync-TCy4nd2953rQvf6C4lzLbHk_PNmyI2fP4iRsqbiGAABobPmBLDAW_ZHrzs8APzMgc5cjKZj6WCEoB6gRzD70jvNFKYNN83Ur08hjZkLrpZEb_cWnJGLjwW2M4BCKW1zA1jz1GedbBMZYptuGOU-TUHlu8HJTGI2mU1SbMhbkf1rJH-H_2SG6P_dSdOymM3mIbay6qMkF-bJToKpQL9VfOum9TFARAabh9cpMpUyMSkZvaspfSWamxoKGR28mIMCquWSyu5jPazAvlVYMDdxgMpucK4CwPvGJJRWtFH9cMA3QUeTWXwV5IqAzy74H1wlN9gIs_9oZYYV5_Sh5FqolDCLOnrW4E43ebT_sd9K5qhqWa6YoorWpMaP1A6koRbFFO5tn2KUk6bLtMDSfoozEqWUVBOSFEU4lIRG6TpQwvj0Cqm06"
GFW_HEADERS = {"Authorization": f"Bearer {GFW_API_TOKEN}"}

engine = create_engine(DB_URI)

def run_pipeline():
    print("1. Loading spatial truth from Supabase...")
    # Pull our 10 Iberian port polygons
    ports_gdf = gpd.read_postgis("SELECT id AS port_zone_id, port_name, geom FROM port_zones", con=engine, geom_col='geom')
    
    # 2. Fetch GFW Data (Placeholder logic for your specific GFW access tier)
    print("2. Fetching 2025 vessel tracks from Global Fishing Watch...")
    
    # Example parameter setup for a GFW API request:
    # We would loop through ports_gdf.bounds to pass exact bounding boxes to the API
    # params = {"start-date": "2025-01-01", "end-date": "2025-12-31", "bbox": "..."}
    
    # --- SIMULATED GFW API RESPONSE FOR ARCHITECTURE DEMO ---
    # In production, this dataframe is built from the requests.get(url).json() payload
    raw_gfw_data = pd.DataFrame({
        'vessel_id': ['MMSI_123', 'MMSI_456', 'MMSI_789'],
        'timestamp': ['2025-01-15T10:00:00Z', '2025-01-15T10:15:00Z', '2025-01-15T10:30:00Z'],
        'speed_knots': [0.1, 12.5, 0.0],
        'lon': [-8.87, -8.95, -9.13], # Coordinates in/around Sines and Lisbon
        'lat': [37.95, 37.90, 38.70]
    })
    # --------------------------------------------------------

    # 3. Convert GFW raw data into a spatial GeoDataFrame
    print("3. Converting API payload to spatial geometries...")
    geometry = [Point(xy) for xy in zip(raw_gfw_data['lon'], raw_raw_data['lat'])]
    tracks_gdf = gpd.GeoDataFrame(raw_gfw_data, crs="EPSG:4326", geometry=geometry)
    
    # 4. THE CORE ENGINE: Spatial Join (Point-in-Polygon)
    print("4. Filtering noise: Running spatial join against port polygons...")
    # This instantly drops any tracking point that is not strictly inside our port boundaries
    filtered_tracks = gpd.sjoin(tracks_gdf, ports_gdf, predicate='within')
    
    # Clean up the dataframe to match our Supabase schema exactly
    final_db_ready_df = filtered_tracks[['vessel_id', 'timestamp', 'speed_knots', 'geometry']]
    
    # 5. Push to Supabase
    if not final_db_ready_df.empty:
        print(f"5. Pushing {len(final_db_ready_df)} validated tracking points to Supabase...")
        final_db_ready_df.to_postgis('vessel_tracks', engine, if_exists='append', index=False)
        print("Pipeline Complete! Data is ready for risk assessment.")
    else:
        print("No vessels detected inside the port boundaries for this time period.")

if __name__ == "__main__":
    run_pipeline()