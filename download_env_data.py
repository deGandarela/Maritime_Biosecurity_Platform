import copernicusmarine

print("Initiating connection to the Copernicus Marine Data Store...")

# 1. Download Temperature (thetao)
print("Downloading Sea Surface Temperature (thetao)...")
copernicusmarine.subset(
    dataset_id="cmems_mod_glo_phy-thetao_anfc_0.083deg_P1M-m",  # The specific temperature dataset
    variables=["thetao"],                          
    start_datetime="2025-01-01T00:00:00",
    end_datetime="2025-12-31T23:59:59",
    minimum_longitude=-12.0,                             
    maximum_longitude=-5.0,                              
    minimum_latitude=35.0,                               
    maximum_latitude=45.0,                               
    minimum_depth=0.49,                                  
    maximum_depth=0.5,
    output_filename="iberian_temperature_2025.nc",
    output_directory=r"c:\Users\Gustavo\Desktop\DocsGustavo\Project_Shipsonic",
    overwrite=True
)

# 2. Download Salinity (so)
print("Downloading Salinity (so)...")
copernicusmarine.subset(
    dataset_id="cmems_mod_glo_phy-so_anfc_0.083deg_P1M-m",      # The specific salinity dataset
    variables=["so"],                          
    start_datetime="2025-01-01T00:00:00",
    end_datetime="2025-12-31T23:59:59",
    minimum_longitude=-12.0,                             
    maximum_longitude=-5.0,                              
    minimum_latitude=35.0,                               
    maximum_latitude=45.0,                               
    minimum_depth=0.49,                                  
    maximum_depth=0.5,
    output_filename="iberian_salinity_2025.nc",
    output_directory=r"c:\Users\Gustavo\Desktop\DocsGustavo\Project_Shipsonic",
    overwrite=True
)

print("Subsetting complete! Both files successfully saved.")