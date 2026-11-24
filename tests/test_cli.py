# -*- coding: UTF-8 -*-
"""Tests for the CLI, sandboxed in temporary folders."""

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
import zipfile
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cli  # noqa: E402
import nvda_utils  # noqa: E402


class CliTests(unittest.TestCase):
	def setUp(self):
		self._tmp = tempfile.TemporaryDirectory()
		self.root = self._tmp.name
		self.nvda = os.path.join(self.root, "nvda")
		os.makedirs(os.path.join(self.nvda, "profiles"))
		with open(os.path.join(self.nvda, "nvda.ini"), "w", encoding="utf-8") as handle:
			handle.write("[general]\n")
		self.profile = os.path.join(self.root, "touch.nvdaprofile")
		self._patch = mock.patch.object(nvda_utils, "is_nvda_running", return_value=False)
		self._patch.start()

	def tearDown(self):
		self._patch.stop()
		self._tmp.cleanup()

	def run_cli(self, argv):
		buffer = io.StringIO()
		with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
			code = cli.main(argv)
		return code, buffer.getvalue()

	def test_create_writes_profile_with_descriptor(self):
		code, _ = self.run_cli(["create", self.profile, "--nvda-dir", self.nvda, "--note", "touch setup"])
		self.assertEqual(code, 0)
		self.assertTrue(os.path.isfile(self.profile))
		with zipfile.ZipFile(self.profile) as archive:
			descriptor = json.loads(archive.read(cli.DESCRIPTOR_NAME))
			self.assertIn("nvda.ini", archive.namelist())
		self.assertEqual(descriptor["note"], "touch setup")

	def test_inspect_json_reports_descriptor(self):
		self.run_cli(["create", self.profile, "--nvda-dir", self.nvda, "--note", "x"])
		code, output = self.run_cli(["inspect", self.profile, "--json"])
		self.assertEqual(code, 0)
		payload = json.loads(output)
		self.assertEqual(payload["descriptor"]["note"], "x")
		self.assertTrue(payload["files"])

	def test_restore_replaces_configuration_and_undo_brings_it_back(self):
		self.run_cli(["create", self.profile, "--nvda-dir", self.nvda])
		marker = os.path.join(self.nvda, "after-profile.txt")
		with open(marker, "w", encoding="utf-8") as handle:
			handle.write("changed after the backup")
		code, _ = self.run_cli(["restore", self.profile, "--nvda-dir", self.nvda, "--yes"])
		self.assertEqual(code, 0)
		self.assertFalse(os.path.exists(marker))
		self.assertTrue(nvda_utils.has_rollback(self.nvda))
		code, _ = self.run_cli(["undo", "--nvda-dir", self.nvda, "--yes"])
		self.assertEqual(code, 0)
		self.assertTrue(os.path.exists(marker))

	def test_restore_requires_confirmation(self):
		self.run_cli(["create", self.profile, "--nvda-dir", self.nvda])
		with self.assertRaises(SystemExit):
			self.run_cli(["restore", self.profile, "--nvda-dir", self.nvda])

	def test_undo_without_rollback_fails(self):
		with self.assertRaises(SystemExit):
			self.run_cli(["undo", "--nvda-dir", self.nvda, "--yes"])

	def test_list_restores_prints_folder(self):
		self.run_cli(["create", self.profile, "--nvda-dir", self.nvda])
		self.run_cli(["restore", self.profile, "--nvda-dir", self.nvda, "--yes"])
		code, output = self.run_cli(["list-restores", "--nvda-dir", self.nvda])
		self.assertEqual(code, 0)
		self.assertIn("nvda.bak-", output)


if __name__ == "__main__":
	unittest.main()
