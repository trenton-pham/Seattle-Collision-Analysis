# Vision Zero Collision Analysis (Seattle, WA)

For nearly a century, motor collisions have posed a significant public health challenge, contributing to thousands of injuries and deaths annually. In order to support traffic safety for the growing population of Seattle, Washington, the Seattle Department of Transportation (SDOT) launched its Vision Zero initiative in 2015, with the goal of ending traffic deaths and serious injuries in Seattle by 2030.

## Project Overview

This analysis investigates Seattle collision data from 2015 through 2025, focusing on how SDOT's Vision Zero initiative has impacted collision frequency, severity, and spatial patterns. A central finding is that while total collision frequency declined after 2020, severe and fatal outcomes became a larger share of recorded collisions, suggesting that lower collision volume does not necessarily mean safer streets.

**Research Questions:**
- How did the spatial distribution and severity of motor-vehicle collisions in Seattle change from pre-2020 to 2020 and onwards?
- Are high-density collision areas more likely to experience severe outcomes (injuries, serious injuries, fatalities)?
- Which geographical areas should SDOT prioritize to ensure that traffic deaths and serious injuries are most effectively reduced by 2030?
- How can collision risk analysis be expanded to better understand safe access to public transportation, walking, biking, and other urban mobility patterns?

## Tech Stack

| Component | Technology |
| --- | --- |
| Data Sources | Seattle Open Data Portal |
| Cleaning & Feature Engineering | Python, Pandas, GeoPandas |
| EDA & Visualization | Pandas, GeoPandas, Matplotlib, Seaborn |
| Spatial Analysis | GeoPandas, SciPy (KDE), Folium |
| Modeling | Pandas, GeoPandas, NumPy, Scikit-learn |
| Dashboard | Python, Matplotlib, GeoPandas, Streamlit |

## Datasets

- `SDOT_Collision_All_Years.geojson` — all collision records (raw); cleaned output: `Collision_All_Filtered.geojson`
- `SDOT_Vehicle.csv` — vehicle-level collision records (raw); cleaned output: `Vehicle_Filtered.csv`
- `Collision_Processed.parquet` — processed collision dataset used by the Streamlit dashboard and modeling notebook
- `Neighborhood_Map_Atlas_Neighborhoods.geojson` — Seattle neighborhood boundaries used for dashboard mapping

The raw and cleaned datasets are excluded from version control because of file size. The processed parquet file is included so the main dashboard and modeling workflow can run without requiring the full raw data download.

## Cleaning Data
| File | Description |
| --- | --- |
| `clean.py` | Converts date columns into datetime, adds temporal features (`YEAR`, `MONTH`, `DAY`, `HOUR`, `Season`), standardizes vehicle categories, drops high-missingness fields, and exports cleaned/processed files |

## Notebooks

| Notebook | Description |
| --- | --- |
| `eda.ipynb` | Temporal and categorical EDA: collisions by year, month, day, hour, season, junction type, severity description, collision type, weather, road condition, light condition, pedestrian/cyclist involvement, and vehicle type trends |
| `geo.ipynb` | Spatial analysis: interactive heatmap, point maps by severity metric, KDE density estimation, severity index, downtown vs. outer area comparisons, and processed data export |
| `model.ipynb` | Modeling: creating zone-level risk labels, training a decision tree, and experimenting with hyperparameter tuning using GridSearchCV and RandomizedSearchCV |

## Notebook Information

### `eda.ipynb`
- Temporal trends: Collision counts by year (2015–2025), month, day of week, hour of day, and season, revealing the COVID-era dip in 2020 and a decrease in total collisions 2020 onwards relative to pre-2020 trends.
- Categorical breakdowns: Distribution of collisions across junction type, severity description, top 10 collision type, weather condition, road condition, and light condition, identifying conditions that are most frequently associated with collisions.
- Pedestrian and cyclist involvement: Yearly aggregation of total pedestrian and cyclist counts involved in collisions, supporting a stronger focus on vulnerable road users.
- Vehicle type analysis: Pie chart and year-over-year grouped bar chart (2019–2025) showing how the mix of vehicle types involved in collisions has shifted.

### `geo.ipynb`
- Interactive heatmap: A Folium-based heatmap weighted by vehicle count (`VEHCOUNT`) across all collisions from 2015 onward, providing an interactive map view of collision hotspots.
- Severity index & KDE density estimation: A composite severity score (`SEVERITY`) is computed per collision. Gaussian KDE is then applied separately to pre-2020 and 2020 onward records, and two collision severity maps (an all collisions map and a filtered severe collisions map) and a density difference map (post-2020 − pre-2020) is plotted.
- Downtown vs. outer Seattle comparison: Coordinate masking that isolates downtown collisions. Mean severity and collision counts are compared year-over-year between downtown and outer areas using side-by-side line plots, confirming downtown as a persistent hotspot for both density and severity.
- The processed GeoDataFrame with the engineered severity column is exported to `data/processed/Collision_Processed.geojson` and `data/processed/Collision_Processed.parquet` for downstream modeling and dashboard use.

### `model.ipynb`
- Grid aggregation: Collisions are grouped into 150×150 lat/lon bins. Each bin is summarized by collision count, mean severity, total injuries, serious injuries, fatalities, average vehicle count, and average pedestrian count, forming the feature set for modeling.
- Risk predictor engineering: A composite risk score is computed per grid cell by standardizing collision count and mean severity, then combining them with a weighted sum (60% density, 40% severity). Scores are then binned into three relative risk categories: Low Risk, Medium Risk, and High Risk.
- Decision tree classifier: A decision tree is trained on a feature set that describes zone context: spatial cells (`cell_lat`, `cell_lon`), temporal ratios (`peak_hour`, `night_ratio`, `weekend_ratio`, `winter_ratio`, `summer_ratio`), collision mix (`avg_vehicle_count`, `avg_pedestrian_count`), and road structure (`intersection_ratio`, parsed from the `LOCATION` string).
- Evaluation: Test set performance is reported by accuracy score, a full classification report (precision, recall, F1 per risk class), a feature importance bar chart, and a confusion matrix. This surfaces which risk tiers are hardest to distinguish and which features drive classification most.
- Spatial visualization: Grid cell centroids are recovered by parsing the interval bin labels, and each bin is plotted as a point on a map colored by predicted risk label, providing a spatial view of the model's zone-level risk classifications across Seattle.

## Dashboard

| File | Description |
| --- | --- |
| `app.py` | Streamlit dashboard using the processed parquet and Seattle neighborhood map to display filtered collision metrics, heatmaps, KDE density, spatial shift, and downtown vs. outer Seattle comparisons |

Run locally with:

```bash
streamlit run app.py
```

## EDA Findings

- Collision frequency is noticeably lower 2020 onwards compared to pre-2020.
- Although total collisions decreased after 2020, severe/fatal outcomes became a larger share of recorded collisions. Serious/fatal collision records increased from about 1.46% of pre-2020 collisions to about 3.19% of 2020 onward collisions.
- Intersection-related collisions account for a large proportion of collisions.
- Collision density had a spatial shift from downtown Seattle to outer areas, specifically southern Seattle, from pre-2020 to 2020 and onwards. This means that although downtown Seattle remains a hotspot in terms of collision severity and frequency, the 2020 and onward distribution suggests a redistribution of collision density into outer areas.
- When filtering collisions to only include `SERIOUSINJURIES` and `FATALITY` collisions, the mean severity shows inconsistent trends for downtown areas, with the mean severity peaking in 2024 from 2015 to 2025. Outer areas remain fairly stable after their peak in 2015, but haven't shown any meaningful improvements since 2016.

## Model Findings

- The decision tree classifies grid cells into three relative risk tiers with **70.2% 5-fold CV accuracy** and **69.5% test accuracy**.
- After implementing hyperparameter tuning, High Risk recall improved from **0.51** in the baseline model to **0.67** using GridSearchCV. This means the tuned model identified a larger share of true high-risk zones.
- Medium Risk recall decreased during tuning, meaning the model became better at identifying higher-risk zones while losing some performance in the middle class.
- Pedestrian involvement (`avg_pedestrian_count`) and seasonal distribution (`summer_ratio`, `winter_ratio`) carry most of the predictive weight compared to spatial cells (`cell_lon`, `cell_lat`). This suggests that what kind of activity a zone sees (pedestrian-heavy or seasonally skewed) is a stronger risk signal than where the zone sits geographically, meaning risk patterns generalize across Seattle rather than being confined to specific hotspots.

## Deliverables
Check out the visualization dashboard here (work in progress): <br>
[https://vision-zero-collision-dashboard.streamlit.app](https://vision-zero-collision-dashboard.streamlit.app)

## Current Caveats
- The year 2020 and potentially 2021 resulted in a disruption of collision trends due to the COVID-19 pandemic. When future studies are conducted, it is best to exclude these years.
- Although the raw dataset `SDOT_Collision_All_Years.geojson` was updated and retrieved in March 2026, the collision count for the month of December 2025 is mildly lower relative to the collision trends in previous years. This may indicate that all collision data have yet to be uploaded.
- When modeling, an equal `qcut` into thirds is used when labeling risk values for each zone (low, medium, high); however, this represents relative risk ranking rather than absolute danger or true future collision probability.
- The model currently predicts a risk label derived from historical collision density and severity. A future version should use temporal validation, such as training on earlier years and testing on later years, to better evaluate future risk prediction.
- Downtown vs. outer-area density comparisons currently use latitude/longitude coordinate masking. Future spatial density work should use projected geometry and exposure measures such as traffic volume, population, transit ridership, or pedestrian activity.

## Next Steps
- Enhancing modeling: comparison with RandomForestClassifier, SVC (in a StandardScaler -> SVC pipeline), and time-based train/test splits for future-risk evaluation.
- Refining risk labels: create labels based on severe/fatal outcomes, exposure-adjusted collision rates, or empirically defined Vision Zero priority thresholds rather than only equal-frequency bins.
- Expanding into public transportation and urban studies: overlay collisions with bus stops, light rail stations, high-frequency transit corridors, bike lanes, school zones, and pedestrian-heavy areas to study safe access to transit.
- Building an equity and access layer: compare collision burden by neighborhood, transit access, and vulnerable road user involvement to identify where street-safety interventions would have the highest public value.
- Deploying the Streamlit dashboard and adding interactive layers for neighborhoods, transit corridors, severe collisions, and model-predicted risk zones.

## Learning Outcomes
- Working with government-sourced data and handling missing values and formatting issues, along with feature engineering on raw records.
- Applying geospatial tools, such as GeoPandas and Folium for spatial data manipulation and visualizations.
- Performing kernel density estimation (KDE) with SciPy to model spatial distributions and difference/comparison maps.
- Building a supervised classification model with hyperparameter tuning to classify relative collision risk levels per zone.
- Translating notebook analysis into an interactive Streamlit dashboard for public-facing exploration.
- Connecting data science methods to urban safety, public transportation access, and Vision Zero policy questions.

## Credits & Sources
- Seattle Open Data Portal - https://data.seattle.gov
- COGS 108 (UC San Diego) Repository - https://github.com/cogs108
- Claude Code / Codex assistance

## Author
**Trenton Pham** <br>
Data Science @ UC San Diego
