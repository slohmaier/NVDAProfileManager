"""Sandboxed tests for nvda_utils.

These tests never touch the real NVDA configuration folder — they operate only
on temporary directories. Run with:

    python -m unittest discover -s tests
"""

import hashlib
import json
import os
import stat
import sys
import tempfile
import unittest
import zipfile
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import nvda_utils  # noqa: E402


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        h.update(fh.read())
    return h.hexdigest()


def write_file(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(content)


class FakeProc:
    """Minimal stand-in for a psutil.Process."""

    def __init__(self, name, exe=None, pid=1000):
        self.info = {'name': name}
        self.pid = pid
        self._exe = exe

    def name(self):
        return self.info['name']

    def exe(self):
        if self._exe is None:
            raise OSError('no exe')
        return self._exe


class SandboxTest(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix='nvda_pm_test_')
        self.nvda = os.path.join(self.base, 'nvda')
        os.makedirs(self.nvda)
        write_file(os.path.join(self.nvda, 'nvda.ini'), 'ORIGINAL')

    def tearDown(self):
        nvda_utils.remove_tree(self.base)

    def make_profile(self, name='p.nvdaprofile', marker='RESTORED'):
        src = tempfile.mkdtemp(prefix='src_', dir=self.base)
        write_file(os.path.join(src, 'nvda.ini'), marker)
        write_file(os.path.join(src, 'sub', 'a.txt'), 'a')
        os.makedirs(os.path.join(src, 'emptydir'), exist_ok=True)
        prof = os.path.join(self.base, name)
        nvda_utils.build_profile_archive(src, prof, {'username': 'tester'})
        return prof


class TestSafeRestore(SandboxTest):
    def test_restore_swaps_and_keeps_rollback(self):
        prof = self.make_profile(marker='RESTORED')
        bak = nvda_utils.safe_restore(self.nvda, prof)

        self.assertTrue(bak and os.path.isdir(bak))
        self.assertIn('nvda.bak-', os.path.basename(bak))
        with open(os.path.join(self.nvda, 'nvda.ini')) as fh:
            self.assertEqual(fh.read(), 'RESTORED')
        with open(os.path.join(bak, 'nvda.ini')) as fh:
            self.assertEqual(fh.read(), 'ORIGINAL')
        self.assertTrue(nvda_utils.has_rollback(self.nvda))

    def test_corrupt_archive_leaves_original_intact(self):
        bad = os.path.join(self.base, 'bad.nvdaprofile')
        write_file(bad, 'not a zip')
        with self.assertRaises(Exception):
            nvda_utils.safe_restore(self.nvda, bad)
        with open(os.path.join(self.nvda, 'nvda.ini')) as fh:
            self.assertEqual(fh.read(), 'ORIGINAL')
        self.assertFalse(nvda_utils.has_rollback(self.nvda))

    def test_no_staging_left_behind(self):
        prof = self.make_profile()
        nvda_utils.safe_restore(self.nvda, prof)
        leftovers = [n for n in os.listdir(self.base) if n.startswith('nvda_restore_')]
        self.assertEqual(leftovers, [])


class TestUndoRestore(SandboxTest):
    def test_undo_returns_original_and_is_reversible(self):
        prof = self.make_profile(marker='RESTORED')
        nvda_utils.safe_restore(self.nvda, prof)
        nvda_utils.undo_restore(self.nvda)

        with open(os.path.join(self.nvda, 'nvda.ini')) as fh:
            self.assertEqual(fh.read(), 'ORIGINAL')
        # The restored config was set aside, so the undo is itself reversible.
        self.assertTrue(nvda_utils.has_rollback(self.nvda))

    def test_undo_without_backup_raises(self):
        with self.assertRaises(RuntimeError):
            nvda_utils.undo_restore(self.nvda)


class TestBackupHelpers(SandboxTest):
    def test_next_backup_path_unique(self):
        first = nvda_utils._next_backup_path(self.nvda)
        os.makedirs(first)
        second = nvda_utils._next_backup_path(self.nvda)
        self.assertNotEqual(first, second)
        os.makedirs(second)

    def test_cleanup_keeps_newest_three(self):
        for stamp in ('20200101-000000', '20200102-000000',
                      '20200103-000000', '20200104-000000', '20200105-000000'):
            os.makedirs(os.path.join(self.base, f'nvda.bak-{stamp}'))
        staging = os.path.join(self.base, 'nvda_restore_leftover')
        os.makedirs(staging)

        nvda_utils.cleanup_stale_restore_dirs(self.nvda, keep_backups=3)

        remaining = sorted(
            n for n in os.listdir(self.base) if n.startswith('nvda.bak-'))
        self.assertEqual(remaining, [
            'nvda.bak-20200103-000000',
            'nvda.bak-20200104-000000',
            'nvda.bak-20200105-000000',
        ])
        self.assertFalse(os.path.exists(staging))

    def test_build_archive_excludes_tmp(self):
        write_file(os.path.join(self.nvda, 'keep.txt'), 'x')
        write_file(os.path.join(self.nvda, 'nvda.ini123.tmp'), 'tmp')
        write_file(os.path.join(self.nvda, 'NVDA.iniABC.TMP'), 'tmp')
        out = os.path.join(self.base, 'out.nvdaprofile')
        nvda_utils.build_profile_archive(self.nvda, out, {'username': 'tester'})

        with zipfile.ZipFile(out) as z:
            names = z.namelist()
        self.assertIn('keep.txt', names)
        self.assertNotIn('nvda.ini123.tmp', names)
        self.assertNotIn('NVDA.iniABC.TMP', names)

    def test_build_archive_preserves_empty_dirs(self):
        os.makedirs(os.path.join(self.nvda, 'emptydir'))
        out = os.path.join(self.base, 'out.nvdaprofile')
        nvda_utils.build_profile_archive(self.nvda, out, {'username': 'tester'})
        with zipfile.ZipFile(out) as z:
            self.assertIn('emptydir/', z.namelist())

    def test_build_archive_is_atomic_on_failure(self):
        out = os.path.join(self.base, 'out.nvdaprofile')
        write_file(out, 'EXISTING')
        with mock.patch('nvda_utils.zipfile.ZipFile', side_effect=RuntimeError('boom')):
            with self.assertRaises(RuntimeError):
                nvda_utils.build_profile_archive(self.nvda, out, {})
        with open(out) as fh:
            self.assertEqual(fh.read(), 'EXISTING')
        self.assertEqual(
            [n for n in os.listdir(self.base) if n.endswith('.tmp')], [])

    def test_remove_tree_clears_readonly(self):
        target = os.path.join(self.base, 'ro')
        write_file(os.path.join(target, 'f.txt'), 'x')
        os.chmod(os.path.join(target, 'f.txt'), stat.S_IREAD)
        nvda_utils.remove_tree(target)
        self.assertFalse(os.path.exists(target))


class TestProcessDetection(unittest.TestCase):
    def test_is_running_true_with_main(self):
        with mock.patch('nvda_utils.get_running_nvda_processes',
                        return_value=[FakeProc('nvda.exe')]):
            self.assertTrue(nvda_utils.is_nvda_running())

    def test_is_running_true_with_slave_only(self):
        with mock.patch('nvda_utils.get_running_nvda_processes',
                        return_value=[FakeProc('nvda_slave.exe')]):
            self.assertTrue(nvda_utils.is_nvda_running())

    def test_is_running_false_when_empty(self):
        with mock.patch('nvda_utils.get_running_nvda_processes', return_value=[]):
            self.assertFalse(nvda_utils.is_nvda_running())

    def test_get_nvda_process_ignores_slave(self):
        procs = [FakeProc('nvda_slave.exe', pid=1), FakeProc('nvda.exe', pid=2)]
        with mock.patch('nvda_utils.get_running_nvda_processes', return_value=procs):
            self.assertEqual(nvda_utils.get_nvda_process().pid, 2)

    def test_find_executable_resolves_portable(self):
        tmp = tempfile.mkdtemp(prefix='portable_')
        self.addCleanup(nvda_utils.remove_tree, tmp)
        exe = os.path.join(tmp, 'nvda.exe')
        write_file(exe, 'stub')
        proc = FakeProc('nvda.exe', exe=exe)

        real_exists = os.path.exists

        def fake_exists(path):
            if isinstance(path, str) and 'Program Files' in path:
                return False
            return real_exists(path)

        with mock.patch('nvda_utils.get_running_nvda_processes', return_value=[proc]), \
                mock.patch('nvda_utils.os.path.exists', side_effect=fake_exists):
            self.assertEqual(nvda_utils.find_nvda_executable(), exe)

    def test_find_executable_from_slave_directory(self):
        tmp = tempfile.mkdtemp(prefix='portable_')
        self.addCleanup(nvda_utils.remove_tree, tmp)
        main_exe = os.path.join(tmp, 'nvda.exe')
        write_file(main_exe, 'stub')
        write_file(os.path.join(tmp, 'nvda_slave.exe'), 'stub')
        proc = FakeProc('nvda_slave.exe', exe=os.path.join(tmp, 'nvda_slave.exe'))

        real_exists = os.path.exists

        def fake_exists(path):
            if isinstance(path, str) and 'Program Files' in path:
                return False
            return real_exists(path)

        with mock.patch('nvda_utils.get_running_nvda_processes', return_value=[proc]), \
                mock.patch('nvda_utils.os.path.exists', side_effect=fake_exists):
            self.assertEqual(nvda_utils.find_nvda_executable(), main_exe)


class TestStartNvda(unittest.TestCase):
    def test_start_uses_shell_execute(self):
        with mock.patch('nvda_utils.find_nvda_executable', return_value=r'C:\x\nvda.exe'), \
                mock.patch('nvda_utils.os.startfile', create=True) as sf:
            self.assertTrue(nvda_utils.start_nvda())
            sf.assert_called_once_with(r'C:\x\nvda.exe')

    def test_start_falls_back_to_popen(self):
        with mock.patch('nvda_utils.find_nvda_executable', return_value=r'C:\x\nvda.exe'), \
                mock.patch('nvda_utils.os.startfile', create=True,
                           side_effect=OSError('nope')), \
                mock.patch('nvda_utils.subprocess.Popen') as popen:
            self.assertTrue(nvda_utils.start_nvda())
            popen.assert_called_once_with([r'C:\x\nvda.exe'], shell=False)

    def test_start_returns_false_without_exe(self):
        with mock.patch('nvda_utils.find_nvda_executable', return_value=None):
            self.assertFalse(nvda_utils.start_nvda())


class TestWaitForNvdaStart(unittest.TestCase):
    def test_returns_true_once_process_is_up(self):
        with mock.patch('nvda_utils.get_nvda_process',
                        return_value=FakeProc('nvda.exe')), \
                mock.patch('nvda_utils.time.sleep'):
            self.assertTrue(nvda_utils.wait_for_nvda_start(timeout=5))

    def test_returns_false_on_timeout(self):
        with mock.patch('nvda_utils.get_nvda_process', return_value=None), \
                mock.patch('nvda_utils.time.sleep'):
            self.assertFalse(nvda_utils.wait_for_nvda_start(timeout=0.1))


if __name__ == '__main__':
    unittest.main()
