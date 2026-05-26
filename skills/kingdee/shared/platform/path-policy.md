# Path Policy

## Stable Path Contract

Shared Kingdee skills use these path categories:

- repository-relative paths for tracked skill files
- explicit user-provided project paths for target codebases
- adapter-owned paths for host installation and synchronization
- temporary paths only for generated local evidence or caches

## Do

- Resolve paths from an explicit root argument or the current workspace.
- Normalize user input before comparing paths.
- Keep generated caches outside committed source unless the owning skill explicitly tracks them.
- Document local-only configuration as examples or templates, not real secrets.

## Do Not

- Hard-code a specific user's agent home directory into shared logic.
- Depend on one IDE's private skill directory from a shared skill.
- Track files whose names contain backslash separators from a downloaded archive.
- Rewrite existing active skill locations during a guardrail or cleanup pass.
- Delete downloaded source material as part of migration documentation.

## Review Checklist

- Can the file be checked out on Windows without path corruption?
- Can the same instructions run from macOS without changing separators?
- Is the path owned by shared logic, an adapter, or a user project?
- Is any host-specific path isolated to adapter/install documentation?
