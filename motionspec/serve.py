"""Live preview: `motionspec serve spec.json` opens a local page with a scrubber, play/pause and a format switch.
Edit the spec or theme and the preview reloads. Frames are rendered on demand at preview size and are identical to the export
(same code path). Binds to 127.0.0.1 only."""
import io
import json
import os
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from PIL import Image

from .layout import FORMATS
from .render import Project, SpecError, load_spec

PAGE = """<!doctype html><meta charset=utf-8><title>motionspec preview</title>
<style>body{margin:0;background:#15171c;color:#e8eaf0;font:14px system-ui;display:flex;flex-direction:column;align-items:center;gap:12px;padding:16px}
img{max-height:68vh;max-width:96vw;border-radius:8px;background:#000}.row{display:flex;gap:10px;align-items:center;width:min(96vw,900px)}
input[type=range]{flex:1}button,select{background:#262b36;color:#e8eaf0;border:1px solid #3a4152;border-radius:6px;padding:6px 12px}
#err{color:#ff7a8a;white-space:pre-wrap;max-width:900px}#sc{color:#9aa3b2}</style>
<img id=f><div class=row><button id=p>Play</button><input id=s type=range min=0 max=1000 value=0><span id=t>0.0s</span>
<select id=fmt></select></div><div id=sc></div><div id=err></div>
<script>
let info=null,playing=false,t=0,busy=false;const f=document.getElementById('f'),s=document.getElementById('s'),T=document.getElementById('t'),E=document.getElementById('err'),S=document.getElementById('sc'),F=document.getElementById('fmt');
async function load(){const r=await fetch('/info?format='+F.value);info=await r.json();E.textContent=info.error||'';if(info.formats&&!F.options.length){info.formats.forEach(x=>F.add(new Option(x,x)));F.value=info.format}draw()}
async function draw(){if(!info||info.error||busy)return;busy=true;f.src='/frame?t='+t.toFixed(3)+'&format='+F.value+'&v='+info.version;T.textContent=t.toFixed(1)+'s / '+info.duration.toFixed(1)+'s';S.textContent=info.scenes.find(x=>t>=x.a&&t<x.b)?.label||'';s.value=Math.round(t/info.duration*1000);f.onload=f.onerror=()=>{busy=false}}
s.oninput=()=>{t=s.value/1000*info.duration;draw()};F.onchange=load;document.getElementById('p').onclick=e=>{playing=!playing;e.target.textContent=playing?'Pause':'Play'};
setInterval(()=>{if(playing&&info){t=(t+0.1)%info.duration;draw()}},100);setInterval(async()=>{const r=await fetch('/info?format='+F.value);const n=await r.json();if(n.version!==(info&&info.version)){info=n;E.textContent=n.error||'';draw()}},1500);load();
</script>"""


def serve(spec_path, port=8765, fmt=None, plugins=(), root=None, allow_abs=False, open_browser=True):
    spec_path = os.path.abspath(spec_path); state = {"ver": None, "P": {}, "error": ""}; lock = threading.Lock()

    def project(fmtname):
        mtime = max(os.path.getmtime(p) for p in {spec_path, *[os.path.join(os.path.dirname(spec_path), f) for f in os.listdir(os.path.dirname(spec_path)) if f.endswith(".json")]})
        with lock:
            if state["ver"] != mtime: state["P"].clear(); state["ver"] = mtime; state["error"] = ""
            if fmtname not in state["P"]:
                try: state["P"][fmtname] = Project(load_spec(spec_path), os.path.dirname(spec_path), fmt=fmtname, plugins=plugins, root=root, allow_abs=allow_abs)
                except (SpecError, ValueError, OSError, RuntimeError) as e: state["error"] = str(e); return None
            return state["P"][fmtname]

    base_fmt = fmt or load_spec(spec_path).get("format", "reel")

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass

        def _send(self, code, body, ctype):
            self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(body)

        def do_GET(self):
            u = urlparse(self.path); q = parse_qs(u.query); fm = (q.get("format") or [base_fmt])[0]
            if u.path == "/": return self._send(200, PAGE.encode(), "text/html; charset=utf-8")
            if fm not in FORMATS: return self._send(400, b"bad format", "text/plain")
            P = project(fm)
            if u.path == "/info":
                if P is None: return self._send(200, json.dumps({"error": state["error"], "version": str(state["ver"]), "formats": sorted(FORMATS), "format": fm, "duration": 1, "scenes": []}).encode(), "application/json")
                sc = [{"a": a, "b": b, "label": f"{i + 1}. {s['type']}"} for i, (a, b, s) in enumerate(P.timeline)]
                return self._send(200, json.dumps({"duration": P.duration, "scenes": sc, "version": str(state["ver"]), "formats": sorted(FORMATS), "format": fm, "error": ""}).encode(), "application/json")
            if u.path == "/frame" and P is not None:
                t = float((q.get("t") or ["0"])[0]); im = P.frame_at(t, int(t * P.fps)); im.thumbnail((720, 720), Image.BILINEAR)
                buf = io.BytesIO(); im.save(buf, "JPEG", quality=88); return self._send(200, buf.getvalue(), "image/jpeg")
            self._send(404, b"not found", "text/plain")

    srv = ThreadingHTTPServer(("127.0.0.1", port), H); url = f"http://127.0.0.1:{port}/"
    print(f"preview at {url}  (Ctrl+C to stop)")
    if open_browser: threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try: srv.serve_forever()
    except KeyboardInterrupt: print("\nstopped")
