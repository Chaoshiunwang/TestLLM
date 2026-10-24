export const ROOT_CATEGORIES=["感官動作","身體器官","手部動作","腳部動作","移動","展延或開合","各類動作","部分與全部"];

const ROOTS=[
  ["dic/dict","感官動作",["dict","dic"],"說、指出、展現"],
  ["spec/spect/spic","感官動作",["spect","spec","spic"],"看"],
  ["view/vis/vid","感官動作",["view","vis","vid"],"看、看見"],
  ["audio/aud/audi","感官動作",["audio","audi","aud"],"聽"],
  ["cord/card/cour","身體器官",["cord","card","cour"],"心"],
  ["ped/pod/pus","身體器官",["ped","pod","pus"],"腳"],
  ["spir","身體器官",["spir"],"呼吸、心、靈魂"],
  ["cap/capt/cip/ceiv/cept","手部動作",["capt","ceiv","cept","cip","cap"],"抓、拿取、有"],
  ["ple/plex/plic/ply (fold)","手部動作",["plex","plic"],"摺、對摺"],
  ["pos/pon","手部動作",["posit","pos","pon"],"放置"],
  ["port (carry)","手部動作",["port"],"攜帶、港口"],
  ["tain/ten/tin","手部動作",["tain","ten","tin"],"握、保留、持有"],
  ["car/cur/curs/cours","腳部動作",["curs","cours","cur","car"],"跑、進行"],
  ["ced/ceed/cess","腳部動作",["ceed","cess","ced"],"走、退讓"],
  ["grad/gred/gress","腳部動作",["gress","grad","gred"],"行走、前進"],
  ["sed/set/sess/sid","腳部動作",["sess","sed","set","sid"],"坐"],
  ["st/stat/stin/stitut/sist","腳部動作",["stitut","sist","stat","stin","st"],"站、建立"],
  ["miss/mis/mit","移動",["miss","mit","mis"],"送、派送"],
  ["mob/mom/mot/move","移動",["move","mob","mom","mot"],"移動"],
  ["vent/ven","移動",["vent","ven"],"來、去"],
  ["close/clud/clus","展延或開合",["close","clud","clus"],"關閉"],
  ["duc/duct","展延或開合",["duct","duc"],"引導、牽引、拉"],
  ["tend/tens/tent","展延或開合",["tend","tens","tent"],"薄、伸展"],
  ["tract/trait/tray/treat/tire","展延或開合",["tract","trait","treat","tray","tire"],"拉、牽引"],
  ["act/ag","各類動作",["act","ag"],"做、行動"],
  ["rect/reg","各類動作",["rect","reg"],"直、統治、正確"],
  ["fact/fect/fic/fit/feat/feit/fair/fy","各類動作",["fact","fect","feat","feit","fair","fic","fit","fy"],"做、製作"],
  ["gen","各類動作",["gener","gen"],"種類、誕生、生產"],
  ["lect/leg/lig","各類動作",["lect","leg","lig"],"聚集、選擇、讀、法律"],
  ["vers/vert","各類動作",["vers","vert"],"轉、轉變、輪流"],
  ["ple/plet/plen/pli/ply (fill)","部分與全部",["plet","plen","pli","ply","ple"],"充滿、完整"],
  ["part/port (part)","部分與全部",["part"],"部分"]
].map(([family,category,variants,meaning])=>({family,category,variants,meaning}));

const BLACKLIST=new Set(["tain/ten/tin:certain","tain/ten/tin:mountain","mob/mom/mot/move:mother","miss/mis/mit:limit","fact/fect/fic/fit/feat/feit/fair/fy:traffic","dic/dict:medical","view/vis/vid:individual","ced/ceed/cess:necessary","tend/tens/tent:content"]);
const SAFE=new Set(["visible","vision","visitor","visit","receive","accept","concept","perceive","deceive","submit","permit","admit","commit","transmit","emit","omit","motion","promote","remote","act","action","active","actual","activity","react","impact","pose","propose","oppose","expose","compose","generate","generation","general","significant","maintain"]);
const FUNCTION_WORDS=new Set("the be to a an of in and they for it that by as with from on at or if but not this these those he she we you i me him her us them my your his its our their who whom whose which what when where why how than then so very too also just only even no nor yes do does did have has had can could may might must shall should will would am is are was were been being there here up down out off into onto over under through during before after between among without within about against toward towards per via each every either neither both all any some many much few several another other same own such once twice again ever never always often sometimes usually perhaps maybe because although though while until unless whether".split(" "));

const CUSTOM={
  significant:{family:"fact/fect/fic/fit/feat/feit/fair/fy",category:"各類動作",variant:"fic",meaning:"做、製作",breakdown:"sign + fic + ant",logic:"sign（記號）＋ fic（做、製作）＋ ant → 能做出明顯標記，引申為「顯著的」。"},
  maintain:{family:"tain/ten/tin",category:"手部動作",variant:"tain",meaning:"握、保留、持有",breakdown:"main + tain",logic:"tain＝hold（持有、維持），可用「持續握住／保持」聯想 maintain＝維持。"}
};

function normalize(w){return String(w||"").toLowerCase().replace(/[^a-z]/g,"")}

export function analyzeRoot(word){
  const w=normalize(word);
  if(!w||FUNCTION_WORDS.has(w)) return null;
  if(CUSTOM[w]) return {...CUSTOM[w],confidence:"HIGH"};

  const candidates=[];
  for(const root of ROOTS){
    for(const variant of [...root.variants].sort((a,b)=>b.length-a.length)){
      const idx=w.indexOf(variant);
      if(idx<0||BLACKLIST.has(root.family+":"+w)) continue;
      candidates.push({root,variant,idx});
    }
  }
  candidates.sort((a,b)=>b.variant.length-a.variant.length||a.idx-b.idx);
  if(!candidates.length) return null;
  const c=candidates[0];
  const left=w.slice(0,c.idx),right=w.slice(c.idx+c.variant.length);
  const confidence=(c.variant.length>=4||SAFE.has(w))?"HIGH":"REVIEW";
  const parts=[left,c.variant,right].filter(Boolean);
  return {
    family:c.root.family,category:c.root.category,variant:c.variant,meaning:c.root.meaning,
    breakdown:parts.join(" + "),
    logic:`${c.variant}＝${c.root.meaning}；${confidence==="HIGH"?"可作為此字的主要構詞線索。":"目前只視為候選字根，避免因字母巧合而過度拆解。"}`,
    confidence
  };
}

export function enrichRoot(record){
  return {...record,root:analyzeRoot(record.h)};
}