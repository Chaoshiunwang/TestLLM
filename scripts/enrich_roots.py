#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "public" / "data" / "gsat-vocabulary-frequency.csv"
DST = ROOT / "public" / "data" / "gsat-vocabulary-frequency-root.csv"
QA_DST = ROOT / "public" / "data" / "root-analysis-qa.json"
MANUAL_REVIEW_DST = ROOT / "public" / "data" / "root-manual-review.csv"
DISCARD_DST = ROOT / "public" / "data" / "root-discarded-candidates.csv"

CATEGORIES = ["感官動作","身體器官","手部動作","腳部動作","移動","展延或開合","各類動作","部分與全部"]

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

# Only a complete decomposition (known prefix + root + known suffix) is promoted to HIGH.
# Ambiguous substring matches remain REVIEW and are NOT exposed as a root category.
PREFIXES = {
    "pre":"在前、預先","pro":"向前、支持","re":"再次、回",
    "in":"在內、不","im":"在內、不","il":"在內、不","ir":"在內、不",
    "con":"共同、一起","com":"共同、一起","co":"共同、一起","col":"共同、一起","cor":"共同、一起",
    "de":"向下、去除","dis":"分開、不","dif":"分開、不",
    "trans":"跨越","sub":"在下","sup":"在下","suc":"在下","suf":"在下","sus":"在下",
    "inter":"在中間","ex":"向外","ef":"向外","e":"向外",
    "ad":"朝向","ac":"朝向","af":"朝向","ap":"朝向","ar":"朝向","as":"朝向","at":"朝向",
    "ob":"朝向、反對","per":"穿過、徹底","a":"向、加強"
}
SUFFIXES = {
    "ation":"名詞字尾","ition":"名詞字尾","tion":"名詞字尾","sion":"名詞字尾","ion":"名詞字尾",
    "ivity":"名詞字尾","ity":"名詞字尾","ment":"名詞字尾","ness":"名詞字尾","ance":"名詞字尾","ence":"名詞字尾",
    "able":"可…的","ible":"可…的","ive":"形容詞字尾","ial":"形容詞字尾","al":"形容詞字尾","ous":"形容詞字尾",
    "ant":"形容詞／名詞字尾","ent":"形容詞／名詞字尾","ary":"形容詞／名詞字尾",
    "er":"人／物","or":"人／物","ist":"人／物","ly":"副詞字尾",
    "ize":"使…化","ise":"使…化","ify":"使…化","fy":"使…化",
    "ing":"現在分詞／動名詞","ed":"過去式／分詞","es":"複數／動詞變化","s":"複數／動詞變化","e":"常見拼字尾"
}

def candidates(word: str):
    w = word.lower().strip()
    hits = []
    for cat, fam, variants, meaning in ROOTS:
        for v in variants:
            start = 0
            while True:
                i = w.find(v, start)
                if i < 0:
                    break
                score = len(v) * 10
                if i == 0 or i + len(v) == len(w):
                    score += 8
                if len(v) <= 2:
                    score -= 40
                elif len(v) == 3:
                    score -= 10
                hits.append((score, cat, fam, v, meaning, i))
                start = i + 1
    return sorted(hits, reverse=True)

def affixes(word: str, variant: str, idx: int):
    before = word[:idx]
    after = word[idx + len(variant):]
    prefix = before if before in PREFIXES else ""
    suffix = after if after in SUFFIXES else ""
    return before, after, prefix, PREFIXES.get(prefix, ""), suffix, SUFFIXES.get(suffix, "")

def is_high_confidence(word: str, variant: str, idx: int):
    before, after, prefix, _, suffix, _ = affixes(word, variant, idx)
    before_ok = not before or bool(prefix)
    after_ok = not after or bool(suffix)
    # Require at least a 3-letter root and full explanation of both sides.
    # Whole-root words are accepted; otherwise at least one recognized affix is required.
    fully_explained = before_ok and after_ok
    has_structure = word == variant or bool(prefix) or bool(suffix)
    return len(variant) >= 3 and fully_explained and has_structure

def review_disposition(word: str, variant: str, idx: int):
    """Split ambiguous substring matches into useful manual review vs obvious coincidence."""
    before, after, prefix, _, suffix, _ = affixes(word, variant, idx)
    at_left = idx == 0
    at_right = idx + len(variant) == len(word)
    boundary = at_left or at_right
    affix_signal = bool(prefix) or bool(suffix)

    # Stronger-looking morphology: keep for a human to check.
    if len(variant) >= 5:
        return "MANUAL_REVIEW", "候選字根長度至少 5，值得人工確認"
    if len(variant) == 4 and (boundary or affix_signal):
        return "MANUAL_REVIEW", "4 字母候選且位於詞首/詞尾或伴隨已知詞綴"
    if len(variant) == 3 and affix_signal and boundary:
        return "MANUAL_REVIEW", "3 字母候選同時具有邊界與詞綴線索"
    if len(variant) >= 3 and boundary and (len(before) <= 3 and len(after) <= 4):
        return "MANUAL_REVIEW", "候選位於單字邊界，剩餘未解釋片段較短"

    # Short/internal matches without morphology are overwhelmingly noisy.
    if len(variant) <= 2:
        return "DISCARD", "候選僅 1–2 字母，字母巧合風險過高"
    if not boundary and not affix_signal:
        return "DISCARD", "候選位於單字內部且無已知詞綴支持"
    return "DISCARD", "目前缺乏足夠構詞證據"


def best_match(word: str):
    w = word.lower().strip()
    hits = candidates(w)
    if not hits:
        return None
    # Prefer the strongest candidate that passes strict structural validation.
    for score, cat, fam, v, meaning, i in hits:
        if is_high_confidence(w, v, i):
            return cat, fam, v, meaning, i, "HIGH"
    # Keep only the strongest remaining match, then decide whether it is worth human review.
    score, cat, fam, v, meaning, i = hits[0]
    disposition, reason = review_disposition(w, v, i)
    return cat, fam, v, meaning, i, disposition, reason

def analyze(word: str, zh: str):
    w = word.lower().strip()
    hit = best_match(w)
    if not hit:
        return {
            "morphology_type":"BASE_OR_UNMATCHED","word_breakdown":word,
            "prefix":"","prefix_meaning_zh":"","root_family":"","root_category":"",
            "root_variant":"","root_meaning_zh":"","suffix":"","suffix_meaning_zh":"",
            "root_logic_zh":"未匹配到本版核心字根；不建議硬拆。",
            "memory_hint_zh":f"先直接連結核心義「{zh}」。",
            "analysis_confidence":"UNMATCHED","root_candidate":"","root_candidate_meaning_zh":"",
            "review_disposition":"","review_reason":"","rejected_candidate":""
        }

    if len(hit) == 6:
        cat, fam, var, meaning, idx, confidence = hit
        reason = ""
    else:
        cat, fam, var, meaning, idx, confidence, reason = hit
    before, after, p, pzh, s, szh = affixes(w, var, idx)

    if confidence == "HIGH":
        parts = [x for x in (p, var, s) if x]
        breakdown = " + ".join(parts) if len(parts) > 1 else word
        logic = f"字根「{var}＝{meaning}」"
        if p:
            logic += f"，字首「{p}＝{pzh}」"
        if s:
            logic += f"，字尾「{s}＝{szh}」"
        logic += "；以完整構詞結構推導字義。"
        return {
            "morphology_type":"ROOT_FAMILY","word_breakdown":breakdown,
            "prefix":p,"prefix_meaning_zh":pzh,"root_family":fam,"root_category":cat,
            "root_variant":var,"root_meaning_zh":meaning,"suffix":s,"suffix_meaning_zh":szh,
            "root_logic_zh":logic,
            "memory_hint_zh":f"把「{var}＝{meaning}」與「{zh}」建立連結。",
            "analysis_confidence":"HIGH","root_candidate":"","root_candidate_meaning_zh":"",
            "review_disposition":"","review_reason":"","rejected_candidate":""
        }

    if confidence == "MANUAL_REVIEW":
        return {
            "morphology_type":"ROOT_CANDIDATE_REVIEW","word_breakdown":word,
            "prefix":"","prefix_meaning_zh":"","root_family":"","root_category":"",
            "root_variant":"","root_meaning_zh":"","suffix":"","suffix_meaning_zh":"",
            "root_logic_zh":f"候選詞素「{var}」具有部分構詞線索，但不足以自動確認；暫不列入正式字根分類。",
            "memory_hint_zh":f"暫以單字義「{zh}」為主，待人工查可靠字源後再決定是否升級。",
            "analysis_confidence":"MANUAL_REVIEW","root_candidate":f"{var} → {fam}",
            "root_candidate_meaning_zh":meaning,
            "review_disposition":"MANUAL_REVIEW","review_reason":reason,"rejected_candidate":""
        }

    return {
        "morphology_type":"BASE_OR_UNMATCHED","word_breakdown":word,
        "prefix":"","prefix_meaning_zh":"","root_family":"","root_category":"",
        "root_variant":"","root_meaning_zh":"","suffix":"","suffix_meaning_zh":"",
        "root_logic_zh":"偵測到的字母片段缺乏足夠構詞證據，視為字母巧合並排除。",
        "memory_hint_zh":f"直接記憶核心義「{zh}」，不使用此候選字根。",
        "analysis_confidence":"DISCARD","root_candidate":"","root_candidate_meaning_zh":"",
        "review_disposition":"DISCARD","review_reason":reason,
        "rejected_candidate":f"{var} → {fam}"
    }

def main():
    with SRC.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    extra = [
        "morphology_type","word_breakdown","prefix","prefix_meaning_zh","root_family","root_category",
        "root_variant","root_meaning_zh","suffix","suffix_meaning_zh","root_logic_zh","memory_hint_zh",
        "analysis_confidence","root_candidate","root_candidate_meaning_zh",
        "review_disposition","review_reason","rejected_candidate"
    ]
    fields = list(rows[0].keys()) + extra

    for row in rows:
        row.update(analyze(row["headword"], row.get("zh_hint", "")))

    with DST.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    confidence = Counter(r["analysis_confidence"] for r in rows)
    categories = Counter(r["root_category"] for r in rows if r["root_category"])
    families = defaultdict(int)
    for r in rows:
        if r["root_family"]:
            families[r["root_family"]] += 1

    manual_rows = [r for r in rows if r["analysis_confidence"] == "MANUAL_REVIEW"]
    discard_rows = [r for r in rows if r["analysis_confidence"] == "DISCARD"]

    review_fields = ["headword","level","pos","zh_hint","count","years_seen","root_candidate","root_candidate_meaning_zh","review_reason"]
    with MANUAL_REVIEW_DST.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=review_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(manual_rows)

    discard_fields = ["headword","level","pos","zh_hint","count","years_seen","rejected_candidate","review_reason"]
    with DISCARD_DST.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=discard_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(discard_rows)

    qa = {
        "records": len(rows),
        "confidence": dict(confidence),
        "classified_high": sum(categories.values()),
        "manual_review_candidates": len(manual_rows),
        "discarded_candidate_matches": len(discard_rows),
        "categories": {c: categories.get(c, 0) for c in CATEGORIES},
        "families": dict(sorted(families.items())),
        "rules": {
            "high": "root >= 3 letters and all text before/after root is empty or a recognized affix",
            "manual_review": "candidate has boundary/length/affix evidence but is not strong enough for automatic classification",
            "discard": "short/internal substring match without enough morphology; rejected as likely coincidence",
            "unmatched": "no root candidate"
        }
    }
    QA_DST.write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(qa, ensure_ascii=False))

if __name__ == "__main__":
    main()
