# Claude Code PowerShell Setup V1.0

**Version:** 1.0
**Created:** 2026-04-13
**Status:** Draft — intended to be folded into `DESKTOP_DEPLOYMENT_GUIDE_V2.0.md` (or its successor) as a new section. Standalone for now.
**Applies to:** Any Windows machine that runs Claude Code against this repo.

---

## Overview

This guide covers two tightly coupled setup steps that must both be in place for the `postgres-dev` MCP server to connect on a Windows machine:

1. **`.mcp.json` must be Windows-compatible** — `npx`-launched MCP servers need the `cmd /c` wrapper on Windows, and the postgres server needs its connection string passed as a positional CLI argument (not via `PGHOST`/`PGUSER` env vars, which this specific server does not honor).
2. **PowerShell profile must auto-source `.env`** — Claude Code reads `${VAR}` references in `.mcp.json` from the shell environment of whichever terminal launched it. A `.env` file is not automatically loaded into the shell. A `claude` shell function in `$PROFILE` closes the gap so that the usual `cd precog-repo; claude` flow "just works" without touching the Windows registry.

The net result is that no database credentials need to be persisted outside `.env`, and nothing about the launch workflow changes for the user.

---

## Prerequisites

| Component | Notes |
|-----------|-------|
| Claude Code | Installed as `claude.exe` on `$PATH` (typically `C:\Users\<you>\.local\bin\`) |
| Node.js | Ships with `npx`, which runs the MCP server package |
| `.env` in repo root | Must define `DEV_DB_HOST`, `DEV_DB_PORT`, `DEV_DB_NAME`, `DEV_DB_USER`, `DEV_DB_PASSWORD` |
| PowerShell | 5.1+ (Windows default) or PowerShell 7+ |
| Execution policy | `RemoteSigned` or less restrictive (`Get-ExecutionPolicy -Scope CurrentUser`) |

---

## Step 1: `.mcp.json` (committed, shared across machines)

The repo-root `.mcp.json` configures the `postgres-dev` MCP server. It is committed to git and shared by every teammate. No machine-specific values live here — only `${VAR}` references that get resolved from the shell environment at Claude Code startup.

```json
{
  "mcpServers": {
    "postgres-dev": {
      "command": "cmd",
      "args": [
        "/c",
        "npx",
        "-y",
        "@modelcontextprotocol/server-postgres@0.6.2",
        "postgresql://${DEV_DB_USER}:${DEV_DB_PASSWORD}@${DEV_DB_HOST}:${DEV_DB_PORT}/${DEV_DB_NAME}"
      ]
    }
  }
}
```

**Why each piece is the way it is:**

| Detail | Reason |
|--------|--------|
| `command: "cmd"` + `/c npx ...` | On Windows, `npx` is a `.cmd` batch file. Node's `child_process.spawn` without a shell cannot invoke `.cmd` files directly; `cmd /c` hands the invocation to the Windows command processor. Claude Code emits a "Windows requires 'cmd /c' wrapper to execute npx" warning if this is missing. |
| Full `postgresql://...` URL as positional arg | `@modelcontextprotocol/server-postgres@0.6.2` reads connection info from `process.argv[2]` only. It does NOT honor libpq env vars (`PGHOST`, `PGUSER`, etc.) despite the fact that most Postgres tools (`psql`, `pg_dump`) do. A config that sets PG* env vars will fail with `Please provide a database URL as a command-line argument`. |
| Version pin `@0.6.2` | Avoids silent breakage if the MCP server package ships a breaking change. Bump deliberately. |

---

## Step 2: PowerShell profile (per-machine, NOT committed)

Claude Code reads `${VAR}` references in `.mcp.json` from the shell environment of whichever terminal launched it. `.env` files are a text convention; PowerShell does not auto-load them. Without a bridge, Claude Code reports `Missing environment variables: DEV_DB_HOST, DEV_DB_PORT, DEV_DB_NAME` (or similar) on startup.

The bridge is a `claude` function in the user's PowerShell profile that sources `.env` from the current directory (if one exists), then hands off to the real `claude.exe`.

### 2.1 Profile location

```powershell
$PROFILE
# Typical output (OneDrive-synced Documents folder):
# C:\Users\<you>\OneDrive\Documents\WindowsPowerShell\Microsoft.PowerShell_profile.ps1
#
# Without OneDrive:
# C:\Users\<you>\Documents\WindowsPowerShell\Microsoft.PowerShell_profile.ps1
```

If the file does not exist, create it (PowerShell 5.1 does not create the profile automatically):

```powershell
New-Item -ItemType File -Path $PROFILE -Force
```

### 2.2 Profile contents

Paste the following function into `$PROFILE`:

```powershell
function claude {
    $envFile = Join-Path (Get-Location) '.env'
    if (Test-Path $envFile) {
        Get-Content $envFile | ForEach-Object {
            if ($_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$') {
                $name = $Matches[1]
                $value = $Matches[2] -replace '^["'']|["'']$', ''
                [Environment]::SetEnvironmentVariable($name, $value, 'Process')
            }
        }
    }
    $realClaude = Get-Command claude -CommandType Application -ErrorAction Stop |
                  Select-Object -First 1
    & $realClaude.Source @args
}
```

### 2.3 How the function works

| Line | What it does | Why it matters |
|------|-------------|----------------|
| `Join-Path (Get-Location) '.env'` | Looks for `.env` in the current directory only | Directory-aware: running `claude` outside a repo with `.env` is a no-op for env loading |
| Regex `^\s*([A-Za-z_]...)\s*=\s*(.*?)\s*$` | Parses `KEY=VALUE` lines, rejects comments (lines starting with `#`) and blanks | Compatible with the `python-dotenv` subset used elsewhere in the project |
| `-replace '^["'']\|["'']$', ''` | Strips surrounding single or double quotes from the value | Handles `VAR="foo bar"` style entries |
| `SetEnvironmentVariable(..., 'Process')` | Writes the var only to the current PowerShell process | Secrets die when the shell exits; never touches the Windows registry |
| `Get-Command claude -CommandType Application` | Resolves to the real `claude.exe`, bypassing the function itself | Without `-CommandType Application`, `Get-Command claude` would return the function and we'd infinite-recurse |
| `& $realClaude.Source @args` | Invokes the real binary and splats every argument through | `claude`, `claude -p "..."`, `claude mcp list` — all pass through unchanged |

### 2.4 Execution policy

If `Get-ExecutionPolicy -Scope CurrentUser` returns `Restricted` or `AllSigned`, the profile will not run. Fix with:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

`RemoteSigned` allows local scripts (your profile) to run unsigned while still requiring signatures on scripts downloaded from the internet.

---

## Step 3: Verification

Open a **fresh** PowerShell window (already-running shells will not have the new profile loaded), `cd` into the repo, then:

```powershell
cd C:\Users\<you>\repos\precog-repo
claude --version          # Triggers the function; .env vars load as a side effect
$env:DEV_DB_HOST          # Should print: localhost (or whatever your .env says)
```

Then launch Claude Code normally and check MCP status:

```
claude
/mcp
```

You want to see `postgres-dev · ✓ connected`. If you see `✘ failed` or a `[Warning]` about missing env vars, see Troubleshooting below.

---

## Step 4: Clean up stale persistent env vars (if any)

If `DEV_DB_USER` / `DEV_DB_PASSWORD` (or any other DB var) were previously persisted via `setx` or System Properties, delete them once the PowerShell profile is working. Keeping two sources of truth risks silent drift: the profile function's `'Process'` scope vars will override registry vars for any shell that goes through `claude`, but any shell that does NOT (for example, a direct `psql` call) will pick up the stale registry value.

```powershell
[Environment]::SetEnvironmentVariable('DEV_DB_USER', $null, 'User')
[Environment]::SetEnvironmentVariable('DEV_DB_PASSWORD', $null, 'User')
# Repeat for any others you'd persisted.
```

Close and reopen the terminal. Verify with:

```powershell
[Environment]::GetEnvironmentVariable('DEV_DB_USER', 'User')      # empty
[Environment]::GetEnvironmentVariable('DEV_DB_PASSWORD', 'User')  # empty
```

**Note:** `setx NAME ""` does NOT actually delete — it sets the value to an empty string, which some tools treat differently than "unset." Always use `SetEnvironmentVariable(..., $null, 'User')` for clean removal.

---

## Step 5: Replicating on a new machine

Three things must be in place. OneDrive may handle one of them automatically.

| Item | How to install | OneDrive auto-syncs? |
|------|---------------|---------------------|
| `claude.exe` + Node.js + `git clone` of repo | Standard dev setup | No |
| `.env` in repo root | Copy from password manager or existing machine — **never commit to git** | No (and must never sync via any cloud service) |
| `$PROFILE` with `claude` function | Paste the function from Step 2.2, OR rely on OneDrive Documents-folder sync if enabled | Yes, if OneDrive is syncing Documents |

Quick check on a new machine after signing in:

```powershell
Test-Path $PROFILE         # True → OneDrive synced it; still verify contents with: notepad $PROFILE
                           # False → create it manually per Step 2
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `/mcp` shows `postgres-dev · ✘ failed`, no warnings | `.mcp.json` passing PG* env vars instead of positional URL | Rewrite to Step 1 format |
| `[Warning] Windows requires 'cmd /c' wrapper to execute npx` | `.mcp.json` has `"command": "npx"` | Change to `"command": "cmd"` with `/c` as first arg |
| `[Warning] Missing environment variables: DEV_DB_*` | Shell that launched Claude Code never sourced `.env` | PowerShell profile not loaded. Check `$PROFILE` exists, has the function, and execution policy is `RemoteSigned`. Open a fresh shell. |
| Function defined but `claude` still doesn't load `.env` | Running from a directory without an `.env` file | The function is directory-aware by design. `cd` into the repo root first. |
| `Please provide a database URL as a command-line argument` when running the MCP server directly | Missing positional URL | Sanity check: `npx -y @modelcontextprotocol/server-postgres@0.6.2 "postgresql://user:pass@host:port/db"` |
| `.mcp.json` changes don't take effect | MCP config is read at Claude Code startup only | Fully exit Claude Code and relaunch. `/mcp` reconnect is not enough for config changes. |
| Password with `@`, `:`, `/`, `#`, `?`, or `%` breaks the URL | URL-reserved characters in password not percent-encoded | Either regenerate the password without reserved chars, or percent-encode the value in `.env` (e.g., `@` → `%40`). |

---

## Security notes

- `.env` is gitignored and must stay that way. `.mcp.json` contains only `${VAR}` references, so it is safe to commit.
- The PowerShell profile function sets env vars at `'Process'` scope only — they never reach the Windows registry and die when the shell exits.
- `RemoteSigned` execution policy is the recommended setting. It allows local profile scripts to run while still requiring signatures on internet-downloaded scripts. Do not use `Unrestricted` or `Bypass`.
- If the `.env` file is ever synced to a cloud service (OneDrive, Dropbox, Google Drive), treat the credentials as compromised and rotate them. `.env` must stay on local disk only.

---

## Version history

| Version | Date | Summary |
|---------|------|---------|
| 1.0 | 2026-04-13 | Initial draft. Covers `.mcp.json` Windows compatibility, PowerShell profile `.env` auto-sourcing, and per-machine replication. |
