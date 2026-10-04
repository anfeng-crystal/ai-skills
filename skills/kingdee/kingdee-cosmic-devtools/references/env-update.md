# Environment Update

Related version and resource notes: [SDK and resource knowledge](https://chatgpt.com/space/page_4da965c745c88191a07bc024728e39f1).

## Directories

`COSMIC_HOME` is the resource root. The script resolves it in this order:

1. explicit `--cosmic-home`
2. `systemProp.cosmic_home` in `gradle.properties`
3. environment variable `COSMIC_HOME`

Standard target directories:

- libs: `<COSMIC_HOME>/mservice-cosmic/lib`
- static resources: `<COSMIC_HOME>/static-file-service`
- cache: `<COSMIC_HOME>/.kddt-cache`
- staging jobs: `<COSMIC_HOME>/.kddt-staging/<job_id>`
- backups: `<COSMIC_HOME>/.kddt-backups/apply-<unique_id>`

Paths are shown with `/` as documentation separators; the CLI uses the host platform path rules at runtime.

## Resource Ownership

Before `start` or `apply`, inspect project configuration and the target directory's owner/manager. The [official KDDT update feed](https://tool.kingdee.com/kddt/idea-updatePlugins.xml), in its 2.4.2-GA notes, distinguishes a separate developer-assistant `cosmic_home` from a CosmicStudio environment directory. It directs overlapping directories to CosmicStudio management or to an independent resource directory; `apppackage-cosmic.zip` and `static-file-service.zip` are cited as diagnostic evidence, not proof of ownership by themselves.

This skill's downloader can understand a Studio-style source manifest, but that does not authorize replacing the Studio-managed environment. If the target overlaps, continue read-only diagnosis and any already authorized independent staging; do not apply there through this updater. Resolve another authorized target or use the environment's supported manager. This is a product/tool compatibility boundary, not an OS-specific path rule.

## Update Sources

The updater first tries `update.json`. If it is not available, it falls back to `update.md5`.

`update.json` mode:

- Parses `webapp.path` and `webapp.files`.
- Parses `appstore.path` and appstore libraries under `biz`, `bos`, `trd`, `cus`.
- Uses MD5 values per zip item to skip already downloaded and verified files.

`update.md5` mode:

- MC-style URLs use `cosmic.zip` and `webapp.zip`.
- Studio-style URLs use `apppackage-cosmic.zip` and `static-file-service.zip`.
- This mode is package-level only; it cannot be as precise as `update.json`.

## Job Lifecycle

- `start`: create job manifest and launch the worker. Downloads go to cache and staging only.
- `status`: read current manifest and log path.
- `resume`: continue a failed or canceled job without discarding verified downloads.
- `cancel`: mark the job as canceled; the worker stops at the next checkpoint.
- `apply`: verify all staged packages, prepare their contents, back up affected resource components, then write them into `COSMIC_HOME`.
- `rollback`: validate all backup components before restoring them; retain the original backup and hold replaced resources under its `replaced-*` directory.

Recommended operator loop:

1. Run `start --foreground` first when the network, VPN, or server state is uncertain. Background workers are suitable only after the first successful run.
2. If the command exits non-zero, run `status` and inspect `worker_log`; do not infer success from a partially populated staging directory.
3. Run `resume --foreground` after transient network errors, server restart, timeout, or `.part` leftovers. Reusing verified cache is expected; deleting staging should be a last resort.
4. Before `apply`, count staged files and compare the manifest item count. For `update.md5` mode, verify the expected package-level zips are present because per-file precision is unavailable.
5. After `apply`, run the nearest compile or launch check that uses the updated `COSMIC_HOME`.

A download or layout error pauses `apply`, not the already authorized status checks, resume, or verified conflict-free layout repair. Continue that recovery loop when evidence supports it; report a blocker when recovery is unavailable, evidence remains incomplete, or the next action needs authorization beyond the current scope. Do not repeat a failed action unchanged without new evidence.

## Network Recovery

- Downloads use `.part` files.
- If the server supports HTTP Range, resume continues the partial file.
- If Range is not supported, only the current failed file is restarted.
- Verified files are not downloaded again.

Failure handling rules:

- `0` downloaded files, missing worker log, or an empty target directory is a hard failure. Report it as failed and keep the old target unchanged.
- MD5 mismatch means the file is not trusted. Keep the file in cache/staging for inspection, but do not apply it.
- HTTP 404/403 on `update.json` may fall back to `update.md5`; HTTP errors on the actual package zips do not count as success.
- macOS shell examples should avoid GNU-only options such as `find -printf`; use Python or portable `find` output when generating reports.
- Finder-visible package checks are not evidence of correctness. Always verify on disk with absolute paths, counts, and hashes.

## Layout Validation

Resource packages must be normalized before apply or manual absorption:

- `mservice-cosmic/lib/bos`, `biz`, `trd`, and `cus` should contain jar files directly.
- Nested custom package layouts such as `cus/<module>/<file>.jar` are invalid for the local package set unless the platform manifest explicitly requires that layout.
- If nested jars are found, generate a report of source path, flattened target path, sha1, and conflict action. Move only after checking that the flattened target does not already contain a different jar with the same basename.
- Static resources belong under `static-file-service`; jar files accidentally extracted there should be reported and not loaded.

## Apply Safety

Before the first resource write, every item must have a staged file inside its job, a matching recorded SHA256 (and remote MD5 when present), a valid ZIP, and safe, conflict-free destination paths. All ZIP contents are read into temporary staging before any target backup or replacement; a bad later package leaves all old resource targets unchanged. A temporary path mirror checks aliases using the filesystem's naming rules; staging and targets must share that filesystem. This verifies local integrity against the recorded manifest, not publisher authenticity.

Legacy `cosmic/apppackage-cosmic` entries map to `mservice-cosmic/lib`; legacy static wrappers map to `static-file-service`. Backups cover affected resource components, never the whole `COSMIC_HOME` or updater staging/cache/backups. Rollback checks every source before moving a target and preserves its own backup. Old root-wide backup manifests are rejected; inspect and restore their resource components separately. Runtime I/O failures after writes begin are reported as failed with a backup for recovery; apply is not a filesystem transaction.

An authorized update includes preparation in its cache, staging, and backup directories; a hidden directory alone does not require another confirmation. Stop the affected write if actual permissions are insufficient, privilege elevation is needed, or the target is outside the authorized paths. Applying the update still requires the review summary and authorization defined in `SKILL.md`.

Manual package absorption follows the same safety model:

- Copy into a staging directory or target subdirectory only after source and target hashes are recorded.
- Keep platform extension candidates, such as Qing/DPP, ISC/DTS, Eye, and KingScript jars, in separate batches. Validate each batch by compiling and launching the local debug module.
- Delete quarantine directories only after the user explicitly approves deletion. Until then, preserve restore commands in the report.
