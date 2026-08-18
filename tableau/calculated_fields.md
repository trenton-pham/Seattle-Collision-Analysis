# Tableau calculated fields

Create these in the `Seattle Collision Data` source. Keep the names exactly as
shown so the dashboard blueprint is easy to follow.

## KPI measures

### Collision Count

```tableau
COUNTD([CollisionID])
```

### Mean Severity

```tableau
SUM([SeverityScore]) / COUNTD([CollisionID])
```

### Serious Injuries

```tableau
SUM([SeriousInjuries])
```

### Fatalities

```tableau
SUM([Fatalities])
```

### Severe Collision Count

```tableau
COUNTD(IF [IsSevere] THEN [CollisionID] END)
```

### Severe Collision Share

```tableau
[Severe Collision Count] / [Collision Count]
```

Format as a percentage with one decimal place.

### Vehicles Involved

```tableau
SUM([VehicleCount])
```

## Area and density

These calculations rely on the logical relationship to `DimNeighborhood`.
Do not use them after physically joining area onto collision rows.

### Selected Area Sq Mi

```tableau
SUM([AreaSqMi])
```

### Annual Collision Density

Use on a view containing `IncidentYear` and either `Neighborhood` or `Zone`.

```tableau
[Collision Count] / [Selected Area Sq Mi]
```

For Page 2, use the already validated `PreAnnualDensity`, `PostAnnualDensity`,
and `AnnualDensityChange` fields from `NeighborhoodChange`. Their fixed periods
are 2015–2019 and 2020–`LatestCompleteYear`, so an Overview year filter cannot
change the comparison.

## Map-weight toggle

Create a string parameter named `Map Weight` with two values:

- `Collisions`
- `Vehicles`

Set `Collisions` as the default.

### Map Weight Row

```tableau
IF [Map Weight] = "Vehicles" THEN [VehicleCount]
ELSE 1
END
```

Use `SUM([Map Weight Row])` as the density-map weight.

## Page 2 outcome control

Create a string parameter named `Comparison Outcome Selection` with these values:

- `All outcomes`
- `No reported injury`
- `Injury`
- `Serious injury`
- `Fatal`

### Keep Fact for Comparison Outcome

```tableau
[Comparison Outcome Selection] = "All outcomes"
OR [OutcomeClass] = [Comparison Outcome Selection]
```

### Keep Change for Comparison Outcome

```tableau
[ComparisonOutcome] = [Comparison Outcome Selection]
```

Place the appropriate field on Filters and keep `True`. This single parameter
can then update the polygon map, ranking, and Downtown/Outer trend sheets while
the pre/post year boundaries remain fixed.

## Labels

### Refresh Caption

```tableau
"Data through " + STR(MIN([LatestIncidentDate]))
+ " • pipeline " + LEFT(ATTR([PipelineRunUtc]), 19)
```

### Comparison Period Caption

```tableau
STR(MIN([PreStartYear])) + "–" + STR(MIN([PreEndYear]))
+ " vs "
+ STR(MIN([PostStartYear])) + "–" + STR(MIN([PostEndYear]))
```

### Change Direction

```tableau
IF SUM([AnnualDensityChange]) > 0 THEN "Increase"
ELSEIF SUM([AnnualDensityChange]) < 0 THEN "Decrease"
ELSE "No change"
END
```

## Recommended formatting

| Field | Format |
|---|---|
| Collision and injury counts | Number, 0 decimals, thousands separator |
| Mean Severity | Number, 2 decimals on cards; 6 decimals during reconciliation |
| Severe Collision Share | Percentage, 1 decimal |
| AreaSqMi | Number, 2 decimals |
| Density measures | Number, 1 decimal |
| DensityPercentChange | Percentage, 1 decimal |
