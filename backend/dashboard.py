"""
================================================================================
 OMBAR FL-AI Studio  -  Embedded dashboard (self-contained fallback)
================================================================================
A SINGLE self-contained HTML string (inline CSS + JS) that server.py serves
at "/" whenever the external frontend/ folder cannot be located.

This guarantees the dashboard ALWAYS renders - even if the user copied only
server.py, or the ZIP extraction flattened the folder structure.

The embedded JS talks back to the SAME backend that served it, using
relative URLs (/api/prompt, /api/status, /ws) so it works on any host/port.
================================================================================
"""

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OMBAR FL-AI Studio</title>
<style>
:root{
  --bg:#0b0f0e; --bg2:#11181a; --panel:#141d1f; --panel2:#182226;
  --border:#22302f; --text:#e7f2ee; --muted:#8aa39c;
  --accent:#2dd4a7; --accent2:#38bdf8; --warn:#f5b042; --danger:#ef5350;
  --mono:"SFMono-Regular",ui-monospace,Menlo,Consolas,monospace;
  --sans:ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
}
*{box-sizing:border-box}
html,body{margin:0;background:var(--bg);color:var(--text);font-family:var(--sans);font-size:15px;line-height:1.5}
.shell{min-height:100vh;display:flex;flex-direction:column}
.topbar{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:14px 22px;
  background:linear-gradient(180deg,#0e1514,var(--bg));border-bottom:1px solid var(--border);
  position:sticky;top:0;z-index:30;flex-wrap:wrap}
.brand{display:flex;align-items:center;gap:14px}
.mark{width:44px;height:44px;display:grid;place-items:center;
  background:linear-gradient(135deg,var(--accent),var(--accent2));color:#06120f;
  font-weight:800;border-radius:12px;box-shadow:0 6px 18px rgba(45,212,167,.35)}
.brand h1{margin:0;font-size:1.15rem}
.brand .sub{color:var(--muted);font-size:.8rem}
.scluster{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.pill{display:inline-flex;align-items:center;gap:8px;padding:6px 12px;background:var(--panel);
  border:1px solid var(--border);border-radius:999px;font-size:.8rem;color:var(--muted)}
.pill .d{width:9px;height:9px;border-radius:50%;background:var(--muted)}
.pill.ok .d{background:var(--accent);box-shadow:0 0 8px var(--accent)}
.pill.bad .d{background:var(--danger);box-shadow:0 0 8px var(--danger)}
.pill.warn .d{background:var(--warn);box-shadow:0 0 8px var(--warn)}
.pill.ok{color:var(--accent);border-color:rgba(45,212,167,.35)}
.pill.bad{color:var(--danger);border-color:rgba(239,83,80,.35)}
.btn{cursor:pointer;border:none;border-radius:10px;padding:10px 16px;font-size:.9rem;font-weight:600}
.btn.ghost{background:transparent;color:var(--muted);border:1px solid var(--border)}
.btn.ghost:hover{color:var(--text);border-color:var(--accent)}
.btn.primary{background:linear-gradient(135deg,var(--accent),var(--accent2));color:#06120f;font-weight:700;
  box-shadow:0 8px 22px rgba(45,212,167,.3)}
.btn.primary:hover{box-shadow:0 12px 28px rgba(45,212,167,.4)}
.btn.primary[disabled]{opacity:.5;cursor:not-allowed;box-shadow:none}
.work{flex:1;display:grid;grid-template-columns:minmax(0,1.15fr) minmax(0,1fr);gap:18px;padding:22px;
  width:100%;max-width:1400px;margin:0 auto}
@media(max-width:900px){.work{grid-template-columns:1fr}}
.panel{background:var(--panel);border:1px solid var(--border);border-radius:14px;padding:20px;
  box-shadow:0 10px 30px rgba(0,0,0,.45)}
.ptitle{margin:0 0 6px;font-size:1.05rem}
.phint{margin:0 0 14px;color:var(--muted);font-size:.85rem}
textarea{width:100%;resize:vertical;background:var(--bg2);color:var(--text);
  border:1px solid var(--border);border-radius:10px;padding:14px;font-family:var(--sans);
  font-size:.95rem;line-height:1.5}
textarea:focus{outline:none;border-color:var(--accent);box-shadow:0 0 0 3px rgba(45,212,167,.15)}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0}
.chip{background:var(--panel2);color:var(--muted);border:1px solid var(--border);border-radius:999px;
  padding:6px 12px;font-size:.78rem;cursor:pointer}
.chip:hover{color:var(--text);border-color:var(--accent);background:rgba(45,212,167,.08)}
.act{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-top:6px}
.urlwrap{margin-left:auto;display:inline-flex;align-items:center;gap:8px;font-size:.78rem;color:var(--muted)}
.urlwrap input{background:var(--bg2);color:var(--text);border:1px solid var(--border);border-radius:8px;
  padding:7px 10px;font-family:var(--mono);font-size:.8rem;width:200px}
.urlwrap input:focus{outline:none;border-color:var(--accent)}
.plan{margin-top:18px;background:var(--bg2);border:1px solid var(--border);border-left:3px solid var(--accent);
  border-radius:10px;padding:14px 16px}
.planh{display:flex;justify-content:space-between;align-items:center}
.planh h3{margin:0;font-size:.95rem}
.conf{font-family:var(--mono);font-size:.78rem;color:var(--accent)}
.planlist{margin:10px 0 0;padding-left:20px}
.planlist li{margin:5px 0;font-size:.85rem}
.tag{display:inline-block;padding:1px 8px;border-radius:6px;font-size:.68px;margin-right:6px;
  font-family:var(--mono);text-transform:uppercase}
.tag.beat{background:rgba(45,212,167,.15);color:var(--accent)}
.tag.mix{background:rgba(56,189,248,.15);color:var(--accent2)}
.tag.arrange{background:rgba(245,176,66,.15);color:var(--warn)}
.tag.system{background:rgba(138,163,156,.18);color:var(--muted)}
.loghead{display:flex;justify-content:space-between;align-items:center}
.as{font-size:.78rem;color:var(--muted);display:inline-flex;align-items:center;gap:6px}
.logstream{margin-top:10px;height:320px;overflow-y:auto;background:#0a1011;border:1px solid var(--border);
  border-radius:10px;padding:12px;font-family:var(--mono);font-size:.8rem;line-height:1.55;color:#cde7df}
.logstream .ts{color:#5f7773}
.logstream .ev{color:var(--accent2)}
.logstream .ev.ok{color:var(--accent)}
.logstream .ev.err{color:var(--danger)}
.logstream .ev.warn{color:var(--warn)}
.hist{margin-top:10px;max-height:220px;overflow-y:auto;display:flex;flex-direction:column;gap:8px}
.hist .it{background:var(--bg2);border:1px solid var(--border);border-radius:8px;padding:10px 12px;font-size:.83rem}
.hist .it .t{display:flex;justify-content:space-between;color:var(--muted);font-size:.72rem;margin-bottom:4px}
.hist .it .p{color:var(--text)}
.hist .it .r.ok{color:var(--accent)}
.hist .it .r.bad{color:var(--danger)}
.hist .empty{color:var(--muted);font-size:.82rem;text-align:center;padding:14px 0}
.logstream::-webkit-scrollbar,.hist::-webkit-scrollbar{width:8px}
.logstream::-webkit-scrollbar-thumb,.hist::-webkit-scrollbar-thumb{background:#23322f;border-radius:8px}
.footer{margin-top:auto;display:flex;justify-content:space-between;gap:14px;padding:12px 22px;
  background:#0a1011;border-top:1px solid var(--border);color:var(--muted);font-size:.76rem;
  font-family:var(--mono);flex-wrap:wrap}
.toast{position:fixed;bottom:22px;left:50%;transform:translateX(-50%);background:var(--panel2);
  color:var(--text);border:1px solid var(--border);border-left:3px solid var(--accent);padding:12px 18px;
  border-radius:10px;box-shadow:0 10px 30px rgba(0,0,0,.45);z-index:100;font-size:.88rem;max-width:90vw}
.toast.err{border-left-color:var(--danger)}
.toast.warn{border-left-color:var(--warn)}
.spin{display:inline-block;width:14px;height:14px;border:2px solid rgba(6,18,15,.3);
  border-top-color:#06120f;border-radius:50%;animation:sp .7s linear infinite}
@keyframes sp{to{transform:rotate(360deg)}}
.notice{margin-top:14px;padding:10px 14px;border-radius:8px;background:rgba(245,176,66,.1);
  border:1px solid rgba(245,176,66,.3);color:var(--warn);font-size:.8rem}
</style>
</head>
<body>
<div class="shell">
  <header class="topbar">
    <div class="brand">
      <div class="mark">AI</div>
      <div>
        <h1>OMBAR FL-AI Studio</h1>
        <div class="sub">Natural-language control for FL Studio via MCP</div>
      </div>
    </div>
    <div class="scluster" id="sc">
      <div class="pill" data-k="backend"><span class="d"></span><span>Backend :8080</span></div>
      <div class="pill" data-k="mcp"><span class="d"></span><span>MCP :9787</span></div>
      <div class="pill" data-k="fl"><span class="d"></span><span>FL Studio</span></div>
      <button class="btn ghost" id="ref" title="Refresh">&#8635;</button>
    </div>
  </header>

  <main class="work">
    <section class="panel">
      <h2 class="ptitle">Prompt Studio</h2>
      <p class="phint">Ketik perintah natural-language. AI menerjemahkan ke perintah FL Studio
        (BPM, beat, instrumen, vocal chain, struktur lagu).
        <span id="modeTag" style="color:var(--accent2);font-family:var(--mono)">embedded mode</span>
      </p>
      <div id="noticeBox"></div>
      <textarea id="pi" rows="4"
        placeholder="Contoh: buat beat hip-hop 90 bpm di A minor, kasih 808 dan hi-hat, lalu pasang vocal chain di insert 6 dengan auto-tune, eq, kompresor maximus, reverb"></textarea>
      <div class="chips">
        <button class="chip" data-p="buat beat hip-hop 90 bpm di A minor dengan 808, kick, snare, hi-hat">Hip-Hop 90 BPM</button>
        <button class="chip" data-p="buat beat papua pop 95 bpm dengan FL Keys dan Sytrus">Papua Pop</button>
        <button class="chip" data-p="buat beat EDM 128 bpm dengan kick four-on-the-floor">EDM 128</button>
        <button class="chip" data-p="pasang vocal chain di insert 6 dengan auto-tune, eq, kompresor maximus, reverb">Vocal Chain</button>
        <button class="chip" data-p="atur struktur lagu: intro, verse, chorus, drop, outro">Song Structure</button>
        <button class="chip" data-p="remix track: duplicate verse jadi drop dan automate filter cutoff">Remix + Automation</button>
      </div>
      <div class="act">
        <button id="send" class="btn primary"><span id="sendIco">&#9658;</span> Kirim ke FL Studio</button>
        <button id="clr" class="btn ghost">Bersihkan</button>
      </div>
      <div class="plan" id="planBox" style="display:none">
        <div class="planh"><h3>Rencana AI</h3><span class="conf" id="conf"></span></div>
        <ol class="planlist" id="planList"></ol>
      </div>
    </section>

    <section class="panel">
      <div class="loghead">
        <h2 class="ptitle">Live Console</h2>
        <label class="as"><input type="checkbox" id="as" checked> auto-scroll</label>
      </div>
      <div class="logstream" id="log"></div>
      <h2 class="ptitle" style="margin-top:22px">Riwayat Perintah</h2>
      <div class="hist" id="hist"></div>
    </section>
  </main>

  <footer class="footer">
    <span>OMBAR FL-AI Studio &middot; FastAPI :8080 &middot; MCP :9787</span>
    <span id="wsState">WebSocket: idle</span>
    <span>v1.5.0 embedded</span>
  </footer>
</div>
<div id="toast" class="toast" style="display:none"></div>
<script>
(function(){
  var $=function(id){return document.getElementById(id)};
  function nowT(){return new Date().toLocaleTimeString("id-ID",{hour12:false})}
  function toast(m,k){var t=$("toast");t.textContent=m;t.className="toast"+(k?" "+k:"");t.style.display="block";
    clearTimeout(toast._);toast._=setTimeout(function(){t.style.display="none"},3200)}
  function log(ev,msg,kind){var d=document.createElement("div");d.className="line";
    d.innerHTML='<span class="ts">['+nowT()+']</span> <span class="ev '+(kind||"")+'">'+(ev||"")+'</span> <span class="msg"></span>';
    d.querySelector(".msg").textContent=msg;$("log").appendChild(d);
    if($("as").checked)$("log").scrollTop=$("log").scrollHeight}
  function setS(k,s){var p=document.querySelector('.pill[data-k="'+k+'"]');if(!p)return;
    p.className="pill "+s}
  // The embedded dashboard ALWAYS uses relative URLs (same origin as backend)
  function api(path){return path}  // relative
  function wsUrl(){var loc=window.location;return (loc.protocol==="https:"?"wss:":"ws:")+loc.host+"/ws"}
  function pollStatus(){
    fetch(api("/api/status")).then(function(r){return r.json()}).then(function(d){
      setS("backend","ok");setS("mcp",d.mcp&&d.mcp.reachable?"ok":"bad");
      setS("fl",d.fl_studio&&d.fl_studio.connected?"ok":"warn");
      log("status","backend ok | mcp "+(d.mcp.reachable?"online":"offline")+
          " | fl "+(d.fl_studio.connected?"connected":"n/a"))
    }).catch(function(e){setS("backend","bad");setS("mcp","bad");setS("fl","bad");
      log("status","backend unreachable: "+e.message,"err")})
  }
  function connectWs(){var url=wsUrl();$("wsState").textContent="WebSocket: connecting...";
    try{ws=new WebSocket(url)}catch(e){$("wsState").textContent="WebSocket: error";return}
    ws.onopen=function(){$("wsState").textContent="WebSocket: connected";log("ws","connected","ok")};
    ws.onmessage=function(e){try{var m=JSON.parse(e.data);handleEv(m)}catch(x){log("ws",e.data)}};
    ws.onclose=function(){$("wsState").textContent="WebSocket: closed";
      log("ws","disconnected - reconnect 4s","warn");setTimeout(connectWs,4000)};
    ws.onerror=function(){$("wsState").textContent="WebSocket: error"}}
  function handleEv(m){var ev=m.event||"event",p=m.payload||{},kind="",text="";
    switch(ev){
      case "prompt.received":text="prompt: "+(p.prompt||"");break;
      case "plan.ready":renderPlan(p.plan);text="rencana siap ("+(p.plan.steps||[]).length+" langkah, paralel per-wave)";kind="ok";break;
      case "wave.start":text=">> wave "+p.wave+": "+p.count+" langkah PARALEL ("+(p.tools||[]).join(", ")+")";kind="ok";break;
      case "wave.done":text="<< wave "+p.wave+" selesai ("+p.count+" langkah)";break;
      case "mcp.prewarmed":text="MCP pre-warmed: "+p.tools+" tools siap (instant mode)";kind="ok";break;
      case "step.start":text="#"+p.index+"/"+p.total+" "+p.tool+" - "+(p.note||"");break;
      case "step.done":kind=p.ok?"ok":"err";text="#"+p.index+" "+(p.ok?"OK":"GAGAL")+
        (p.result&&p.result.text?" -> "+p.result.text:"");break;
      case "plan.done":text="eksekusi selesai ("+(p.results||[]).length+" hasil)";kind="ok";break;
      case "mcp.connected":text="MCP terhubung";kind="ok";break;
      case "server.start":text="backend start | mcp "+(p.mcp_reachable?"ok":"offline");break;
      default:text=JSON.stringify(p)}
    log(ev,text,kind)}
  function renderPlan(plan){if(!plan||!plan.steps||!plan.steps.length){$("planBox").style.display="none";return}
    var ul=$("planList");ul.innerHTML="";
    plan.steps.forEach(function(s){var li=document.createElement("li");
      li.innerHTML='<span class="tag '+s.group+'">'+s.group+'</span><b>'+s.tool+'</b> - '+(s.note||"")+
        ' <code style="color:#8aa39c">'+JSON.stringify(s.args)+"</code>";ul.appendChild(li)});
    $("conf").textContent="confidence "+Math.round((plan.confidence||0)*100)+"%";
    $("planBox").style.display="block"}
  function sendPrompt(){var p=$("pi").value.trim();if(!p){toast("Prompt kosong","warn");return}
    $("send").disabled=true;var ic=$("sendIco");ic.innerHTML='<span class="spin"></span>';ic.textContent="";
    log("send",'POST /api/prompt  "'+p.slice(0,60)+(p.length>60?"...":"")+'"');
    fetch(api("/api/prompt"),{method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({prompt:p})}).then(function(r){return r.text()}).then(function(raw){
      var d;try{d=JSON.parse(raw)}catch(e){d={ok:false,error:"Bad JSON"}}
      if(d.ok){renderPlan(d.plan);var ok=(d.results||[]).filter(function(x){return x&&x.ok!==false}).length;
        addHist(p,true,ok+"/"+(d.results||[]).length+" langkah OK");
        toast("Selesai: "+ok+"/"+(d.results||[]).length+" langkah OK");
        log("done","respons diterima ("+(d.results||[]).length+" hasil)","ok")}
      else{addHist(p,false,d.error||"gagal");toast("Gagal: "+(d.error||"unknown"),"err");
        log("done","error: "+(d.error||"unknown"),"err")}
    }).catch(function(e){addHist(p,false,"koneksi gagal");
      toast("Tidak bisa hubungi backend - jalankan server.py","err");
      log("done","fetch error: "+e.message,"err")}).then(function(){
      $("send").disabled=false;ic.innerHTML="&#9658;"})}
  function addHist(p,ok,sm){hist.unshift({time:nowT(),prompt:p,ok:ok,sm:sm});hist=hist.slice(0,25);renderHist()}
  var hist=[];
  try{var h=localStorage.getItem("ombar.hist2");if(h)hist=JSON.parse(h)}catch(e){}
  function renderHist(){if(!hist.length){$("hist").innerHTML='<div class="empty">Belum ada perintah.</div>';return}
    $("hist").innerHTML="";hist.forEach(function(h){var it=document.createElement("div");it.className="it";
      it.innerHTML='<div class="t"><span>'+h.time+'</span><span class="r '+(h.ok?"ok":"bad")+'">'+(h.ok?"OK":"GAGAL")+
        '</span></div><div class="p"></div><div class="t" style="margin-top:4px"><span>'+h.sm+'</span></div>';
      it.querySelector(".p").textContent=h.prompt;$("hist").appendChild(it)})}
  $("send").addEventListener("click",sendPrompt);
  $("pi").addEventListener("keydown",function(e){if((e.ctrlKey||e.metaKey)&&e.key=="Enter"){e.preventDefault();sendPrompt()}});
  $("clr").addEventListener("click",function(){$("pi").value="";$("planBox").style.display="none";$("pi").focus()});
  Array.prototype.forEach.call(document.querySelectorAll(".chip"),function(c){
    c.addEventListener("click",function(){$("pi").value=c.getAttribute("data-p");$("pi").focus()})});
  $("ref").addEventListener("click",pollStatus);
  // Show notice if embedded (frontend folder was missing)
  try{fetch(api("/api/paths")).then(function(r){return r.json()}).then(function(d){
    if(d.embedded){var n=$("noticeBox");n.innerHTML='<div class="notice"><b>Catatan:</b> '+
      'Folder frontend eksternal tidak ditemukan, jadi dashboard tertanam (embedded) dipakai. '+
      'Path yang dicari: '+d.searched.join(", ")+"."+
      " Untuk pakai frontend penuh, ekstrak folder <code>frontend/</code> sejajar dengan <code>backend/</code>.</div>";
      log("info","embedded dashboard active (frontend folder missing)","warn")}})}
  catch(e){}
  renderHist();log("boot","OMBAR FL-AI Studio dashboard ready (embedded)");pollStatus();connectWs();
  setInterval(pollStatus,15000)
})();
</script>
</body>
</html>"""
