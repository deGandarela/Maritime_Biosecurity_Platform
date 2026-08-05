import pandas as pd

def calculate_residency_time(filtered_tracks):
    print("Calculating stationary residency times...")
    
    # 1. Ensure time data is properly formatted
    filtered_tracks['timestamp'] = pd.to_datetime(filtered_tracks['timestamp'])
    
    # 2. Sort chronologically to ensure time flows forward for each specific vessel
    df = filtered_tracks.sort_values(by=['vessel_id', 'timestamp']).copy()
    
    # 3. Calculate the time delta (in hours) between consecutive AIS pings
    df['time_delta_hours'] = df.groupby('vessel_id')['timestamp'].diff().dt.total_seconds() / 3600.0
    
    # 4. The Logic Gate: Flag only the points where the vessel is effectively docked
    df['is_docked'] = df['speed_knots'] < 0.5
    
    # 5. Filter for docked periods and sum the time deltas per vessel, per port
    docked_periods = df[df['is_docked']]
    
    residency_summary = docked_periods.groupby(
        ['vessel_id', 'port_zone_id']
    )['time_delta_hours'].sum().reset_index()
    
    # Rename the aggregated column for clarity
    residency_summary = residency_summary.rename(
        columns={'time_delta_hours': 'residency_hours'}
    )
    
    # 6. Optional: Filter out noise (e.g., ships that dropped below 0.5 for less than 2 hours)
    # This prevents brief anchoring or tugboat maneuvering from triggering false alerts
    valid_visits = residency_summary[residency_summary['residency_hours'] >= 2.0]
    
    print(f"Calculated {len(valid_visits)} valid port visits.")
    return valid_visits

# --- Integration Example ---
# Assuming `filtered_tracks` is the output from our GeoPandas spatial join in Step 2:
# final_residency_data = calculate_residency_time(filtered_tracks)