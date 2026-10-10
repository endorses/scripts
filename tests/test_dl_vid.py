"""Exercise a changing download queue without network access."""

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "dl-vid"
FAKE_DOWNLOADER = """#!/usr/bin/env python3
import json, os, pathlib, signal, subprocess, sys, time
root = pathlib.Path(os.environ['FAKE_QUEUE_ROOT'])
url = sys.argv[-1]
calls = root / 'calls.jsonl'
previous = [json.loads(line) for line in calls.read_text().splitlines()] if calls.exists() else []
attempt = 1 + sum(call['url'] == url for call in previous)
rules = json.loads((root / 'rules.json').read_text())
rule = rules.get(url, {})
with calls.open('a') as log:
    log.write(json.dumps({'url': url, 'args': sys.argv[1:], 'pid': os.getpid(), 'attempt': attempt}) + '\\n')
def stop(signum, frame):
    (root / 'child-stopped').write_text(str(signum))
    sys.exit(128 + signum)
signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)
if rule.get('descendant'):
    code = "import pathlib, signal, sys, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); pathlib.Path(sys.argv[1]).touch(); time.sleep(100)"
    descendant = subprocess.Popen([sys.executable, '-c', code, str(root / 'descendant-ready')])
    (root / 'descendant-pid').write_text(str(descendant.pid))
while rule.get('hold') and not (root / 'release').exists():
    time.sleep(0.01)
if attempt <= rule.get('fail_attempts', 0):
    sys.exit(1)
with (root / 'finished.jsonl').open('a') as log:
    log.write(json.dumps(url) + '\\n')
"""


class DownloadQueueTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="queue-test-", dir=ROOT)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.links = self.root / "links with spaces.txt"
        self.links.write_text("")
        self.rules = self.root / "rules.json"
        self.rules.write_text("{}")
        self.bin = self.root / "bin"
        self.bin.mkdir()
        downloader = self.bin / "yt-dlp"
        downloader.write_text(FAKE_DOWNLOADER)
        downloader.chmod(0o755)
        self.env = dict(
            os.environ,
            PATH=f"{self.bin}:{os.defpath}",
            FAKE_QUEUE_ROOT=str(self.root),
            PYTHONUNBUFFERED="1",
            PYTHONDONTWRITEBYTECODE="1",
        )
        self.processes = []
        self.addCleanup(self.stop_processes)

    def stop_processes(self):
        for process in self.processes:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)
            for stream in (process.stdout, process.stderr):
                if stream:
                    stream.close()
        for call in self.calls():
            try:
                os.killpg(call["pid"], signal.SIGKILL)
            except ProcessLookupError:
                pass

    def start(self, *args, watch=True, links=None):
        command = [
            sys.executable,
            str(SCRIPT),
            "--interval",
            "0.03",
            "--retry-delay",
            "0.04",
        ]
        if watch:
            command.append("--watch")
        command.extend([str(links or self.links), *args])
        process = subprocess.Popen(
            command,
            env=self.env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        self.processes.append(process)
        return process

    def calls(self):
        path = self.root / "calls.jsonl"
        return (
            [json.loads(line) for line in path.read_text().splitlines()]
            if path.exists()
            else []
        )

    def finished(self):
        path = self.root / "finished.jsonl"
        return (
            [json.loads(line) for line in path.read_text().splitlines()]
            if path.exists()
            else []
        )

    def wait_for(self, predicate, description, timeout=5):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(0.01)
        self.fail(f"timed out waiting for {description}")

    def finish_process(self, process, expected=0):
        stdout, stderr = process.communicate(timeout=5)
        self.assertEqual(process.returncode, expected, stdout + stderr)
        return stdout, stderr

    def interrupt(self, process, expected=130):
        process.send_signal(signal.SIGINT)
        return self.finish_process(process, expected)

    def test_batch_comments_duplicate_urls_and_unterminated_last_line(self):
        self.links.write_text(
            "# comment\n; comment\n] comment\n\nhttps://example.com/one\nhttps://example.com/one\nhttps://example.com/two"
        )
        process = self.start(watch=False)
        self.finish_process(process)
        self.assertEqual(
            [call["url"] for call in self.calls()],
            ["https://example.com/one", "https://example.com/two"],
        )
        self.assertIn("--download-archive", self.calls()[0]["args"])

    def test_bom_inline_comments_and_url_fragments(self):
        self.links.write_text(
            "\ufeff# saved list\nhttps://example.com/one#fragment # note\n"
        )
        self.finish_process(self.start(watch=False))
        self.assertEqual(self.calls()[0]["url"], "https://example.com/one#fragment")

    def test_append_during_download_then_append_after_queue_is_empty(self):
        first = "https://example.com/first"
        second = "https://example.com/second"
        third = "https://example.com/third"
        self.rules.write_text(json.dumps({first: {"hold": True}}))
        self.links.write_text(first + "\n")
        process = self.start()
        self.wait_for(lambda: len(self.calls()) == 1, "first download to start")
        with self.links.open("a") as target:
            target.write(second + "\n")
        (self.root / "release").touch()
        self.wait_for(lambda: len(self.finished()) == 2, "appended download to finish")
        self.assertIsNone(process.poll(), "watcher exited at EOF")
        with self.links.open("a") as target:
            target.write(third + "\n")
        self.wait_for(
            lambda: len(self.finished()) == 3, "idle watcher to pick up third link"
        )
        self.interrupt(process)
        self.assertEqual([call["url"] for call in self.calls()], [first, second, third])

    def test_atomic_editor_replacement_and_temporary_missing_file(self):
        process = self.start()
        time.sleep(0.1)
        self.links.unlink()
        time.sleep(0.1)
        replacement = self.root / "replacement"
        replacement.write_text("https://example.com/replaced\n")
        replacement.replace(self.links)
        self.wait_for(lambda: len(self.finished()) == 1, "replacement file to be read")
        self.interrupt(process)
        self.assertEqual(self.calls()[0]["url"], "https://example.com/replaced")

    def test_restart_skips_completed_urls(self):
        self.links.write_text("https://example.com/one\n")
        self.finish_process(self.start(watch=False))
        self.links.write_text("https://example.com/one\nhttps://example.com/two\n")
        self.finish_process(self.start(watch=False))
        self.assertEqual(
            [call["url"] for call in self.calls()],
            ["https://example.com/one", "https://example.com/two"],
        )

    def test_failures_retry_without_blocking_other_urls(self):
        failed = "https://example.com/flaky"
        other = "https://example.com/other"
        self.rules.write_text(json.dumps({failed: {"fail_attempts": 2}}))
        self.links.write_text(failed + "\n" + other + "\n")
        self.finish_process(self.start(watch=False))
        self.assertEqual(
            [call["url"] for call in self.calls()], [failed, other, failed, failed]
        )
        self.finish_process(self.start(watch=False))
        self.assertEqual(len(self.calls()), 4)

    def test_exhausted_url_does_not_spin_and_does_not_block_new_link(self):
        failed = "https://example.com/broken"
        self.rules.write_text(json.dumps({failed: {"fail_attempts": 1000}}))
        self.links.write_text(failed + "\n")
        process = self.start("--max-attempts", "2")
        self.wait_for(lambda: len(self.calls()) == 2, "two failed attempts")
        time.sleep(0.15)
        self.assertEqual(len(self.calls()), 2)
        with self.links.open("a") as target:
            target.write("https://example.com/new\n")
        self.wait_for(
            lambda: "https://example.com/new" in self.finished(),
            "new link after exhausted one",
        )
        self.interrupt(process)
        self.assertEqual(len(self.calls()), 3)

    def test_batch_exhaustion_returns_failure_and_can_retry_on_restart(self):
        url = "https://example.com/broken"
        self.rules.write_text(json.dumps({url: {"fail_attempts": 2}}))
        self.links.write_text(url + "\n")
        self.finish_process(self.start("--max-attempts", "2", watch=False), expected=1)
        self.assertEqual(len(self.calls()), 2)
        self.finish_process(self.start(watch=False))
        self.assertEqual(len(self.calls()), 3)

    def test_removing_failed_link_stops_pending_retry(self):
        url = "https://example.com/removed"
        self.rules.write_text(json.dumps({url: {"fail_attempts": 1000}}))
        self.links.write_text(url + "\n")
        process = self.start("--retry-delay", "0.4")
        self.wait_for(lambda: len(self.calls()) == 1, "failed attempt")
        self.links.write_text("")
        time.sleep(0.5)
        self.interrupt(process)
        self.assertEqual(len(self.calls()), 1)

    def test_interrupt_stops_child_and_does_not_mark_success(self):
        url = "https://example.com/interrupted"
        self.rules.write_text(json.dumps({url: {"hold": True}}))
        self.links.write_text(url + "\n")
        process = self.start()
        self.wait_for(lambda: len(self.calls()) == 1, "blocked downloader")
        child_pid = self.calls()[0]["pid"]
        self.interrupt(process)
        self.assertTrue((self.root / "child-stopped").exists())
        with self.assertRaises(ProcessLookupError):
            os.kill(child_pid, 0)
        (self.root / "release").touch()
        self.finish_process(self.start(watch=False))
        self.assertEqual(len(self.calls()), 2)

    def test_same_state_cannot_have_two_workers(self):
        first = self.start()
        time.sleep(0.1)
        second = self.start(watch=False)
        _, stderr = self.finish_process(second, expected=1)
        self.assertIn("worker", stderr.lower())
        self.interrupt(first)

    def test_interrupt_kills_descendant_after_downloader_parent_exits(self):
        url = "https://example.com/descendant"
        self.rules.write_text(json.dumps({url: {"hold": True, "descendant": True}}))
        self.links.write_text(url + "\n")
        process = self.start()
        self.wait_for(
            lambda: (self.root / "descendant-ready").exists(),
            "ignoring descendant to start",
        )
        pid = int((self.root / "descendant-pid").read_text())
        self.interrupt(process)
        status = Path(f"/proc/{pid}/status")
        if status.exists():
            self.assertIn("State:\tZ", status.read_text(), "descendant remains running")

    def test_corrupt_state_is_preserved_and_rejected(self):
        state = self.root / "state.json"
        state.write_text("{not JSON")
        process = self.start("--state-file", str(state), watch=False)
        self.finish_process(process, expected=1)
        self.assertEqual(state.read_text(), "{not JSON")
        self.assertEqual(self.calls(), [])

    def test_downloader_options_are_forwarded_as_arguments(self):
        self.links.write_text("https://example.com/?a=1&b=2\n")
        self.finish_process(
            self.start(
                "--", "-P", "directory with spaces", "--no-playlist", watch=False
            )
        )
        args = self.calls()[0]["args"]
        self.assertIn("directory with spaces", args)
        self.assertIn("--no-playlist", args)
        self.assertEqual(args[-2:], ["--", "https://example.com/?a=1&b=2"])

    def test_help_and_invalid_numeric_options(self):
        help_result = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"],
            env=self.env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        self.assertIn("--watch", help_result.stdout)
        for option, value in [
            ("--interval", "0"),
            ("--interval", "nan"),
            ("--interval", "inf"),
            ("--retry-delay", "-1"),
            ("--max-attempts", "0"),
        ]:
            process = self.start(option, value, watch=False)
            stdout, stderr = process.communicate(timeout=5)
            self.assertNotEqual(process.returncode, 0, stdout + stderr)
        self.assertEqual(self.calls(), [])

    def test_managed_downloader_options_are_rejected(self):
        self.links.write_text("https://example.com/one\n")
        for option in (
            "--batch-file=other.txt",
            "-aother.txt",
            "--download-archive=other.txt",
            "--no-download-archive",
            "--no-batch-file",
            "--simulate",
            "-s",
            "--skip-download",
            "--list-formats",
            "--ignore-errors",
            "-i",
            "--config-locations=other.conf",
            "--alias",
            "-qF",
            "-qh",
            "-qU",
            "-V",
            "-U",
        ):
            process = self.start("--", option, watch=False)
            stdout, stderr = process.communicate(timeout=5)
            self.assertNotEqual(process.returncode, 0, stdout + stderr)
        self.assertEqual(self.calls(), [])

    def test_inherited_non_download_config_is_disabled(self):
        self.links.write_text("https://example.com/one\n")
        self.finish_process(self.start(watch=False))
        args = self.calls()[0]["args"]
        self.assertIn("--no-simulate", args)
        self.assertIn("--no-batch-file", args)
        self.assertIn("--ignore-config", args)
        self.assertIn("--abort-on-error", args)

    def test_input_state_and_archive_paths_must_be_distinct(self):
        self.links.write_text("https://example.com/one\n")
        original = self.links.read_bytes()
        for option in ("--state-file", "--archive"):
            process = self.start(option, str(self.links), watch=False)
            stdout, stderr = process.communicate(timeout=5)
            self.assertNotEqual(process.returncode, 0, stdout + stderr)
            self.assertEqual(self.links.read_bytes(), original)
        self.assertEqual(self.calls(), [])


if __name__ == "__main__":
    unittest.main()
