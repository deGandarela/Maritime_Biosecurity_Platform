import osmnx as ox
import geopandas as pd
import pandas as pd
import time

# Alternative Overpass API mirrors to bypass the main server block
endpoints = [
    "https://lz4.overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.openstreetmap.ru/api/interpreter",
    "https://overpass-api.de/api/interpreter"
]

ox.settings.timeout = 180

port_regions = [
    "Sines, Portugal",
    "Matosinhos, Portugal", 
    "Lisbon, Portugal",
    "Setúbal, Portugal",
    "Aveiro, Portugal",
    "Valencia, Spain",
    "Barcelona, Spain",
    "Algeciras, Spain",
    "Bilbao, Spain",
    "Vigo, Spain"
]

tags = {
    'landuse': 'port',
    'industrial': 'port'
}

print("Fetching high-resolution port polygons using mirror rotation...")

gdf_list = []

for port in port_regions:
    success = False
    
    for endpoint in endpoints:
        if success:
            break
            
        # Point OSMnx to the current mirror in the loop
        ox.settings.overpass_endpoint = endpoint
        print(f"Querying {port} via {endpoint.split('//')[1].split('/')[0]}...")
        
        try:
            gdf = ox.features_from_place(port, tags)
            polygons = gdf[gdf.geometry.type.isin(['Polygon', 'MultiPolygon'])]
            
            if not polygons.empty:
                gdf_list.append(polygons)
                print(f" -> Success: Found {len(polygons)} polygons.")
            else:
                print(" -> No polygons found.")
                
            success = True
            time.sleep(2) # Brief pause before hitting the server for the next port
            
        except Exception as e:
            print(f" -> Connection failed on this mirror. Trying the next one...")
            time.sleep(1)
            
    if not success:
        print(f" -> CRITICAL: Failed to fetch {port} across all available mirrors.")

# Merge and clean data
if gdf_list:
    print("\nMerging and cleaning data...")
    all_ports_gdf = pd.concat(gdf_list)
    
    columns_to_keep = ['name', 'landuse', 'geometry']
    all_ports_gdf = all_ports_gdf[[c for c in columns_to_keep if c in all_ports_gdf.columns]]
    all_ports_gdf = all_ports_gdf.dropna(subset=['name'])
    
    output_file = "iberian_port_boundaries.geojson"
    all_ports_gdf.to_file(output_file, driver="GeoJSON")
    print(f"\nDone! {len(all_ports_gdf)} port polygons saved to {output_file}.")
else:
    print("\nNo data was retrieved. Ensure your local firewall isn't blocking Python network requests.")