# Security Policy

## Supported Versions

Security fixes are applied to the current release line.

| Version | Supported |
|---------|-----------|
| **1.2.2** | ✅ Current |
| 1.2.1 | ✅ Best effort |
| 1.2.0 | ❌ Upgrade recommended |
| < 1.2.0 | ❌ Unsupported |

Install the latest release: `pip install --upgrade man1lab`

---

## Reporting a Vulnerability

**Do not open public GitHub Issues for security vulnerabilities.**

Use one of these channels:

1. **[GitHub Private Vulnerability Reporting](https://github.com/maniac1um/Man1Lab/security/advisories/new)** (preferred)
2. Contact the maintainer through GitHub with a private security advisory request

Include:

- Description of the vulnerability
- Steps to reproduce
- Affected version(s)
- Impact assessment (if known)
- Suggested fix (optional)

---

## What to Report

Examples of in-scope reports:

- Credential leakage paths in the codebase or packaging
- Unsafe deserialization or command execution
- Authentication or authorization flaws in future API surfaces
- Dependency vulnerabilities with a demonstrated exploit path in Man1Lab

---

## What Never to Submit

**Never include the following in a security report, issue, or pull request:**

| Item | Reason |
|------|--------|
| **API keys** | Rotate compromised keys immediately; do not share them |
| **Tokens** | GitHub, OpenAI, Anthropic, or other bearer tokens |
| **Private papers** | Research PDFs may contain unpublished work |
| **Personal credentials** | Passwords, SSH keys, certificates |
| **Large datasets** | Use secure transfer if truly required — contact maintainer first |

If you accidentally committed a secret, rotate it immediately and report only the **location** and **type** of exposure — not the secret value.

---

## Response Process

| Step | Timeline |
|------|----------|
| Acknowledgment | Within 7 days |
| Initial assessment | Within 14 days |
| Fix or mitigation plan | Depends on severity |
| Coordinated disclosure | After a patch is available |

We will:

1. Confirm receipt of your report.
2. Investigate and determine severity.
3. Develop and test a fix on a private branch when applicable.
4. Release a patched version and publish an advisory.
5. Credit reporters who wish to be acknowledged (unless you prefer anonymity).

---

## Secure Development Practices

Contributors should:

- Never commit `.env` files or API keys
- Use `api_key_reference` in model profiles — secrets belong in environment variables only
- Run `man1lab doctor` to verify configuration without printing secret values
- Review `MANIFEST.in` and package contents before release (`outputs/`, `logs/`, `mlruns/` must not be bundled)

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines.

---

## Security Contact

| Channel | Link |
|---------|------|
| Private vulnerability reporting | https://github.com/maniac1um/Man1Lab/security/advisories/new |
| Maintainer | [@maniac1um](https://github.com/maniac1um) (via GitHub Security Advisories) |

For non-security bugs, use [GitHub Issues](https://github.com/maniac1um/Man1Lab/issues). See [SUPPORT.md](SUPPORT.md).
