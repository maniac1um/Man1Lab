# Security Policy

Man1Lab is an open-source research platform. If you believe you have found a security vulnerability, please report it responsibly.

---

## Supported Versions

Security fixes are provided for the current **1.2.x** release line. Upgrade to the latest release when possible.

| Version | Supported |
|---------|-----------|
| **1.2.x** (current: 1.2.4) | ✅ |
| 1.1.x | ❌ Best effort only |
| < 1.1 | ❌ Unsupported |

```bash
pip install --upgrade man1lab
man1lab --version
```

---

## Reporting a Vulnerability

**Do not disclose security vulnerabilities in public GitHub Issues, Discussions, or Pull Requests.**

### Preferred channel

**[GitHub Private Vulnerability Reporting](https://github.com/maniac1um/Man1Lab/security/advisories/new)**

This is the preferred way to report issues in this repository. Reports remain private until a fix is coordinated.

### If private reporting is unavailable

Contact the maintainer ([@maniac1um](https://github.com/maniac1um)) through GitHub and request a **private security advisory**. Do not post vulnerability details publicly.

### What to include

- A clear description of the issue
- Steps to reproduce (commands, configuration, or minimal code sample)
- Affected Man1Lab version (`man1lab --version`)
- Environment details when relevant (OS, Python version, install method)
- Impact assessment and suggested fix (optional)

### What not to include

Never paste secrets into a report:

| Do not send | Why |
|-------------|-----|
| API keys (OpenAI, Anthropic, DeepSeek, etc.) | Rotate compromised keys immediately |
| GitHub or other bearer tokens | Report exposure location only |
| Private research PDFs or unpublished data | Describe the scenario without attaching content |
| Passwords, SSH keys, or certificates | Rotate and report type of exposure only |

If you accidentally committed a secret, rotate it first, then report the **location** and **type** of exposure — not the secret value.

---

## Response Process

We aim to handle reports responsibly. Timelines depend on severity and complexity; no SLA is guaranteed.

Typical process:

1. **Acknowledgement** — confirm receipt of your report
2. **Investigation** — reproduce and assess severity
3. **Fix** — develop and test a patch on a private branch when applicable
4. **Release** — publish a patched version and security advisory when ready
5. **Disclosure** — coordinate public disclosure after a fix is available
6. **Credit** — acknowledge reporters who wish to be named (anonymous reports are respected)

We will keep you informed of material status changes when possible.

---

## Scope

### In scope

Security issues that affect Man1Lab users or the integrity of their environment, including:

- Credential or secret leakage in code, packaging, logs, or default configuration
- Remote code execution or command injection through Man1Lab interfaces
- Unsafe file handling (path traversal, arbitrary file write/read beyond documented workspace scope)
- Dependency vulnerabilities with a demonstrated exploit path through Man1Lab
- Authentication or authorization flaws in future API or network surfaces

### Out of scope

These are not treated as security vulnerabilities:

- LLM hallucinations, incorrect analysis, or poor reproduction quality
- Bugs in upstream model providers (OpenAI, Anthropic, DeepSeek, etc.)
- Unsupported Python versions or operating environments
- Ordinary runtime errors, misconfiguration, or missing API keys
- Feature requests and general product feedback
- Issues in third-party repositories discovered by Man1Lab but not controlled by this project

Report out-of-scope product bugs via [GitHub Issues](https://github.com/maniac1um/Man1Lab/issues). See [SUPPORT.md](SUPPORT.md).

---

## Third-Party Services and Dependencies

Man1Lab integrates with external services and libraries. Vulnerabilities in upstream systems should be reported to their respective maintainers:

| Service / dependency | Examples |
|---------------------|----------|
| LLM providers | OpenAI-compatible APIs, Anthropic, DeepSeek |
| Source control APIs | GitHub REST API (discovery) |
| Python packages | See `pyproject.toml` (Pydantic, Hydra, MLflow, Docling, etc.) |

Man1Lab stores API keys in environment variables (`.env`) and references them by name in model profiles — never in committed YAML. Users are responsible for securing their own credentials and workspace files.

---

## Secure Development

Contributors should follow basic hygiene:

- Never commit `.env` files, API keys, or tokens
- Use `api_key_reference` in model profiles; keep secrets in environment variables
- Run `man1lab doctor` to validate configuration without printing secret values

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines.

---

## Other Channels

| Need | Channel |
|------|---------|
| Security vulnerability | [Private advisory](https://github.com/maniac1um/Man1Lab/security/advisories/new) |
| Bug report | [GitHub Issues](https://github.com/maniac1um/Man1Lab/issues) |
| Questions | [GitHub Discussions](https://github.com/maniac1um/Man1Lab/discussions) or Issues |
| General support | [SUPPORT.md](SUPPORT.md) |
