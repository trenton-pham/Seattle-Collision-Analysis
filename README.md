# Seattle Collision Analysis (SDOT)

For nearly a century, motor collisions have posed a significant public health challenge, contributing to thousands of injuries and deaths annually. In order to support traffic safety for the growing population of Seattle, Washington, the Seattle Department of Transportation (SDOT) launched its Vision Zero initiative in 2015, with the goal of ending traffic deaths and serious injuries in Seattle by 2030.

## Project Overview

This analysis investigates Seattle collision data from 2015 through 2025, focusing on how SDOT's Vision Zero initiative has impacted collision frequency, severity, and spatial patterns.

**Research Questions:**
- How did the spatial distribution and severity of motor-vehicle collisions in Seattle change from pre-2020 to 2020 and onwards?
- Are high-density collision areas more likely to experience severe outcomes (injuries, serious injuries, fatalities)?
- Which geographical areas should SDOT prioritize to ensure that traffic deaths and serious injuries are most effectively reduced by 2030?

## Tech Stack

| Component | Technology |
| --- | --- |
| Data Sources | Seattle Open Data Portal |
| Cleaning & Feature Engineering | Python, Pandas, GeoPandas |
| EDA & Visualization | Pandas, GeoPandas, Matplotlib, Seaborn |
| Spatial Analysis | GeoPandas, SciPy (KDE), Folium |

## Datasets

- `SDOT_Collision_All_Years.geojson` — all collision records (raw); cleaned output: `Collision_All_Filtered.geojson`
- `SDOT_Vehicle.csv` — vehicle-level collision records (raw); cleaned output: `Vehicle_Filtered.csv`

## Cleaning Data
| File | Description |
| --- | --- |
| `clean.py` | Converts date column into datetime, add temporal features (`YEAR`, `MONTH`, `DAY`, `HOUR`, `Season`) and drop columns with high NaN values |

## Notebooks

| Notebook | Description |
| --- | --- |
| `eda.ipynb` | Temporal and categorical EDA: collisions by year, day, season, junction type, severity description, collision type, weather, road condition, light condition, and vehicle type trends |
| `geo.ipynb` | Spatial analysis: interactive heatmap, point maps by severity metric, KDE density estimation, severity index, and downtown vs. outer area comparisons |
| `model.ipynb` | Modeling: creating categorical predictors (risk label), training a baseline decision tree on label-derived features, retraining on label-independent context features to avoid leakage, and plotting each lat/lon bin classification |

## Notebook Information

### `eda.ipynb`
- Temporal trends: Collision counts by year (2004–2025), day of week, and season, revealing the COVID-era dip in 2020 and a decrease in collisions 2020 onwards relative to pre-2020 trends.
- Categorical breakdowns: Distribution of collisions across junction type, severity description, top 10 collision type, weather condition, road condition, and light condition, identifying conditions that are most frequently associated with collisions.
- Vehicle type analysis: Pie chart and year-over-year grouped bar chart (2019–2025) showing how the mix of vehicle types involved in collisions has shifted, including the 2025 increase in truck/SUV involvement relative to passenger vehicles.

### `geo.ipynb`
- Interactive heatmap: A Folium-based heatmap weighted by vehicle count (VEHCOUNT) across all collisions from 2015 onward, providing an interactive map view of collision hotspots.
- Severity index & KDE density estimation: A composite severity score (`SEVERITY`) is computed per collision. Gaussian KDE is then applied separately to pre-2020 and 2020 onward records, and two collision severity maps (an all collisions map and a filtered severe collisions map) and a density difference map (post-2020 − pre-2020) is plotted.
- Downtown vs. outer Seattle comparison: Coordinate masking that isolates downtown collisions. Mean severity and collision counts are compared year-over-year between downtown and outer areas using side-by-side line plots, confirming downtown as a persistent hotspot for both density and severity.
- The processed GeoDataFrame with the engineered severity column is exported to data/processed/Collision_Processed.geojson for use in downstream modeling.

### `model.ipynb`
- Grid aggregation: Collisions are grouped into 150×150 lat/lon bins. Each bin is summarized by collision count, mean severity, total injuries, serious injuries, fatalities, average vehicle count, and average pedestrian count, forming the feature set for modeling.
- Risk predictor engineering: A composite risk score is computed per grid cell by standardizing collision count and mean severity, then combining them with a weighted sum (60% density, 40% severity). Scores are then quartile-binned into four categories: Very Low Risk, Low Risk, Medium Risk, High Risk, and Very High Risk.
- Decision tree classifier: A decision tree tree is trained on a feature set that describes zone context: spatial positions (`cell_lat`, `cell_lon`), temporal ratios (`peak_hour`, `night_ratio`, `weekend_ratio`, `winter_ratio`, `summer_ratio`), collision mix (`ped_involvement_ratio`, `cyclist_involvement_ratio`), and road structure (`intersection_ratio`, parsed from the `LOCATION` string).
- Evaluation: Test set performance is reported by accuracy score, a full classification report (precision, recall, F1 per risk class), a feature importance bar chart, and a confusion matrix. This surfaces which risk tiers are hardest to distinguish and which features drive classification most.
- Spatial visualization: Grid cell centroids are recovered by parsing the interval bin labels, and each bin is plotted as a point on a map colored by predicted risk label, providing a spatial view of the model's zone-level risk classifications across Seattle.

## EDA Findings

- Collision frequency are noticeably less 2020 onwards compared to pre-2020.
- Intersection-related collisions account for a large proportion of collisions.
- Collision density had a spatial shift from downtown Seattle to outer areas, specifically southern Seattle, from pre-2020 to 2020 and onwards. This means that although downtown Seattle remains a hotspot in terms of collision severity and frequency, the 2020 and onward distribution suggests a redistribution of collision density into outer areas.

## Model Findings

- The decision tree classifies grid cells into three risk tiers with **68.4% 5-fold CV accuracy** and **66.6% test accuracy**.
- Class-level performance is asymmetric: **Low Risk** zones are identified most reliably (F1 = 0.74), while **High Risk** zones show **high precision (0.84) but low recall (0.51)**. When the model flags a zone as high-risk it is usually correct, but it misses roughly half of the true high-risk zones, which default into the Medium tier.
- **Medium Risk** acts as the model's uncertainty bucket (precision 0.54, recall 0.72) — Cells whose context features sit in the middle of the distribution get pushed there, inflating recall at the cost of precision.
- Pedestrian involvement (`ped_involvement_ratio`) and seasonal distribution (`summer_ratio`, `winter_ratio`) carry most of the predictive weight compared to location cells (`cell_lon`, `cell_lat`). This suggests that what kind of activity a zone sees (pedestrian-heavy or seasonally skewed) is a stronger risk signal than where the zone sits geographically, meaning risk patterns generalize across Seattle rather than being confined to specific hotspots.

## Current Caveats
- The year 2020 and potentially 2021 resulted in a disruption of collision trends due to the COVID-19 pandemic. When future studies are conducted, it is best to exclude these years.
- Although the raw dataset `SDOT_Collision_All_Years.geojson` was updated and retrieved in March 2026, the collision count for the month of December 2025 is mildly lower relative to the collision trends in previous years. This may indicate that all collision data have yet to be uploaded.

## Next Steps
- Concluding
- (Uncertain) Creating interactive dashboard and deploy

## Learning Outcomes
- Working with government-sourced data and handling missing values and formatting issues, along with feature engineering on raw records.
- Applying geospatial tools, such as Geopandas and Folium for spatial data manipulation and visualizations.
- Performing kernel density estimation (KDE) with SciPy to model spatial distributions and difference/comparison maps.
- Building a supervised classification model to predict collision risk levels per zone.

## Credits & Sources
- Seattle Open Data Portal - https://data.seattle.gov
- COGS 108 (UC San Diego) Repository - https://github.com/cogs108
- Claude Code

## Author
**Trenton Pham** <br>
Data Science @ UC San Diego