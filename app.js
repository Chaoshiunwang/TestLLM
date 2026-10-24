import {ROOT_CATEGORIES,enrichRoot} from "./roots.js";

const DATA_BASE="https://copper0722.github.io/gsat-vocabulary-map/data";
const $=(s)=>{const e=document.querySelector(s);if(!e)throw new Error("Missing "+s);return e};
const esc=(v)=>String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
let words=[],progress=loadProgress(),mode={type:"track",value:"target12"},offset=0,visible=24,current=[];
const filters={q:new URLSearchParams(location.search).get("q")||"",level:"all",category:"all",tier:"all",sort:"priority"};

async function fetchJson(name){
  try{const r=await fetch("./data/"+name,{cache:"no-store"});if(r.ok)return r.json()}catch{}
  const r=await fetch(DATA_BASE+"/"+name);if(!r.ok)throw new Error(name+" 載入失敗");return r.json();
}
function loadProgress(){try{return JSON.parse(localStorage.getItem("gsat-root-progress-v1")||"{}")}catch{return {}}}
function saveProgress(){localStorage.setItem("gsat-root-progress-v1",JSON.stringify(progress))}
function tierLabel(t){return {core:"核心高頻",priority:"值得優先",low_frequency:"低頻",long_tail:"只出現 1 次",not_seen:"未出現"}[t]||t}
function levelLabel(r){return r.l?("第 "+r.l+" 級"):(r.s==="ceec_appendix"?"官方附錄":"詞表外")}
function rootBlock(r){
  if(!r.root)return "";
  const candidate=r.root.confidence==="REVIEW"?" · 候選":"";
  return `<div class="root-summary"><span class="root-category">${esc(r.root.category)}${candidate}</span><strong>字根 ${esc(r.root.variant)}｜${esc(r.root.meaning)}</strong><p>${esc(r.root.logic)}</p></div>`;
}
function card(r){
  const state=progress[r.id];
  return `<article class="word-card"><button class="word-main" data-open="${r.id}"><div class="word-card-top"><span class="level-badge">${levelLabel(r)}</span><span class="tier-badge">${tierLabel(r.b)}</span></div><strong class="word-headword">${esc(r.h)}</strong><span class="word-pos">${esc(r.p||r.d||"")}</span><span class="word-translation">${esc(r.z||"")}</span>${rootBlock(r)}<dl class="word-metrics"><div><dt>總次數</dt><dd>${r.c}</dd></div><div><dt>出現年份</dt><dd>${r.y} / 16</dd></div></dl></button><div class="word-actions"><button data-progress="known" data-id="${r.id}" class="${state==="known"?"is-selected":""}">我會了</button><button data-progress="review" data-id="${r.id}" class="${state==="review"?"is-selected":""}">再複習</button></div></article>`;
}
function score(r){const st=progress[r.id];return (st==="review"?1e9:0)+(st==="known"?-1e9:0)+(r.root?.confidence==="HIGH"?2e6:0)+(r.o||0)*100+r.c}
function unique(list){const seen=new Set();return list.filter(r=>seen.has(r.id)?false:(seen.add(r.id),true))}
function rotate(list,n){if(!list.length)return list;const x=((n%list.length)+list.length)%list.length;return list.slice(x).concat(list.slice(0,x))}
function deckPool(){
  const available=words.filter(r=>r.c>0&&progress[r.id]!=="known");
  const sorted=[...available].sort((a,b)=>score(b)-score(a));
  const review=sorted.filter(r=>progress[r.id]==="review");
  const unseen=sorted.filter(r=>progress[r.id]!=="review");
  if(mode.type==="root"){
    return unique(review.filter(r=>r.root?.category===mode.value).concat(unseen.filter(r=>r.root?.category===mode.value)));
  }
  if(mode.value==="foundation") return unique(review.concat(unseen.filter(r=>(r.l??9)<=2&&r.c>=2)));
  if(mode.value==="target12") return unique(review.concat(unseen.filter(r=>r.l!==null&&r.l>=3&&r.l<=4&&r.c>=3),unseen.filter(r=>(r.l??9)<=2&&r.c>=3)));
  const upper=rotate(unseen.filter(r=>(r.l??0)>=5),offset).slice(0,8);
  const recurring=rotate(unseen.filter(r=>r.c>=3&&(r.l??9)<=4),offset*3+5).slice(0,8);
  const longTail=rotate(unseen.filter(r=>r.c===1),offset*5+11).slice(0,4);
  return unique(review.concat(upper,recurring,longTail));
}
function renderDeck(){
  const pool=deckPool();const deck=rotate(pool,offset).slice(0,20);
  $('[data-study-deck]').innerHTML=deck.length?deck.map(card).join(""):"<p>這個分類目前沒有可用單字。</p>";
  $('[data-study-status]').textContent=mode.type==="root"?"字根分類 · "+mode.value+" · "+deck.length+" 字":(mode.value==="foundation"?"補地基":mode.value==="target12"?"高報酬":"長尾挑戰")+" · "+deck.length+" 字";
  $('[data-progress-count]').textContent=Object.keys(progress).length;
}
function searchable(r){const root=r.root;return [r.h,r.d,r.z,...(r.x||[]),root?.family,root?.variant,root?.meaning,root?.category,root?.breakdown,root?.logic].filter(Boolean).join(" ").toLocaleLowerCase("zh-Hant-TW")}
function filtered(){
  const q=filters.q.trim().toLocaleLowerCase("zh-Hant-TW");
  return words.filter(r=>{
    if(q&&!searchable(r).includes(q))return false;
    if(filters.level!=="all"){if(filters.level==="other"){if(r.l!==null)return false}else if(r.l!==Number(filters.level))return false}
    if(filters.category!=="all"&&r.root?.category!==filters.category)return false;
    if(filters.tier!=="all"&&r.b!==filters.tier)return false;
    return true;
  }).sort((a,b)=>filters.sort==="frequency"?b.c-a.c:filters.sort==="level"?(a.l??99)-(b.l??99)||b.c-a.c:filters.sort==="alphabetical"?a.h.localeCompare(b.h,"en"):score(b)-score(a));
}
function renderExplorer(reset=false){
  if(reset)visible=24;current=filtered();const shown=current.slice(0,visible);
  $('[data-word-grid]').innerHTML=shown.length?shown.map(card).join(""):"<p>沒有符合的單字。</p>";
  $('[data-result-count]').textContent=`找到 ${current.length.toLocaleString("zh-TW")} 筆，顯示前 ${shown.length.toLocaleString("zh-TW")} 筆`;
  $('[data-load-more]').hidden=shown.length>=current.length;
}
function setMode(type,value){
  mode={type,value};offset=0;
  document.querySelectorAll("[data-track]").forEach(b=>b.classList.toggle("is-active",type==="track"&&b.dataset.track===value));
  document.querySelectorAll("[data-root-mode]").forEach(b=>b.classList.toggle("is-active",type==="root"&&b.dataset.rootMode===value));
  renderDeck();location.hash="study";
}
function toast(msg){const e=$('[data-toast]');e.textContent=msg;e.classList.add("is-visible");setTimeout(()=>e.classList.remove("is-visible"),1500)}
function openDialog(r){
  const d=$('[data-word-dialog]');const root=r.root;
  $('[data-dialog-content]').innerHTML=`<div class="dialog-title"><span class="level-badge">${levelLabel(r)}</span><h2>${esc(r.h)}</h2><p>${esc(r.p||r.d||"")} · ${esc(r.z||"")}</p></div>${root?`<section class="dialog-root"><span class="root-category">${esc(root.category)}${root.confidence==="REVIEW"?" · 候選":""}</span><h3>${esc(root.breakdown)}</h3><dl><dt>字根家族</dt><dd>${esc(root.family)}</dd><dt>核心字根</dt><dd>${esc(root.variant)}｜${esc(root.meaning)}</dd><dt>構詞說明</dt><dd>${esc(root.logic)}</dd><dt>可信度</dt><dd>${root.confidence==="HIGH"?"高信心":"候選，建議複核"}</dd></dl></section>`:`<section class="dialog-root"><h3>此字目前不硬拆字根</h3><p>高頻功能詞或未匹配到本版 32 組核心字根時，保留整字與語境記憶。</p></section>`}<p>歷屆總次數：<strong>${r.c}</strong> · 出現年份：<strong>${r.y}/16</strong></p>`;
  d.showModal();
}
function bind(){
  $('[data-root-picker]').innerHTML=ROOT_CATEGORIES.map(c=>`<button data-root-mode="${c}">${c}</button>`).join("");
  $('[data-root-category]').insertAdjacentHTML("beforeend",ROOT_CATEGORIES.map(c=>`<option value="${c}">${c}</option>`).join(""));
  document.addEventListener("click",e=>{
    const t=e.target.closest("button");if(!t)return;
    if(t.dataset.track)setMode("track",t.dataset.track);
    if(t.dataset.rootMode)setMode("root",t.dataset.rootMode);
    if(t.dataset.open){const r=words.find(x=>x.id===t.dataset.open);if(r)openDialog(r)}
    if(t.dataset.progress){progress[t.dataset.id]=t.dataset.progress;saveProgress();renderDeck();renderExplorer();toast(t.dataset.progress==="known"?"已標記會了":"已放進複習")}
  });
  $('[data-refresh-deck]').onclick=()=>{offset+=20;renderDeck()};
  $('[data-export-progress]').onclick=()=>{const blob=new Blob([JSON.stringify({version:1,exported_at:new Date().toISOString(),progress},null,2)],{type:"application/json"});const u=URL.createObjectURL(blob);const a=document.createElement("a");a.href=u;a.download="gsat-root-progress.json";a.click();URL.revokeObjectURL(u)};
  $('[data-reset-progress]').onclick=()=>{if(confirm("確定清除本機學習進度？")){progress={};saveProgress();renderDeck();renderExplorer()}};
  $('[data-dialog-close]').onclick=()=>$('[data-word-dialog]').close();
  $('[data-hero-search]').onsubmit=e=>{e.preventDefault();filters.q=$('#hero-query').value.trim();$('[data-query]').value=filters.q;renderExplorer(true);location.hash="explorer"};
  $('[data-query]').value=filters.q;let timer;$('[data-query]').oninput=e=>{clearTimeout(timer);timer=setTimeout(()=>{filters.q=e.target.value;renderExplorer(true)},120)};
  $('[data-level]').onchange=e=>{filters.level=e.target.value;renderExplorer(true)};
  $('[data-root-category]').onchange=e=>{filters.category=e.target.value;renderExplorer(true)};
  $('[data-tier]').onchange=e=>{filters.tier=e.target.value;renderExplorer(true)};
  $('[data-sort]').onchange=e=>{filters.sort=e.target.value;renderExplorer(true)};
  $('[data-load-more]').onclick=()=>{visible+=24;renderExplorer()};
}
async function init(){
  bind();
  const raw=await fetchJson("vocabulary.json");
  words=raw.map(enrichRoot);
  $('[data-stat-total]').textContent=words.length.toLocaleString("zh-TW");
  $('[data-stat-rooted]').textContent=words.filter(r=>r.root).length.toLocaleString("zh-TW");
  renderDeck();renderExplorer();
}
init().catch(err=>{console.error(err);$('[data-study-status]').textContent="資料載入失敗：請執行 scripts/fetch-data.sh 或確認網路連線。"});