# Ways of working

## Source workspace

- Edit source files directly in `/home/jmnovak/projects/plexintel`, the user's open workspace.
- Do not put the primary implementation in a separate checkout or worktree under `/tmp` unless the user explicitly requests that arrangement. Keep changes visible in the user's workspace.
- `/tmp` is appropriate for source backups, isolated test data, and scratch execution directories.
- Clearly distinguish uncommitted changes, local commits, pushed branches, merges, and deployments when reporting status. A local commit does not make a change available on GitHub.

## Generated artifacts and private data

- Put temporary test logs, fixtures, reports, and scratch artifacts in a task-specific directory under `/tmp`, such as `/tmp/plexintel-<task>-<date>/`.
- Reserve `.secrets/` for credentials, persistent private runtime data, and private evidence or recovery backups that need retention. Do not use it as the default destination for routine test output, or copy temporary test logs there merely because it is ignored by Git.
- When retaining private evidence, explain its location and why it needs to persist. Keep sensitive temporary directories and files private, and keep private/generated data out of Git.
- Do not automatically move or delete existing `.secrets/` contents during cleanup; they may include required model artifacts, accounting records, recovery evidence, or backups.

These instructions record the user's working preferences. Follow the current task's scope and production boundaries; this file does not add routine approval checkpoints or override explicitly authorized work.
