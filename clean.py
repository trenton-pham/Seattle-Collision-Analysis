import geopandas as gpd
import pandas as pd


def all_years_clean():
    gdf = gpd.read_file("data/raw/SDOT_Collision_All_Years.geojson")

    gdf["INCDATE"] = pd.to_datetime(gdf["INCDATE"], errors="coerce")
    gdf["YEAR"] = gdf["INCDATE"].dt.year
    gdf["MONTH"] = gdf["INCDATE"].dt.month
    gdf["DAY"] = gdf["INCDATE"].dt.day

    gdf["INCDTTM"] = pd.to_datetime(gdf["INCDTTM"], errors="coerce")
    gdf["HOUR"] = gdf["INCDTTM"].dt.hour
    gdf = gdf[(gdf["YEAR"] >= 2004) & (gdf["YEAR"] <= 2025)].copy()

    cols_to_drop = [
        "EXCEPTRSNCODE",
        "EXCEPTRSNDESC",
        "INATTENTIONIND",
        "PEDROWNOTGRNT",
        "SPEEDING",
        "SHAREDMICROMOBILITYCD",
        "SHAREDMICROMOBILITYDESC",
        "SDOTCOLNUM",
        "SPDCASENO",
        "ST_COLCODE",
        "ST_COLDESC",
        "REPORTNO",
        "SE_ANNO_CAD_DATA",
        "INCKEY",
        "STATUS",
        "ADDRTYPE",
        "DIAGRAMLINK",
        "SOURCEDESC",
        "ADDDTTM",
        "MODDTTM",
        "OBJECTID",
        "INTKEY",
        "COLLISIONTYPE",
        "REPORTLINK",
        "SEGLANEKEY",
        "CROSSWALKKEY",
        "HITPARKEDCAR",
        "SOURCE",
    ]

    gdf = gdf.drop(columns=cols_to_drop, errors="ignore")

    moderate_nan_cols = ["UNDERINFL", "WEATHER", "ROADCOND", "LIGHTCOND", "JUNCTIONTYPE"]

    for col in moderate_nan_cols:
        if col in gdf.columns:
            gdf[col] = gdf[col].fillna("Unknown")

    gdf["Day_of_Week"] = gdf["INCDATE"].dt.day_name()

    def get_season(month):
        if pd.isna(month):
            return "Unknown"
        if month in (12, 1, 2):
            return "Winter"
        if month in (3, 4, 5):
            return "Spring"
        if month in (6, 7, 8):
            return "Summer"
        if month in (9, 10, 11):
            return "Fall"
        return "Unknown"

    gdf = gdf.assign(Season=gdf["MONTH"].apply(get_season))

    gdf.to_file("data/cleaned/Collision_All_Filtered.geojson", driver="GeoJSON")
    return gdf


def vehicles_clean():
    df_vehicle = pd.read_csv("data/raw/SDOT_Vehicle.csv")

    df_vehicle["Incident Date"] = pd.to_datetime(df_vehicle["Incident Date"], errors="coerce")
    df_vehicle["YEAR"] = df_vehicle["Incident Date"].dt.year
    df_vehicle = df_vehicle[(df_vehicle["YEAR"] >= 2004) & (df_vehicle["YEAR"] <= 2025)].copy()

    vehicle_type_map = {
        "Passenger Car": "Passenger Vehicle",
        "Taxi": "Passenger Vehicle",
        "Pickup, Panel Truck or Vannette Under 10,000 lbs": "Truck/SUV",
        "Motorcycle": "Two-Wheeled",
        "Moped": "Two-Wheeled",
        "Scooter Bike": "Two-Wheeled",
        "Truck (Flatbed, Van, etc)": "Commercial Trucks",
        "Truck - Double trailer Combinations": "Commercial Trucks",
        "Truck Tractor": "Commercial Trucks",
        "Truck Tractor and Semi-Trailer": "Commercial Trucks",
        "Truck and Trailer": "Commercial Trucks",
        "Bus or Motor Stage": "Buses",
        "School Bus": "Buses",
        "Farm Tractor and/or Farm Equipment": "Other",
        "Other": "Other",
        "Not Stated": "Other",
        "Railway Vehicle": "Other",
    }

    df_vehicle["ST_VEH_TYPE_DESC"] = df_vehicle["ST_VEH_TYPE_DESC"].replace(vehicle_type_map)
    df_vehicle = df_vehicle.dropna(subset=["ST_VEH_TYPE_DESC"])

    df_vehicle_filtered = df_vehicle[["COLDETKEY", "ST_VEH_TYPE_DESC", "YEAR"]].set_index("COLDETKEY")

    df_vehicle_filtered.to_csv("data/cleaned/Vehicle_Filtered.csv")
    return df_vehicle_filtered


def gdf_to_parquet():
    gdf = gpd.read_file("data/processed/Collision_Processed.geojson")
    gdf.to_parquet("data/processed/Collision_Processed.parquet", index=False)
    return gdf


# Backwards-compatible aliases for older notebook references.
All_Years_Clean = all_years_clean
Vehicles_Clean = vehicles_clean


if __name__ == "__main__":
    gdf_to_parquet()
