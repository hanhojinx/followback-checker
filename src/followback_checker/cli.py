"""Command-line interface; all state is stored locally."""

import argparse
import sys
import zipfile
from pathlib import Path

from .comparator import changes, normalize_username
from .exporter import export_report
from .fetcher import ExportFetcher, LiveFetcher
from .history import latest_changes, load_snapshots, save_snapshot


def build_parser():
    common = argparse.ArgumentParser(add_help=False)
    # SUPPRESS lets flags work before or after the command without overwriting.
    common.add_argument("--data-dir", type=Path, default=argparse.SUPPRESS)
    common.add_argument("--output-dir", type=Path, default=argparse.SUPPRESS)
    common.add_argument("--account", default=argparse.SUPPRESS,
                        help="Local history label; use a different label for each account")
    parser = argparse.ArgumentParser(prog="fbchk", parents=[common],
                                     description="Local Instagram follow audit")
    sub = parser.add_subparsers(dest="command", required=True)
    scan = sub.add_parser("scan", parents=[common], help="Import and save a new audit")
    scan.add_argument("--source", choices=["export", "live"], default="export")
    scan.add_argument("--path", type=Path, help="ZIP, directory, or a standard-named export file")
    sub.add_parser("nonfollowers", parents=[common], help="Show latest saved non-mutual accounts")
    sub.add_parser("changes", parents=[common], help="Compare the last two saved snapshots")
    export = sub.add_parser("export", parents=[common], help="Export latest saved result")
    export.add_argument("--format", choices=["csv", "txt", "json"], default="csv")
    return parser


def print_changes(diff):
    if diff is None:
        print("No previous snapshot; changes will be available after the next scan.")
        return
    for key, users in diff.items():
        print(f"{key}: {len(users)}")
        for user in users:
            print(f"  @{user}")


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    data_dir = getattr(args, "data_dir", Path("data")) / "snapshots"
    output_dir = getattr(args, "output_dir", Path("output"))
    try:
        account = normalize_username(getattr(args, "account", "local"))
        if args.command == "scan":
            if args.source == "export" and args.path is None:
                parser.error("scan --source export requires --path")
            source = ExportFetcher(args.path) if args.source == "export" else LiveFetcher()
            current = source.fetch()
            snapshots = load_snapshots(data_dir, account)
            diff = changes(snapshots[-1][2], current) if snapshots else None
            saved = save_snapshot(data_dir, account, current)
            print(f"Account label: @{account}")
            print(f"Followers: {len(current.followers)}\nFollowing: {len(current.following)}")
            print(f"Mutual: {len(current.mutual)}\nNot following back: {len(current.nonfollowers)}")
            for user in current.nonfollowers:
                print(f"@{user}")
            print(f"Snapshot: {saved}")
            for format in ("csv", "txt", "json"):
                print(f"Saved: {export_report(current.nonfollowers, output_dir, format)}")
            print_changes(diff)
        else:
            snapshots = load_snapshots(data_dir, account)
            if not snapshots:
                raise ValueError("No saved snapshot for this account. Run fbchk scan first.")
            if args.command == "changes":
                print_changes(latest_changes(snapshots))
            elif args.command == "nonfollowers":
                users = snapshots[-1][2].nonfollowers
                print(f"Not following back: {len(users)}")
                for user in users:
                    print(f"@{user}")
            else:
                print(f"Saved: {export_report(snapshots[-1][2].nonfollowers, output_dir, args.format)}")
        return 0
    except (OSError, ValueError, NotImplementedError, zipfile.BadZipFile, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
