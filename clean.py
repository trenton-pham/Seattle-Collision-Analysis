import geopandas as gpd
import pandas as pd
import datetime as dt

def All_Years_Clean():
    gdf = gpd.read_file('data/raw/SDOT_Collision_All_Years.geojson')

    gdf['INCDATE'] = pd.to_datetime(gdf['INCDATE'])
    gdf['YEAR'] = gdf['INCDATE'].dt.year
    gdf = gdf[(gdf["YEAR"] >= 2004) & (gdf['YEAR'] <= 2025)]

    cols_to_drop = [
        'EXCEPTRSNCODE',    
        'EXCEPTRSNDESC',    
        'INATTENTIONIND',   
        'PEDROWNOTGRNT',  
        'SPEEDING',          
        'SHAREDMICROMOBILITYCD',  
        'SHAREDMICROMOBILITYDESC',
        'SDOTCOLNUM',    
        'SPDCASENO',  
        'ST_COLCODE', 
        'ST_COLDESC',
        'REPORTNO',
        'SE_ANNO_CAD_DATA',
        'INCKEY',
        'STATUS',
        'ADDRTYPE',
        'DIAGRAMLINK',
        'SOURCEDESC',
        'ADDDTTM',
        'MODDTTM',
        'OBJECTID',
        'INTKEY',
        'COLLISIONTYPE',
        'REPORTLINK',
        'SEGLANEKEY',
        'CROSSWALKKEY',
        'HITPARKEDCAR',
        'SOURCE'
    ]

    gdf.drop(columns=cols_to_drop, inplace=True)

    moderate_nan_cols = ['UNDERINFL', 'WEATHER', 'ROADCOND', 'LIGHTCOND', 'JUNCTIONTYPE']

    for col in moderate_nan_cols:
        gdf[col].fillna('Unknown', inplace=True)

    gdf['Day_of_Week'] = gdf['INCDATE'].dt.day_name()

    def get_season(month):
        if ((month > 0) & (month < 3)) | (month == 12):
            return 'Winter'
        elif (month > 2) & (month < 6):
            return 'Spring'
        elif (month > 5) & (month < 9):
            return 'Summer'
        elif (month > 8) & (month < 12):
            return 'Fall'

    gdf = gdf.assign(Season=gdf.get('INCDATE').dt.month.apply(get_season))
    gdf

    gdf.to_file('data/cleaned/Collision_All_Filtered.geojson', driver='GeoJSON')

def Vehicles_Clean():
    df_vehicle = pd.read_csv('data/raw/SDOT_Vehicle.csv')

    df_vehicle['Incident Date'] = pd.to_datetime(df_vehicle['Incident Date'])
    df_vehicle['YEAR'] = df_vehicle['Incident Date'].dt.year
    df_vehicle = df_vehicle[(df_vehicle['YEAR'] >= 2004) & (df_vehicle['YEAR'] <= 2025)]

    passenger_vehicle = ['Passenger Car', 'Taxi']
    truck_suv = ['Pickup, Panel Truck or Vannette Under 10,000 lbs']
    two_wheeled_vehicle = ['Motorcycle', 'Moped', 'Scooter Bike']
    commercial_trucks = ['Truck (Flatbed, Van, etc)', 'Truck - Double trailer Combinations', 'Truck Tractor', 'Truck Tractor and Semi-Trailer', 'Truck and Trailer']
    buses = ['Bus or Motor Stage', 'School Bus']
    other = ['Farm Tractor and/or Farm Equipment', 'Other', 'Not Stated', 'Railway Vehicle']

    df_vehicle['ST_VEH_TYPE_DESC'] = df_vehicle['ST_VEH_TYPE_DESC'].replace(passenger_vehicle, 'Passenger Vehicle')
    df_vehicle['ST_VEH_TYPE_DESC'] = df_vehicle['ST_VEH_TYPE_DESC'].replace(truck_suv, 'Truck/SUV')
    df_vehicle['ST_VEH_TYPE_DESC'] = df_vehicle['ST_VEH_TYPE_DESC'].replace(two_wheeled_vehicle, 'Two-Wheeled')
    df_vehicle['ST_VEH_TYPE_DESC'] = df_vehicle['ST_VEH_TYPE_DESC'].replace(commercial_trucks, 'Commercial Trucks')
    df_vehicle['ST_VEH_TYPE_DESC'] = df_vehicle['ST_VEH_TYPE_DESC'].replace(buses, 'Buses')
    df_vehicle['ST_VEH_TYPE_DESC'] = df_vehicle['ST_VEH_TYPE_DESC'].replace(other, 'Other')

    df_vehicle = df_vehicle.dropna(subset=['ST_VEH_TYPE_DESC'])

    df_vehicle_filtered = df_vehicle.get(['COLDETKEY', 'ST_VEH_TYPE_DESC', 'YEAR']).set_index('COLDETKEY')

    df_vehicle_filtered.to_csv('data/cleaned/Vehicle_Filtered.csv')

class main():
    All_Years_Clean()
    Vehicles_Clean()