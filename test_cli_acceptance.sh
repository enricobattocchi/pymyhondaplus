#!/usr/bin/env bash
# CLI acceptance tests.
#
# Split into two phases:
#   Phase 1: Offline tests (--help, flag parsing, error handling) — no API calls.
#   Phase 2: Online tests (read-only API calls) — requires valid auth.
#
# Phase 1 is always safe. Phase 2 makes a small number of API calls with
# a pause between each to avoid exhausting the refresh token.

set -uo pipefail

# Activate venv if present
if [ -f .venv/bin/activate ]; then
    # shellcheck disable=SC1091
    source .venv/bin/activate
fi

PASS=0
FAIL=0

pass() { ((PASS++)); echo "  PASS: $1"; }
fail() { ((FAIL++)); echo "  FAIL: $1"; }

expect_ok() {
    local desc="$1"; shift
    if "$@" >/dev/null 2>&1; then pass "$desc"
    else fail "$desc (exit $?)"; fi
}

# ---------------------------------------------------------------------------
echo "=== Phase 1: Offline tests (no API calls) ==="
echo ""

echo "--- --help works for all subcommands ---"
all_cmds=(login logout list status location lock unlock horn
    climate-start climate-stop charge-start charge-stop
    climate-settings climate-settings-set charge-limit
    charge-schedule charge-schedule-set charge-schedule-clear
    climate-schedule climate-schedule-set climate-schedule-clear
    trips trip-detail trip-stats)
for cmd in "${all_cmds[@]}"; do
    expect_ok "$cmd --help" pymyhondaplus "$cmd" --help
done

echo ""
echo "--- --debug and --timeout on all subcommands ---"
for cmd in "${all_cmds[@]}"; do
    help_out=$(pymyhondaplus "$cmd" --help 2>&1)
    if echo "$help_out" | grep -q "\-\-debug"; then pass "$cmd has --debug"
    else fail "$cmd missing --debug"; fi
    if echo "$help_out" | grep -q "\-\-timeout"; then pass "$cmd has --timeout"
    else fail "$cmd missing --timeout"; fi
done

echo ""
echo "--- -y only on destructive commands ---"
destructive_cmds=(lock unlock horn climate-start climate-stop charge-start charge-stop
    climate-settings-set charge-limit charge-schedule-set charge-schedule-clear
    climate-schedule-set climate-schedule-clear)
for cmd in "${destructive_cmds[@]}"; do
    if pymyhondaplus "$cmd" --help 2>&1 | grep -q "\-y"; then pass "$cmd accepts -y"
    else fail "$cmd should accept -y"; fi
done

readonly_cmds=(status location list trips trip-stats climate-settings charge-schedule climate-schedule)
for cmd in "${readonly_cmds[@]}"; do
    err_out=$(pymyhondaplus "$cmd" -y 2>&1 || true)
    if echo "$err_out" | grep -q "unrecognized arguments"; then pass "$cmd rejects -y"
    else fail "$cmd should NOT accept -y"; fi
done

echo ""
echo "--- Flags work in any position (via --help, no API calls) ---"
expect_ok "lock --timeout 5 -y --help" pymyhondaplus lock --timeout 5 -y --help
expect_ok "lock --debug -y --help" pymyhondaplus lock --debug -y --help
expect_ok "lock --timeout 5 --debug -y --help" pymyhondaplus lock --timeout 5 --debug -y --help
expect_ok "status --debug --help" pymyhondaplus status --debug --help
expect_ok "status --timeout 30 --help" pymyhondaplus status --timeout 30 --help

echo ""
echo "--- Confirmation prompt (piped stdin = non-interactive, no prompt) ---"
prompt_out=$(echo "" | pymyhondaplus lock 2>&1 || true)
if echo "$prompt_out" | grep -q "Execute"; then
    fail "lock should not prompt with piped stdin"
else
    pass "lock skips prompt with piped stdin"
fi

echo ""
echo "--- Error handling (corrupted token file, no API calls) ---"
echo "not json" > /tmp/bad_honda_tokens.json

err_out=$(pymyhondaplus --token-file /tmp/bad_honda_tokens.json --storage plain status 2>&1 || true)
if echo "$err_out" | grep -q "Traceback"; then fail "clean error shows traceback"
else pass "clean error (no traceback)"; fi

debug_out=$(pymyhondaplus --token-file /tmp/bad_honda_tokens.json --storage plain status --debug 2>&1 || true)
if echo "$debug_out" | grep -q "Traceback"; then pass "--debug shows traceback"
else fail "--debug should show traceback"; fi

pymyhondaplus --token-file /tmp/bad_honda_tokens.json --storage plain status >/dev/null 2>&1 || ec=$?
if [ "${ec:-0}" -ne 0 ]; then pass "bad token file exits non-zero ($ec)"
else fail "bad token file should exit non-zero"; fi

rm -f /tmp/bad_honda_tokens.json

echo ""
echo "--- Phase 1 done ---"
P1_PASS=$PASS P1_FAIL=$FAIL

# ---------------------------------------------------------------------------
echo ""
echo "=== Phase 2: Online tests (API calls, requires valid auth) ==="
echo ""

# Pre-flight: check auth works before making many calls
if ! pymyhondaplus status >/dev/null 2>&1; then
    echo "  SKIP: Auth not working — run 'pymyhondaplus login' first."
    echo "  Skipping all online tests."
    echo ""
    echo "================================"
    echo "PASS: $PASS  FAIL: $FAIL  (online tests skipped)"
    if [ "$FAIL" -gt 0 ]; then exit 1; fi
    exit 0
fi
pass "auth pre-flight check"

echo ""
echo "--- Read-only commands ---"
# Small delay between calls to avoid token refresh races
for test_cmd in \
    "status explicit:status" \
    "status --json:--json status" \
    "list:list" \
    "location:location" \
    "climate-settings:climate-settings" \
    "charge-schedule:charge-schedule" \
    "climate-schedule:climate-schedule" \
    "trips:trips" \
    "trip-stats:trip-stats" \
; do
    desc="${test_cmd%%:*}"
    cmd="${test_cmd#*:}"
    # shellcheck disable=SC2086
    if pymyhondaplus $cmd >/dev/null 2>&1; then pass "$desc"
    else fail "$desc"; fi
    sleep 1
done

echo ""
echo "--- CSV output ---"
csv_out=$(pymyhondaplus trips --csv 2>/dev/null) || true
if echo "$csv_out" | head -1 | grep -q "^OneTripDate"; then pass "trips --csv starts with header row"
else fail "trips --csv header row"; fi
if echo "$csv_out" | grep -q "^\["; then fail "trips --csv contains vehicle header"
else pass "trips --csv no vehicle header"; fi
if echo "$csv_out" | grep -q "^Page "; then fail "trips --csv contains Page line"
else pass "trips --csv no Page line"; fi

sleep 1
stats_csv=$(pymyhondaplus trip-stats --csv 2>/dev/null) || true
if echo "$stats_csv" | wc -l | grep -q "^2$"; then pass "trip-stats --csv is header + 1 row"
else fail "trip-stats --csv row count"; fi

sleep 1
csv_loc=$(pymyhondaplus trips --csv --all --locations 2>/dev/null) || true
if echo "$csv_loc" | head -1 | grep -q "StartLat"; then pass "trips --csv --locations has StartLat column"
else fail "trips --csv --locations missing StartLat"; fi

echo ""
echo "--- Exit codes ---"
pymyhondaplus status >/dev/null 2>&1
if [ $? -eq 0 ]; then pass "status exits 0"
else fail "status should exit 0"; fi

# ---------------------------------------------------------------------------
echo ""
echo "================================"
echo "Phase 1: PASS=$P1_PASS  FAIL=$P1_FAIL"
echo "Total:   PASS=$PASS  FAIL=$FAIL"
if [ "$FAIL" -gt 0 ]; then exit 1; fi
