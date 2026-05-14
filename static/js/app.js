(function(){
"use strict";

let sessionId=null,isLoading=false,docData=null,docType="generic",editorVisible=false;
let uploadedText="",uploadedFilename="";
let streamAbort=null;
const $=s=>document.querySelector(s),$$=s=>document.querySelectorAll(s);

// Landing elements
const landingPage=$("#landingPage"),landingInput=$("#landingInput"),landingSend=$("#landingSend");
const detectionBadge=$("#detectionBadge"),detectionLabel=$("#detectionLabel");
const landingFileInput=$("#landingFileInput"),landingFileInfo=$("#landingFileInfo"),landingFileName=$("#landingFileName"),landingUploadCard=$("#landingUploadCard"),landingClearFile=$("#landingClearFile");

// Workspace elements
const workspace=$("#workspace"),chatMessages=$("#chatMessages"),chatInput=$("#chatInput");
const sendBtn=$(".send-btn"),thinkingPanel=$(".thinking-panel"),suggestions=$("#suggestions");
const docPage=$("#docPage"),pageWrapper=$("#pageWrapper");
const exportMenu=$("#exportMenu"),editorPanel=$("#editorPanel"),docTypeBadge=$("#docTypeBadge");
const backBtn=$("#backBtn"),backBtnEditor=$("#backBtnEditor"),toastEl=$("#toast");
const editorDocType=$("#editorDocType"),zoomLevel=$("#zoomLevel");
const wsFileInput=$("#wsFileInput"),wsFileInfo=$("#wsFileInfo"),wsFileName=$("#wsFileName"),wsClearFile=$("#wsClearFile");

let socket=null;
function initSocket(){
  if(socket&&socket.connected)return socket;
  socket=io({
    reconnection:true,
    reconnectionAttempts:5,
    reconnectionDelay:1000,
    reconnectionDelayMax:5000,
  });
  socket.on("connect",()=>{sessionId=socket.id});
  socket.on("session_id",d=>{sessionId=d.session_id});
  socket.on("disconnect",()=>{if(!isLoading)toast("Connection lost. Reconnecting...","warning")});
  socket.on("reconnect",()=>{toast("Reconnected.","success")});
  return socket;
}
initSocket();

let zoom=1;

/* ─── DEBOUNCE ─── */
function debounce(fn,wait){
  let t;
  return function(...args){
    clearTimeout(t);
    t=setTimeout(()=>fn.apply(this,args),wait);
  };
}

/* ─── ABORT CONTROLLER ─── */
function abortStream(){
  if(streamAbort){
    try{streamAbort.abort()}catch(e){}
    streamAbort=null;
  }
}

/* ─── HELPERS ─── */
function esc(t){if(t==null)return '';const d=document.createElement("div");d.textContent=t;return d.innerHTML}
function toast(m,type){
  toastEl.textContent=m;
  toastEl.className="toast"+(type?" toast-"+type:"");
  toastEl.classList.remove("hidden");
  toastEl.style.transition="none";
  toastEl.style.opacity="0";
  toastEl.style.transform="translateX(-50%) translateY(16px) scale(0.95)";
  requestAnimationFrame(()=>{
    toastEl.style.transition="";
    toastEl.style.opacity="";
    toastEl.style.transform="";
  });
  clearTimeout(toastEl._t);
  toastEl._t=setTimeout(()=>toastEl.classList.add("hidden"),2800);
}
function addMsg(role,content){
  const div=document.createElement("div");div.className=`msg ${role}`;
  const av=role==="user"?'<div class="msg-avatar user"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg></div>':'<div class="msg-avatar agent"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg></div>';
  div.innerHTML=av+'<div class="msg-body"><div class="msg-bubble">'+esc(content)+"</div></div>";
  chatMessages.appendChild(div);chatMessages.scrollTop=chatMessages.scrollHeight;
}
function addLoad(){
  const d=document.createElement("div");d.className="msg agent";d.id="loadMsg";
  d.innerHTML='<div class="msg-avatar agent"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg></div><div class="msg-body"><div class="msg-bubble"><div class="loading-dots"><span></span><span></span><span></span></div></div></div>';
  chatMessages.appendChild(d);chatMessages.scrollTop=chatMessages.scrollHeight;
}
function rmLoad(){const e=document.getElementById("loadMsg");if(e)e.remove()}
function showThink(){thinkingPanel.classList.remove("hidden")}
function hideThink(){thinkingPanel.classList.add("hidden")}

function zoomIn(){zoom=Math.min(zoom+.1,1.5);applyZoom()}
function zoomOut(){zoom=Math.max(zoom-.1,.5);applyZoom()}
function applyZoom(){pageWrapper.style.transform=`scale(${zoom})`;zoomLevel.textContent=Math.round(zoom*100)+"%"}

function showSkeleton(){
  const sk=document.querySelector("#skeleton");
  docPage.innerHTML=sk&&sk.innerHTML?'<div class="skeleton-doc">'+sk.innerHTML+'</div>':'<div class="skeleton-doc"><div class="sk-block w-40" style="height:20px;margin:30px auto"></div><div class="sk-block w-70" style="height:8px;margin:0 auto 18px"></div><div class="sk-block w-25" style="height:10px;margin:10px 0 5px"></div><div class="sk-block w-90" style="height:7px;margin:3px 0"></div><div class="sk-block w-75" style="height:7px;margin:3px 0"></div><div class="sk-block w-25" style="height:10px;margin:14px 0 5px"></div><div class="sk-block w-95" style="height:7px;margin:3px 0"></div></div>';
  docPage.classList.remove("loaded");editorPanel.classList.add("generating");
}
function hideSkeleton(){
  if(!docPage.innerHTML||docPage.innerHTML.trim()===''){
    showSkeleton();return;
  }
  docPage.classList.add("loaded");editorPanel.classList.remove("generating");
}

function showSuggestions(items){
  suggestions.innerHTML="";suggestions.classList.remove("hidden");
  items.forEach(t=>{
    const b=document.createElement("button");b.className="sug-chip";b.textContent=t;
    b.addEventListener("click",()=>{chatInput.value=t;send()});
    suggestions.appendChild(b);
  });
}

/* ─── INTELLIGENT DOCUMENT CLASSIFIER (universal) ─── */
const docClassifiers={
  /* PROFESSIONAL / CAREER */
  resume:[
    {w:12,k:["resume","cv","curriculum vitae","résumé"]},
    {w:6,k:["ats","ats friendly"]},
    {w:4,k:["job","career","hire","applicant","candidate","work history","professional summary","achievement"]},
    {w:2,k:["experience","skills","education"]},
  ],
  cover_letter:[
    {w:12,k:["cover letter","letter of intent","letter of application","recommendation letter","reference letter","experience letter","offer letter","relieving letter"]},
    {w:6,k:["statement of purpose","personal statement","letter of recommendation"]},
    {w:4,k:["dear hiring","dear manager","application for","sincerely","regards","i am writing to"]},
  ],
  /* BUSINESS */
  proposal:[
    {w:12,k:["proposal","business plan","project proposal","business proposal","sales proposal","partnership proposal","investor pitch"]},
    {w:6,k:["scope of work","company profile","executive summary","pricing proposal"]},
    {w:4,k:["budget","pitch","solution","deliverables","timeline","investment"]},
  ],
  report:[
    {w:12,k:["report","project report","status report","research report","financial report","annual report","field report"]},
    {w:6,k:["analysis","methodology","findings","executive summary","retrospective","risk assessment","project charter"]},
    {w:4,k:["abstract","recommendations","conclusion","objectives","requirements specification","scope document"]},
    {w:2,k:["meeting minutes","agenda"]},
  ],
  /* FINANCE */
  invoice:[
    {w:12,k:["invoice","bill","statement of work","quotation","estimate","purchase order"]},
    {w:6,k:["expense report","budget proposal","financial statement"]},
    {w:4,k:["payment terms","amount due","subtotal","itemized","total due","due date"]},
    {w:2,k:["price","cost","payment"]},
  ],
  /* COMMUNICATION */
  email:[
    {w:12,k:["email","e-mail","email template"]},
    {w:6,k:["follow-up","follow up","cold outreach","newsletter","outreach","press release","internal announcement","announcement"]},
    {w:4,k:["formal letter","complaint letter","appreciation letter","cover note"]},
    {w:2,k:["subject","to:","dear","regards"]},
  ],
  /* TECHNICAL / DOCUMENTATION */
  documentation:[
    {w:12,k:["documentation","technical documentation","user guide","user manual","api documentation","api doc","reference manual"]},
    {w:8,k:["workflow","architecture","system design","design document","technical specification","technical spec","product requirements","prd","functional spec","software design","system architecture"]},
    {w:6,k:["setup guide","installation guide","configuration guide","developer guide","knowledge base","release notes","troubleshooting guide"]},
    {w:4,k:["sop","standard operating","how to","readme"]},
    {w:2,k:["guide","handbook","wiki","technical writing"]},
  ],
};

/* Extended keyword mappings that route to generic (catches everything else) */
const docGenericHints=[
  {w:8,k:["nda","non-disclosure","non disclosure","confidentiality agreement","non compete"]},
  {w:8,k:["contract","service agreement","legal agreement","terms of service","terms & conditions","terms and conditions","privacy policy","consent form","compliance"]},
  {w:8,k:["marketing plan","marketing strategy","campaign brief","ad copy","landing page","social media content","content plan","product description"]},
  {w:6,k:["business plan","business strategy","strategic plan","company overview","company profile","organizational chart"]},
  {w:6,k:["memo","memorandum","policy document","policy","procedure"]},
  {w:6,k:["project charter","scope document","timeline","roadmap","risk assessment"]},
  {w:6,k:["meeting minutes","meeting agenda","action items","discussion notes"]},
  {w:6,k:["assignment","thesis","dissertation","literature review","case study","whitepaper","white paper","abstract","research paper"]},
  {w:6,k:["letter of","formal letter","official letter","business letter"]},
  {w:4,k:["document","create a","generate","draft","write"]},
];

const docLabels={resume:"Resume",cover_letter:"Cover Letter",proposal:"Proposal",report:"Report",invoice:"Invoice",email:"Email",documentation:"Documentation",generic:"Document"};
const docSuggestions={
  resume:["Improve bullet points","Make more ATS-friendly","Quantify achievements","Shorten to 1 page","Professional tone boost"],
  cover_letter:["Make more formal","Highlight key skills","Shorten","Add enthusiasm","Company-specific optimization"],
  proposal:["Improve persuasiveness","Add pricing details","Strengthen executive summary","Add timeline"],
  report:["Summarize findings","Improve clarity","Add recommendations","Generate citations"],
  invoice:["Add line items","Recalculate totals","Add payment terms","Convert currency"],
  email:["Make more professional","Shorten","Improve tone","Add call to action"],
  documentation:["Add more sections","Improve clarity","Add examples","Format as reference","Restructure content"],
  generic:["Improve structure","Polish writing","Add more detail","Format professionally","Add sections"],
};

function detectDocType(text){
  const t=text.toLowerCase().trim();
  if(!t)return"generic";
  const scores={};
  for(const [type,groups] of Object.entries(docClassifiers)){
    let score=0;
    for(const g of groups){
      for(const kw of g.k){
        if(t.includes(kw)){score+=g.w;break}
      }
    }
    scores[type]=score;
  }
  /* Score generic hints separately */
  let genericScore=0;
  for(const g of docGenericHints){
    for(const kw of g.k){
      if(t.includes(kw)){genericScore+=g.w;break}
    }
  }
  scores.generic=genericScore;

  let best={type:"generic",score:0};
  for(const [type,score] of Object.entries(scores)){
    if(score>best.score){best={type,score}}
  }

  /* CONFIDENCE THRESHOLD: >=6 high, >=3 medium, <3 low */
  if(best.score>=6)return best.type;
  if(best.score>=3)return best.type;
  return"generic";
}

/* ─── RECENT DOCS TRACKING ─── */
function trackRecentDoc(type){
  const recent=JSON.parse(localStorage.getItem("da_recent")||"[]");
  const label=docLabels[type]||type;
  const filtered=recent.filter(r=>r.type!==type);
  filtered.unshift({type,label,timestamp:Date.now()});
  localStorage.setItem("da_recent",JSON.stringify(filtered.slice(0,10)));
}

/* ─── LANDING TO WORKSPACE TRANSITION ─── */
function revealWorkspace(type){
  docType=type;editorVisible=true;
  const label=docLabels[type]||"Document";
  docTypeBadge.textContent=label;
  editorDocType.textContent=label;
  landingPage.classList.add("hidden");
  workspace.classList.remove("hidden");
  workspace.classList.add("show");
  addMsg("assistant","I'll create a **"+label+"** for you. Let me generate that now.");
  setTimeout(()=>{if(chatInput)chatInput.focus()},600);
}

/* ─── RESUME RENDERER (UNTOUCHED) ─── */
function mdBold(t){return t.replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>')}
function renderResume(data){
  docData=data;let html="";
  html+=`<div class="r-name">${esc(data.name||"Your Name")}</div>`;
  const c=data.contact||{},parts=[];
  if(c.email)parts.push(esc(c.email));
  if(c.phone)parts.push(esc(c.phone));
  if(c.location)parts.push(esc(c.location));
  if(c.linkedin)parts.push(esc(c.linkedin));
  if(c.github)parts.push(esc(c.github));
  if(parts.length)html+=`<div class="r-contact">${parts.join('<span> | </span>')}</div>`;
  html+=`<hr class="r-divider">`;
  if(data.summary){html+=`<div class="r-section">Professional Summary</div>`;html+=`<p style="font-size:9.5pt;line-height:1.4;margin-bottom:4px">${mdBold(esc(data.summary))}</p>`;}
  if(data.experience&&data.experience.length){html+=`<div class="r-section">Experience</div>`;data.experience.forEach(exp=>{html+=`<div class="r-exp-header"><span class="r-role">${esc(exp.role)}</span><span class="r-dates">${esc(exp.dates)}</span></div><div class="r-company">${esc(exp.company)}${exp.location?" — "+esc(exp.location):""}</div>`;if(exp.bullets&&exp.bullets.length){html+="<ul>";exp.bullets.forEach(b=>{html+=`<li>${mdBold(esc(b))}</li>`});html+="</ul>"}});}
  if(data.projects&&data.projects.length){html+=`<div class="r-section">Projects</div>`;data.projects.forEach(proj=>{html+=`<div class="r-exp-header"><span class="r-role">${esc(proj.name)}</span>${proj.dates?`<span class="r-dates">${esc(proj.dates)}</span>`:""}</div>`;if(proj.technologies)html+=`<div class="r-company">${esc(proj.technologies)}</div>`;if(proj.bullets&&proj.bullets.length){html+="<ul>";proj.bullets.forEach(b=>{html+=`<li>${mdBold(esc(b))}</li>`});html+="</ul>"}});}
  if(data.education&&data.education.length){html+=`<div class="r-section">Education</div>`;data.education.forEach(edu=>{html+=`<div class="r-edu-header"><span class="r-school">${esc(edu.institution)}</span><span class="r-edu-dates">${esc(edu.dates)}</span></div><div class="r-degree">${esc(edu.degree)}${edu.location?" — "+esc(edu.location):""}</div>`;if(edu.details)html+=`<div style="font-size:9pt;color:#555">${esc(edu.details)}</div>`;});}
  if(data.skills){html+=`<div class="r-section">Skills</div>`;const sk=data.skills;if(sk.languages)html+=`<div class="r-skills"><strong>Languages:</strong> ${esc(sk.languages)}</div>`;if(sk.frameworks)html+=`<div class="r-skills"><strong>Frameworks:</strong> ${esc(sk.frameworks)}</div>`;if(sk.tools)html+=`<div class="r-skills"><strong>Tools:</strong> ${esc(sk.tools)}</div>`;}
  docPage.innerHTML=html;hideSkeleton();
}

/* ─── COVER LETTER RENDERER ─── */
function renderCoverLetter(data){
  if(!data||typeof data!=='object'){showSkeleton();return}
  docData=data;let html="<div class='cl-wrapper'>";
  const s=data.sender||{},r=data.recipient||{};
  html+=`<div class="cl-sender"><div class="cl-name">${esc(s.name||"")}</div>${esc(s.email||"")}<br>${esc(s.phone||"")}<br>${esc(s.address||"")}</div>`;
  html+=`<hr class="cl-divider">`;
  if(r.name)html+=`<div class="cl-recipient-block">${esc(r.name)}<br>${esc(r.company||"")}<br>${esc(r.address||"")}</div>`;
  html+=`<div class="cl-date-block">${esc(data.date||new Date().toLocaleDateString('en-US',{month:'long',day:'numeric',year:'numeric'}))}</div>`;
  if(data.subject)html+=`<div class="cl-subject">Re: ${esc(data.subject)}</div>`;
  html+=`<div class="cl-greeting">${esc(data.greeting||"Dear Hiring Manager,")}</div>`;
  html+=`<div class="cl-body">`;
  if(data.body&&data.body.length){data.body.forEach(p=>{html+=`<p>${mdBold(esc(p))}</p>`});}
  html+=`</div>`;
  html+=`<div class="cl-closing">${esc(data.closing||"Sincerely,")}</div>`;
  html+=`<div class="cl-signature"><div class="cl-sig-name">${esc(s.name||"Your Name")}</div><div class="cl-sig-title">${esc(s.title||"")}</div></div>`;
  html+="</div>";docPage.innerHTML=html;hideSkeleton();
}

/* ─── PROPOSAL RENDERER ─── */
function renderProposal(data){
  if(!data||typeof data!=='object'){showSkeleton();return}
  docData=data;let html="";
  html+=`<div class="prop-cover-page"><h1>${esc(data.title||"Business Proposal")}</h1><div class="prop-subtitle">Prepared by: ${esc(data.prepared_by||"")} | Prepared for: ${esc(data.prepared_for||"")}</div><div class="prop-meta">${esc(data.date||"")}</div></div>`;
  if(data.executive_summary){html+=`<div class="prop-section"><h2>Executive Summary</h2><p>${mdBold(esc(data.executive_summary))}</p></div>`;}
  if(data.problem_statement){html+=`<div class="prop-section"><h2>Problem Statement</h2><p>${mdBold(esc(data.problem_statement))}</p></div>`;}
  if(data.solution){html+=`<div class="prop-section"><h2>Proposed Solution</h2><p>${mdBold(esc(data.solution))}</p></div>`;}
  if(data.scope && data.scope.length){html+=`<div class="prop-section"><h2>Scope of Work</h2>${data.scope.map(sc=>`<div class="prop-card"><div class="prop-card-title">${esc(sc.title||"")}</div><div class="prop-card-desc">${esc(sc.description||"")}</div></div>`).join("")}</div>`;}
  if(data.pricing && data.pricing.length){html+=`<div class="prop-section"><h2>Investment</h2><table class="prop-pricing-table">${data.pricing.map(p=>`<tr><td>${esc(p.item||"")}</td><td>$${parseFloat(p.cost||0).toFixed(2)}</td></tr>`).join("")}<tr class="prop-total-row"><td>Total</td><td>$${data.pricing.reduce((s,p)=>s+parseFloat(p.cost||0),0).toFixed(2)}</td></tr></table></div>`;}else if(data.budget){html+=`<div class="prop-section"><h2>Investment</h2><p>${esc(data.budget)}</p></div>`;}
  if(data.timeline){html+=`<div class="prop-section"><h2>Timeline</h2><p>${mdBold(esc(data.timeline))}</p></div>`;}
  if(data.deliverables && data.deliverables.length){html+=`<div class="prop-section"><h2>Deliverables</h2><ul class="prop-deliverables">${data.deliverables.map(d=>`<li>${esc(d)}</li>`).join("")}</ul></div>`;}
  html+=`<div class="prop-section"><h2>Terms & Conditions</h2><p style="font-size:9pt;color:#555;line-height:1.4">This proposal is valid for 30 days. A 50% advance payment is required to commence work. Final payment due upon completion. Revisions beyond scope will be quoted separately.</p></div>`;
  html+=`<div class="prop-signature"><p>Accepted and agreed by:</p><p><span class="prop-sig-line"></span><span style="font-size:9.5pt;color:#333">${esc(data.prepared_for||"")}</span></p><p style="margin-top:4px">Date: ___________________</p></div>`;
  docPage.innerHTML=html;hideSkeleton();
}

/* ─── REPORT RENDERER ─── */
function renderReport(data){
  if(!data||typeof data!=='object'){showSkeleton();return}
  docData=data;let html="";
  html+=`<div class="rpt-title-page"><h1>${esc(data.title||"Project Report")}</h1><div class="rpt-author">Prepared by: ${esc(data.prepared_by||"")}</div><div class="rpt-date">${esc(data.date||"")}</div></div>`;
  if(data.abstract){html+=`<div class="rpt-abstract"><div class="rpt-abstract-label">Abstract</div><p>${mdBold(esc(data.abstract))}</p></div>`;}
  html+=`<div class="rpt-toc"><div class="rpt-toc-title">Table of Contents</div><ol>`;
  const sectionKeys=[["executive_summary","1. Executive Summary"],["introduction","2. Introduction"],["objectives","3. Objectives"],["methodology","4. Methodology"],["implementation","5. Implementation"],["analysis","6. Analysis & Results"],["findings","7. Findings"],["recommendations","8. Recommendations"],["conclusion","9. Conclusion"]];
  sectionKeys.forEach(([key,label]) => {if(data[key]) html+=`<li>${label}</li>`});
  html+=`</ol></div>`;
  sectionKeys.forEach(([key,label]) =>{
    if(data[key]){
      html+=`<div class="rpt-section"><h2>${label}</h2><p>${mdBold(esc(data[key]))}</p></div>`;
    }
  });
  if(data.references && data.references.length){html+=`<div class="rpt-section"><h2>References</h2><div class="rpt-references">${data.references.map(r=>`<p>${esc(r)}</p>`).join("")}</div></div>`;}
  docPage.innerHTML=html;hideSkeleton();
}

/* ─── INVOICE RENDERER ─── */
function renderInvoice(data){
  if(!data||typeof data!=='object'){showSkeleton();return}
  docData=data;let html="<div class='inv-wrapper'>";
  const biz=data.business||{},cli=data.client||{};
  html+=`<div class="inv-header"><div class="inv-from"><div class="inv-company">${esc(biz.name||"")}</div>${esc(biz.email||"")}<br>${esc(biz.phone||"")}<br>${esc(biz.address||"")}</div><div class="inv-meta"><div class="inv-number">INVOICE #${esc(data.invoice_number||"INV-001")}</div>${esc(data.date||"")}<br><strong>Due:</strong> ${esc(data.due_date||"Net 30")}</div></div>`;
  html+=`<div class="inv-bill-section"><div class="inv-bill-to"><div class="inv-label">Bill To</div>${esc(cli.name||"")}<br>${esc(cli.company||"")}<br>${esc(cli.email||"")}<br>${esc(cli.address||"")}</div></div>`;
  html+=`<table class="inv-table"><tr><th style="width:50%">Description</th><th style="width:12%">Qty</th><th style="width:18%">Rate</th><th style="width:20%">Amount</th></tr>`;
  const cur=data.currency||"$";let sub=0;
  if(data.items&&data.items.length){data.items.forEach(i=>{const amt=(i.qty||0)*(i.rate||0);sub+=amt;html+=`<tr><td>${esc(i.description||"")}</td><td>${i.qty||0}</td><td>${cur}${(i.rate||0).toFixed(2)}</td><td>${cur}${amt.toFixed(2)}</td></tr>`;});}
  html+=`</table>`;
  const taxRate=data.tax_rate||0.18,tax=sub*taxRate,total=sub+tax;
  html+=`<div class="inv-totals"><div class="inv-line">Subtotal: ${cur}${sub.toFixed(2)}</div><div class="inv-line">Tax (${(taxRate*100).toFixed(0)}%): ${cur}${tax.toFixed(2)}</div><div class="inv-grand">Total Due: ${cur}${total.toFixed(2)}</div></div>`;
  html+=`<div class="inv-footer"><div class="inv-payment">Payment Method: ${esc(data.payment_method||"Bank Transfer")}</div>${esc(data.notes||"Thank you for your business.")}</div>`;
  html+="</div>";docPage.innerHTML=html;hideSkeleton();
}

/* ─── EMAIL RENDERER ─── */
function renderEmail(data){
  if(!data||typeof data!=='object'){showSkeleton();return}
  docData=data;let html="<div class='email-wrapper'>";
  html+=`<div class="email-header-bar"><span>📧 Email</span><span>To: ${esc(data.to||"recipient")}</span></div>`;
  html+=`<div class="email-outer">`;
  html+=`<div class="email-subject-line">${esc(data.subject||"Subject")}</div>`;
  html+=`<div class="email-to-line"><strong>To:</strong> ${esc(data.to||"")}${data.cc?` | <strong>Cc:</strong> ${esc(data.cc)}`:""}</div>`;
  html+=`<div class="email-greeting-text">${esc(data.greeting||"Hi,")}</div>`;
  html+=`<div class="email-body-content">`;
  if(data.body&&data.body.length){data.body.forEach(p=>{html+=`<p>${mdBold(esc(p))}</p>`});}else if(data.body_text){html+=`<p>${mdBold(esc(data.body_text))}</p>`;}
  html+=`</div>`;
  html+=`<div class="email-closing-text">${esc(data.closing||"Best regards,")}</div>`;
  html+=`<div class="email-sig-block"><div class="email-sig-name">${esc(data.sender_name||"")}</div><div class="email-sig-detail">${esc(data.sender_title||"")}${data.sender_email?" | "+esc(data.sender_email):""}</div></div>`;
  html+=`</div></div>`;
  docPage.innerHTML=html;hideSkeleton();
}

/* ─── DOCUMENTATION RENDERER ─── */
function renderDocumentation(data){
  if(!data||typeof data!=='object'){showSkeleton();return}
  docData=data;let html="<div class='doc-wrapper'>";
  html+=`<div class="doc-title-page"><h1>${esc(data.title||"Documentation")}</h1>`;
  if(data.author)html+=`<div class="doc-author">By: ${esc(data.author)}</div>`;
  if(data.version)html+=`<div class="doc-version">Version: ${esc(data.version)}</div>`;
  if(data.date)html+=`<div class="doc-date">${esc(data.date)}</div>`;
  html+=`</div>`;
  if(data.overview){html+=`<div class="doc-section"><h2>Overview</h2><p>${mdBold(esc(data.overview))}</p></div>`;}
  if(data.sections&&data.sections.length){
    data.sections.forEach((sec,i)=>{
      html+=`<div class="doc-section"><h2>${esc(sec.heading||sec.title||"Section "+(i+1))}</h2>`;
      if(sec.body)html+=`<p>${mdBold(esc(sec.body))}</p>`;
      if(sec.content)html+=`<p>${mdBold(esc(sec.content))}</p>`;
      if(sec.paragraphs&&sec.paragraphs.length){sec.paragraphs.forEach(p=>{html+=`<p>${mdBold(esc(p))}</p>`});}
      if(sec.subsections&&sec.subsections.length){
        sec.subsections.forEach(sub=>{
          html+=`<h3>${esc(sub.heading||sub.title||"")}</h3>`;
          if(sub.body)html+=`<p>${mdBold(esc(sub.body))}</p>`;
          if(sub.content)html+=`<p>${mdBold(esc(sub.content))}</p>`;
        });
      }
      if(sec.code){html+=`<pre><code>${esc(sec.code)}</code></pre>`;}
      html+=`</div>`;
    });
  }
  if(data.conclusion){html+=`<div class="doc-section"><h2>Conclusion</h2><p>${mdBold(esc(data.conclusion))}</p></div>`;}
  html+="</div>";docPage.innerHTML=html;hideSkeleton();
}

/* ─── UNIVERSAL GENERIC DOCUMENT RENDERER ─── */
function renderGeneric(data){
  if(!data||typeof data!=='object'){showSkeleton();return}
  docData=data;let html="<div class='gen-wrapper'>";
  html+=`<div class="gen-title-page"><h1>${esc(data.title||"Document")}</h1>`;
  if(data.document_type)html+=`<div class="gen-doctype-label">${esc(data.document_type)}</div>`;
  if(data.author)html+=`<div class="gen-author">${esc(data.author)}</div>`;
  if(data.date)html+=`<div class="gen-date">${esc(data.date)}</div>`;
  html+=`</div>`;
  if(data.summary){html+=`<div class="gen-section"><h2>Summary</h2><p>${mdBold(esc(data.summary))}</p></div>`;}
  if(data.sections&&data.sections.length){
    data.sections.forEach((sec,i)=>{
      const heading=sec.heading||sec.title||"";
      html+=`<div class="gen-section">`;
      if(heading)html+=`<h2>${esc(heading)}</h2>`;
      if(sec.body)html+=`<p>${mdBold(esc(sec.body))}</p>`;
      if(sec.content)html+=`<p>${mdBold(esc(sec.content))}</p>`;
      if(sec.paragraphs&&sec.paragraphs.length){sec.paragraphs.forEach(p=>{html+=`<p>${mdBold(esc(p))}</p>`});}
      if(sec.items&&sec.items.length){html+=`<ul>${sec.items.map(it=>`<li>${esc(it)}</li>`).join("")}</ul>`;}
      if(sec.subsections&&sec.subsections.length){
        sec.subsections.forEach(sub=>{
          html+=`<h3>${esc(sub.heading||sub.title||"")}</h3>`;
          if(sub.body)html+=`<p>${mdBold(esc(sub.body))}</p>`;
        });
      }
      html+=`</div>`;
    });
  }
  if(data.content&&data.content.length){
    data.content.forEach(item=>{
      if(typeof item==="string"){html+=`<p>${mdBold(esc(item))}</p>`;}
      else if(item.heading){html+=`<div class="gen-section"><h2>${esc(item.heading)}</h2>${item.body?`<p>${mdBold(esc(item.body))}</p>`:""}</div>`;}
    });
  }
  if(data.conclusion){html+=`<div class="gen-section"><h2>Conclusion</h2><p>${mdBold(esc(data.conclusion))}</p></div>`;}
  html+="</div>";docPage.innerHTML=html;hideSkeleton();
}

/* ─── FILE UPLOAD ─── */
async function handleFileUpload(file,source){
  const fd=new FormData();fd.append("file",file);
  try{
    const r=await fetch("/api/upload",{method:"POST",body:fd,headers:{"X-Session-Id":sessionId||""}});
    const d=await r.json();
    if(d.error){toast(d.error,"error");return}
    uploadedText=d.text;uploadedFilename=d.filename;
    if(source==="landing"){
      landingFileName.textContent="📎 "+d.filename;landingFileInfo.classList.remove("hidden");
    }else{
      wsFileName.textContent="📎 "+d.filename;wsFileInfo.classList.remove("hidden");
    }
    toast("Loaded: "+d.filename,"success");
  }catch(e){
    if(e.status===429){toast("Upload rate limit reached. Please wait.","warning")}
    else{toast("Upload failed.","error")}
  }
}

landingFileInput.addEventListener("change",()=>{if(landingFileInput.files.length)handleFileUpload(landingFileInput.files[0],"landing")});
landingUploadCard.addEventListener("click",(e)=>{if(e.target.closest('.uz-clear'))return;landingFileInput.click()});
landingClearFile.addEventListener("click",(e)=>{e.stopPropagation();uploadedText="";uploadedFilename="";landingFileInfo.classList.add("hidden");landingFileInput.value=""});
// Drag-drop on card
landingUploadCard.addEventListener("dragover",e=>{e.preventDefault();landingUploadCard.style.borderColor="var(--accent)";landingUploadCard.style.background="rgba(20,184,166,0.05)"});
landingUploadCard.addEventListener("dragleave",()=>{landingUploadCard.style.borderColor="";landingUploadCard.style.background=""});
landingUploadCard.addEventListener("drop",e=>{e.preventDefault();landingUploadCard.style.borderColor="";landingUploadCard.style.background="";if(e.dataTransfer.files.length)handleFileUpload(e.dataTransfer.files[0],"landing")});
wsFileInput.addEventListener("change",()=>{if(wsFileInput.files.length)handleFileUpload(wsFileInput.files[0],"workspace")});
$("#wsUploadBtn").addEventListener("click",()=>wsFileInput.click());
wsClearFile.addEventListener("click",()=>{uploadedText="";uploadedFilename="";wsFileInfo.classList.add("hidden");wsFileInput.value=""});

/* ─── GENERATE ─── */
/* ─── STREAM INDICATOR ─── */
function showStreamIndicator(type){
  const el=document.getElementById("streamIndicator");
  const label=document.getElementById("streamLabel");
  if(el)el.classList.remove("hidden");
  if(label)label.textContent="AI is generating your "+(docLabels[type]||"document")+"…";
}
function hideStreamIndicator(){
  const el=document.getElementById("streamIndicator");
  if(el)el.classList.add("hidden");
}
function afterGeneration(type){
  const sug=docSuggestions[type]||["Improve","Polish","Export"];
  showSuggestions(sug);
  rmLoad();isLoading=false;suggestions.classList.remove("hidden");
  sendBtn.disabled=false;chatInput.focus();
  toast((docLabels[type]||"Document")+" generated!","success");
  trackRecentDoc(type);
}

async function generateDoc(text,type){
  if(!text||!text.trim()){toast("Please provide a description.","warning");rmLoad();isLoading=false;sendBtn.disabled=false;return}
  showThink();showSkeleton();showStreamIndicator(type);
  abortStream();
  streamAbort=new AbortController();
  const timeoutId=setTimeout(()=>{abortStream();toast("Generation timed out.","error");hideThink();hideStreamIndicator();rmLoad();isLoading=false;sendBtn.disabled=false},120000);
  try{
    const r=await fetch("/api/generate-stream",{
      method:"POST",
      headers:{"Content-Type":"application/json","X-Session-Id":sessionId||""},
      body:JSON.stringify({prompt:text,doc_type:type,model:"deepseek-chat"}),
      signal:streamAbort.signal,
    });
    if(!r.ok){
      hideThink();hideStreamIndicator();
      if(r.status===429){toast("Rate limit reached. Please wait.","warning");rmLoad();isLoading=false;sendBtn.disabled=false;return}
      throw new Error("Stream not available ("+r.status+")");
    }
    if(!r.body){hideThink();hideStreamIndicator();throw new Error("Stream body missing")}
    const reader=r.body.getReader();
    const dec=new TextDecoder();
    let buf="",full="";
    while(true){
      const{done,value}=await reader.read();
      if(done)break;
      buf+=dec.decode(value,{stream:true});
      const parts=buf.split("\n");buf=parts.pop();
      for(const p of parts){
        if(!p.startsWith("data: "))continue;
        try{
          const m=JSON.parse(p.slice(6));
          if(m.t){
            full+=m.t;
            try{const parsed=JSON.parse(full);const rs={resume:renderResume,cover_letter:renderCoverLetter,proposal:renderProposal,report:renderReport,invoice:renderInvoice,email:renderEmail,documentation:renderDocumentation,generic:renderGeneric};if(rs[type]&&parsed&&typeof parsed==='object')rs[type](parsed)}catch(e){}
          }
          else if(m.d){
            clearTimeout(timeoutId);hideThink();hideStreamIndicator();
            const rs={resume:renderResume,cover_letter:renderCoverLetter,proposal:renderProposal,report:renderReport,invoice:renderInvoice,email:renderEmail,documentation:renderDocumentation,generic:renderGeneric};
            if(rs[type]&&m.d&&typeof m.d==='object')rs[type](m.d);
            else renderGeneric(m.d);
            afterGeneration(type);streamAbort=null;return;
          }else if(m.e){
            clearTimeout(timeoutId);hideThink();hideStreamIndicator();toast(m.e||"Generation error.","error");rmLoad();isLoading=false;sendBtn.disabled=false;streamAbort=null;return;
          }
        }catch(e){/* skip parse errors */}
      }
    }
    clearTimeout(timeoutId);
    hideThink();hideStreamIndicator();
    if(full.trim()){
      const jm=full.match(/\{.*\}/s);
      if(jm){try{const d=JSON.parse(jm[0]);const rs={resume:renderResume,cover_letter:renderCoverLetter,proposal:renderProposal,report:renderReport,invoice:renderInvoice,email:renderEmail,documentation:renderDocumentation,generic:renderGeneric};if(rs[type]&&d&&typeof d==='object')rs[type](d);else renderGeneric(d);afterGeneration(type)}catch(e){toast("Could not parse AI response.","error");rmLoad();isLoading=false;sendBtn.disabled=false}}
      else{toast("Could not parse AI response.","error");rmLoad();isLoading=false;sendBtn.disabled=false}
    }else{toast("No response from AI.","error");rmLoad();isLoading=false;sendBtn.disabled=false}
  }catch(e){
    clearTimeout(timeoutId);
    hideThink();hideStreamIndicator();
    if(e.name==="AbortError"){toast("Generation cancelled.","warning");rmLoad();isLoading=false;sendBtn.disabled=false;return}
    try{
      const r=await fetch("/api/generate-resume",{
        method:"POST",headers:{"Content-Type":"application/json","X-Session-Id":sessionId||""},
        body:JSON.stringify({prompt:text,doc_type:type,model:"deepseek-chat"})
      });
      const d=await r.json();hideThink();
      if(d.error){toast(d.error||"Generation issue.","error");rmLoad();isLoading=false;sendBtn.disabled=false;return}
      if(!d.resume){toast("Could not parse AI response.","error");rmLoad();isLoading=false;sendBtn.disabled=false;return}
      const rs={resume:renderResume,cover_letter:renderCoverLetter,proposal:renderProposal,report:renderReport,invoice:renderInvoice,email:renderEmail,documentation:renderDocumentation,generic:renderGeneric};
      if(rs[type]&&d.resume&&typeof d.resume==='object')rs[type](d.resume);
      else renderGeneric(d.resume);
      afterGeneration(type);
    }catch(e2){hideThink();toast("Generation failed. Please try again.","error");rmLoad();isLoading=false;sendBtn.disabled=false}
  }
  streamAbort=null;
}

/* ─── LANDING SEND ─── */
function doLandingSend(){
  const text=landingInput.value.trim();
  if(!text||isLoading)return;
  isLoading=true;landingSend.disabled=true;

  const type=detectDocType(text);
  detectionLabel.textContent="Detected: "+(docLabels[type]);
  detectionBadge.classList.remove("hidden");

  // Include uploaded text if present
  const fullPrompt=uploadedText ? text+"\n\n[Attached document: "+uploadedFilename+"]\n"+uploadedText : text;
  addMsg("user",uploadedText ? text+" (with file: "+uploadedFilename+")" : text);
  addLoad();

  setTimeout(()=>{
    detectionBadge.classList.add("hidden");
    revealWorkspace(type);
    setTimeout(()=>{generateDoc(fullPrompt,type)},400);
  },800);
}

const debouncedLandingSend=debounce(doLandingSend,300);
const debouncedSend=debounce(send,300);

/* ─── WORKSPACE SEND ─── */
function send(){
  const text=chatInput.value.trim();
  if(!text||isLoading)return;
  isLoading=true;sendBtn.disabled=true;
  const fullPrompt=uploadedText ? text+"\n\n[Attached document: "+uploadedFilename+"]\n"+uploadedText : text;
  addMsg("user",uploadedText ? text+" (with file: "+uploadedFilename+")" : text);
  addLoad();
  showSuggestions([]);
  generateDoc(fullPrompt,docType);
  chatInput.value="";chatInput.style.height="auto";
}

/* ─── EXPORT ─── */
const exportTrigger=$("#exportTrigger");
function closeExportMenu(){
  exportMenu.classList.remove("open");exportTrigger.classList.remove("open");
  exportMenu.style.position="";exportMenu.style.top="";exportMenu.style.right="";exportMenu.style.left="";exportMenu.style.bottom="";
}
function toggleExportMenu(e){
  e.stopPropagation();
  const isOpen=exportMenu.classList.contains("open");
  if(isOpen){closeExportMenu()}else{
    const r=exportTrigger.getBoundingClientRect();
    exportMenu.style.position="fixed";
    exportMenu.style.top=(r.bottom+4)+"px";
    exportMenu.style.right=(window.innerWidth-r.right)+"px";
    exportMenu.style.left="auto";exportMenu.style.bottom="auto";
    exportMenu.classList.add("open");exportTrigger.classList.add("open");
  }
}
document.addEventListener("click",function(e){
  if(!e.target.closest(".export-wrap"))closeExportMenu();
});
exportTrigger.addEventListener("click",toggleExportMenu);

function triggerDownload(blob,filename){
  const u=URL.createObjectURL(blob);
  const a=document.createElement("a");a.href=u;a.download=filename;
  document.body.appendChild(a);a.click();
  setTimeout(()=>{document.body.removeChild(a);URL.revokeObjectURL(u)},100);
}
function showExporting(){exportTrigger.textContent="⏳";exportTrigger.disabled=true}
function hideExporting(){exportTrigger.innerHTML='Export <svg viewBox="0 0 10 6" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><path d="M1 1l4 4 4-4"/></svg>';exportTrigger.disabled=false}
function cleanDocHTML(){
  const c=docPage.cloneNode(true);
  const sk=c.querySelector(".skeleton-doc");
  if(sk)sk.remove();
  return c.innerHTML;
}
async function fetchCSS(){
  try{const r=await fetch("/static/css/style.css");return await r.text()}catch{return""}
}
async function doExport(fmt){
  if(isLoading){toast("Please wait for generation to complete.","warning");return}
  const content=cleanDocHTML();
  if(!content||content.trim()===''||content.includes('skeleton')){toast("No document content to export.","warning");return}
  const label=docLabels[docType]||"document";
  closeExportMenu();

  // Non-HTML-based actions
  if(fmt==="print"){window.print();return}
  if(fmt==="copy-text"){
    try{await navigator.clipboard.writeText(docPage.textContent);toast("Text copied!","success")}catch{toast("Copy failed.","error")}
    return
  }
  if(fmt==="copy-html"){
    try{await navigator.clipboard.writeText(content);toast("HTML copied!","success")}catch{toast("Copy failed.","error")}
    return
  }

  showExporting();
  try{
    const css=await fetchCSS();
    const fix='#docPage{box-shadow:none!important;margin:0 auto!important;overflow:visible!important;outline:none!important}';
    const fullCSS=css+' '+fix;

    if(fmt==="html"){
      const h='<!DOCTYPE html><html><head><meta charset="utf-8"><title>'+label.replace(/[<>&"]/g,'')+'</title><style>'+fullCSS+'</style></head><body><div id="docPage">'+content+'</div></body></html>';
      triggerDownload(new Blob([h],{type:"text/html"}),label+".html");
      toast("HTML exported!","success");return;
    }

    if(fmt==="pdf"){
      if(typeof html2pdf==="undefined"){toast("PDF library not loaded.","error");hideExporting();return}
      const prevOverflow=docPage.style.overflow;
      docPage.style.overflow="visible";
      try{
        await html2pdf().set({
          margin:[0,0,0,0],filename:label+".pdf",
          image:{type:"jpeg",quality:0.98},
          html2canvas:{scale:2,useCORS:true,logging:false,letterRendering:true},
          jsPDF:{unit:"mm",format:"a4",orientation:"portrait"},
          pagebreak:{mode:["avoid-all","css","legacy"]}
        }).from(docPage).save();
      }catch(pdfErr){
        docPage.style.overflow=prevOverflow;
        throw pdfErr;
      }
      docPage.style.overflow=prevOverflow;
      toast("PDF exported!","success");return;
    }

    if(fmt==="docx"){
      const h='<html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:w="urn:schemas-microsoft-com:office:word" xmlns="http://www.w3.org/TR/REC-html40"><head><meta charset="utf-8"><!--[if gte mso 9]><xml><w:WordDocument><w:View>Print</w:View></w:WordDocument></xml><![endif]--><style>'+fullCSS+'</style></head><body><div id="docPage">'+content+'</div></body></html>';
      triggerDownload(new Blob([h],{type:"application/msword"}),label+".docx");
      toast("DOCX downloaded!","success");return;
    }
  }catch(exc){toast("Export failed. Please try again.","error")}
  finally{hideExporting()}
}

/* ─── EVENTS ─── */

// Landing
function autoResize(el,max){
  const m=max||220;
  el.style.height="auto";
  el.style.overflowY="hidden";
  const h=Math.min(el.scrollHeight,m);
  el.style.height=h+"px";
  if(h>=m)el.style.overflowY="auto";
}
landingInput.addEventListener("input",function(){autoResize(this);landingSend.disabled=!this.value.trim()});
landingInput.addEventListener("keydown",e=>{if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();if(!isLoading)debouncedLandingSend()}});
landingSend.addEventListener("click",function(){if(!isLoading)debouncedLandingSend()});
// Template card clicks
$$(".lp-card[data-prompt]").forEach(card=>{
  card.addEventListener("click",()=>{if(isLoading)return;landingInput.value=card.dataset.prompt;autoResize(landingInput);debouncedLandingSend()});
});
// Category filter pills
$$(".lp-cat").forEach(btn=>{
  btn.addEventListener("click",()=>{
    $$(".lp-cat").forEach(b=>b.classList.remove("active"));
    btn.classList.add("active");
    const cat=btn.textContent.trim().toLowerCase();
    $$(".lp-card").forEach(card=>{
      const type=card.dataset.type||"";
      if(cat==="all"||!cat){card.style.display="";return}
      if(card.id==="landingUploadCard"){card.style.display="";return}
      card.style.display="none";
    });
    // Animate visible cards
    $$(".lp-card:not([style*='none'])").forEach((c,i)=>{c.style.animation="none";c.offsetHeight;c.style.animation=`gridIn 0.4s ease ${i*0.04}s both`});
  });
});

// Workspace
chatInput.addEventListener("input",function(){autoResize(this,80);sendBtn.disabled=!this.value.trim()||isLoading});
chatInput.addEventListener("keydown",e=>{if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();if(!isLoading)debouncedSend()}});
sendBtn.addEventListener("click",function(){if(!isLoading)debouncedSend()});

// Back to landing
function goToLanding(){
  abortStream();
  if(isLoading){rmLoad();isLoading=false;sendBtn.disabled=false}
  workspace.classList.add("hidden");workspace.classList.remove("show");
  landingPage.classList.remove("hidden");
  landingPage.style.opacity="";landingPage.style.transform="";
  chatMessages.innerHTML="";
  const sk=document.querySelector("#skeleton");
  const skHTML=sk?sk.outerHTML:'<div id="skeleton" class="skeleton-doc"><div class="sk-block w-40" style="height:20px;margin:30px auto;border-radius:4px"></div><div class="sk-block w-70" style="height:8px;margin:0 auto 18px;border-radius:4px"></div><div class="sk-block w-25" style="height:10px;margin:10px 0 5px;border-radius:4px"></div><div class="sk-block w-90" style="height:7px;margin:3px 0"></div><div class="sk-block w-75" style="height:7px;margin:3px 0"></div><div class="sk-block w-25" style="height:10px;margin:14px 0 5px"></div><div class="sk-block w-95" style="height:7px;margin:3px 0"></div></div>';
  docPage.innerHTML=skHTML;
  docPage.classList.remove("loaded");
  suggestions.classList.add("hidden");hideThink();docData=null;
  landingInput.value="";landingInput.focus();
  uploadedText="";uploadedFilename="";wsFileInfo.classList.add("hidden");landingFileInfo.classList.add("hidden");landingFileInput.value="";
  hideExporting();closeExportMenu();
}
backBtn.addEventListener("click",goToLanding);
if(backBtnEditor)backBtnEditor.addEventListener("click",goToLanding);

// Zoom
$("#zoomIn").addEventListener("click",zoomIn);$("#zoomOut").addEventListener("click",zoomOut);

/* ─── TOOLBAR — exec all commands ─── */
function exec(cmd,val){docPage.focus();document.execCommand(cmd,false,val||null)}

// Enable CSS-styled font sizes
document.execCommand("styleWithCSS",false,true);

// Undo/Redo
document.getElementById("undoBtn")?.addEventListener("click",()=>exec("undo"));
document.getElementById("redoBtn")?.addEventListener("click",()=>exec("redo"));

// Formatting toggles
[["boldBtn","bold"],["italicBtn","italic"],["underlineBtn","underline"],["strikeBtn","strikeThrough"],
 ["ulBtn","insertUnorderedList"],["olBtn","insertOrderedList"],
 ["cleanBtn","removeFormat"]]
.forEach(([id,cmd])=>{const e=document.getElementById(id);if(e)e.addEventListener("click",()=>{exec(cmd);updateToolbarState()})});

// Alignment
[["alignLeftBtn","justifyLeft"],["alignCenterBtn","justifyCenter"],["alignRightBtn","justifyRight"],["alignJustifyBtn","justifyFull"]]
.forEach(([id,cmd])=>{const e=document.getElementById(id);if(e)e.addEventListener("click",()=>{exec(cmd);updateToolbarState()})});

// Style select — apply block format & track active
const styleEl=document.getElementById("styleSelect");
if(styleEl){
  styleEl.addEventListener("change",function(){
    const v=this.value;docPage.focus();
    const map={p:"<p>",h1:"<h1>",h2:"<h2>",h3:"<h3>",blockquote:"<blockquote>",pre:"<pre>"};
    if(map[v])exec("formatBlock",map[v]);
    this.blur();
    updateToolbarState();
  });
}

// Font select
const fontEl=document.getElementById("fontSelect");
if(fontEl)fontEl.addEventListener("change",function(){exec("fontName",this.value);this.blur();updateToolbarState()});

// Font size — use inline CSS for real pt values
const sizeEl=document.getElementById("sizeSelect");
if(sizeEl){
  sizeEl.addEventListener("change",function(){
    docPage.focus();
    const size=this.value;
    exec("fontSize","7");
    const markers=docPage.querySelectorAll('font[size="7"]');
    markers.forEach(el=>{
      const span=document.createElement("span");
      span.style.fontSize=size+"pt";
      span.innerHTML=el.innerHTML;
      el.parentNode.replaceChild(span,el);
    });
    this.blur();
    updateToolbarState();
  });
}

// Colors
document.getElementById("textColorInput")?.addEventListener("input",function(){exec("foreColor",this.value);updateToolbarState()});
document.getElementById("hiliteColorInput")?.addEventListener("input",function(){exec("hiliteColor",this.value);updateToolbarState()});

// Image — support URL + file upload
document.getElementById("imageBtn")?.addEventListener("click",()=>{
  const input=document.createElement("input");input.type="file";input.accept="image/*";
  input.onchange=function(){
    if(!this.files||!this.files[0])return;
    const reader=new FileReader();
    reader.onload=function(e){
      docPage.focus();exec("insertImage",e.target.result);updateToolbarState();
    };
    reader.readAsDataURL(this.files[0]);
  };
  input.click();
});

// Link
document.getElementById("linkBtn")?.addEventListener("click",()=>{
  const sel=window.getSelection().toString();
  const url=prompt("Enter link URL:","https://");
  if(url){docPage.focus();exec("createLink",url);updateToolbarState();}
  else if(sel){docPage.focus();exec("unlink");updateToolbarState();}
});

// Table
document.getElementById("tableBtn")?.addEventListener("click",()=>{
  const rows=prompt("Rows:","2")||2,cols=prompt("Columns:","2")||2;
  let html='<table border="1" cellpadding="6" cellspacing="0" style="width:100%;border-collapse:collapse;margin:6px 0;font-size:9pt">';
  for(let r=0;r<rows;r++){html+="<tr>";for(let c=0;c<cols;c++)html+=`<td style="min-width:40px;padding:4px 6px;border:1px solid #d2d2d6">Cell</td>`;html+="</tr>"}
  html+="</table>";
  docPage.focus();document.execCommand("insertHTML",false,html);updateToolbarState();
});

/* ─── DYNAMIC TOOLBAR STATE TRACKING ─── */
const alignMap={left:"alignLeftBtn",center:"alignCenterBtn",right:"alignRightBtn",justify:"alignJustifyBtn"};
const styleMap={p:"p",h1:"h1",h2:"h2",h3:"h3",blockquote:"blockquote",pre:"pre"};

function updateToolbarState(){
  // Formatting buttons
  [["boldBtn","bold"],["italicBtn","italic"],["underlineBtn","underline"],["strikeBtn","strikeThrough"],
   ["ulBtn","insertUnorderedList"],["olBtn","insertOrderedList"]]
  .forEach(([id,cmd])=>{
    const e=document.getElementById(id);
    if(e)e.classList.toggle("active",document.queryCommandState(cmd));
  });

  // Alignment
  const al=document.queryCommandValue("justify");
  Object.entries(alignMap).forEach(([val,id])=>{
    const e=document.getElementById(id);
    if(e)e.classList.toggle("active",al===val);
  });

  // Style select — detect parent block
  if(styleEl){
    const parent=docPage.querySelector(":focus")||window.getSelection()?.anchorNode;
    if(parent){
      let el=parent.nodeType===3?parent.parentElement:parent;
      while(el&&el!==docPage){
        const tag=el.tagName?.toLowerCase();
        if(styleMap[tag]){styleEl.value=tag;break;}
        if(tag==="li"){styleEl.value="p";break;}
        el=el.parentElement;
      }
    }
  }

  // Font select — detect font family
  if(fontEl){
    const val=document.queryCommandValue("fontName");
    if(val){const opt=Array.from(fontEl.options).find(o=>val.includes(o.value.replace(/'/g,"").split(",")[0].trim()));if(opt)fontEl.value=opt.value;}
  }
}

docPage.addEventListener("mouseup",updateToolbarState);
docPage.addEventListener("keyup",updateToolbarState);

// Also update on selection change to keep toolbar in sync
document.addEventListener("selectionchange",debounce(function(){
  if(editorVisible&&document.activeElement&&docPage.contains(document.activeElement)){
    updateToolbarState();
  }
},100));

/* ─── KEYBOARD SHORTCUTS ─── */
docPage.addEventListener("keydown",function(e){
  const mod=/(Mac|iPhone|iPod|iPad)/i.test(navigator.platform)?e.metaKey:e.ctrlKey;
  if(!mod)return;
  if(e.key==="z"){e.preventDefault();exec(e.shiftKey?"redo":"undo");updateToolbarState()}
  if(e.key==="y"){e.preventDefault();exec("redo");updateToolbarState()}
  if(e.key==="b"){e.preventDefault();exec("bold");updateToolbarState()}
  if(e.key==="i"){e.preventDefault();exec("italic");updateToolbarState()}
  if(e.key==="u"){e.preventDefault();exec("underline");updateToolbarState()}
});

// Doc action
$("#docActionBtn")?.addEventListener("click",()=>{
  const sug=docSuggestions[docType]||["Improve","Polish","Export"];
  chatInput.value=sug[0]||"Improve this document";chatInput.focus();
});

// Export via dropdown items
document.querySelectorAll(".export-menu .em-item").forEach(b=>{
  b.addEventListener("click",(e)=>{e.stopPropagation();doExport(b.dataset.fmt)});
});

})();
