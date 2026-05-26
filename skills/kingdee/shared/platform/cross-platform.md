# Cross Platform Notes

## Goal

Kingdee shared skills must work from macOS, Linux, and Windows checkouts without relying on one shell, one path separator, or one host application's private directory layout.

## Path Rules

- Use repository-relative POSIX-style paths in tracked documentation and manifests.
- In scripts, build paths with language-native path APIs instead of string concatenation.
- Do not create tracked file names that contain a backslash character.
- Do not copy downloaded artifacts whose names encode Windows separators into the active skill tree.
- Keep host-specific installation details in adapter or install documentation, not in shared skill logic.

## Command Rules

- Prefer Python or Node scripts for shared automation when shell portability matters.
- If a PowerShell example is necessary, mark it as platform-specific and provide a non-Windows equivalent when the workflow is shared.
- Do not assume user home directories, IDE cache locations, or global agent configuration directories are writable.

## Verification

From `/Users/anfeng/AI/skills/active`:

```bash
git ls-files | rg '\\' || true
```

Expected result: no tracked path contains a literal backslash. If output appears, inspect whether it is a real tracked filename issue, not just text content inside a file.
