from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, Polygon

from tableau_prep import ValidationError, prepare_tables, write_outputs


RUN_TIME = datetime(2026, 1, 2, 14, 0, tzinfo=timezone.utc)
SOURCE_METADATA = {
    "source_url": "test-source",
    "source_catalog_url": "test-catalog",
    "source_last_modified_utc": "2026-01-01T00:00:00Z",
}


def collisions() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {
            "COLDETKEY": [1, 2, 3, 4, 5],
            "INCDATE": pd.to_datetime(
                ["2015-06-01", "2019-06-01", "2020-06-01", "2024-06-01", "2025-06-01"]
            ),
            "VEHCOUNT": [2, 1, 3, 2, 1],
            "INJURIES": [0, 1, 1, 1, 2],
            "SERIOUSINJURIES": [0, 0, 1, 0, 1],
            "FATALITIES": [0, 0, 0, 1, 0],
        },
        geometry=[
            Point(-122.40, 47.55),
            Point(-122.40, 47.55),
            Point(-122.40, 47.55),
            Point(-122.30, 47.65),
            Point(-122.30, 47.65),
        ],
        crs="EPSG:4326",
    )


def neighborhoods() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {
            "OBJECTID": [10, 20],
            "L_HOOD": ["Southwest", "Downtown"],
            "S_HOOD": ["West", "Core"],
        },
        geometry=[
            Polygon([(-122.45, 47.50), (-122.35, 47.50), (-122.35, 47.60), (-122.45, 47.60)]),
            Polygon([(-122.35, 47.60), (-122.25, 47.60), (-122.25, 47.70), (-122.35, 47.70)]),
        ],
        crs="EPSG:4326",
    )


class TableauPreparationTests(unittest.TestCase):
    def prepare(self, **kwargs):
        return prepare_tables(
            collisions(),
            neighborhoods(),
            SOURCE_METADATA,
            run_time=RUN_TIME,
            **kwargs,
        )

    def test_derives_outcomes_severity_and_official_downtown(self):
        tables = self.prepare()
        fact = tables["fact_collisions"].set_index("CollisionID")
        self.assertEqual(fact.loc[1, "OutcomeClass"], "No reported injury")
        self.assertEqual(fact.loc[2, "OutcomeClass"], "Injury")
        self.assertEqual(fact.loc[3, "OutcomeClass"], "Serious injury")
        self.assertEqual(fact.loc[4, "OutcomeClass"], "Fatal")
        self.assertEqual(fact.loc[3, "SeverityScore"], 4)
        self.assertEqual(fact.loc[4, "SeverityScore"], 6)
        self.assertTrue(bool(fact.loc[5, "IsSevere"]))

        dimension = tables["dim_neighborhood"].set_index("NeighborhoodID")
        self.assertEqual(dimension.loc[20, "Zone"], "Downtown")
        self.assertGreater(dimension.loc[20, "AreaSqMi"], 0)

    def test_builds_fixed_pre_post_comparison(self):
        change = self.prepare()["neighborhood_change"]
        row = change.loc[
            change["NeighborhoodID"].eq(10) & change["ComparisonOutcome"].eq("All outcomes")
        ].iloc[0]
        self.assertEqual(row["PreCollisionCount"], 2)
        self.assertEqual(row["PostCollisionCount"], 1)
        self.assertEqual(row["PreYears"], 5)
        self.assertEqual(row["PostYears"], 6)

    def test_rejects_duplicate_collision_ids(self):
        source = collisions()
        source.loc[1, "COLDETKEY"] = 1
        with self.assertRaisesRegex(ValidationError, "unique and non-null"):
            prepare_tables(source, neighborhoods(), SOURCE_METADATA, run_time=RUN_TIME)

    def test_rejects_missing_required_source_column(self):
        source = collisions().drop(columns=["FATALITIES"])
        with self.assertRaisesRegex(ValidationError, "missing required columns"):
            prepare_tables(source, neighborhoods(), SOURCE_METADATA, run_time=RUN_TIME)

    def test_rejects_invalid_incident_date(self):
        source = collisions()
        source["INCDATE"] = source["INCDATE"].astype("object")
        source.loc[0, "INCDATE"] = "not-a-date"
        with self.assertRaisesRegex(ValidationError, "Incident dates"):
            prepare_tables(source, neighborhoods(), SOURCE_METADATA, run_time=RUN_TIME)

    def test_rejects_negative_counts(self):
        source = collisions()
        source.loc[0, "VEHCOUNT"] = -1
        with self.assertRaisesRegex(ValidationError, "negative"):
            prepare_tables(source, neighborhoods(), SOURCE_METADATA, run_time=RUN_TIME)

    def test_rejects_large_row_decrease(self):
        with self.assertRaisesRegex(ValidationError, "fell by"):
            self.prepare(previous_count=10)

    def test_metadata_reconciles_input_and_geometry_exclusions(self):
        source_metadata = {
            **SOURCE_METADATA,
            "source_feature_count": 7,
            "excluded_missing_geometry_rows": 2,
        }
        metadata = prepare_tables(
            collisions(), neighborhoods(), source_metadata, run_time=RUN_TIME
        )["refresh_metadata"].iloc[0]
        self.assertEqual(metadata["InputRowCount"], 7)
        self.assertEqual(metadata["OutputRowCount"], 5)
        self.assertEqual(metadata["ExcludedMissingGeometryRows"], 2)

    def test_rejects_low_neighborhood_coverage(self):
        source = collisions()
        source.loc[0, "geometry"] = Point(-122.49, 47.79)
        with self.assertRaisesRegex(ValidationError, "coverage"):
            prepare_tables(source, neighborhoods(), SOURCE_METADATA, run_time=RUN_TIME)

    def test_outputs_are_reproducible_with_fixed_run_time(self):
        tables = self.prepare()
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            write_outputs(tables, first)
            write_outputs(self.prepare(), second)
            for filename in [
                "FactCollisions.csv",
                "DimNeighborhood.csv",
                "RefreshMetadata.csv",
                "NeighborhoodChange.csv",
                "neighborhoods.geojson",
            ]:
                self.assertEqual((Path(first) / filename).read_bytes(), (Path(second) / filename).read_bytes())


if __name__ == "__main__":
    unittest.main()
