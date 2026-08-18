"""Publish validated Tableau tables to Google Sheets without partial updates."""

from __future__ import annotations

import argparse
import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import google.auth
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
TABLE_FILES = {
    "FactCollisions": "FactCollisions.csv",
    "DimNeighborhood": "DimNeighborhood.csv",
    "RefreshMetadata": "RefreshMetadata.csv",
    "NeighborhoodChange": "NeighborhoodChange.csv",
}
STAGING_PREFIX = "__next_"
WRITE_CHUNK_ROWS = 5_000


def _credentials():
    credential_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if credential_json:
        info = json.loads(credential_json)
        return service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    credential_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if credential_path:
        credentials, _ = google.auth.load_credentials_from_file(credential_path, scopes=SCOPES)
        return credentials
    credentials, _ = google.auth.default(scopes=SCOPES)
    return credentials


def _service():
    return build("sheets", "v4", credentials=_credentials(), cache_discovery=False)


def _sheet_map(service: Any, spreadsheet_id: str) -> dict[str, int]:
    spreadsheet = service.spreadsheets().get(
        spreadsheetId=spreadsheet_id,
        fields="sheets.properties(sheetId,title)",
    ).execute()
    return {
        sheet["properties"]["title"]: int(sheet["properties"]["sheetId"])
        for sheet in spreadsheet.get("sheets", [])
    }


def _quoted_sheet(title: str) -> str:
    return "'" + title.replace("'", "''") + "'"


def _delete_staging_tabs(service: Any, spreadsheet_id: str) -> None:
    sheets = _sheet_map(service, spreadsheet_id)
    requests = [
        {"deleteSheet": {"sheetId": sheet_id}}
        for title, sheet_id in sheets.items()
        if title.startswith(STAGING_PREFIX)
    ]
    if requests:
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": requests},
        ).execute()


def _create_staging_tab(
    service: Any,
    spreadsheet_id: str,
    title: str,
    row_count: int,
    column_count: int,
) -> int:
    response = service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={
            "requests": [
                {
                    "addSheet": {
                        "properties": {
                            "title": title,
                            "gridProperties": {
                                "rowCount": max(row_count + 10, 100),
                                "columnCount": max(column_count + 2, 10),
                                "frozenRowCount": 1,
                            },
                        }
                    }
                }
            ]
        },
    ).execute()
    return int(response["replies"][0]["addSheet"]["properties"]["sheetId"])


def _write_csv_to_tab(service: Any, spreadsheet_id: str, tab: str, csv_path: Path) -> None:
    frame = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
    rows = [frame.columns.tolist(), *frame.values.tolist()]
    for start in range(0, len(rows), WRITE_CHUNK_ROWS):
        chunk = rows[start : start + WRITE_CHUNK_ROWS]
        first_row = start + 1
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"{_quoted_sheet(tab)}!A{first_row}",
            valueInputOption="USER_ENTERED",
            body={"majorDimension": "ROWS", "values": chunk},
        ).execute()


def upload_tables(spreadsheet_id: str, input_dir: str | Path) -> None:
    input_path = Path(input_dir)
    missing = [filename for filename in TABLE_FILES.values() if not (input_path / filename).exists()]
    if missing:
        raise FileNotFoundError(f"Missing Tableau output files: {', '.join(missing)}")

    service = _service()
    _delete_staging_tabs(service, spreadsheet_id)
    staging_ids: dict[str, int] = {}
    for canonical, filename in TABLE_FILES.items():
        csv_path = input_path / filename
        dimensions = pd.read_csv(csv_path, nrows=0).shape[1]
        with csv_path.open("r", encoding="utf-8") as handle:
            row_count = sum(1 for _ in handle)
        staging = f"{STAGING_PREFIX}{canonical}"
        staging_ids[canonical] = _create_staging_tab(
            service, spreadsheet_id, staging, row_count, dimensions
        )
        _write_csv_to_tab(service, spreadsheet_id, staging, csv_path)

    current = _sheet_map(service, spreadsheet_id)
    suffix = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    swap_requests: list[dict[str, Any]] = []
    old_ids: list[int] = []
    for canonical, staging_id in staging_ids.items():
        old_id = current.get(canonical)
        if old_id is not None:
            old_ids.append(old_id)
            swap_requests.append(
                {
                    "updateSheetProperties": {
                        "properties": {"sheetId": old_id, "title": f"__old_{canonical}_{suffix}"},
                        "fields": "title",
                    }
                }
            )
        swap_requests.append(
            {
                "updateSheetProperties": {
                    "properties": {"sheetId": staging_id, "title": canonical},
                    "fields": "title",
                }
            }
        )
    swap_requests.extend({"deleteSheet": {"sheetId": sheet_id}} for sheet_id in old_ids)
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": swap_requests},
    ).execute()


def download_metadata(spreadsheet_id: str, output: str | Path, allow_missing: bool = False) -> bool:
    service = _service()
    if "RefreshMetadata" not in _sheet_map(service, spreadsheet_id):
        if allow_missing:
            return False
        raise RuntimeError("The spreadsheet does not contain a RefreshMetadata tab.")
    try:
        response = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range="'RefreshMetadata'!A:AZ",
        ).execute()
    except HttpError:
        if allow_missing:
            return False
        raise
    values = response.get("values", [])
    if not values:
        if allow_missing:
            return False
        raise RuntimeError("RefreshMetadata is empty.")
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerows(values)
    return True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    upload = subparsers.add_parser("upload", help="Stage and atomically publish all Tableau tabs.")
    upload.add_argument("--spreadsheet-id", required=True)
    upload.add_argument("--input-dir", default="data/tableau")

    download = subparsers.add_parser("download-metadata", help="Download the previous refresh metadata.")
    download.add_argument("--spreadsheet-id", required=True)
    download.add_argument("--output", required=True)
    download.add_argument("--allow-missing", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "upload":
        upload_tables(args.spreadsheet_id, args.input_dir)
        print(f"Published {len(TABLE_FILES)} Tableau tabs to Google Sheets.")
    else:
        downloaded = download_metadata(args.spreadsheet_id, args.output, args.allow_missing)
        print("Downloaded previous refresh metadata." if downloaded else "No previous metadata found.")


if __name__ == "__main__":
    main()
