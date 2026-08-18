from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from google_sheets_sync import TABLE_FILES, upload_tables


def _write_fixture_tables(directory: Path) -> None:
    for index, filename in enumerate(TABLE_FILES.values(), start=1):
        (directory / filename).write_text(f"ID,Value\n{index},test\n", encoding="utf-8")


def _sheet_response() -> dict:
    return {
        "sheets": [
            {"properties": {"sheetId": index, "title": title}}
            for index, title in enumerate(TABLE_FILES, start=1)
        ]
    }


def _fake_service() -> tuple[MagicMock, MagicMock]:
    service = MagicMock()
    spreadsheets = service.spreadsheets.return_value
    spreadsheets.get.return_value.execute.side_effect = [_sheet_response(), _sheet_response()]
    add_responses = [
        {"replies": [{"addSheet": {"properties": {"sheetId": sheet_id}}}]}
        for sheet_id in range(100, 104)
    ]
    spreadsheets.batchUpdate.return_value.execute.side_effect = [*add_responses, {}]
    spreadsheets.values.return_value.update.return_value.execute.return_value = {}
    return service, spreadsheets


class GoogleSheetsPublishingTests(unittest.TestCase):
    def test_upload_stages_every_table_then_performs_one_canonical_swap(self):
        service, spreadsheets = _fake_service()
        with tempfile.TemporaryDirectory() as directory, patch(
            "google_sheets_sync._service", return_value=service
        ):
            _write_fixture_tables(Path(directory))
            upload_tables("spreadsheet-id", directory)

        self.assertEqual(spreadsheets.values.return_value.update.call_count, 4)
        batch_calls = spreadsheets.batchUpdate.call_args_list
        self.assertEqual(len(batch_calls), 5)
        final_requests = batch_calls[-1].kwargs["body"]["requests"]
        self.assertEqual(len(final_requests), 12)
        canonical_titles = [
            request["updateSheetProperties"]["properties"]["title"]
            for request in final_requests
            if "updateSheetProperties" in request
        ]
        for title in TABLE_FILES:
            self.assertIn(title, canonical_titles)
        self.assertEqual(sum("deleteSheet" in request for request in final_requests), 4)

    def test_write_failure_never_runs_the_canonical_swap(self):
        service, spreadsheets = _fake_service()
        spreadsheets.values.return_value.update.return_value.execute.side_effect = RuntimeError(
            "simulated upload failure"
        )
        with tempfile.TemporaryDirectory() as directory, patch(
            "google_sheets_sync._service", return_value=service
        ):
            _write_fixture_tables(Path(directory))
            with self.assertRaisesRegex(RuntimeError, "simulated"):
                upload_tables("spreadsheet-id", directory)

        self.assertEqual(len(spreadsheets.batchUpdate.call_args_list), 1)


if __name__ == "__main__":
    unittest.main()
