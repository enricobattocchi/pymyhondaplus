# CLI Manual Acceptance Test Plan

## Argument parsing — every subcommand still works

```bash
# No subcommand (defaults to status)
pymyhondaplus
pymyhondaplus --json

# Auth commands
pymyhondaplus login --help
pymyhondaplus logout --help

# Read-only commands
pymyhondaplus list
pymyhondaplus status
pymyhondaplus status --fresh
pymyhondaplus status --watch 5s          # Ctrl+C after a couple ticks
pymyhondaplus --json status
pymyhondaplus location
pymyhondaplus climate-settings
pymyhondaplus charge-schedule
pymyhondaplus climate-schedule
pymyhondaplus trips
pymyhondaplus trips --all
pymyhondaplus trips --csv
pymyhondaplus trip-stats
pymyhondaplus trip-stats --csv

# Destructive commands (answer N to all)
pymyhondaplus lock
pymyhondaplus unlock
pymyhondaplus horn
pymyhondaplus climate-start
pymyhondaplus climate-stop
pymyhondaplus charge-start
pymyhondaplus charge-stop
pymyhondaplus charge-limit --home 80 --away 90
pymyhondaplus climate-settings-set --temp normal
pymyhondaplus charge-schedule-clear
pymyhondaplus climate-schedule-clear
```

## Flags work in any position

```bash
# --timeout and --debug after subcommand
pymyhondaplus lock --timeout 5 -y
pymyhondaplus status --debug
pymyhondaplus status --timeout 30

# --timeout and --debug before subcommand (still on main parser via defaults)
pymyhondaplus --json status

# -y after subcommand
pymyhondaplus lock -y
pymyhondaplus horn -y

# Combined flags after subcommand
pymyhondaplus lock --timeout 5 --debug -y
```

## -y only on destructive commands

```bash
# These should accept -y
pymyhondaplus lock -y --help
pymyhondaplus charge-schedule-set --help    # should show -y
pymyhondaplus climate-schedule-clear --help # should show -y

# These should NOT accept -y
pymyhondaplus status -y           # error: unrecognized arguments
pymyhondaplus trips -y            # error: unrecognized arguments
pymyhondaplus location -y         # error: unrecognized arguments
```

## Confirmation behavior

```bash
# Interactive — prompts, answer n
pymyhondaplus lock                     # "Execute 'lock'? [y/N]" → n → "Aborted."

# Skip with -y
pymyhondaplus lock -y                  # executes immediately

# Piped stdin — no prompt
echo "" | pymyhondaplus lock           # executes immediately (non-interactive)
```

## Error handling

```bash
# Clean error (no traceback)
pymyhondaplus --token-file /tmp/nope status

# Full traceback with --debug
pymyhondaplus status --debug --token-file /tmp/nope

# Exit codes
pymyhondaplus status; echo $?                              # 0
pymyhondaplus --token-file /tmp/nope status; echo $?       # 1 or 2
pymyhondaplus lock --timeout 5 -y; echo $?                 # 1 (timeout)
```

## Spinner

```bash
pymyhondaplus lock -y              # should show spinning indicator
pymyhondaplus lock -y 2>/dev/null  # spinner hidden, only result on stdout
```

## CSV output

```bash
pymyhondaplus trips --csv                    # all pages, clean CSV, no vehicle header
pymyhondaplus trips --csv --locations        # includes StartLat, StartLon, etc.
pymyhondaplus trip-stats --csv               # single row with header
pymyhondaplus --json trips --csv             # JSON wins (checked first), no crash
```

## Shell completion

```bash
eval "$(register-python-argcomplete pymyhondaplus)"
pymyhondaplus <TAB>                          # lists all subcommands
pymyhondaplus --storage <TAB>                # shows auto keyring encrypted plain
pymyhondaplus clim<TAB>                      # completes climate commands
```

## --help on every subcommand

Verify `--debug` and `--timeout` show up on all subcommands, `-y`/`--yes` only on destructive ones.

```bash
for cmd in login logout list status location lock unlock horn \
  climate-start climate-stop charge-start charge-stop \
  climate-settings climate-settings-set charge-limit \
  charge-schedule charge-schedule-set charge-schedule-clear \
  climate-schedule climate-schedule-set climate-schedule-clear \
  trips trip-detail trip-stats; do
  echo "=== $cmd ==="
  pymyhondaplus $cmd --help 2>&1 | grep -E '\-\-(debug|timeout|yes)' || echo "(none)"
done
```
