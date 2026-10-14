"""generate --bios must write generated/<stem>.emitter.sha, matching
tools/bios_emitter_fingerprint.sh's stamp format, or CMake's staleness check
(runtime/runtime.cmake) warns/fails on BIOS this CLI just generated cleanly."""
from pathlib import Path
from unittest import mock
import io
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import psxrecomp_cli
from sdk_progress import ProgressReporter


def fake_run(fingerprint: str, returncode: int = 0):
    def _run(cmd, **kwargs):
        return mock.Mock(returncode=returncode, stdout=fingerprint, stderr="")
    return _run


class BiosEmitterStampTest(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.fw = Path(self.tmp.name)
        (self.fw / "bios").mkdir()
        (self.fw / "tools").mkdir()
        (self.fw / "tools" / "bios_emitter_fingerprint.cmake").write_text("", encoding="utf-8")
        (self.fw / "bios" / "SCPH1001.toml").write_text(
            "[recompiler]\n"
            'seeds = "recompiler/seeds/phase2_ghidra_seeds.json"\n'
            'out_dir = "generated"\n'
            'out_stem = "SCPH1001"\n',
            encoding="utf-8",
        )
        self.progress = ProgressReporter(stream=io.StringIO(), log_stream=io.StringIO())

    def tearDown(self):
        self.tmp.cleanup()

    def test_writes_stamp_matching_fingerprint_output(self):
        with mock.patch.object(psxrecomp_cli, "_which_tool", return_value=Path("/usr/bin/cmake")), \
             mock.patch.object(psxrecomp_cli.subprocess, "run", side_effect=fake_run("deadbeef" * 8 + "\n")):
            psxrecomp_cli.write_bios_emitter_stamp(
                self.fw, "bios/SCPH1001.toml", progress=self.progress
            )
        stamp = self.fw / "generated" / "SCPH1001.emitter.sha"
        self.assertTrue(stamp.is_file())
        self.assertEqual(stamp.read_text(encoding="utf-8"), "deadbeef" * 8 + "\n")

    def test_missing_out_stem_raises(self):
        (self.fw / "bios" / "SCPH1001.toml").write_text(
            "[recompiler]\nseeds = \"x\"\nout_dir = \"generated\"\n", encoding="utf-8"
        )
        with mock.patch.object(psxrecomp_cli, "_which_tool", return_value=Path("/usr/bin/cmake")):
            with self.assertRaisesRegex(RuntimeError, "out_stem"):
                psxrecomp_cli.write_bios_emitter_stamp(
                    self.fw, "bios/SCPH1001.toml", progress=self.progress
                )

    def test_missing_cmake_raises(self):
        with mock.patch.object(psxrecomp_cli, "_which_tool", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "cmake not found"):
                psxrecomp_cli.write_bios_emitter_stamp(
                    self.fw, "bios/SCPH1001.toml", progress=self.progress
                )

    def test_fingerprint_failure_raises(self):
        with mock.patch.object(psxrecomp_cli, "_which_tool", return_value=Path("/usr/bin/cmake")), \
             mock.patch.object(psxrecomp_cli.subprocess, "run", side_effect=fake_run("", returncode=1)):
            with self.assertRaises(RuntimeError):
                psxrecomp_cli.write_bios_emitter_stamp(
                    self.fw, "bios/SCPH1001.toml", progress=self.progress
                )


if __name__ == "__main__":
    unittest.main()
