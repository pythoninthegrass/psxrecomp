#!/usr/bin/env python3
"""Guard psx_resolve_app_icon: explicit APP_ICON, game copy, framework default, NONE opt-out."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RESOLVE = REPO / "runtime" / "psx_app_icon.cmake"

_failures: list[str] = []


def check(cond: bool, what: str) -> None:
    print(f"  {'ok  ' if cond else 'FAIL'} {what}")
    if not cond:
        _failures.append(what)


def resolve(cmake: str, tmp: Path, explicit: str, game_dir: Path, fw_root: Path) -> tuple[int, str]:
    driver = tmp / "driver.cmake"
    driver.write_text(
        f'include("{RESOLVE.as_posix()}")\n'
        f'psx_resolve_app_icon(_out "{explicit}" "{game_dir.as_posix()}" "{fw_root.as_posix()}")\n'
        'message(STATUS "ICON=[${_out}]")\n',
        encoding="utf-8",
    )
    r = subprocess.run([cmake, "-P", str(driver)], capture_output=True, text=True)
    out = r.stdout + r.stderr
    icon = out.split("ICON=[", 1)[1].split("]", 1)[0] if "ICON=[" in out else ""
    return r.returncode, icon


def touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"ico")
    return path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cmake", default=shutil.which("cmake") or "cmake")
    args = ap.parse_args()

    tmp = Path(tempfile.mkdtemp(prefix="app_icon_"))
    try:
        game, fw = tmp / "game", tmp / "fw"
        game.mkdir()
        fw.mkdir()

        rc, icon = resolve(args.cmake, tmp, "", game, fw)
        check(rc == 0 and icon == "", "no icon anywhere resolves to empty")

        fw_ico = touch(fw / "assets" / "psxrecomp.ico")
        rc, icon = resolve(args.cmake, tmp, "", game, fw)
        check(rc == 0 and icon == fw_ico.as_posix(), "framework default is the last fallback")

        game_ico = touch(game / "assets" / "psxrecomp.ico")
        rc, icon = resolve(args.cmake, tmp, "", game, fw)
        check(rc == 0 and icon == game_ico.as_posix(), "game assets/ copy beats framework default")

        explicit = touch(tmp / "mine.ico")
        rc, icon = resolve(args.cmake, tmp, explicit.as_posix(), game, fw)
        check(rc == 0 and icon == explicit.as_posix(), "explicit APP_ICON beats both fallbacks")

        rc, icon = resolve(args.cmake, tmp, "NONE", game, fw)
        check(rc == 0 and icon == "", "APP_ICON NONE resolves to empty although both fallbacks exist")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if _failures:
        print(f"\n{len(_failures)} failure(s)")
        return 1
    print("\nall passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
