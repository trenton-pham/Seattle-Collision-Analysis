# Tableau migration QA checklist

Record the result and date for each check before replacing Streamlit.

## Data reconciliation

For the checked-in snapshot, select all years, all outcomes, and all neighborhoods.
The workbook must show:

| Metric | Expected |
|---|---:|
| Collisions | 103,801 |
| Mean severity | 0.410333 |
| Serious injuries | 2,141 |
| Fatalities | 276 |
| Severe collisions | 2,243 |
| No reported injury rows | 75,596 |
| Injury rows | 25,962 |
| Serious injury rows | 1,977 |
| Fatal rows | 266 |
| Neighborhood match rate | 98.6002% |
| Unmatched/Unknown rows | 1,453 |

The four outcome row counts must sum to 103,801. Fatal rows differ from total
fatalities because one collision can contain more than one fatality.

## Data-model checks

- [ ] `CollisionID` is unique and no card inflates after adding neighborhood fields.
- [ ] Unknown-neighborhood collisions remain in Page 1 totals.
- [ ] `ExcludedMissingGeometryRows` is reviewed; SDOT records without coordinates are not plotted or imported.
- [ ] The neighborhood dimension contains 94 official polygons plus one Unknown row.
- [ ] Downtown is based on `L_HOOD = Downtown`, not a coordinate rectangle.
- [ ] Total official neighborhood area is approximately 83.6224 square miles.
- [ ] `LatestCompleteYear` is used for Page 2’s post period.
- [ ] `RefreshMetadata` contains exactly one row with `ValidationStatus = Passed`.

## Interaction checks

- [ ] Every Page 1 filter updates the KPI cards, density map, and both trend charts.
- [ ] An empty filter selection produces a clear empty state, not a misleading zero.
- [ ] The Page 2 year periods do not change when the Page 1 year range changes.
- [ ] The Page 2 outcome choice updates both the polygon map and ranking.
- [ ] Selecting a map polygon filters or highlights the ranking correctly.
- [ ] Selecting a ranking row highlights the same neighborhood polygon.
- [ ] Tooltips use readable names and units.

## Refresh checks

- [ ] A manual GitHub Actions run succeeds.
- [ ] The Google Sheet’s four canonical tabs change only after validation passes.
- [ ] A deliberately invalid local input fails before any upload.
- [ ] Tableau Public’s **Request Update** changes the displayed pipeline timestamp.
- [ ] The next scheduled monthly GitHub run starts at 6:00 AM Pacific.
- [ ] Tableau Public reflects the changed Google Sheet within its next 24-hour window.

## Performance checks

Use **Help > Settings and Performance > Start Performance Recording**, interact
with each dashboard, then stop the recording.

- [ ] Ordinary charts render in under two seconds.
- [ ] Maps render in under three seconds.
- [ ] A complete dashboard filter update finishes in under five seconds.
- [ ] No worksheet produces an unexpectedly large mark count.
- [ ] Unused fields are hidden before the final public publish.

## Public-safety checks

- [ ] Open the viz in a signed-out/private browser window.
- [ ] No street addresses, report links, or unused source columns are exposed.
- [ ] Downloadable underlying data contains only the prepared public fields.
- [ ] Source, latest incident date, refresh time, and pandemic caveat are visible.

Run this checklist for the initial release and two consecutive scheduled monthly
refreshes before retiring Streamlit.
