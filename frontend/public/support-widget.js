(function(){"use strict";const m=`
  :host { all: initial; }

  #btn {
    position: fixed;
    bottom: 24px;
    right: 24px;
    width: 52px;
    height: 52px;
    border-radius: 50%;
    background: #2563eb;
    color: #fff;
    font-size: 22px;
    border: none;
    cursor: pointer;
    box-shadow: 0 4px 14px rgba(37,99,235,.45);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 2147483646;
    transition: background .15s;
  }
  #btn:hover { background: #1d4ed8; }

  #panel {
    position: fixed;
    bottom: 88px;
    right: 24px;
    width: 320px;
    height: 480px;
    background: #fff;
    border-radius: 12px;
    box-shadow: 0 8px 32px rgba(0,0,0,.18);
    display: flex;
    flex-direction: column;
    z-index: 2147483645;
    font-family: system-ui, -apple-system, sans-serif;
    font-size: 14px;
    overflow: hidden;
    cursor: default;
  }
  #panel.hidden { display: none; }

  #header {
    background: #2563eb;
    color: #fff;
    padding: 12px 16px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    user-select: none;
    cursor: move;
  }
  #header-title { font-weight: 600; font-size: 15px; }
  #header-actions { display: flex; gap: 6px; }
  .hbtn {
    background: rgba(255,255,255,.2);
    border: none;
    color: #fff;
    width: 24px;
    height: 24px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 13px;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .hbtn:hover { background: rgba(255,255,255,.35); }

  #tabs { display: flex; border-bottom: 1px solid #e5e7eb; }
  .tab {
    flex: 1;
    padding: 10px;
    text-align: center;
    cursor: pointer;
    color: #6b7280;
    font-weight: 500;
    font-size: 13px;
    border-bottom: 2px solid transparent;
    transition: color .1s, border-color .1s;
  }
  .tab.active { color: #2563eb; border-bottom-color: #2563eb; }

  #body { flex: 1; overflow-y: auto; padding: 14px; }

  label { display: block; font-size: 12px; color: #374151; font-weight: 500; margin-bottom: 3px; margin-top: 10px; }
  label:first-child { margin-top: 0; }
  input[type=text], textarea, select {
    width: 100%;
    box-sizing: border-box;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    padding: 7px 10px;
    font-size: 13px;
    color: #111827;
    outline: none;
    font-family: inherit;
    transition: border-color .15s;
  }
  input[type=text]:focus, textarea:focus, select:focus { border-color: #2563eb; }
  textarea { height: 90px; resize: vertical; }

  #submit-btn {
    margin-top: 14px;
    width: 100%;
    background: #2563eb;
    color: #fff;
    border: none;
    border-radius: 6px;
    padding: 9px;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    transition: background .15s;
  }
  #submit-btn:hover { background: #1d4ed8; }
  #submit-btn:disabled { background: #93c5fd; cursor: not-allowed; }

  #form-msg { margin-top: 8px; font-size: 12px; padding: 6px 10px; border-radius: 5px; display: none; }
  #form-msg.success { background: #dcfce7; color: #166534; display: block; }
  #form-msg.error { background: #fee2e2; color: #991b1b; display: block; }

  .ticket-card {
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    padding: 10px 12px;
    margin-bottom: 8px;
  }
  .ticket-card-title { font-weight: 600; color: #111827; font-size: 13px; margin-bottom: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .ticket-card-meta { display: flex; gap: 8px; align-items: center; }
  .badge { font-size: 11px; font-weight: 600; padding: 2px 7px; border-radius: 99px; text-transform: uppercase; }
  .badge-new { background: #dbeafe; color: #1d4ed8; }
  .badge-intake { background: #fef9c3; color: #854d0e; }
  .badge-in_progress { background: #ede9fe; color: #5b21b6; }
  .badge-needs_human { background: #fee2e2; color: #991b1b; }
  .badge-resolved { background: #dcfce7; color: #166534; }
  .ticket-date { font-size: 11px; color: #6b7280; }

  .empty { text-align: center; color: #6b7280; font-size: 13px; padding: 24px 0; }
  .loading { text-align: center; color: #9ca3af; font-size: 13px; padding: 16px 0; }

  #login-section { padding: 14px; }
  #login-section h3 { margin: 0 0 12px; font-size: 15px; color: #111827; }
  #login-btn {
    width: 100%;
    background: #2563eb;
    color: #fff;
    border: none;
    border-radius: 6px;
    padding: 9px;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    margin-top: 10px;
  }
  #login-btn:hover { background: #1d4ed8; }
  #login-msg { margin-top: 8px; font-size: 12px; color: #991b1b; display: none; }
`,r="support_jwt",d="support_widget_state",g="support_last_ticket";async function f(o){const t=localStorage.getItem(r);if(!t)return!1;try{const i=await fetch(`${o}/api/support/auth/whoami`,{headers:{Authorization:`Bearer ${t}`}});if(!i.ok)return!1;const e=await i.json();return Array.isArray(e.roles)&&e.roles.includes("support_reporter")}catch{return!1}}function l(o){return String(o).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;")}function x(o){const t=new Date(o.created_at*1e3).toLocaleDateString(),e=`badge badge-${(o.status||"").toLowerCase()}`,n=o.id?o.id.slice(0,8):"?",s=l(o.title||""),a=(o.status||"").replace(/_/g," ");return`
    <div class="ticket-card">
      <div class="ticket-card-title" title="${s}">${s}</div>
      <div class="ticket-card-meta">
        <span class="${e}">${a}</span>
        <span class="ticket-date">${t} · #${n}</span>
      </div>
    </div>
  `}async function u(o,t){const i=o.getElementById("tab-list");i.innerHTML='<div class="loading">Loading…</div>';try{const e=localStorage.getItem(r),n=await fetch(`${t}/api/support/tickets/`,{headers:{Authorization:`Bearer ${e}`}});if(!n.ok)throw new Error(`HTTP ${n.status}`);const s=await n.json();if(!s.length){i.innerHTML='<div class="empty">No tickets yet.</div>';return}i.innerHTML=s.map(x).join("")}catch(e){i.innerHTML=`<div class="empty">Error: ${l(e.message)}</div>`}}async function y(o,t){const i=o.getElementById("title").value.trim(),e=o.getElementById("description").value.trim(),n=o.getElementById("ticket-type").value,s=o.getElementById("submit-btn"),a=o.getElementById("form-msg");if(!i||!e){a.className="error",a.textContent="Title and description are required.";return}s.disabled=!0,s.textContent="Submitting…",a.className="",a.textContent="";try{const c=localStorage.getItem(r),p=await fetch(`${t}/api/support/tickets/`,{method:"POST",headers:{"Content-Type":"application/json",Authorization:`Bearer ${c}`},body:JSON.stringify({title:i,description:e,ticket_type:n})});if(!p.ok)throw new Error(`HTTP ${p.status}`);const h=await p.json();localStorage.setItem(g,h.id),o.getElementById("title").value="",o.getElementById("description").value="",a.className="success",a.textContent=`Ticket #${h.id.slice(0,8)} submitted!`}catch(c){a.className="error",a.textContent=`Failed: ${l(c.message)}`}finally{s.disabled=!1,s.textContent="Submit Ticket"}}async function _(o){const t=localStorage.getItem(g);if(!t)return null;try{const i=localStorage.getItem(r),e=await fetch(`${o}/api/support/tickets/${t}`,{headers:{Authorization:`Bearer ${i}`}});if(!e.ok)return null;const n=await e.json();return["NEW","INTAKE","IN_PROGRESS"].includes(n.status)?n:null}catch{return null}}const w=`
  <label>Title</label>
  <input type="text" id="title" placeholder="Brief description of the issue" />
  <label>Description</label>
  <textarea id="description" placeholder="What happened? Steps to reproduce…"></textarea>
  <label>Type</label>
  <select id="ticket-type">
    <option value="bug">Bug</option>
    <option value="feature">Feature Request</option>
    <option value="question">Question</option>
  </select>
  <button id="submit-btn">Submit Ticket</button>
  <div id="form-msg"></div>
`;class v extends HTMLElement{constructor(){super(),this._shadow=this.attachShadow({mode:"open"}),this._state="closed",this._tab="new",this._gateway="http://localhost:8000",this._dragOffX=0,this._dragOffY=0,this._onDrag=null,this._onDragEnd=null}async connectedCallback(){const t=document.querySelector("script[data-gateway-url]");if(t&&(this._gateway=t.getAttribute("data-gateway-url")),!await f(this._gateway))return;this._mount(),this._restoreState(),await _(this._gateway)&&(this._open(),this._switchTab("list"))}_mount(){const t=this._shadow,i=document.createElement("style");i.textContent=m,t.appendChild(i);const e=document.createElement("button");e.id="btn",e.title="Support",e.textContent="?",t.appendChild(e);const n=document.createElement("div");n.id="panel",n.classList.add("hidden"),n.innerHTML=`
      <div id="header">
        <span id="header-title">Support</span>
        <div id="header-actions">
          <button class="hbtn" id="min-btn" title="Minimize">−</button>
          <button class="hbtn" id="close-btn" title="Close">✕</button>
        </div>
      </div>
      <div id="tabs">
        <div class="tab active" data-tab="new">New Ticket</div>
        <div class="tab" data-tab="list">My Tickets</div>
      </div>
      <div id="body">
        <div id="tab-new">${w}</div>
        <div id="tab-list" style="display:none"><div class="loading">Loading…</div></div>
      </div>
    `,t.appendChild(n),e.addEventListener("click",()=>this._togglePanel()),t.getElementById("min-btn").addEventListener("click",()=>this._minimize()),t.getElementById("close-btn").addEventListener("click",()=>this._close()),t.querySelectorAll(".tab").forEach(s=>{s.addEventListener("click",()=>this._switchTab(s.dataset.tab))}),t.getElementById("submit-btn").addEventListener("click",()=>y(t,this._gateway)),this._makeDraggable(n,t.getElementById("header"))}_makeDraggable(t,i){this._onDrag=e=>{t.style.left=e.clientX-this._dragOffX+"px",t.style.top=e.clientY-this._dragOffY+"px",t.style.right="auto",t.style.bottom="auto"},this._onDragEnd=()=>{document.removeEventListener("mousemove",this._onDrag),document.removeEventListener("mouseup",this._onDragEnd)},i.addEventListener("mousedown",e=>{const n=t.getBoundingClientRect();this._dragOffX=e.clientX-n.left,this._dragOffY=e.clientY-n.top,document.addEventListener("mousemove",this._onDrag),document.addEventListener("mouseup",this._onDragEnd)})}_togglePanel(){this._state==="open"?this._close():this._open()}_open(){this._state="open",this._shadow.getElementById("panel").classList.remove("hidden"),localStorage.setItem(d,"open"),this._tab==="list"&&u(this._shadow,this._gateway)}_minimize(){this._state="minimized",this._shadow.getElementById("panel").classList.add("hidden"),localStorage.setItem(d,"minimized")}_close(){this._state="closed",this._shadow.getElementById("panel").classList.add("hidden"),localStorage.setItem(d,"closed")}_restoreState(){localStorage.getItem(d)==="open"&&this._open()}_switchTab(t){this._tab=t;const i=this._shadow;i.querySelectorAll(".tab").forEach(e=>e.classList.toggle("active",e.dataset.tab===t)),i.getElementById("tab-new").style.display=t==="new"?"":"none",i.getElementById("tab-list").style.display=t==="list"?"":"none",t==="list"&&u(i,this._gateway)}}customElements.define("support-bot-widget",v);function b(){if(!document.getElementById("__support-bot-widget__")){const o=document.createElement("support-bot-widget");o.id="__support-bot-widget__",document.body.appendChild(o)}}document.readyState==="loading"?document.addEventListener("DOMContentLoaded",b):b()})();
