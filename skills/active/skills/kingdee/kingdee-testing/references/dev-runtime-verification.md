# Dev Runtime Verification

## Probe Policy

- Only probe explicit dev/test URLs or user-approved targets.
- Default methods are read-only: `GET`, `HEAD`, or `OPTIONS`.
- Mutating methods such as `POST`, `PUT`, `PATCH`, and `DELETE` require explicit user approval and should not be the default path.
- Never change production or metadata configuration from this workflow.

## Minimal Probe Steps

1. Confirm target URL and environment label.
2. Add only required headers, such as cookies or CSRF tokens supplied by the user or environment.
3. Run `run_dev_probe.py` with a timeout and optional expected status.
4. Save status, headers, elapsed time, and a capped response preview.
5. If the response indicates auth, CSRF, or permission failure, report it as runtime evidence instead of retrying blindly.

## Example

```bash
python3 <skill-root>/scripts/run_dev_probe.py \
  --url "https://dev.example.com/ierp/api/ping" \
  --method GET \
  --expect-status 200 \
  --output /tmp/dev-probe.json
```
