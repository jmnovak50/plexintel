# Pipeline log retention and interrupted workers

Manual run 327 was interrupted by a backend deployment on November 9, 2026 at
07:33:21 Central. The worker is part of the backend service's systemd control
group. Its last heartbeat was one second earlier; training preparation had begun,
and no new production publication occurred. Durable item checkpoints remain
available to the existing manual resume path. No pipeline is automatically resumed
by this observability fix.

Worker stdout/stderr previously lived in anonymous temporary files and were only
copied to the combined log on worker exit. A backend termination lost those files
and left the run recorded as started. Structured stage events retained counts,
but did not retain the per-item title output.

Workers now write to mode-0600 files named `logs/pipeline-run-RUNID-*.stdout.log`
and `*.stderr.log`. The parent reads bounded tails with `os.pread`, preserving the
child's write offset, and updates the original worker row while execution runs.
Credential values are redacted from UI tails. Complete files survive a backend
termination; their exact paths appear in `logs/pipeline.log` at worker launch.
They follow the existing local pipeline-log retention policy and are Git-ignored.

The pipeline page shows up to 200 distinct successfully inferred media titles per
run, with the complete total. This comes from exact UUID-correlated request and
item checkpoints, including interrupted runs whose original worker log was lost.
Reused vectors, watch IDs, owners, prompts and vectors are excluded. These counts
describe completed inference, not proof that a run published its staged results.
New media-text output also includes catalog title/show names.

Status reconciliation marks a run failed only when its heartbeat is older than
30 seconds, its registered worker no longer exists, and the shared execution lock
is free (a controller may still be finalizing after its child exits). Live workers and independent
discovery jobs are preserved. A conditional update protects concurrent heartbeats.
Completed stages remain intact; active/unreached stages become failed/skipped.
The reconciliation timestamp is explicitly not presented as a known worker-exit
time. Production-run checkpoints and their resumability are unchanged.

Use the guarded deployment command, which holds the shared execution lock
through the existing service restart and refuses active pipeline/labeling jobs:

```bash
cd /home/jmnovak/projects/plexintel
plexenv/bin/python scripts/restart_backend_safely.py --check-only
plexenv/bin/python scripts/restart_backend_safely.py --restart
```

Continue the normal deployed-code receipt verification after restarting. This
guard changes neither systemd settings nor pipeline scheduling. Inspect live
output from an existing run without starting another one:

```bash
tail -f logs/pipeline-run-RUNID-*.stdout.log
```

Actual run 327 predates retained files; its completed titles are recovered from
durable checkpoints on the pipeline page. Resuming through the existing manual
Run pipeline action reuses completed stages and proceeds through the existing
training, scoring, quality and publication gates.
