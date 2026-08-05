import os
import glob
import geopandas as gpd
from sqlalchemy import create_engine
import warnings

# Suppress minor Shapely warnings
warnings.filterwarnings('ignore')

# 1. Configure your Supabase Connection string
# Find this in Supabase -> Project Settings -> Database -> Connection string (URI)
# It should look something like: postgresql://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres
DB_URI = "postgresql://postgres:@CasadaBouca3@db.ntbhkrfwibgmulwbotts.supabase.co:5432/postgres"
engine = create_engine(DB_URI)

# 2. Get all GeoJSON files in the current directory
geojson_files = glob.glob("*.geojson")
print(f"Found {len(geojson_files)} port files. Beginning ingestion...")

for file in geojson_files:
    port_name = file.replace('.geojson', '').capitalize()
    country = "Spain" if port_name in ["Vigo", "Bilbao", "Algeciras", "Barcelona", "Valencia"] else "Portugal"
    
    print(f"Processing {port_name}...")
    
    try:
        # Load the GeoJSON
        gdf = gpd.read_file(file)
        
        # Ensure coordinates are standard WGS 84 (GPS)
        if gdf.crs is None or gdf.crs.to_epsg() != 4326:
            gdf = gdf.set_crs(epsg=4326, allow_override=True)
        
        # 3. The Architecture Fix: Convert 1D Lines to 2D Polygons (approx 50m buffer)
        # 0.0005 degrees is roughly 50 meters at these latitudes
        gdf['geometry'] = gdf['geometry'].apply(
            lambda geom: geom.buffer(0.0005) if geom.geom_type in ['LineString', 'MultiLineString'] else geom
        )
        
        # Create a clean dataframe matching our SQL schema
        clean_gdf = gpd.GeoDataFrame({
            'port_name': [port_name] * len(gdf),
            'country': [country] * len(gdf),
            'geometry': gdf['geometry']
        }, crs="EPSG:4326")
        
        # 4. Push directly into the Supabase PostGIS table
        clean_gdf.to_postgis('port_zones', engine, if_exists='append', index=False)
        print(f" -> Successfully inserted {len(clean_gdf)} zones for {port_name}.")
        
    except Exception as e:
        print(f" -> ERROR processing {port_name}: {e}")

print("\nIngestion complete! Check your Supabase database.")