# Support

How to get help with Man1Lab.

---

## Quick Links

| Resource | Link |
|----------|------|
| Installation guide | [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md) |
| Current capabilities | [docs/CURRENT_STATUS.md](docs/CURRENT_STATUS.md) |
| Architecture | [docs/architecture/ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md) |
| Contributing | [CONTRIBUTING.md](CONTRIBUTING.md) |
| Security | [SECURITY.md](SECURITY.md) |

---

## Where to Ask Questions

**General questions** — how to install, configure models, or understand architecture:

- [GitHub Discussions](https://github.com/maniac1um/Man1Lab/discussions) — preferred for open-ended questions (if enabled)
- [GitHub Issues](https://github.com/maniac1um/Man1Lab/issues) with the `question` label — if Discussions are unavailable

Include `man1lab --version`, Python version, and OS when asking environment questions.

---

## Where to Report Bugs

**Reproducible defects** — crashes, incorrect behavior, CLI errors:

- [GitHub Issues](https://github.com/maniac1um/Man1Lab/issues) — use the **Bug Report** template

Include reproduction steps, `man1lab --version`, and relevant log excerpts. Do not paste API keys or private paper content.

---

## Where to Request Features

**Enhancement proposals** — new capabilities, CLI improvements, documentation gaps:

- [GitHub Issues](https://github.com/maniac1um/Man1Lab/issues) — use the **Feature Request** template

Check [ROADMAP.md](ROADMAP.md) first — planned work may already be documented.

---

## Security Reports

**Vulnerabilities** — credential leaks, unsafe behavior, packaging issues:

- [SECURITY.md](SECURITY.md) — use **private** vulnerability reporting only

**Never** open a public issue for security problems.

---

## Channel Guide

| Channel | Best for | Public? |
|---------|----------|---------|
| **Discussion** | How-to questions, architecture clarification, ideas | Yes |
| **Issue (bug)** | Reproducible defects with steps and logs | Yes |
| **Issue (feature)** | Concrete enhancement proposals | Yes |
| **Security advisory** | Vulnerabilities and credential exposure | **No** |

---

## Self-Service Diagnostics

Before opening an issue, try:

```bash
man1lab --version
man1lab doctor
man1lab model validate
man1lab config
```

For model configuration problems, see [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md#model-management-cli).

---

## Response Expectations

Man1Lab is a research prototype maintained by a small team. We aim to respond to issues within a reasonable timeframe but do not guarantee SLA-backed support.

For security reports, see timelines in [SECURITY.md](SECURITY.md).
