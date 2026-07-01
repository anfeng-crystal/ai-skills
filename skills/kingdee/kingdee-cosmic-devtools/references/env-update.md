# Environment Update

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
- backups: `<COSMIC_HOME>/.kddt-backups/<timestamp>`

Paths are shown with `/` as documentation separators; the CLI uses the host platform path rules at runtime.

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
- `apply`: verify the completed job, back up current targets, then extract staged zips into `COSMIC_HOME`.
- `rollback`: restore a previous backup manifest.

Recommended operator loop:

1. Run `start --foreground` first when the network, VPN, or server state is uncertain. Background workers are suitable only after the first successful run.
2. If the command exits non-zero, run `status` and inspect `worker_log`; do not infer success from a partially populated staging directory.
3. Run `resume --foreground` after transient network errors, server restart, timeout, or `.part` leftovers. Reusing verified cache is expected; deleting staging should be a last resort.
4. Before `apply`, count staged files and compare the manifest item count. For `update.md5` mode, verify the expected package-level zips are present because per-file precision is unavailable.
5. After `apply`, run the nearest compile or launch check that uses the updated `COSMIC_HOME`.

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

Before writing into `COSMIC_HOME`, the script checks that the job completed, paths stay inside `COSMIC_HOME`, zips do not contain unsafe paths, and a backup can be created.

Manual package absorption follows the same safety model:

- Copy into a staging directory or target subdirectory only after source and target hashes are recorded.
- Keep platform extension candidates, such as Qing/DPP, ISC/DTS, Eye, and KingScript jars, in separate batches. Validate each batch by compiling and launching the local debug module.
- Delete quarantine directories only after the user explicitly approves deletion. Until then, preserve restore commands in the report.
