# Team and AI collaboration

The same repository guidance applies to every teammate and AI tool. Shared
requirements live in [docs/PROJECT.md](docs/PROJECT.md), coding rules in
[AGENTS.md](AGENTS.md), and milestone summaries in [docs/PROGRESS.md](docs/PROGRESS.md).

## Start on your own computer

1. Install Git and clone the repository into a directory you choose, as shown in
   [README.md](README.md). Use your own GitHub identity and repository access.
2. Open the repository root in your chosen editor or AI tool. No particular editor,
   connector, global skill collection or personal cloud account is required for
   documentation work.
3. Ask the AI to read `AGENTS.md` and the documents relevant to your task. If automatic
   loading is supported, use the existing tool entry point. Confirm the AI can describe
   the task, scope and verification steps before relying on that context.
4. Once the stack is selected, follow the versions and actual install/run/check
   commands recorded in `docs/PROJECT.md`. Until then, there is nothing to install
   beyond the tools needed for the documentation task.

Commands below use Git plus `cd`, which work in PowerShell, bash and zsh. Run them
one line at a time. Replace example branch names and task IDs with unique names;
choose an unused directory for a new clone or worktree. Paths are relative to the
current checkout, and teammates may choose different locations.

## Shared files and personal configuration

| Share in Git | Keep on each machine |
| --- | --- |
| Product requirements, task contracts, supported versions and lockfiles | Installed runtimes, package caches and virtual environments |
| Portable source paths and safe configuration examples | Absolute paths, machine-specific executables and local service overrides |
| `AGENTS.md` and the tool entry points | Personal AI preferences, account credentials and tool permissions |
| `.editorconfig`, `.gitattributes` and reviewed portable editor settings | Personal IDE state and connector settings containing local paths or secrets |

- Keep paths relative to the repository or a documented configuration variable.
  Use proper path APIs in application code and exact filename case.
- Keep local environment values in ignored `.env` files and optional scratch notes
  under ignored `.local/`. Add `.env.example` with placeholders when the application
  actually needs configuration; document required names and defaults.
- The native MCP configuration paths `.mcp.json` and `.cursor/mcp.json` are ignored
  by default. If needed, share reviewed `.mcp.example.json` or
  `.cursor/mcp.example.json` templates, then configure them separately on each machine.
  These example filenames are templates, not files the tools automatically load.
- Other portable tool project settings can be reviewed and committed. Personal
  preferences belong in the tool's user-level settings or documented local overrides.
  Never copy a home configuration directory or credentials into the repository.
- Git ignore rules prevent accidental additions; they are not a boundary preventing
  an AI or other software from reading files. Do not include real credentials in prompts.
- Diagnose path, permission or ownership problems on the affected machine. Do not
  turn a local workaround into a team-wide global configuration command.

## Separate tasks and working directories

Agree on a task ID, owner (person and AI if applicable), acceptance criteria, API
contract and files before concurrent work. Copy [docs/tasks/TEMPLATE.md](docs/tasks/TEMPLATE.md)
to a uniquely named task file such as `docs/tasks/map-search.md`, and fill it in.
Two AI sessions must not stage or switch branches inside the same working directory.

For one task in an otherwise idle checkout, start from the current shared main:

```text
git status
git fetch origin
git switch -c feat/your-task origin/main
```

Continue only with a clean worktree or after coordinating existing changes. Do not
discard or stash somebody else's work to make these commands succeed.

For another concurrent task on the same computer, use an independent clone or a
worktree. Run this from the repository root; choose a distinct branch and path:

```text
git fetch origin
git worktree add -b feat/second-task ../OxHack-second-task origin/main
cd ../OxHack-second-task
git status
```

Each worktree has its own working files, index and task branch, while sharing Git
objects and repository configuration. Coordinate fetches and other shared metadata
operations, and do not change repository-wide configuration while other agents run.
Use a separate clone if tasks need independent Git configuration or tooling does not
support worktrees. An agent must operate only in its assigned working directory.

Ignored local files and installed dependencies are not automatically copied into
a new worktree or clone. Configure them there using the shared setup instructions
and each teammate's own credentials. Give concurrent application instances different
ports or isolated local databases when the chosen stack requires it; document the
configuration names instead of hard-coding a particular developer's values.

## Review and integration

- Coordinate edits to shared API/schema files and lockfiles with their owner. Merge
  these changes early enough to verify integration; a branch does not avoid conflicts.
- Update your task file with changes, exact checks run, OS/runtime, outcomes and any
  unverified behavior. Keep personal absolute paths and credentials out of that record.
- Review and stage intended files explicitly, then commit and push your task branch:

```text
git diff --check
git status
```

After staging and committing the reviewed files:

```text
git push -u origin feat/your-task
```

Open a pull request targeting `main`. The task owner and integrator resolve conflicts
without discarding others' work; run the affected integration checks after merging.
The integrator updates `docs/PROGRESS.md` and team decisions in `docs/PROJECT.md`.
Task authors maintain their separate task files so several agents do not continually
overwrite the same progress table. Agree on the integrator before implementation.

Format and workflow references: [Git worktrees](https://git-scm.com/docs/git-worktree),
[Git attributes](https://git-scm.com/docs/gitattributes) and
[EditorConfig](https://editorconfig.org/).
