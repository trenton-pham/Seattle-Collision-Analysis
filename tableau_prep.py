"""Prepare validated, Tableau-friendly Seattle collision data.

The module can read the checked-in parquet snapshot for local development or
download the current SDOT ArcGIS layer for scheduled production refreshes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


ARCGIS_LAYER_URL = (
    "https://services.arcgis.com/ZOyb2t4B0UYuYNYH/arcgis/rest/services/"
    "SDOT_Collisions_All_Years_1/FeatureServer/0"
)
DATA_CATALOG_URL = "https://catalog.data.gov/dataset/sdot-collisions-all-years"
START_YEAR = 2015
PRE_END_YEAR = 2019
POST_START_YEAR = 2020
MIN_NEIGHBORHOOD_COVERAGE = 0.98
MAX_ROW_DECREASE = 0.05
MAX_MISSING_GEOMETRY_SHARE = 0.05
EXPECTED_NEIGHBORHOODS = 94

REQUIRED_SOURCE_COLUMNS = {
    "COLDETKEY",
    "INCDATE",
    "VEHCOUNT",
    "INJURIES",
    "SERIOUSINJURIES",
    "FATALITIES",
    "geometry",
}
COUNT_COLUMNS = ["VEHCOUNT", "INJURIES", "SERIOUSINJURIES", "FATALITIES"]
OUTCOME_ORDER = ["No reported injury", "Injury", "Serious injury", "Fatal"]

FACT_COLUMNS = [
    "CollisionID",
    "IncidentDate",
    "IncidentYear",
    "Latitude",
    "Longitude",
    "Injuries",
    "SeriousInjuries",
    "Fatalities",
    "VehicleCount",
    "SeverityScore",
    "OutcomeClass",
    "OutcomeSort",
    "IsSevere",
    "NeighborhoodID",
    "RefreshKey",
]


class ValidationError(RuntimeError):
    """Raised when a refresh is unsafe to publish."""


def _utc_iso(value: datetime | pd.Timestamp) -> str:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")
    else:
        timestamp = timestamp.tz_convert("UTC")
    return timestamp.floor("s").isoformat().replace("+00:00", "Z")


def _parse_datetime_series(values: pd.Series) -> pd.Series:
    if pd.api.types.is_datetime64_any_dtype(values.dtype):
        return pd.to_datetime(values, errors="coerce", utc=True).dt.tz_localize(None)
    numeric = pd.to_numeric(values, errors="coerce")
    numeric_share = float(numeric.notna().mean()) if len(values) else 0.0
    if numeric_share > 0.95 and numeric.dropna().abs().median() > 10_000_000_000:
        return pd.to_datetime(numeric, unit="ms", errors="coerce", utc=True).dt.tz_localize(None)
    return pd.to_datetime(values, errors="coerce", utc=True, format="mixed").dt.tz_localize(None)


def _requests_session() -> requests.Session:
    retry = Retry(
        total=5,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET", "POST"}),
    )
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers.update({"User-Agent": "seattle-collision-tableau-pipeline/1.0"})
    return session


def download_arcgis_collisions(
    layer_url: str = ARCGIS_LAYER_URL,
    start_year: int = START_YEAR,
) -> tuple[gpd.GeoDataFrame, dict[str, str]]:
    """Download all collision features from the authoritative ArcGIS layer."""

    session = _requests_session()
    metadata_response = session.get(layer_url, params={"f": "json"}, timeout=60)
    metadata_response.raise_for_status()
    layer_metadata = metadata_response.json()
    if "error" in layer_metadata:
        raise RuntimeError(f"ArcGIS metadata request failed: {layer_metadata['error']}")

    object_id_field = layer_metadata.get("objectIdField", "OBJECTID")
    where = f"INCDATE >= DATE '{start_year}-01-01 00:00:00'"
    ids_response = session.post(
        f"{layer_url}/query",
        data={"f": "json", "where": where, "returnIdsOnly": "true"},
        timeout=120,
    )
    ids_response.raise_for_status()
    ids_payload = ids_response.json()
    if "error" in ids_payload:
        raise RuntimeError(f"ArcGIS ID query failed: {ids_payload['error']}")

    object_ids = sorted(ids_payload.get("objectIds") or [])
    if not object_ids:
        raise ValidationError("The ArcGIS source returned no collision records.")

    fields = ",".join(
        [object_id_field, "COLDETKEY", "INCDATE", "VEHCOUNT", "INJURIES", "SERIOUSINJURIES", "FATALITIES"]
    )
    frames: list[gpd.GeoDataFrame] = []
    chunk_size = min(int(layer_metadata.get("maxRecordCount", 2000)), 1000)
    for offset in range(0, len(object_ids), chunk_size):
        chunk = object_ids[offset : offset + chunk_size]
        response = session.post(
            f"{layer_url}/query",
            data={
                "f": "geojson",
                "objectIds": ",".join(str(value) for value in chunk),
                "outFields": fields,
                "returnGeometry": "true",
                "outSR": "4326",
            },
            timeout=180,
        )
        response.raise_for_status()
        payload = response.json()
        if "error" in payload:
            raise RuntimeError(f"ArcGIS feature query failed: {payload['error']}")
        frames.append(gpd.GeoDataFrame.from_features(payload.get("features", []), crs="EPSG:4326"))

    collisions = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs="EPSG:4326")
    source_feature_count = len(collisions)
    missing_geometry = collisions.geometry.isna() | collisions.geometry.is_empty
    missing_geometry_count = int(missing_geometry.sum())
    missing_geometry_share = missing_geometry_count / source_feature_count
    if missing_geometry_share > MAX_MISSING_GEOMETRY_SHARE:
        raise ValidationError(
            f"The source has {missing_geometry_count:,} records without point geometry "
            f"({missing_geometry_share:.2%}); the allowed maximum is "
            f"{MAX_MISSING_GEOMETRY_SHARE:.2%}."
        )
    collisions = collisions.loc[~missing_geometry].copy()
    edit_millis = (layer_metadata.get("editingInfo") or {}).get("lastEditDate")
    source_modified = ""
    if edit_millis:
        source_modified = _utc_iso(pd.to_datetime(edit_millis, unit="ms", utc=True))
    return collisions, {
        "source_url": layer_url,
        "source_catalog_url": DATA_CATALOG_URL,
        "source_last_modified_utc": source_modified,
        "source_feature_count": source_feature_count,
        "excluded_missing_geometry_rows": missing_geometry_count,
    }


def read_collision_source(source: str, start_year: int = START_YEAR) -> tuple[gpd.GeoDataFrame, dict[str, str]]:
    if source.startswith(("http://", "https://")):
        return download_arcgis_collisions(source, start_year)

    source_path = Path(source)
    if not source_path.exists():
        raise FileNotFoundError(f"Collision source not found: {source_path}")
    if source_path.suffix.lower() == ".parquet":
        collisions = gpd.read_parquet(source_path)
    else:
        collisions = gpd.read_file(source_path)
    modified = datetime.fromtimestamp(source_path.stat().st_mtime, tz=timezone.utc)
    return collisions, {
        "source_url": f"local-snapshot:{source_path.name}",
        "source_catalog_url": DATA_CATALOG_URL,
        "source_last_modified_utc": _utc_iso(modified),
    }


def read_neighborhoods(path: str | Path, expected_count: int = EXPECTED_NEIGHBORHOODS) -> gpd.GeoDataFrame:
    neighborhoods = gpd.read_file(path)
    required = {"OBJECTID", "L_HOOD", "S_HOOD", "geometry"}
    missing = sorted(required.difference(neighborhoods.columns))
    if missing:
        raise ValidationError(f"Neighborhood source is missing required columns: {', '.join(missing)}")
    if neighborhoods.crs is None:
        raise ValidationError("Neighborhood geometry has no coordinate reference system.")
    neighborhoods = neighborhoods.to_crs("EPSG:4326")
    if neighborhoods["OBJECTID"].isna().any() or not neighborhoods["OBJECTID"].is_unique:
        raise ValidationError("Neighborhood OBJECTID values must be unique and non-null.")
    if neighborhoods.geometry.isna().any() or not neighborhoods.geometry.is_valid.all():
        raise ValidationError("Neighborhood polygons contain missing or invalid geometry.")
    if len(neighborhoods) != expected_count:
        raise ValidationError(f"Expected {expected_count} neighborhoods, found {len(neighborhoods)}.")
    return neighborhoods


def _prepare_collision_fields(collisions: gpd.GeoDataFrame, start_year: int) -> gpd.GeoDataFrame:
    missing = sorted(REQUIRED_SOURCE_COLUMNS.difference(collisions.columns))
    if missing:
        raise ValidationError(f"Collision source is missing required columns: {', '.join(missing)}")
    if collisions.crs is None:
        raise ValidationError("Collision geometry has no coordinate reference system.")

    work = collisions.copy().to_crs("EPSG:4326")
    work["INCDATE"] = _parse_datetime_series(work["INCDATE"])
    if work["INCDATE"].isna().any():
        raise ValidationError("Incident dates contain missing or invalid values.")
    work = work.loc[work["INCDATE"].dt.year.ge(start_year)].copy()
    if work.empty:
        raise ValidationError(f"No collision rows remain after filtering to {start_year} onward.")

    if work["COLDETKEY"].isna().any() or not work["COLDETKEY"].is_unique:
        raise ValidationError("Collision IDs must be unique and non-null.")
    if (work["INCDATE"].dt.date > datetime.now(timezone.utc).date()).any():
        raise ValidationError("Incident dates contain future values.")
    if work.geometry.isna().any() or work.geometry.is_empty.any():
        raise ValidationError("Collision coordinates contain missing geometry.")
    if not work.geometry.geom_type.eq("Point").all():
        raise ValidationError("Every collision geometry must be a point.")

    work["Longitude"] = work.geometry.x
    work["Latitude"] = work.geometry.y
    coordinate_ok = work["Longitude"].between(-122.5, -122.2) & work["Latitude"].between(47.45, 47.80)
    if not coordinate_ok.all():
        raise ValidationError(f"Found {(~coordinate_ok).sum():,} coordinates outside the Seattle validation bounds.")

    for column in COUNT_COLUMNS:
        numeric = pd.to_numeric(work[column], errors="coerce")
        if numeric.isna().any():
            raise ValidationError(f"{column} contains missing or non-numeric values.")
        if (numeric < 0).any():
            raise ValidationError(f"{column} contains negative values.")
        if not (numeric % 1 == 0).all():
            raise ValidationError(f"{column} contains non-integer values.")
        work[column] = numeric.astype("int64")

    work["SeverityScore"] = (
        work["INJURIES"] + 3 * work["SERIOUSINJURIES"] + 5 * work["FATALITIES"]
    ).astype("int64")
    expected_severity = work["INJURIES"] + 3 * work["SERIOUSINJURIES"] + 5 * work["FATALITIES"]
    if not work["SeverityScore"].equals(expected_severity.astype("int64")):
        raise ValidationError("Severity-score verification failed.")

    work["OutcomeClass"] = "No reported injury"
    work.loc[work["INJURIES"].gt(0), "OutcomeClass"] = "Injury"
    work.loc[work["SERIOUSINJURIES"].gt(0), "OutcomeClass"] = "Serious injury"
    work.loc[work["FATALITIES"].gt(0), "OutcomeClass"] = "Fatal"
    outcome_sort = {label: index for index, label in enumerate(OUTCOME_ORDER)}
    work["OutcomeSort"] = work["OutcomeClass"].map(outcome_sort).astype("int64")
    work["IsSevere"] = work["SERIOUSINJURIES"].gt(0) | work["FATALITIES"].gt(0)
    return work


def _build_neighborhood_dimension(neighborhoods: gpd.GeoDataFrame) -> tuple[pd.DataFrame, gpd.GeoDataFrame]:
    projected = neighborhoods.to_crs("EPSG:2285")
    area_sq_mi = projected.geometry.area / (5280.0**2)
    spatial = neighborhoods[["OBJECTID", "L_HOOD", "S_HOOD", "geometry"]].copy()
    spatial["NeighborhoodID"] = spatial["OBJECTID"].astype("int64")
    spatial["LargeNeighborhood"] = spatial["L_HOOD"].fillna("Unknown").astype(str)
    spatial["Neighborhood"] = spatial["S_HOOD"].fillna("Unknown").astype(str)
    spatial["Zone"] = spatial["LargeNeighborhood"].eq("Downtown").map({True: "Downtown", False: "Outer"})
    spatial["AreaSqMi"] = area_sq_mi.to_numpy()

    dimension = spatial[
        ["NeighborhoodID", "LargeNeighborhood", "Neighborhood", "AreaSqMi", "Zone"]
    ].copy()
    unknown = pd.DataFrame(
        [{
            "NeighborhoodID": -1,
            "LargeNeighborhood": "Unknown",
            "Neighborhood": "Unknown",
            "AreaSqMi": 0.0,
            "Zone": "Unknown",
        }]
    )
    dimension = pd.concat([dimension, unknown], ignore_index=True).sort_values("NeighborhoodID")
    dimension["NeighborhoodID"] = dimension["NeighborhoodID"].astype("int64")
    return dimension.reset_index(drop=True), spatial


def _assign_neighborhoods(
    collisions: gpd.GeoDataFrame,
    spatial: gpd.GeoDataFrame,
    min_coverage: float,
) -> tuple[gpd.GeoDataFrame, float]:
    lookup = spatial[["NeighborhoodID", "geometry"]]
    joined = gpd.sjoin(collisions, lookup, how="left", predicate="within")
    if len(joined) != len(collisions):
        raise ValidationError("Spatial join duplicated collision rows; neighborhood polygons may overlap.")
    matched = joined["NeighborhoodID"].notna()
    match_rate = float(matched.mean())
    if match_rate < min_coverage:
        raise ValidationError(
            f"Neighborhood coverage is {match_rate:.2%}; required minimum is {min_coverage:.2%}."
        )
    joined["NeighborhoodID"] = joined["NeighborhoodID"].fillna(-1).astype("int64")
    return joined.drop(columns=["index_right"], errors="ignore"), match_rate


def _latest_complete_year(incident_dates: pd.Series, run_time: datetime) -> int:
    latest_year = int(incident_dates.dt.year.max())
    return min(latest_year, run_time.year - 1)


def _build_fact(collisions: gpd.GeoDataFrame) -> pd.DataFrame:
    fact = pd.DataFrame(
        {
            "CollisionID": collisions["COLDETKEY"].astype("int64"),
            "IncidentDate": collisions["INCDATE"].dt.strftime("%Y-%m-%d"),
            "IncidentYear": collisions["INCDATE"].dt.year.astype("int64"),
            "Latitude": collisions["Latitude"],
            "Longitude": collisions["Longitude"],
            "Injuries": collisions["INJURIES"].astype("int64"),
            "SeriousInjuries": collisions["SERIOUSINJURIES"].astype("int64"),
            "Fatalities": collisions["FATALITIES"].astype("int64"),
            "VehicleCount": collisions["VEHCOUNT"].astype("int64"),
            "SeverityScore": collisions["SeverityScore"].astype("int64"),
            "OutcomeClass": collisions["OutcomeClass"],
            "OutcomeSort": collisions["OutcomeSort"].astype("int64"),
            "IsSevere": collisions["IsSevere"].astype(bool),
            "NeighborhoodID": collisions["NeighborhoodID"].astype("int64"),
            "RefreshKey": 1,
        }
    )
    return fact[FACT_COLUMNS].sort_values("CollisionID").reset_index(drop=True)


def _build_neighborhood_change(
    fact: pd.DataFrame,
    dimension: pd.DataFrame,
    latest_complete_year: int,
) -> pd.DataFrame:
    comparison_fact = fact.loc[fact["IncidentYear"].le(latest_complete_year)].copy()
    neighborhoods = dimension.loc[dimension["NeighborhoodID"].ne(-1)].copy()
    pre_years = PRE_END_YEAR - START_YEAR + 1
    post_years = latest_complete_year - POST_START_YEAR + 1
    if post_years <= 0:
        raise ValidationError("The data does not contain a completed post-2020 comparison period.")

    frames: list[pd.DataFrame] = []
    for outcome in ["All outcomes", *OUTCOME_ORDER]:
        subset = comparison_fact
        if outcome != "All outcomes":
            subset = subset.loc[subset["OutcomeClass"].eq(outcome)]

        pre = subset.loc[subset["IncidentYear"].between(START_YEAR, PRE_END_YEAR)]
        post = subset.loc[subset["IncidentYear"].between(POST_START_YEAR, latest_complete_year)]
        pre_counts = pre.groupby("NeighborhoodID").size()
        post_counts = post.groupby("NeighborhoodID").size()
        all_counts = subset.groupby("NeighborhoodID").size()
        serious = subset.groupby("NeighborhoodID")["SeriousInjuries"].sum()
        fatalities = subset.groupby("NeighborhoodID")["Fatalities"].sum()

        result = neighborhoods.copy()
        result["ComparisonOutcome"] = outcome
        result["PreStartYear"] = START_YEAR
        result["PreEndYear"] = PRE_END_YEAR
        result["PostStartYear"] = POST_START_YEAR
        result["PostEndYear"] = latest_complete_year
        result["PreYears"] = pre_years
        result["PostYears"] = post_years
        result["PreCollisionCount"] = result["NeighborhoodID"].map(pre_counts).fillna(0).astype("int64")
        result["PostCollisionCount"] = result["NeighborhoodID"].map(post_counts).fillna(0).astype("int64")
        result["TotalCollisionCount"] = result["NeighborhoodID"].map(all_counts).fillna(0).astype("int64")
        result["SeriousInjuries"] = result["NeighborhoodID"].map(serious).fillna(0).astype("int64")
        result["Fatalities"] = result["NeighborhoodID"].map(fatalities).fillna(0).astype("int64")
        result["PreAnnualCollisions"] = result["PreCollisionCount"] / pre_years
        result["PostAnnualCollisions"] = result["PostCollisionCount"] / post_years
        result["PreAnnualDensity"] = result["PreAnnualCollisions"] / result["AreaSqMi"]
        result["PostAnnualDensity"] = result["PostAnnualCollisions"] / result["AreaSqMi"]
        result["AnnualDensityChange"] = result["PostAnnualDensity"] - result["PreAnnualDensity"]
        result["DensityPercentChange"] = result["AnnualDensityChange"].div(
            result["PreAnnualDensity"].replace(0, pd.NA)
        )
        frames.append(result)

    change = pd.concat(frames, ignore_index=True)
    outcome_order = {"All outcomes": -1, **{value: index for index, value in enumerate(OUTCOME_ORDER)}}
    change["ComparisonOutcomeSort"] = change["ComparisonOutcome"].map(outcome_order)
    columns = [
        "NeighborhoodID",
        "LargeNeighborhood",
        "Neighborhood",
        "Zone",
        "AreaSqMi",
        "ComparisonOutcome",
        "ComparisonOutcomeSort",
        "PreStartYear",
        "PreEndYear",
        "PostStartYear",
        "PostEndYear",
        "PreYears",
        "PostYears",
        "PreCollisionCount",
        "PostCollisionCount",
        "TotalCollisionCount",
        "SeriousInjuries",
        "Fatalities",
        "PreAnnualCollisions",
        "PostAnnualCollisions",
        "PreAnnualDensity",
        "PostAnnualDensity",
        "AnnualDensityChange",
        "DensityPercentChange",
    ]
    return change[columns].sort_values(["ComparisonOutcomeSort", "NeighborhoodID"]).reset_index(drop=True)


def _previous_output_count(path: str | Path | None) -> int | None:
    if not path:
        return None
    previous_path = Path(path)
    if not previous_path.exists() or previous_path.stat().st_size == 0:
        return None
    previous = pd.read_csv(previous_path)
    if previous.empty or "OutputRowCount" not in previous.columns:
        raise ValidationError("Previous refresh metadata does not contain OutputRowCount.")
    return int(previous.iloc[0]["OutputRowCount"])


def _validate_row_count(current_count: int, previous_count: int | None, max_decrease: float) -> None:
    if previous_count is None or previous_count <= 0:
        return
    decrease = (previous_count - current_count) / previous_count
    if decrease > max_decrease:
        raise ValidationError(
            f"Collision count fell by {decrease:.2%} ({previous_count:,} to {current_count:,}); "
            f"the allowed decrease is {max_decrease:.2%}."
        )


def prepare_tables(
    collisions: gpd.GeoDataFrame,
    neighborhoods: gpd.GeoDataFrame,
    source_metadata: dict[str, str],
    *,
    run_time: datetime | None = None,
    start_year: int = START_YEAR,
    min_coverage: float = MIN_NEIGHBORHOOD_COVERAGE,
    previous_count: int | None = None,
    max_row_decrease: float = MAX_ROW_DECREASE,
) -> dict[str, Any]:
    run_time = run_time or datetime.now(timezone.utc)
    if run_time.tzinfo is None:
        run_time = run_time.replace(tzinfo=timezone.utc)

    prepared = _prepare_collision_fields(collisions, start_year)
    dimension, spatial = _build_neighborhood_dimension(neighborhoods)
    assigned, match_rate = _assign_neighborhoods(prepared, spatial, min_coverage)
    fact = _build_fact(assigned)
    _validate_row_count(len(fact), previous_count, max_row_decrease)

    latest_complete = _latest_complete_year(prepared["INCDATE"], run_time)
    change = _build_neighborhood_change(fact, dimension, latest_complete)
    data_fingerprint = hashlib.sha256(
        fact.to_csv(index=False, lineterminator="\n").encode("utf-8")
    ).hexdigest()
    outcome_counts = fact["OutcomeClass"].value_counts()
    severe_count = int(fact["IsSevere"].sum())
    metadata = pd.DataFrame(
        [{
            "RefreshKey": 1,
            "PipelineRunUtc": _utc_iso(run_time),
            "SourceUrl": source_metadata.get("source_url", ""),
            "SourceCatalogUrl": source_metadata.get("source_catalog_url", DATA_CATALOG_URL),
            "SourceLastModifiedUtc": source_metadata.get("source_last_modified_utc", ""),
            "InputRowCount": int(source_metadata.get("source_feature_count", len(prepared))),
            "OutputRowCount": len(fact),
            "ExcludedMissingGeometryRows": int(
                source_metadata.get("excluded_missing_geometry_rows", 0)
            ),
            "LatestIncidentDate": prepared["INCDATE"].max().strftime("%Y-%m-%d"),
            "LatestCompleteYear": latest_complete,
            "NeighborhoodMatchRate": match_rate,
            "UnmatchedNeighborhoodRows": int(fact["NeighborhoodID"].eq(-1).sum()),
            "MinimumYear": int(fact["IncidentYear"].min()),
            "MaximumYear": int(fact["IncidentYear"].max()),
            "MeanSeverity": float(fact["SeverityScore"].mean()),
            "SevereCollisionRows": severe_count,
            "SeriousInjuryCount": int(fact["SeriousInjuries"].sum()),
            "FatalityCount": int(fact["Fatalities"].sum()),
            "VehicleCount": int(fact["VehicleCount"].sum()),
            "FatalRows": int(outcome_counts.get("Fatal", 0)),
            "SeriousInjuryRows": int(outcome_counts.get("Serious injury", 0)),
            "InjuryRows": int(outcome_counts.get("Injury", 0)),
            "NoReportedInjuryRows": int(outcome_counts.get("No reported injury", 0)),
            "DataFingerprint": data_fingerprint,
            "ValidationStatus": "Passed",
        }]
    )
    if int(outcome_counts.sum()) != len(fact):
        raise ValidationError("Outcome classes do not total to the collision count.")

    geojson = spatial[
        ["NeighborhoodID", "LargeNeighborhood", "Neighborhood", "Zone", "AreaSqMi", "geometry"]
    ].sort_values("NeighborhoodID")
    return {
        "fact_collisions": fact,
        "dim_neighborhood": dimension,
        "refresh_metadata": metadata,
        "neighborhood_change": change,
        "neighborhoods_geojson": geojson,
    }


def write_outputs(tables: dict[str, Any], output_dir: str | Path) -> None:
    output_path = Path(output_dir)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.mkdir(parents=True, exist_ok=True)
    filenames = {
        "fact_collisions": "FactCollisions.csv",
        "dim_neighborhood": "DimNeighborhood.csv",
        "refresh_metadata": "RefreshMetadata.csv",
        "neighborhood_change": "NeighborhoodChange.csv",
        "neighborhoods_geojson": "neighborhoods.geojson",
    }
    with tempfile.TemporaryDirectory(prefix="tableau-refresh-", dir=output_path.parent) as temp_dir:
        temp_path = Path(temp_dir)
        for key, filename in filenames.items():
            destination = temp_path / filename
            if key == "neighborhoods_geojson":
                tables[key].to_file(destination, driver="GeoJSON")
            else:
                tables[key].to_csv(destination, index=False, lineterminator="\n")
        for filename in filenames.values():
            os.replace(temp_path / filename, output_path / filename)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        default=ARCGIS_LAYER_URL,
        help="ArcGIS layer URL, parquet path, or GeoJSON path (default: authoritative SDOT layer).",
    )
    parser.add_argument(
        "--neighborhoods",
        default="data/processed/Neighborhood_Map_Atlas_Neighborhoods.geojson",
        help="Seattle neighborhood GeoJSON path.",
    )
    parser.add_argument("--output-dir", default="data/tableau", help="Directory for Tableau outputs.")
    parser.add_argument(
        "--previous-metadata",
        help="Optional previous RefreshMetadata.csv used for the row-decrease guard.",
    )
    parser.add_argument(
        "--run-time",
        help="Optional ISO-8601 UTC run time, useful for exact reproducibility tests.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    run_time = pd.Timestamp(args.run_time).to_pydatetime() if args.run_time else None
    collisions, source_metadata = read_collision_source(args.source)
    neighborhoods = read_neighborhoods(args.neighborhoods)
    previous_count = _previous_output_count(args.previous_metadata)
    tables = prepare_tables(
        collisions,
        neighborhoods,
        source_metadata,
        run_time=run_time,
        previous_count=previous_count,
    )
    write_outputs(tables, args.output_dir)

    metadata = tables["refresh_metadata"].iloc[0]
    summary = {
        "status": metadata["ValidationStatus"],
        "rows": int(metadata["OutputRowCount"]),
        "latest_incident_date": metadata["LatestIncidentDate"],
        "latest_complete_year": int(metadata["LatestCompleteYear"]),
        "neighborhood_match_rate": round(float(metadata["NeighborhoodMatchRate"]), 6),
        "data_fingerprint": metadata["DataFingerprint"],
        "output_dir": str(Path(args.output_dir).resolve()),
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
