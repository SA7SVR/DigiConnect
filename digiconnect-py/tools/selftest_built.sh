#!/usr/bin/env bash
# Starts the BUILT program (the one that goes into the installer / package) in self-test mode and checks the result:
# the program must start with an empty profile, open every page and find its protocol engine. Usage: selftest_built.sh <path to the program>
set -u
EXE="$1"; OUT="$PWD/selftest.txt"; rm -f "$OUT" selftest_out.txt; rm -rf selftest_updates
[ -e "$EXE" ] || { echo "SELFTEST: program not found: $EXE"; exit 1; }
DC_SELFTEST="$OUT" DC_UPDATES_DIR="$PWD/selftest_updates" QT_QPA_PLATFORM=offscreen "$EXE" > selftest_out.txt 2>&1 &
for i in $(seq 1 90); do [ -s "$OUT" ] && break; sleep 2; done
if [ ! -s "$OUT" ]; then echo "SELFTEST: the built program wrote no result (did not start or hung)"; cat selftest_out.txt; exit 1; fi
cat "$OUT"; echo
grep -q '^OK engine=' "$OUT" || { echo "SELFTEST FAILED"; exit 1; }
grep -q 'engine=None' "$OUT" && { echo "SELFTEST FAILED: the protocol engine is not found next to the built program"; exit 1; }
echo "SELFTEST OK"
