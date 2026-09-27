"""Run SimpleVisualPlanner's test suite before releasing (proposal id 7) and produce an
HTML report with a clear pass/fail summary shown right at the top.

Usage:
    python run_tests.py            # fast suite only (skips real-browser UI tests)
    python run_tests.py --ui       # UI (Playwright) tests only
    python run_tests.py --all      # everything

Any other arguments are passed straight through to pytest (e.g. `-k user_admin`,
`-v`). See README.md ("Running the tests") for setup (requirements-dev.txt,
`playwright install chromium` for --ui/--all).
"""
import subprocess
import sys
from pathlib import Path

REPORT_PATH = Path(__file__).resolve().parent / "test-report.html"


def main() -> int:
    args = sys.argv[1:]
    if "--ui" in args:
        marker_args = ["-m", "ui"]
        args.remove("--ui")
    elif "--all" in args:
        marker_args = []
        args.remove("--all")
    else:
        marker_args = ["-m", "not ui"]

    cmd = [
        sys.executable, "-m", "pytest",
        *marker_args,
        f"--html={REPORT_PATH}", "--self-contained-html",
        *args,
    ]
    print("Running:", " ".join(cmd))
    result = subprocess.run(cmd)

    print()
    print(f"Test report: {REPORT_PATH.as_uri()}")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
