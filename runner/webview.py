"""Virtualni LED matice v prohlizeci (pro vyvoj na PC, prehravac s --web).

Ma stejne rozhrani jako RGBMatrix z rgbmatrix (CreateFrameCanvas,
SwapOnVSync, Clear). Posledni snimek drzi v pameti a male HTTP server
(jen localhost) ho posila strance, ktera ho kresli jako mrizku LED diod.
"""
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from runner import contract as C

PAGE = """<!doctype html>
<html lang="cs"><head><meta charset="utf-8"><title>LED matice 64×64</title>
<style>
 body{margin:0;background:#111;color:#aaa;font:14px system-ui,sans-serif;
      display:flex;flex-direction:column;align-items:center;gap:10px;padding:16px}
 canvas{background:#000;width:min(90vw,640px);height:auto;image-rendering:pixelated}
 #info{min-height:1.4em}
</style></head><body>
<canvas id="c" width="640" height="640"></canvas>
<div id="info">čekám na přehrávač…</div>
<script>
const W=%(w)d, H=%(h)d, S=10, c=document.getElementById('c'), g=c.getContext('2d');
const info=document.getElementById('info');
let busy=false;
async function tick(){
  if(busy) return; busy=true;
  try{
    const r=await fetch('/frame',{cache:'no-store'});
    const name=r.headers.get('X-Animation')||'';
    const px=new Uint8Array(await r.arrayBuffer());
    g.fillStyle='#000'; g.fillRect(0,0,W*S,H*S);
    for(let y=0,i=0;y<H;y++) for(let x=0;x<W;x++,i+=3){
      const R=px[i],G=px[i+1],B=px[i+2];
      if(R|G|B){ g.fillStyle=`rgb(${R},${G},${B})`;
        g.beginPath(); g.arc(x*S+S/2,y*S+S/2,S*0.42,0,6.2832); g.fill(); }
    }
    info.textContent=name;
  }catch(e){ info.textContent='přehrávač neběží'; }
  busy=false;
}
setInterval(tick, 33);
</script></body></html>
""" % {"w": C.WIDTH, "h": C.HEIGHT}


class WebMatrix:
    class _Canvas:
        def __init__(self):
            self.data = bytes(C.WIDTH * C.HEIGHT * 3)

        def SetImage(self, img, *a, **kw):
            self.data = img.convert("RGB").tobytes()

        def Clear(self):
            self.data = bytes(C.WIDTH * C.HEIGHT * 3)

    def __init__(self, port):
        self.front = bytes(C.WIDTH * C.HEIGHT * 3)
        self.label = ""
        self._lock = threading.Lock()
        matrix = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                if self.path == "/frame":
                    with matrix._lock:
                        body, label = matrix.front, matrix.label
                    ctype = "application/octet-stream"
                elif self.path in ("/", "/index.html"):
                    body, label, ctype = PAGE.encode("utf-8"), "", "text/html; charset=utf-8"
                else:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                if label:
                    self.send_header("X-Animation", label.encode("ascii", "replace").decode())
                self.end_headers()
                self.wfile.write(body)

        self.server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def CreateFrameCanvas(self):
        return self._Canvas()

    def SwapOnVSync(self, canvas, *a, **kw):
        with self._lock:
            self.front = canvas.data
        return canvas

    def Clear(self):
        with self._lock:
            self.front = bytes(C.WIDTH * C.HEIGHT * 3)
