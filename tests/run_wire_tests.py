#!/usr/bin/env python3
# SPDX-License-Identifier: CC0-1.0
# Public-domain example code (CC0) - see ../LICENSE.
"""Run every B-BBMD Wire Test, one after another, and report one result.

    python3 tests/run_wire_tests.py [--exe build/BACnetExampleBBBMD] [--port 47900]

Exit code 0 = every check in every script passed. [KNOWN GAP] lines are reported but
do not fail the run (TODO.md). failure_modes_test.py waits out a foreign device's
grace period, so the whole run takes about two minutes.
"""
import subprocess
import sys
from pathlib import Path

import bbmd_setup as setup

TESTS = Path(__file__).resolve().parent
SCRIPTS = ["forwarding_test.py", "tables_test.py", "failure_modes_test.py"]


def main():
    args = setup.parser(__doc__).parse_args()
    outcomes = []
    for script in SCRIPTS:
        print(f"\n===== {script} =====", flush=True)
        run = subprocess.run([sys.executable, "-B", str(TESTS / script), "--exe", args.exe, "--port", str(args.port)],
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        print(run.stdout, end="", flush=True)
        totals = [line for line in run.stdout.splitlines() if "checks passed" in line]
        outcomes.append((script, run.returncode, totals[-1] if totals else "no summary"))

    print("\n===== summary =====")
    for script, returncode, totals in outcomes:
        print(f"{'PASS' if returncode == 0 else 'FAIL'}  {script:26} {totals}")
    failed = [script for script, returncode, _ in outcomes if returncode != 0]
    print("ALL WIRE TESTS PASSED" if not failed else f"FAILED: {', '.join(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
