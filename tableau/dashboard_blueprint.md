# Two-dashboard Tableau blueprint

Use a fixed desktop size of **1280 × 800** while building, then test the public
view at narrower browser widths. Use tiled containers for the main structure.

## Visual system

| Role | Color |
|---|---|
| Dashboard background | `#0E1117` |
| Panel background | `#161B22` |
| Divider/border | `#30363D` |
| Primary text | `#E6EDF3` |
| Secondary text | `#8B949E` |
| Blue accent / Downtown | `#3B82F6` |
| Orange comparison / Outer | `#F97316` |

Use a clean sans-serif font, 18–22 pt dashboard titles, 10–12 pt chart labels,
and 24–30 pt KPI values. Remove heavy gridlines and legends that repeat titles.

## Dashboard 1 — Overview & Hotspots

### Filters

Create these as compact controls across the top or in a left rail:

1. `IncidentYear`: range of values.
2. `OutcomeClass`: multiple values dropdown.
3. `LargeNeighborhood`: multiple values dropdown.
4. `Neighborhood`: multiple values dropdown.
5. `Map Weight`: parameter control.

Apply the first four filters to every worksheet on Dashboard 1 that uses the
collision fact. Do not apply `IncidentYear` to Dashboard 2.

### KPI row

Create one text worksheet per measure and place five equal cards:

1. Collision Count.
2. Mean Severity.
3. Serious Injuries.
4. Fatalities.
5. Severe Collision Share.

Use panel background, a subtle one-pixel border, and a short label above the value.

### Collision density map

1. Double-click `Longitude`, then `Latitude`.
2. Set Marks to **Density**.
3. Put `SUM(Map Weight Row)` on Color/Intensity.
4. Use an orange-red sequential palette over the charcoal basemap.
5. Put Collision Count, Vehicles Involved, Serious Injuries, Fatalities,
   Neighborhood, and IncidentYear in the tooltip.
6. Default `Map Weight` to `Collisions`.

This replaces the Streamlit KDE calculations. Do not add Python visuals or a
custom KDE extension.

### Trend charts

Create two separate line charts:

- `IncidentYear` versus Collision Count.
- `IncidentYear` versus Severe Collision Share.

Use a continuous year axis, label the final mark only, and keep zero in the
collision-count axis. Do not combine measures with unrelated scales.

### Footer

Add the `Refresh Caption` worksheet and a source link to the
[SDOT data catalog](https://catalog.data.gov/dataset/sdot-collisions-all-years).

## Dashboard 2 — Spatial Change

### Fixed comparison controls

Show the `Comparison Outcome Selection` parameter as a single-value dropdown.
Default it to `All outcomes`. Put `Keep Change for Comparison Outcome = True`
on the map and ranking. Do not add `IncidentYear` to those sheets.

### Neighborhood change map

Use the spatial-blending procedure in `README.md`:

1. `Geometry` from `Seattle Neighborhood Geometry` creates the marks.
2. `NeighborhoodID` is on Detail and is the active blend link.
3. `AnnualDensityChange` from `NeighborhoodChange` is on Color.
4. Use a blue-to-red diverging palette with **Center = 0**; blue is decrease,
   red is increase.
5. Tooltip: Neighborhood, Zone, AreaSqMi, PreAnnualDensity,
   PostAnnualDensity, AnnualDensityChange, TotalCollisionCount,
   SeriousInjuries, and Fatalities.

### Downtown versus Outer trends

Create two line sheets from `FactCollisions` related to `DimNeighborhood`:

- `IncidentYear` versus Annual Collision Density, colored by `Zone`.
- `IncidentYear` versus Mean Severity, colored by `Zone`.

Filter `Zone` to Downtown and Outer. Use blue for Downtown and orange for Outer.
Put `Keep Fact for Comparison Outcome = True` on both trend sheets so the same
parameter controls the fact data without altering the fixed comparison years.

### Neighborhood ranking

Build a highlight table with one row per Neighborhood and these columns:

1. PreAnnualDensity.
2. PostAnnualDensity.
3. AnnualDensityChange.
4. TotalCollisionCount.
5. SeriousInjuries.
6. Fatalities.

Sort descending by AnnualDensityChange. Add a top-N parameter only if the full
94-row table feels too dense; default to 15.

### Explanatory note

Use this exact text:

> The comparison is descriptive, not causal. The 2020–2021 period was disrupted
> by pandemic-related changes in travel. Rates are annual collision counts per
> square mile; they do not adjust for traffic, population, or pedestrian exposure.

## Interaction rules

- Map selection filters the ranking and highlights the trend sheets.
- Ranking selection highlights the corresponding polygon.
- Dashboard 1 filters do not carry to Dashboard 2.
- Dashboard 2 outcome selection affects the map, ranking, and trends while the
  comparison-table period years stay fixed.
- Keep animations off and avoid third-party extensions.
