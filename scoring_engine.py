import math

# The threats your system tracks
KNOWN_THREATS = ["Golden Mussel", "Carpet Sea Squirt", "Veined Rapa Whelk", "European Green Crab"]

def calculate_final_risk(residency_time_hours, origin_coords, host_coords, month, traffic_volume_multiplier=1.0):
    """
    Calculates the biosecurity risk score (0-100) based on environmental and biological factors.
    """
    
    # 1. Environmental Suitability (Calculated by geographic distance as a placeholder for climate)
    dist = math.sqrt((origin_coords[0] - host_coords[0])**2 + (origin_coords[1] - host_coords[1])**2)
    environmental_similarity = max(0.0, 100.0 - (dist * 1.5))
    
    # 2. Biological Multiplier (Longer residency = higher risk of biofouling)
    if residency_time_hours > 720: # Sat idle for more than 1 month
        biological_multiplier = 2.0
    elif residency_time_hours > 168: # Sat idle for more than 1 week
        biological_multiplier = 1.5
    elif residency_time_hours > 24: # Sat idle for more than 1 day
        biological_multiplier = 1.2
    else:
        biological_multiplier = 1.0

    # 3. Final Computation
    raw_score = environmental_similarity * biological_multiplier * traffic_volume_multiplier
    
    # Cap the maximum score at 100.0
    final_score = min(100.0, raw_score)
    
    # Assign threats if the score flags high
    triggered_threats = KNOWN_THREATS if final_score > 70 else []
    
    return {
        "environmental_similarity": round(environmental_similarity, 2),
        "biological_multiplier_applied": round(biological_multiplier, 2),
        "triggered_threats": triggered_threats,
        "final_risk_score": round(final_score, 1)
    }