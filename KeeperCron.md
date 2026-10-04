
## Keeper cron install (parent-owned; NOT yet installed by the keeper lane)

Watchdog script: `/home/hermes/.hermes/scripts/zikai-keeper.py` (no_agent;
prints `zikai ok` / `zikai DEAD: <detail>`; relaunches serve detached via
start_new_session, log at
`profiles/clankville/cache/scratch/zikai-serve.log`). Estate convention for
no_agent watchdog alerts in this profile is `ntfy` (same as
REFLECTOR-DEADMAN / zikai-nightly-mapping). Exact command, run as the
clankville profile:

```bash
hermes cron add "every 60m" --name ZIKAI-KEEPER --no-agent --script zikai-keeper.py --deliver ntfy
```

Verified 2026-10-04: keeper revived a SIGKILLed serve within the 10s re-probe
window; healthz green after (`{"ok":true,"version":"1.0.0",...}`); revived
process is its own session leader (SID==PID), so it survives the cron jail.

## Re-verified 2026-10-04T15:27Z (zikai-keeper-cron lane, second pass)

Fresh kill -> keeper -> healthz cycle run from a clean SIGKILL of the live
serve (pid confirmed DEAD: URLError, connection refused), then
`python3 /home/hermes/.hermes/scripts/zikai-keeper.py` printed
`zikai ok (revived: version=1.0.0 idioms=1072)` exit 0; healthz then returned
`{"ok":true,"version":"1.0.0","idioms":1072,"clusters":43,"themes":5}` and the
revived process (pid 67723, started 15:27:12) is its own session leader
(SID==PID), surviving the launching terminal's teardown. Version string comes
from `importlib.metadata.version("zikai")` == 1.0.0 == tag v1.0.0 (main).
Cron install command above unchanged and matches `hermes cron create` grammar
(schedule positional, --no-agent --script under ~/.hermes/scripts/).
