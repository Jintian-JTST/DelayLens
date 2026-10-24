# OxHack
Hackathon project developed at OxHack 2026, University of Oxford.

The team is building **DelayLens**: departure choices from recorded London bus
predictions, with visible data-quality and small-sample limits. Read
[PLAN.md](PLAN.md) for the agreed direction; implementation and verification are
tracked separately in [docs/PROGRESS.md](docs/PROGRESS.md).

## Start here

1. Read [AGENTS.md](AGENTS.md) for shared coding and collaboration rules.
2. Read [PLAN.md](PLAN.md) and [docs/PROJECT.md](docs/PROJECT.md) for the product,
   event constraints still to verify, MVP scope, stack and demo plan.
3. Use [docs/PROGRESS.md](docs/PROGRESS.md) for milestones, verification, blockers
   and agent handoffs.
4. Build one working end-to-end slice, verify it, then add optional features.

For team onboarding, personal configuration and concurrent human/AI tasks, read
[CONTRIBUTING.md](CONTRIBUTING.md). Each task can use the
[handoff template](tasks/TEMPLATE.md).

## AI tool entry points

| Tool | Repository instructions |
| --- | --- |
| Codex | [AGENTS.md](AGENTS.md) |
| GitHub Copilot | [.github/copilot-instructions.md](.github/copilot-instructions.md) |
| Claude Code | [CLAUDE.md](CLAUDE.md) |
| Gemini CLI | [GEMINI.md](GEMINI.md) |
| Cursor | [.cursor/rules/oxhack.mdc](.cursor/rules/oxhack.mdc) |

Keep shared guidance in `AGENTS.md`; the other files point to it.

Official format references: [Codex](https://learn.chatgpt.com/docs/agent-configuration/agents-md),
[Copilot](https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/add-custom-instructions/add-repository-instructions),
[Claude Code](https://code.claude.com/docs/en/memory),
[Gemini CLI](https://geminicli.com/docs/reference/memport/) and
[Cursor](https://cursor.com/docs/rules).

## Local setup on Windows, macOS or Linux

Choose any parent directory you can write to. These commands work in PowerShell,
bash and zsh; no particular home directory, drive or editor is required:

```text
git clone https://github.com/Jintian-JTST/OxHack.git
cd OxHack
git status
git remote -v
```

Use your own GitHub access and AI tool configuration. Local tool accounts and
connectors are optional unless a specific task needs them. Open the repository root
in your chosen tool; if it does not load rules automatically, explicitly ask it to
read `AGENTS.md` and the relevant project/task documents.

The intended stack is Python/FastAPI/NumPy with uv, React/Vite/TypeScript with
npm, Tiger Data and Vultr. The inspected main baseline currently contains
planning documents rather than runnable application tooling. Owners will add
actual setup/run/check commands with source and lockfiles; do not infer a working
app from this plan. The inherited ignore rules do not define the stack.

## Development workflow

- Check the current branch and worktree before editing; keep changes scoped.
- Use short feature branches for team tasks and coordinate shared interfaces.
- Give concurrent AI tasks separate clones or worktrees and task branches; keep
  ownership and handoffs in separate files under `tasks/`.
- Keep real credentials in ignored environment files. Add `.env.example` with
  placeholders when configuration is introduced; commit the selected lockfile.
- Run the checks relevant to the change and record the actual result.
- Update the project brief for decisions and progress notes at meaningful handoffs.

Shared text files use UTF-8 and LF through `.editorconfig` and `.gitattributes`;
Windows `.bat` and `.cmd` scripts use CRLF. Machine-specific configuration belongs
in ignored local files or each developer's user settings.

## License

[MIT](LICENSE).
