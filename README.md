# Seattle Collision Analysis (SDOT)

For nearly a century, motor collisions have posed a significant public health challenge, contributing to thousands of injuries and deaths annually. In order to support traffic safety for the growing population of Seattle, Washington, the Seattle Department of Transportation (SDOT) launched its Vision Zero initiative in 2015, with the goal of ending traffic deaths and serious injuries in Seattle by 2030.

## Project Overview

This analysis investigates Seattle collision data from 2015 through 2025, focusing on how SDOT's Vision Zero initiative has impacted collision frequency, severity, and spatial patterns.

**Research Questions:**
- How did the spatial distribution and severity of motor-vehicle collisions in Seattle change from pre-2020 to post-2020?
- Are high-density collision areas more likely to experience severe outcomes (injuries, serious injuries, fatalities)?

## Tech Stack

| Component | Technology |
| --- | --- |
| Data Sources | Seattle Open Data Portal |
| Cleaning & Feature Engineering | Python, Pandas, GeoPandas |
| EDA & Visualization | Pandas, GeoPandas, Matplotlib, Seaborn |
| Spatial Analysis | GeoPandas, SciPy (KDE), Folium |

## Notebooks

| Notebook | Description |
| --- | --- |
| `eda.ipynb` | Temporal and categorical EDA: collisions by year, day, season, junction type, severity description, collision type, weather, road condition, light condition, and vehicle type trends |
| `geo.ipynb` | Spatial analysis: interactive heatmap, point maps by severity metric, KDE density estimation, severity index, and downtown vs. outer area comparisons |
| `model.ipynb` | Modeling: creating categorical predictors (risk label), modeling decision tree (5-fold CV), and plotting each lat/lon bin classification |

## Datasets

- `SDOT_Collision_All_Years.geojson` — all collision records (raw); cleaned output: `Collision_All_Filtered.geojson`
- `SDOT_Vehicle.csv` — vehicle-level collision records (raw); cleaned output: `Vehicle_Filtered.csv`

## Abstract Findings

- Collision frequency peaked in pre-2020 years, with a dip during 2020 due to COVID. Trends are still noticeably less post-2020 compared to pre-2020.
- Winter and rainfall conditions are likely contributing factors to collision count.
- Most collisions occur under clear weather and dry road conditions, but other adverse conditions (e.g., wet conditions) still play a factor.
- Intersection and mid-block junction types account for a large proportion of collisions.
- Passenger vehicles represent the majority of collision counts across most years; however, 2025 showed trucks/SUVs having higher collision counts compared to passenger vehicles.
- Downtown Seattle remains a spatial hotspot for both collision density and severity.

## Next Steps
- Enhancing visualizations
- Writing 2-3 sentence description for visualizations
- Finalizing decision tree modeling
- Create and deploy dashboard application

## Credits & Sources
- Seattle Open Data Portal - https://data.seattle.gov
- COGS 108 (UC San Diego) Repository - https://github.com/cogs108
- Claude by Anthropic