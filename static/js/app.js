(function(){
"use strict";

let sessionId=null,isLoading=false,docData=null,docType="resume",editorVisible=false;
let uploadedText="",uploadedFilename="";
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
const backBtn=$("#backBtn"),backBtnEditor=$("#backBtnEditor"),newChatBtn=$("#newChatBtn"),toastEl=$("#toast");
const editorDocType=$("#editorDocType"),zoomLevel=$("#zoomLevel");
const wsFileInput=$("#wsFileInput"),wsFileInfo=$("#wsFileInfo"),wsFileName=$("#wsFileName"),wsClearFile=$("#wsClearFile");

const socket=io();
socket.on("connect",()=>{sessionId=socket.id});
socket.on("session_id",d=>{sessionId=d.session_id});

let zoom=1;

/* ─── HELPERS ─── */
function esc(t){if(t==null)return '';const d=document.createElement("div");d.textContent=t;return d.innerHTML}
function toast(m){
  toastEl.textContent=m;
  toastEl.classList.remove("hidden");
  toastEl.style.transition="none";toastEl.style.opacity="0";toastEl.style.transform="translateX(-50%) translateY(16px) scale(0.95)";
  requestAnimationFrame(()=>{
    toastEl.style.transition="";
    toastEl.style.opacity="";toastEl.style.transform="";
  });
  clearTimeout(toastEl._t);
  toastEl._t=setTimeout(()=>toastEl.classList.add("hidden"),2800);
}
function addMsg(role,content){
  const div=document.createElement("div");div.className=`msg ${role}`;
  const av=role==="user"?`<div class="msg-avatar user">👤</div>`:`<div class="msg-avatar agent">🤖</div>`;
  div.innerHTML=av+`<div class="msg-body"><div class="msg-bubble">${esc(content)}</div></div>`;
  chatMessages.appendChild(div);chatMessages.scrollTop=chatMessages.scrollHeight;
}
function addLoad(){
  const d=document.createElement("div");d.className="msg agent";d.id="loadMsg";
  d.innerHTML=`<div class="msg-avatar agent">🤖</div><div class="msg-body"><div class="msg-bubble"><div class="loading-dots"><span></span><span></span><span></span></div></div></div>`;
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
  docPage.innerHTML=sk&&sk.innerHTML?'<div class="skeleton-doc">'+sk.innerHTML+'</div>':'<div class="skeleton-doc"><div class="sk-block w-40" style="height:22px;margin:30px auto"></div><div class="sk-block w-70" style="height:9px;margin:0 auto 20px"></div><div class="sk-block w-25" style="height:11px;margin:10px 0 6px"></div><div class="sk-block w-90" style="height:8px;margin:4px 0"></div><div class="sk-block w-75" style="height:8px;margin:4px 0"></div><div class="sk-block w-25" style="height:11px;margin:14px 0 6px"></div><div class="sk-block w-95" style="height:8px;margin:4px 0"></div></div>';
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

/* ─── DOCUMENT TYPE DETECTION ─── */
const docPatterns={
  resume:/resume|cv|curriculum\s*vitae|r[eé]sum[eé]/i,
  cover_letter:/cover\s*letter|letter\s*of\s*(application|intent)/i,
  proposal:/proposal|pitch|business\s*plan/i,
  report:/report|project\s*report|status\s*report|findings/i,
  invoice:/invoice|bill|statement\s*of\s*work/i,
  email:/email|e-?mail|message|outreach/i,
};
const docLabels={resume:"Resume",cover_letter:"Cover Letter",proposal:"Proposal",report:"Report",invoice:"Invoice",email:"Email"};
const docSuggestions={
  resume:["Improve bullet points","Make more ATS-friendly","Quantify achievements","Shorten to 1 page","Professional tone boost"],
  cover_letter:["Make more formal","Highlight key skills","Shorten","Add enthusiasm","Company-specific optimization"],
  proposal:["Improve persuasiveness","Add pricing details","Strengthen executive summary","Add timeline"],
  report:["Summarize findings","Improve clarity","Add recommendations","Generate citations"],
  invoice:["Add line items","Recalculate totals","Add payment terms","Convert currency"],
  email:["Make more professional","Shorten","Improve tone","Add call to action"],
};

/* ─── RECENT DOCS TRACKING ─── */
function trackRecentDoc(type){
  const recent=JSON.parse(localStorage.getItem("da_recent")||"[]");
  const label=docLabels[type]||type;
  const filtered=recent.filter(r=>r.type!==type);
  filtered.unshift({type,label,timestamp:Date.now()});
  localStorage.setItem("da_recent",JSON.stringify(filtered.slice(0,10)));
}
function renderRecentDocs(){
  const panel=document.getElementById("sbRecentPanel"),list=document.getElementById("sbRecentList");
  if(!panel||!list)return;
  const recent=JSON.parse(localStorage.getItem("da_recent")||"[]");
  const empty=panel.querySelector(".sb-recent-empty");
  if(!recent.length){list.innerHTML="";if(empty)empty.classList.remove("hidden");return}
  if(empty)empty.classList.add("hidden");
  list.innerHTML=recent.map(r=>`<div class="sb-recent-item" data-type="${r.type}"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg><span>${esc(r.label)}</span></div>`).join("");
}

function detectDocType(text){
  for(const [type,pattern] of Object.entries(docPatterns)){
    if(pattern.test(text)) return type;
  }
  // Fallback heuristic
  if(/experience|skills|education|job/i.test(text)) return "resume";
  if(/price|cost|payment|total|amount/i.test(text)) return "invoice";
  if(/dear|sincerely|regards|application/i.test(text)) return "cover_letter";
  if(/budget|solution|service/i.test(text)) return "proposal";
  return "resume";
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
  addMsg("assistant",`I'll create a **${label}** for you. Let me generate that now.`);
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
      const num=label.split(".")[0];
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

/* ─── FILE UPLOAD ─── */
async function handleFileUpload(file,source){
  const fd=new FormData();fd.append("file",file);
  try{
    const r=await fetch("/api/upload",{method:"POST",body:fd});
    const d=await r.json();
    if(d.error){toast(d.error);return}
    uploadedText=d.text;uploadedFilename=d.filename;
    if(source==="landing"){
      landingFileName.textContent=`📎 ${d.filename}`;landingFileInfo.classList.remove("hidden");
    }else{
      wsFileName.textContent=`📎 ${d.filename}`;wsFileInfo.classList.remove("hidden");
    }
    toast(`Loaded: ${d.filename}`);
  }catch{toast("Upload failed.")}
}

landingFileInput.addEventListener("change",()=>{if(landingFileInput.files.length)handleFileUpload(landingFileInput.files[0],"landing")});
landingUploadCard.addEventListener("click",(e)=>{if(e.target.closest('.uz-clear'))return;landingFileInput.click()});
landingClearFile.addEventListener("click",(e)=>{e.stopPropagation();uploadedText="";uploadedFilename="";landingFileInfo.classList.add("hidden");landingFileInput.value=""});
// Drag-drop on card
landingUploadCard.addEventListener("dragover",e=>{e.preventDefault();landingUploadCard.style.borderColor="var(--accent)";landingUploadCard.style.background="var(--accent-glow)"});
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
  if(label)label.textContent=`AI is generating your ${docLabels[type]||"document"}...`;
}
function hideStreamIndicator(){
  const el=document.getElementById("streamIndicator");
  if(el)el.classList.add("hidden");
}
function afterGeneration(type){
  const sug=docSuggestions[type]||["Improve","Polish","Export"];
  showSuggestions(sug);
  rmLoad();isLoading=false;suggestions.classList.remove("hidden");
  addMsg("assistant",`Your **${docLabels[type]}** is ready! Edit directly in the preview or use suggestions below.`);
  sendBtn.disabled=false;chatInput.focus();
  toast(`${docLabels[type]} generated!`);
  trackRecentDoc(type);
}

async function generateDoc(text,type){
  showThink();showSkeleton();showStreamIndicator(type);
  try{
    const r=await fetch("/api/generate-stream",{
      method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({prompt:text,doc_type:type,model:"deepseek-chat"})
    });
    if(!r.ok||!r.body){hideThink();hideStreamIndicator();throw new Error("Stream not available")}
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
            // Try to parse partial JSON and progressively render the document
            try{const parsed=JSON.parse(full);const rs={resume:renderResume,cover_letter:renderCoverLetter,proposal:renderProposal,report:renderReport,invoice:renderInvoice,email:renderEmail};if(rs[type]&&parsed&&typeof parsed==='object')rs[type](parsed)}catch(e){}
          }
          else if(m.d){
            hideThink();hideStreamIndicator();
            const rs={resume:renderResume,cover_letter:renderCoverLetter,proposal:renderProposal,report:renderReport,invoice:renderInvoice,email:renderEmail};
            if(rs[type]&&m.d&&typeof m.d==='object')rs[type](m.d);
            else renderResume(m.d);
            afterGeneration(type);return;
          }else if(m.e){
            hideThink();hideStreamIndicator();toast(m.e);rmLoad();isLoading=false;sendBtn.disabled=false;return;
          }
        }catch(e){/* skip parse errors */}
      }
    }
    // Fallback: try parsing full accumulated text
    hideThink();hideStreamIndicator();
    const jm=full.match(/\{.*\}/s);
    if(jm){const d=JSON.parse(jm[0]);const rs={resume:renderResume,cover_letter:renderCoverLetter,proposal:renderProposal,report:renderReport,invoice:renderInvoice,email:renderEmail};if(rs[type]&&d&&typeof d==='object')rs[type](d);else renderResume(d);afterGeneration(type)}
    else{toast("Could not parse AI response.");rmLoad();isLoading=false;sendBtn.disabled=false}
  }catch(e){
    hideThink();hideStreamIndicator();
    // Fallback to non-streaming endpoint
    try{
      const r=await fetch("/api/generate-resume",{
        method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({prompt:text,doc_type:type,model:"deepseek-chat"})
      });
      const d=await r.json();hideThink();
      if(d.error){toast(d.error||"Generation issue.");rmLoad();isLoading=false;sendBtn.disabled=false;return}
      if(!d.resume){toast("Could not parse AI response.");rmLoad();isLoading=false;sendBtn.disabled=false;return}
      const rs={resume:renderResume,cover_letter:renderCoverLetter,proposal:renderProposal,report:renderReport,invoice:renderInvoice,email:renderEmail};
      if(rs[type]&&d.resume&&typeof d.resume==='object')rs[type](d.resume);
      else renderResume(d.resume);
      afterGeneration(type);
    }catch(e2){hideThink();toast("Generation failed."+e2.message);rmLoad();isLoading=false;sendBtn.disabled=false}
  }
}

/* ─── LANDING SEND ─── */
function doLandingSend(){
  const text=landingInput.value.trim();
  if(!text||isLoading)return;
  isLoading=true;landingSend.disabled=true;

  const type=detectDocType(text);
  detectionLabel.textContent=`Detected: ${docLabels[type]}`;
  detectionBadge.classList.remove("hidden");

  // Include uploaded text if present
  const fullPrompt=uploadedText ? `${text}\n\n[Attached document: ${uploadedFilename}]\n${uploadedText}` : text;
  addMsg("user",uploadedText ? `${text} (with file: ${uploadedFilename})` : text);
  addLoad();

  setTimeout(()=>{
    detectionBadge.classList.add("hidden");
    revealWorkspace(type);
    setTimeout(()=>{generateDoc(fullPrompt,type)},400);
  },800);
}

/* ─── WORKSPACE SEND ─── */
function send(){
  const text=chatInput.value.trim();
  if(!text||isLoading)return;
  isLoading=true;sendBtn.disabled=true;
  const fullPrompt=uploadedText ? `${text}\n\n[Attached document: ${uploadedFilename}]\n${uploadedText}` : text;
  addMsg("user",uploadedText ? `${text} (with file: ${uploadedFilename})` : text);
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
  const content=cleanDocHTML();
  if(!content||content.trim()===''||content.includes('skeleton')){toast("No document content to export.");return}
  const label=docLabels[docType]||"document";
  closeExportMenu();

  // Non-HTML-based actions
  if(fmt==="print"){window.print();return}
  if(fmt==="copy-text"){
    try{await navigator.clipboard.writeText(docPage.textContent);toast("Text copied!")}catch{toast("Copy failed.")}
    return
  }
  if(fmt==="copy-html"){
    try{await navigator.clipboard.writeText(content);toast("HTML copied!")}catch{toast("Copy failed.")}
    return
  }

  showExporting();
  try{
    const css=await fetchCSS();
    const fix='#docPage{box-shadow:none!important;margin:0 auto!important;overflow:visible!important;outline:none!important}';
    const fullCSS=css+' '+fix;

    if(fmt==="html"){
      const h='<!DOCTYPE html><html><head><meta charset="utf-8"><title>'+label+'</title><style>'+fullCSS+'</style></head><body><div id="docPage">'+content+'</div></body></html>';
      triggerDownload(new Blob([h],{type:"text/html"}),label+".html");
      toast("HTML exported!");return;
    }

    if(fmt==="pdf"){
      if(typeof html2pdf==="undefined"){toast("PDF library not loaded.");hideExporting();return}
      const prevOverflow=docPage.style.overflow;
      docPage.style.overflow="visible";
      await html2pdf().set({
        margin:[0,0,0,0],filename:label+".pdf",
        image:{type:"jpeg",quality:0.98},
        html2canvas:{scale:2,useCORS:true,logging:false,letterRendering:true},
        jsPDF:{unit:"mm",format:"a4",orientation:"portrait"},
        pagebreak:{mode:["avoid-all","css","legacy"]}
      }).from(docPage).save();
      docPage.style.overflow=prevOverflow;
      toast("PDF exported!");return;
    }

    if(fmt==="docx"){
      const h='<html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:w="urn:schemas-microsoft-com:office:word" xmlns="http://www.w3.org/TR/REC-html40"><head><meta charset="utf-8"><!--[if gte mso 9]><xml><w:WordDocument><w:View>Print</w:View></w:WordDocument></xml><![endif]--><style>'+fullCSS+'</style></head><body><div id="docPage">'+content+'</div></body></html>';
      triggerDownload(new Blob([h],{type:"application/msword"}),label+".docx");
      toast("DOCX downloaded!");return;
    }
  }catch(exc){toast("Export failed: "+exc.message)}
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
landingInput.addEventListener("keydown",e=>{if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();doLandingSend()}});
landingSend.addEventListener("click",doLandingSend);
// Template card clicks
$$(".lp-card[data-prompt]").forEach(card=>{
  card.addEventListener("click",()=>{landingInput.value=card.dataset.prompt;autoResize(landingInput);doLandingSend()});
});
// Blank card
document.querySelector(".lp-card-blank")?.addEventListener("click",()=>{
  landingInput.value="Create a blank document with placeholder content";
  autoResize(landingInput);
  doLandingSend();
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
      if(cat==="blank"&&type==="blank"){card.style.display="";return}
      if(type===cat){card.style.display="";return}
      // Show blank + upload always
      if(type==="blank"||card.id==="landingUploadCard"){card.style.display="";return}
      card.style.display="none";
    });
    // Animate visible cards
    $$(".lp-card:not([style*='none'])").forEach((c,i)=>{c.style.animation="none";c.offsetHeight;c.style.animation=`gridIn 0.4s ease ${i*0.04}s both`});
  });
});

// Workspace
chatInput.addEventListener("input",function(){autoResize(this,80);sendBtn.disabled=!this.value.trim()});
chatInput.addEventListener("keydown",e=>{if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();send()}});

// Back to landing
function goToLanding(){
  workspace.classList.add("hidden");workspace.classList.remove("show");
  landingPage.classList.remove("hidden");
  landingPage.style.opacity="";landingPage.style.transform="";
  chatMessages.innerHTML="";
  const sk=document.querySelector("#skeleton");
  const skHTML=sk?sk.outerHTML:'<div id="skeleton" class="skeleton-doc"><div class="sk-block w-40" style="height:22px;margin:30px auto;border-radius:4px"></div><div class="sk-block w-70" style="height:9px;margin:0 auto 20px;border-radius:4px"></div><div class="sk-block w-25" style="height:11px;margin:10px 0 6px;border-radius:4px"></div><div class="sk-block w-90" style="height:8px;margin:4px 0;border-radius:4px"></div><div class="sk-block w-75" style="height:8px;margin:4px 0;border-radius:4px"></div><div class="sk-block w-25" style="height:11px;margin:14px 0 6px;border-radius:4px"></div><div class="sk-block w-95" style="height:8px;margin:4px 0;border-radius:4px"></div></div>';
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
function setId(id,val){const e=document.getElementById(id);if(e)e.value=val}

// Enable CSS-styled font sizes
document.execCommand("styleWithCSS",false,true);

// Undo/Redo
document.getElementById("undoBtn")?.addEventListener("click",()=>exec("undo"));
document.getElementById("redoBtn")?.addEventListener("click",()=>exec("redo"));

// Formatting toggles
[["boldBtn","bold"],["italicBtn","italic"],["underlineBtn","underline"],["strikeBtn","strikeThrough"],
 ["ulBtn","insertUnorderedList"],["olBtn","insertOrderedList"],
 ["outdentBtn","outdent"],["indentBtn","indent"],["cleanBtn","removeFormat"]]
.forEach(([id,cmd])=>{const e=document.getElementById(id);if(e)e.addEventListener("click",()=>exec(cmd))});

// Alignment
[["alignLeftBtn","justifyLeft"],["alignCenterBtn","justifyCenter"],["alignRightBtn","justifyRight"],["alignJustifyBtn","justifyFull"]]
.forEach(([id,cmd])=>{const e=document.getElementById(id);if(e)e.addEventListener("click",()=>exec(cmd))});

// Style select — apply block format & track active
const styleEl=document.getElementById("styleSelect");
if(styleEl){
  styleEl.addEventListener("change",function(){
    const v=this.value;docPage.focus();
    const map={p:"<p>",h1:"<h1>",h2:"<h2>",h3:"<h3>",blockquote:"<blockquote>",pre:"<pre>"};
    if(map[v])exec("formatBlock",map[v]);
    this.blur();
  });
}

// Font select
const fontEl=document.getElementById("fontSelect");
if(fontEl)fontEl.addEventListener("change",function(){exec("fontName",this.value);this.blur()});

// Font size — use inline CSS for real pt values
const sizeEl=document.getElementById("sizeSelect");
if(sizeEl){
  sizeEl.addEventListener("change",function(){
    docPage.focus();
    const size=this.value;
    // Use CSS fontSize via execCommand with fontSize then replace with inline style
    exec("fontSize","7"); // temporary large size marker
    // Find all font tags with size 7 and replace with inline style
    const markers=docPage.querySelectorAll('font[size="7"]');
    markers.forEach(el=>{
      const span=document.createElement("span");
      span.style.fontSize=size+"pt";
      span.innerHTML=el.innerHTML;
      el.parentNode.replaceChild(span,el);
    });
    this.blur();
  });
}

// Colors
document.getElementById("textColorInput")?.addEventListener("input",function(){exec("foreColor",this.value)});
document.getElementById("hiliteColorInput")?.addEventListener("input",function(){exec("hiliteColor",this.value)});

// Image — support URL + file upload
document.getElementById("imageBtn")?.addEventListener("click",()=>{
  const input=document.createElement("input");input.type="file";input.accept="image/*";
  input.onchange=function(){
    if(!this.files||!this.files[0])return;
    const reader=new FileReader();
    reader.onload=function(e){
      docPage.focus();exec("insertImage",e.target.result);
    };
    reader.readAsDataURL(this.files[0]);
  };
  input.click();
});

// Link
document.getElementById("linkBtn")?.addEventListener("click",()=>{
  const sel=window.getSelection().toString();
  const url=prompt("Enter link URL:","https://");
  if(url){docPage.focus();exec("createLink",url);}
  else if(sel){docPage.focus();exec("unlink");}
});

// Table
document.getElementById("tableBtn")?.addEventListener("click",()=>{
  const rows=prompt("Rows:","2")||2,cols=prompt("Columns:","2")||2;
  let html='<table border="1" cellpadding="6" cellspacing="0" style="width:100%;border-collapse:collapse;margin:6px 0">';
  for(let r=0;r<rows;r++){html+="<tr>";for(let c=0;c<cols;c++)html+=`<td style="min-width:40px">Cell</td>`;html+="</tr>"}
  html+="</table>";
  docPage.focus();document.execCommand("insertHTML",false,html);
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
docPage.addEventListener("input",updateToolbarState);

/* ─── KEYBOARD SHORTCUTS ─── */
docPage.addEventListener("keydown",function(e){
  const mod=/(Mac|iPhone|iPod|iPad)/i.test(navigator.platform)?e.metaKey:e.ctrlKey;
  if(!mod)return;
  if(e.key==="z"){e.preventDefault();exec(e.shiftKey?"redo":"undo")}
  if(e.key==="y"){e.preventDefault();exec("redo")}
  if(e.key==="b"){e.preventDefault();exec("bold")}
  if(e.key==="i"){e.preventDefault();exec("italic")}
  if(e.key==="u"){e.preventDefault();exec("underline")}
});

// Doc action (moved to export bar)
$("#docActionBtn")?.addEventListener("click",()=>{
  const sug=docSuggestions[docType]||["Improve","Polish","Export"];
  chatInput.value=sug[0]||"Improve this document";chatInput.focus();
});

// Export via dropdown items
document.querySelectorAll(".export-menu .em-item").forEach(b=>{
  b.addEventListener("click",(e)=>{e.stopPropagation();doExport(b.dataset.fmt)});
});

})();
