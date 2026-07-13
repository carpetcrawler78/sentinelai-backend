# Claude Code Execution Errors

## 2026-06-01 20:xx -- Command too long for parsing

- **Error:** `Command too long for parsing (1068 bytes; max 965 bytes)`
- **Root cause:** Attempted to run a long inline SSH command containing nested
  shell quoting, Python code, and JSON payloads in a single command string.
  The Claude Code command parser has a hard 965-byte limit on command length.
- **Fix applied:** Write logic to a temporary script file first, SCP it to the
  remote host, then run it with a short `ssh host "python3 /tmp/script.py"`.
- **Prevention rule:** No inline command over ~800 bytes. No JSON payloads
  embedded directly in shell commands. No inline Python with nested quotes via
  SSH. Use Write + SCP + short execute pattern for all non-trivial remote logic.

### Safe pattern (use from now on)

```
# 1. Write script locally
Write /tmp/sentinelai_dashboard_audit/script.py

# 2. Copy to remote
scp /tmp/sentinelai_dashboard_audit/script.py cap@46.225.109.99:/tmp/script.py

# 3. Execute with short command
ssh cap@46.225.109.99 "python3 /tmp/script.py"

# 4. For curl JSON payloads: write to file, use --data-binary @file
curl -sS -u 'admin:REDACTED' -X POST http://localhost:3000/api/dashboards/db \
  -H 'Content-Type: application/json' --data-binary @/tmp/payload.json
```
