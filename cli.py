#!/usr/bin/env python3
"""Command line interface for NVDA Profile Manager.

Creates, inspects and restores ``.nvdaprofile`` archives without the GUI,
so profiles can be rolled out to other machines from a script.

Examples:
    NVDAProfileManagerCLI.exe create touch.nvdaprofile --note "Touch setup"
    NVDAProfileManagerCLI.exe inspect touch.nvdaprofile --json
    NVDAProfileManagerCLI.exe restore touch.nvdaprofile --yes
    NVDAProfileManagerCLI.exe undo --yes
    NVDAProfileManagerCLI.exe list-restores
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import zipfile
from datetime import datetime

import nvda_utils

DESCRIPTOR_NAME = "profile_descriptor.json"
CLI_VERSION = "1.0"


def default_nvda_path() -> str:
	appdata = os.getenv("APPDATA", "")
	return os.path.join(appdata, "nvda") if appdata else ""


def resolve_nvda_path(value: str | None) -> str:
	return os.path.abspath(value) if value else default_nvda_path()


def fail(message: str) -> "SystemExit":
	print(f"error: {message}", file=sys.stderr)
	return SystemExit(1)


def stop_nvda_if_needed(args: argparse.Namespace) -> bool:
	"""Stop NVDA if it runs. Returns True when the CLI stopped it."""
	if not nvda_utils.is_nvda_running():
		return False
	if not getattr(args, "yes", False):
		raise fail("NVDA is running. Close it first or pass --yes to close and restart it.")
	print("Stopping NVDA ...")
	if not nvda_utils.stop_nvda():
		raise fail("NVDA could not be stopped.")
	nvda_utils.wait_for_nvda_exit()
	return True


def resume_nvda(stopped_by_us: bool, args: argparse.Namespace) -> None:
	if not stopped_by_us or getattr(args, "no_restart", False):
		return
	if nvda_utils.start_nvda():
		nvda_utils.wait_for_nvda_start()


def command_create(args: argparse.Namespace) -> int:
	nvda_path = resolve_nvda_path(args.nvda_dir)
	if not os.path.isdir(nvda_path):
		raise fail(f"NVDA configuration folder not found: {nvda_path}")
	descriptor = {
		"username": os.getenv("USERNAME"),
		"computer_name": os.getenv("COMPUTERNAME"),
		"created_date": datetime.now().isoformat(),
		"nvda_path": nvda_path,
	}
	if args.note:
		descriptor["note"] = args.note
	stopped = stop_nvda_if_needed(args)
	try:
		nvda_utils.build_profile_archive(nvda_path, os.path.abspath(args.output), descriptor)
	finally:
		resume_nvda(stopped, args)
	size_mb = os.path.getsize(args.output) / (1024 * 1024)
	print(f"Created {args.output} ({size_mb:.1f} MB)")
	print(f"  from {nvda_path}")
	print(f"  user {descriptor['username']} on {descriptor['computer_name']}")
	return 0


def read_descriptor(archive: zipfile.ZipFile) -> dict:
	try:
		return json.loads(archive.read(DESCRIPTOR_NAME))
	except KeyError:
		return {}
	except json.JSONDecodeError:
		return {}


def command_inspect(args: argparse.Namespace) -> int:
	if not os.path.isfile(args.profile):
		raise fail(f"profile not found: {args.profile}")
	with zipfile.ZipFile(args.profile) as archive:
		infos = archive.infolist()
		descriptor = read_descriptor(archive)
	if args.json:
		payload = {
			"path": os.path.abspath(args.profile),
			"descriptor": descriptor,
			"entries": len(infos),
			"uncompressed_bytes": sum(info.file_size for info in infos),
			"files": [info.filename for info in infos],
		}
		print(json.dumps(payload, indent=2))
		return 0
	print(f"Profile: {os.path.abspath(args.profile)}")
	print(f"Entries: {len(infos)}")
	print(f"Uncompressed: {sum(info.file_size for info in infos) / (1024 * 1024):.1f} MB")
	for key in ("username", "computer_name", "created_date", "note", "nvda_path"):
		if key in descriptor:
			print(f"{key}: {descriptor[key]}")
	return 0


def command_restore(args: argparse.Namespace) -> int:
	if not os.path.isfile(args.profile):
		raise fail(f"profile not found: {args.profile}")
	if not args.yes:
		raise fail("restore replaces the current NVDA configuration; pass --yes to confirm.")
	nvda_path = resolve_nvda_path(args.nvda_dir)
	stopped = stop_nvda_if_needed(args)
	try:
		rollback = nvda_utils.safe_restore(nvda_path, os.path.abspath(args.profile))
	finally:
		resume_nvda(stopped, args)
	print(f"Restored {args.profile} into {nvda_path}")
	if rollback:
		print(f"Previous configuration kept as {rollback}")
		print("Undo with: NVDAProfileManagerCLI.exe undo --yes")
	return 0


def command_undo(args: argparse.Namespace) -> int:
	nvda_path = resolve_nvda_path(args.nvda_dir)
	if not nvda_utils.has_rollback(nvda_path):
		raise fail("no rollback folder found.")
	if not args.yes:
		raise fail("undo replaces the current configuration; pass --yes to confirm.")
	stopped = stop_nvda_if_needed(args)
	try:
		nvda_utils.undo_restore(nvda_path)
	finally:
		resume_nvda(stopped, args)
	print(f"Restored the configuration that was replaced last in {nvda_path}")
	return 0


def command_list_restores(args: argparse.Namespace) -> int:
	nvda_path = resolve_nvda_path(args.nvda_dir)
	parent = os.path.dirname(nvda_path.rstrip("\\/"))
	prefix = os.path.basename(nvda_path.rstrip("\\/")) + ".bak-"
	found = []
	if os.path.isdir(parent):
		for name in sorted(os.listdir(parent)):
			if name.startswith(prefix):
				found.append(os.path.join(parent, name))
	for path in found:
		print(path)
	if not found:
		print("no rollback folders found.")
	return 0


def build_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(
		prog="NVDAProfileManagerCLI",
		description="Create, inspect and restore NVDA profiles without the GUI.",
	)
	parser.add_argument("--version", action="version", version=f"%(prog)s {CLI_VERSION}")
	subparsers = parser.add_subparsers(dest="command", required=True)

	def add_common(sub: argparse.ArgumentParser) -> None:
		sub.add_argument("--nvda-dir", default=None, help="NVDA configuration folder (default: %%APPDATA%%\\nvda)")
		sub.add_argument("--yes", action="store_true", help="confirm closing NVDA and destructive operations")
		sub.add_argument("--no-restart", action="store_true", help="do not restart NVDA afterwards")

	create = subparsers.add_parser("create", help="create a .nvdaprofile from the current configuration")
	create.add_argument("output", help="path of the .nvdaprofile to write")
	create.add_argument("--note", default="", help="free text stored in the profile descriptor")
	add_common(create)
	create.set_defaults(func=command_create)

	inspect = subparsers.add_parser("inspect", help="show metadata and contents of a profile")
	inspect.add_argument("profile")
	inspect.add_argument("--json", action="store_true", help="machine readable output")
	inspect.set_defaults(func=command_inspect)

	restore = subparsers.add_parser("restore", help="replace the NVDA configuration from a profile")
	restore.add_argument("profile")
	add_common(restore)
	restore.set_defaults(func=command_restore)

	undo = subparsers.add_parser("undo", help="bring back the configuration replaced by the last restore")
	add_common(undo)
	undo.set_defaults(func=command_undo)

	list_restores = subparsers.add_parser("list-restores", help="list rollback folders")
	add_common(list_restores)
	list_restores.set_defaults(func=command_list_restores)

	return parser


def main(argv: list[str] | None = None) -> int:
	parser = build_parser()
	args = parser.parse_args(argv)
	return args.func(args)


if __name__ == "__main__":
	sys.exit(main())
