#!/usr/bin/env python3
from __future__ import annotations
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "public" / "data" / "gsat-vocabulary-frequency.csv"
DST = ROOT / "public" / "data" / "gsat-vocabulary-frequency-root.csv"

ROOTS = [
    ("感官動作","dic/dict",["dict","dic"],"說、指出"),
    ("感官動作","spec/spect/spic",["spect","spec","spic"],"看"),
    ("感官動作","view/vis/vid",["view","vis","vid"],"看"),
    ("感官動作","audio/aud/audi",["audio","audi","aud"],"聽"),
    ("身體器官","cord/card/cour",["cord","card","cour"],"心"),
    ("身體器官","ped/pod/pus",["ped","pod","pus"],"腳"),
    ("身體器官","spir",["spir"],"呼吸"),
    ("手部動作","cap/capt/cip/ceiv/cept",["capt","cept","ceiv","cap","cip"],"拿、抓、接收"),
    ("手部動作","ple/plex/plic/ply (fold)",["plex","plic","ply"],"摺、彎"),
    ("手部動作","pos/pon",["pos","pon"],"放置"),
    ("手部動作","port (carry)",["port"],"攜帶"),
    ("手部動作","tain/ten/tin",["tain","ten","tin"],"持有"),
    ("腳部動作","car/cur/curs/cours",["cours","curs","cur","car"],"跑、行進"),
    ("腳部動作","ced/ceed/cess",["ceed","cess","ced"],"走、前進"),
    ("腳部動作","grad/gred/gress",["gress","grad","gred"],"走、步"),
    ("腳部動作","sed/set/sess/sid",["sess","sed","set","sid"],"坐"),
    ("腳部動作","st/stat/stin/stitut/sist",["stitut","stat","stin","sist","st"],"站、建立"),
    ("移動","miss/mis/mit",["miss","mit","mis"],"送、放"),
    ("移動","mob/mom/mot/move",["move","mob","mom","mot"],"移動"),
    ("移動","vent/ven",["vent","ven"],"來、去"),
    ("展延或開合","close/clud/clus",["close","clud","clus"],"關閉"),
    ("展延或開合","duc/duct",["duct","duc"],"引導、帶領"),
    ("展延或開合","tend/tens/tent",["tend","tens","tent"],"伸展、延伸"),
    ("展延或開合","tract/trait/tray/treat/tire",["tract","trait","treat","tray","tire"],"拉、拖"),
    ("各類動作","act/ag",["act","ag"],"做、行動"),
    ("各類動作","rect/reg",["rect","reg"],"引導、治理"),
    ("各類動作","fact/fect/fic/fit/feat/feit/fair/fy",["fact","fect","feat","feit","fair","fic","fit","fy"],"做、製作"),
    ("各類動作","gen",["gen"],"生、產生"),
    ("各類動作","lect/leg/lig",["lect","leg","lig"],"選擇、收集、讀"),
    ("各類動作","vers/vert",["vers","vert"],"轉"),
    ("部分與全部","ple/plet/plen/pli/ply (fill)",["plet","plen","pli","ple"],"充滿、完整"),
    ("部分與全部","part/port (part)",["part"],"部分、分開"),
]

PREFIXES = {
    "pre":"在前、預先","pro":"向前、支持","re":"再次、回","in":"在內、不","im":"在內、不",
    "con":"共同、一起","com":"共同、一起","de":"向下、去除","dis":"分開、不","trans":"跨越",
    "sub":"在下","inter":"在中間","ex":"向外","e":"向外","ad":"朝向","ob":"朝向、反對",
    "per":"穿過、徹底","a":"向、加強"
}
SUFFIXES = {
    "tion":"名詞字尾","sion":"名詞字尾","ment":"名詞字尾","ity":"名詞字尾","ness":"名詞字尾",
    "able":"可…的","ible":"可…的","ive":"形容詞字尾","al":"形容詞字尾","ous":"形容詞字尾",
    "ant":"形容詞／名詞字尾","ent":"形容詞／名詞字尾","er":"人／物","or":"人／物","ly":"副詞字尾",
    "ize":"使…化","ise":"使…化","ify":"使…化","fy":"使…化","ing":"現在分詞／動名詞","ed":"過去式／分詞",
    "e":"常見拼字尾"
}

def best_match(word: str):
    w = word.lower().strip()
    hits=[]
    for cat,fam,variants,meaning in ROOTS:
        for v in variants:
            i=w.find(v)
            if i < 0: continue
            score=len(v)*10
            if i==0 or i+len(v)==len(w): score+=8
            if len(v)<=2: score-=30
            elif len(v)==3: score-=8
            hits.append((score,cat,fam,v,meaning,i))
    if not hits: return None
    hits.sort(reverse=True)
    score,cat,fam,v,meaning,i=hits[0]
    confidence = "HIGH" if (len(v)>=4 or (len(v)==3 and (i==0 or i+len(v)==len(w)))) else "REVIEW"
    return cat,fam,v,meaning,i,confidence

def affixes(word:str, variant:str, idx:int):
    before=word[:idx]
    after=word[idx+len(variant):]
    prefix=""
    pzh=""
    suffix=""
    szh=""
    for p in sorted(PREFIXES,key=len,reverse=True):
        if before==p:
            prefix,pzh=p,PREFIXES[p]
            break
    for s in sorted(SUFFIXES,key=len,reverse=True):
        if after==s:
            suffix,szh=s,SUFFIXES[s]
            break
    return prefix,pzh,suffix,szh

def analyze(word:str, zh:str):
    hit=best_match(word)
    if not hit:
        return {
            "morphology_type":"BASE_OR_UNMATCHED","word_breakdown":word,
            "prefix":"","prefix_meaning_zh":"","root_family":"","root_category":"",
            "root_variant":"","root_meaning_zh":"","suffix":"","suffix_meaning_zh":"",
            "root_logic_zh":"未匹配到本版 32 組高信心核心字根；不建議硬拆。",
            "memory_hint_zh":f"先直接連結核心義「{zh}」，未來若加入更完整字源庫再補充。",
            "analysis_confidence":"HIGH","root_candidate":"","root_candidate_meaning_zh":""
        }
    cat,fam,var,meaning,idx,confidence=hit
    p,pzh,s,szh=affixes(word.lower(),var,idx)
    parts=[x for x in (p,var,s) if x]
    breakdown=" + ".join(parts) if len(parts)>1 else word
    logic=f"先抓核心字根「{var}＝{meaning}」"
    if p or s: logic+="，再用前後詞綴推導整體字義。"
    else: logic+="，再回到單字語境理解整體字義。"
    base={
        "word_breakdown":breakdown,"prefix":p,"prefix_meaning_zh":pzh,
        "root_family":fam if confidence=="HIGH" else "","root_category":cat,
        "root_variant":var if confidence=="HIGH" else "","root_meaning_zh":meaning if confidence=="HIGH" else "",
        "suffix":s,"suffix_meaning_zh":szh,"root_logic_zh":logic,
        "memory_hint_zh":f"把「{var}＝{meaning}」與「{zh}」建立連結。",
        "analysis_confidence":confidence,
        "root_candidate":"" if confidence=="HIGH" else f"{var} → {fam}",
        "root_candidate_meaning_zh":"" if confidence=="HIGH" else meaning,
        "morphology_type":"ROOT_FAMILY" if confidence=="HIGH" else "ROOT_CANDIDATE_REVIEW"
    }
    return base

def main():
    with SRC.open(encoding="utf-8-sig",newline="") as f:
        rows=list(csv.DictReader(f))
    extra=["morphology_type","word_breakdown","prefix","prefix_meaning_zh","root_family","root_category",
           "root_variant","root_meaning_zh","suffix","suffix_meaning_zh","root_logic_zh","memory_hint_zh",
           "analysis_confidence","root_candidate","root_candidate_meaning_zh"]
    fields=list(rows[0].keys())+extra
    for row in rows:
        row.update(analyze(row["headword"],row.get("zh_hint","")))
    with DST.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields)
        w.writeheader();w.writerows(rows)
    rooted=sum(bool(r.get("root_category")) for r in rows)
    print(f"enriched {len(rows)} records; root-classified {rooted}")

if __name__=="__main__":
    main()
