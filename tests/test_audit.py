import contextlib
import csv
import io
import json
import tempfile
import unittest
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from followback_checker.cli import main
from followback_checker.comparator import Relationships, changes
from followback_checker.exporter import export_report
from followback_checker.history import latest_changes, load_snapshots, save_snapshot
from followback_checker.parser import load_export, parse_document

FIXTURES = Path(__file__).parent / "fixtures"


class ComparatorTests(unittest.TestCase):
    def test_normalization_deduplication_and_difference(self):
        relation = Relationships.from_iterables([" Alice ", "@BOB", "alice"], ["alice", "CAROL"])
        self.assertEqual(relation.nonfollowers, ["carol"])
        self.assertEqual(relation.mutual, {"alice"})
        self.assertEqual(len(relation.followers), 2)

    def test_all_history_categories(self):
        before = Relationships.from_iterables(["alice", "bob"], ["alice", "carol"])
        after = Relationships.from_iterables(["alice", "dave"], ["alice", "eve"])
        self.assertEqual(changes(before, after), {
            "unfollowed_you": ["bob"], "new_followers": ["dave"],
            "you_followed": ["eve"], "you_unfollowed": ["carol"],
            "current_non_mutual": ["eve"],
        })

    def test_empty_sets_and_invalid_username(self):
        self.assertEqual(Relationships.from_iterables([], []).nonfollowers, [])
        with self.assertRaises(ValueError):
            Relationships.from_iterables(["../invalid"], [])


class ParserTests(unittest.TestCase):
    def test_realistic_json_fixtures_and_single_file(self):
        result = load_export(FIXTURES)
        self.assertEqual(result.followers, {"alice", "bob"})
        self.assertEqual(result.nonfollowers, ["carol", "dave"])
        self.assertEqual(load_export(FIXTURES / "following.json"), result)

    def test_zip_nested_split_files_without_extraction(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "export.zip"
            with zipfile.ZipFile(archive, "w") as z:
                for fixture in FIXTURES.glob("*.json"):
                    z.write(fixture, "connections/followers_and_following/" + fixture.name)
                z.writestr("connections/followers_and_following/followers_2.json",
                           '[{"string_list_data": [{"value": "CAROL"}]}]')
                z.writestr("../../unrelated.txt", "never extract this")
            self.assertEqual(load_export(archive).nonfollowers, ["dave"])
            self.assertEqual(sorted(p.name for p in Path(tmp).iterdir()), ["export.zip"])

    def test_html_uses_profile_urls_not_display_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "followers_1.html").write_text(
                '<h1>Followers</h1><a href="https://www.instagram.com/alice/">Alice Smith</a>'
                '<a href="https://example.com/bob/">bob</a>'
                '<a href="https://www.instagram.com/accounts/login/">Login</a>', encoding="utf-8")
            (root / "following.html").write_text(
                '<h1>Following</h1><a href="https://www.instagram.com/_u/ALICE">Alice</a>'
                '<a href="https://www.instagram.com/carol/?x=1&amp;y=2">C</a>', encoding="utf-8")
            self.assertEqual(load_export(root).nonfollowers, ["carol"])

    def test_title_only_following_and_legacy_wrapper(self):
        self.assertEqual(parse_document(b'{"relationships_following":[{"title":"alice"}]}',
                                        ".json", "following"), {"alice"})
        self.assertEqual(parse_document(b'{"relationships_followers":[]}', ".json", "followers"), set())

    def test_missing_empty_and_malformed_are_distinct(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "followers_1.json").write_text("[]")
            with self.assertRaisesRegex(ValueError, "Missing.*following"):
                load_export(root)
            (root / "following.json").write_text('{"relationships_following": []}')
            self.assertEqual(load_export(root).nonfollowers, [])
            (root / "following.json").write_text('{"relationships_following": [{}]}')
            with self.assertRaisesRegex(ValueError, "no valid username"):
                load_export(root)
            (root / "following.json").write_text("broken json")
            with self.assertRaisesRegex(ValueError, "Cannot parse"):
                load_export(root)

    def test_unrecognized_html_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_document(b"<html>unrelated document</html>", ".html", "followers")

    def test_unrecognized_input_filename_does_not_import_siblings(self):
        with tempfile.TemporaryDirectory() as tmp:
            unrelated = Path(tmp) / "unrelated.json"
            unrelated.write_text("[]")
            with self.assertRaisesRegex(ValueError, "filename"):
                load_export(unrelated)


class HistoryTests(unittest.TestCase):
    def test_equal_timestamps_preserve_creation_order_across_saves(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            before = Relationships.from_iterables(["alice", "bob"], ["alice", "carol"])
            after = Relationships.from_iterables(["alice", "dave"], ["alice", "eve"])
            fixed = datetime(2026, 10, 7, 12, tzinfo=timezone.utc)
            # Force equal timestamps and reverse filename order. Separate clock
            # patches model independent CLI runs rather than in-memory state.
            for relation, identifier in ((before, "ffffffff"), (after, "00000000")):
                with patch("followback_checker.history.datetime", wraps=datetime) as clock, \
                        patch("followback_checker.history.uuid4", return_value=SimpleNamespace(hex=identifier)):
                    clock.now.return_value = fixed
                    save_snapshot(root, "me", relation)
            snapshots = load_snapshots(root, "me")
            self.assertEqual(snapshots[0][2], before)
            self.assertEqual(snapshots[-1][2], after)
            self.assertEqual([item[1]["sequence"] for item in snapshots], [1, 2])
            self.assertEqual(latest_changes(snapshots), changes(before, after))

    def test_clock_moving_backwards_does_not_reverse_saved_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            before = Relationships.from_iterables(["alice"], [])
            after = Relationships.from_iterables(["bob"], [])
            fixed = datetime(2026, 10, 7, 12, tzinfo=timezone.utc)
            with patch("followback_checker.history.datetime", wraps=datetime) as clock:
                clock.now.side_effect = [fixed, fixed - timedelta(hours=1)]
                save_snapshot(root, "me", before)
                save_snapshot(root, "me", after)
            snapshots = load_snapshots(root, "me")
            self.assertEqual(latest_changes(snapshots), changes(before, after))

    def test_legacy_snapshot_is_readable_and_precedes_new_saves(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy = {
                "schema_version": 1, "account": "me", "created_at": "2026-10-07T12:00:00+00:00",
                "followers": ["alice"], "following": [],
            }
            (root / "legacy.json").write_text(json.dumps(legacy))
            with patch("followback_checker.history.datetime", wraps=datetime) as clock:
                clock.now.return_value = datetime(2026, 10, 7, 11, tzinfo=timezone.utc)
                save_snapshot(root, "me", Relationships.from_iterables(["bob"], []))
                save_snapshot(root, "me", Relationships.from_iterables(["carol"], []))
            snapshots = load_snapshots(root, "me")
            self.assertEqual(snapshots[0][0].name, "legacy.json")
            self.assertEqual([item[2].followers for item in snapshots], [{"alice"}, {"bob"}, {"carol"}])
            self.assertEqual([item[1].get("sequence", 0) for item in snapshots], [0, 1, 2])

    def test_invalid_sequence_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            saved = save_snapshot(root, "me", Relationships.from_iterables([], []))
            payload = json.loads(saved.read_text())
            for sequence in (0, -1, "1", True):
                with self.subTest(sequence=sequence):
                    payload["sequence"] = sequence
                    saved.write_text(json.dumps(payload))
                    with self.assertRaisesRegex(ValueError, "sequence"):
                        load_snapshots(root, "me")

    def test_round_trip_first_scan_diff_and_account_isolation(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            before = Relationships.from_iterables(["alice", "bob"], ["alice", "carol"])
            after = Relationships.from_iterables(["alice", "dave"], ["alice", "eve"])
            first = save_snapshot(directory, "me", before)
            self.assertIsNone(latest_changes(load_snapshots(directory, "me")))
            second = save_snapshot(directory, "me", after)
            save_snapshot(directory, "other", before)
            self.assertNotEqual(first, second)
            snapshots = load_snapshots(directory, "me")
            self.assertEqual(len(snapshots), 2)
            self.assertEqual(latest_changes(snapshots), changes(before, after))
            self.assertEqual(load_snapshots(directory, "missing"), [])
            self.assertEqual(load_snapshots(directory, "other")[0][1]["sequence"], 1)
            self.assertEqual(snapshots[-1][2], after)

    def test_corruption_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "bad.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "Invalid snapshot"):
                load_snapshots(Path(tmp), "me")

    def test_order_uses_timezone_aware_instants(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # A timezone change can make a later instant look earlier locally.
            for filename, instant, follower in (
                ("first.json", "2026-10-06T10:00:00+09:00", "alice"),
                ("second.json", "2026-10-06T03:00:00+00:00", "bob"),
            ):
                (root / filename).write_text(json.dumps({
                    "schema_version": 1, "account": "me", "created_at": instant,
                    "followers": [follower], "following": [],
                }))
            snapshots = load_snapshots(root, "me")
            self.assertEqual(snapshots[-1][0].name, "second.json")
            self.assertEqual(latest_changes(snapshots)["new_followers"], ["bob"])


class CliAndExporterTests(unittest.TestCase):
    def test_csv_and_repeat_preserve_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = export_report(["carol", "alice"], root, "csv")
            second = export_report(["dave"], root, "csv")
            self.assertNotEqual(first, second)
            with first.open(encoding="utf-8", newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual([row["username"] for row in rows], ["alice", "carol"])
            self.assertEqual(json.loads(export_report([], root, "json").read_text()),
                             {"not_following_back": []})

    def test_full_cli_flow_and_stub(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            flags = ["--data-dir", str(root / "data"), "--output-dir", str(root / "out")]
            with contextlib.redirect_stdout(io.StringIO()) as output:
                for _ in range(2):
                    self.assertEqual(main(flags + ["scan", "--path", str(FIXTURES)]), 0)
                self.assertEqual(main(["nonfollowers"] + flags), 0)
                self.assertEqual(main(["changes"] + flags), 0)
                self.assertEqual(main(["export", "--format", "json"] + flags), 0)
            self.assertIn("Not following back: 2", output.getvalue())
            self.assertIn("unfollowed_you: 0", output.getvalue())
            self.assertEqual(len(list((root / "data" / "snapshots").glob("*.json"))), 2)
            with contextlib.redirect_stderr(io.StringIO()) as error:
                self.assertEqual(main(flags + ["scan", "--source", "live"]), 1)
            self.assertIn("not implemented", error.getvalue())
            self.assertEqual(len(list((root / "data" / "snapshots").glob("*.json"))), 2)

    def test_no_saved_snapshot_is_an_actionable_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            with contextlib.redirect_stderr(io.StringIO()) as error:
                self.assertEqual(main(["nonfollowers", "--data-dir", tmp]), 1)
            self.assertIn("scan first", error.getvalue())


if __name__ == "__main__":
    unittest.main()
