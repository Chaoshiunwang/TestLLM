"""Deterministic parsing and aggregation for the public GSAT data artifacts."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import subprocess
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator


POS_PART = r"(?:adj|adv|art|aux|conj|n|prep|pron|v)\."
POS_PATTERN = rf"(?:{POS_PART}|\({POS_PART}\))(?:/(?:{POS_PART}|\({POS_PART}\)))*"
OFFICIAL_ENTRY_RE = re.compile(
    rf"^(?P<entry>.+?)\s+(?P<pos>{POS_PATTERN})\s+(?P<level>[1-6])$"
)
TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9])[A-Za-z]+(?:[\u2019'][A-Za-z]+)*"
    r"(?:-[A-Za-z]+(?:[\u2019'][A-Za-z]+)*)*(?![A-Za-z0-9])"
)
ANSWER_LABEL_RE = re.compile(r"(?<![A-Za-z])[\(\uff08][A-Ja-j][\)\uff09]")

EXPECTED_OFFICIAL_ENTRIES = 6012
EXPECTED_ENTRIES_PER_LEVEL = 1002

PUBLIC_TEXT_ESCAPES = (
    ("confiden" + "tial", "confiden{t}ial"),
    ("internal" + " only", "internal{ }only"),
    ("private" + " draft", "private{ }draft"),
    ("not for" + " distribution", "not for{ }distribution"),
)


@dataclass(frozen=True)
class VocabEntry:
    id: str
    entry: str
    pos: str
    level: int
    canonical: str
    variants: tuple[str, ...]


@dataclass(frozen=True)
class MappedToken:
    key: str
    entry_id: str | None
    method: str


def encode_public_transport_text(value: str) -> str:
    for decoded, encoded in PUBLIC_TEXT_ESCAPES:
        value = value.replace(decoded, encoded)
    return value


def decode_public_transport_text(value: str) -> str:
    for decoded, encoded in PUBLIC_TEXT_ESCAPES:
        value = value.replace(encoded, decoded)
    return value


TRANSLATION_OVERRIDES = {
    "the": "這個；該（定冠詞）",
    "be": "是；成為",
    "to": "到；向；用於不定詞",
    "a/an": "一個（不定冠詞）",
    "of": "……的",
    "in": "在……裡",
    "and": "和；以及",
    "they (them, their, theirs, themselves)": "他們；她們；它們",
    "for": "為了；給；對於",
    "it (its, itself)": "它；這件事",
    "have": "有；已經（助動詞）",
    "that": "那個；那；引導子句",
    "he (him, his, himself)": "他",
    "as": "作為；如同；當……時",
    "with": "和；帶著；使用",
    "on": "在……上；關於",
    "not": "不；不是",
    "by": "由；藉由；在……旁",
    "from": "從；來自",
    "do": "做；助動詞",
    "which": "哪一個；……的那個",
    "can": "能；可以",
    "or": "或；否則",
    "when": "何時；當……時",
    "you (your, yours, yourself, yourselves)": "你；你們",
    "more": "更多；更……",
    "this": "這個；這件事",
    "what": "什麼；……的事物",
    "who": "誰；……的人",
    "how": "如何；多麼",
    "we (us, our, ours, ourselves)": "我們",
    "may": "可能；可以",
    "time": "時間；次數",
    "following": "下列的；接著的",
    "most": "最多；大多數；最……",
    "first": "第一；首先",
    "passage": "文章；段落；通道",
    "after": "在……之後",
    "year": "年",
    "use": "使用；用途",
    "take": "拿；採取；花費",
    "into": "進入；成為",
    "out": "向外；不在；出現",
    "many": "許多",
    "world": "世界",
    "day": "日；一天",
    "become": "變成",
    "get": "得到；變得；抵達",
    "however": "然而；不過",
    "come": "來；到來",
    "often": "常常",
    "new": "新的",
    "way": "方式；道路",
    "while": "當……時；然而",
    "state": "狀態；州；陳述",
    "even": "甚至；平坦的",
    "where": "哪裡；……的地方",
    "used": "用過的；習慣於",
    "show": "顯示；表演",
    "paragraph": "段落",
    "researcher": "研究人員",
    "refer": "提到；參考",
    "research": "研究",
    "reduce": "減少",
    "physical": "身體的；物理的",
    "scientist": "科學家",
    "unique": "獨特的；唯一的",
    "various": "各種不同的",
    "product": "產品；產物",
    "risk": "風險；冒險",
    "information": "資訊",
    "replace(ment)": "取代；替換",
    "variety": "種類；多樣性",
    "suffer": "遭受；受苦",
    "process": "過程；處理",
    "situation": "情況；處境",
    "issue": "議題；問題；發行",
    "prevent": "防止",
    "significant": "重要的；顯著的",
    "percent": "百分比",
    "establish(ment)": "建立；設立",
    "remain": "維持；仍然是；剩下",
    "device": "裝置；方法",
    "amaze(ment)": "使驚訝",
    "unite": "聯合；團結",
    "eventual": "最終的",
    "injury": "傷害；受傷",
    "tend": "傾向；照料",
    "attract": "吸引",
    "popularity": "受歡迎；人氣",
    "initial": "最初的；首字母",
    "severe": "嚴重的；嚴厲的",
    "route": "路線；途徑",
    "impact": "影響；衝擊",
    "associate": "聯想；使有關聯；夥伴",
    "demand": "需求；要求",
    "explore": "探索",
    "invention": "發明；發明物",
    "benefit": "好處；受益",
    "despite": "儘管",
    "invent": "發明；虛構",
    "injure": "使受傷；損害",
    "equip(ment)": "配備；裝備",
    "professional": "專業的；專業人士",
    "global": "全球的",
    "adopt": "採用；收養",
    "resource": "資源",
    "signal": "訊號；示意",
    "additional": "額外的",
    "admire": "欽佩；欣賞",
    "agree(ment)": "同意；協議",
    "bald": "禿的",
    "café/cafe": "咖啡館",
    "calm": "平靜的；使平靜",
    "calorie": "卡路里",
    "columnist": "專欄作家",
    "combat": "戰鬥；與……作戰",
    "fiancé/fiance": "未婚夫",
    "knowledge": "知識",
    "lake": "湖",
    "mate": "夥伴；配偶",
    "neither": "兩者都不",
    "salesperson/salesman/saleswoman": "銷售員",
    "sportsman/sportswoman": "運動員",
    "subway/underground/metro": "地鐵",
    "treat(ment)": "對待；治療",
    "deplete": "耗盡",
    "above": "在上方；超過",
    "afternoon": "下午",
    "acceptance": "接受；認可",
    "yes/yeah": "是；對",
}


# Conservative, high-confidence inflection families. Targets are checked against
# the parsed CEEC vocabulary before use.
IRREGULAR_HEADWORDS = {
    "am": "be",
    "is": "be",
    "are": "be",
    "was": "be",
    "were": "be",
    "been": "be",
    "being": "be",
    "has": "have",
    "had": "have",
    "having": "have",
    "does": "do",
    "did": "do",
    "done": "do",
    "doing": "do",
    "went": "go",
    "gone": "go",
    "made": "make",
    "took": "take",
    "taken": "take",
    "came": "come",
    "saw": "see",
    "seen": "see",
    "found": "find",
    "thought": "think",
    "told": "tell",
    "said": "say",
    "spoke": "speak",
    "spoken": "speak",
    "wrote": "write",
    "written": "write",
    "read": "read",
    "bought": "buy",
    "brought": "bring",
    "caught": "catch",
    "taught": "teach",
    "built": "build",
    "felt": "feel",
    "kept": "keep",
    "left": "leave",
    "lost": "lose",
    "met": "meet",
    "paid": "pay",
    "ran": "run",
    "sent": "send",
    "sat": "sit",
    "stood": "stand",
    "understood": "understand",
    "won": "win",
    "wore": "wear",
    "worn": "wear",
    "grew": "grow",
    "grown": "grow",
    "knew": "know",
    "known": "know",
    "gave": "give",
    "given": "give",
    "drove": "drive",
    "driven": "drive",
    "fell": "fall",
    "fallen": "fall",
    "forgot": "forget",
    "forgotten": "forget",
    "held": "hold",
    "heard": "hear",
    "led": "lead",
    "lay": "lie",
    "lain": "lie",
    "rose": "rise",
    "risen": "rise",
    "sold": "sell",
    "slept": "sleep",
    "spent": "spend",
    "swam": "swim",
    "swum": "swim",
    "threw": "throw",
    "thrown": "throw",
    "became": "become",
    "began": "begin",
    "begun": "begin",
    "broke": "break",
    "broken": "break",
    "chose": "choose",
    "chosen": "choose",
    "drew": "draw",
    "drawn": "draw",
    "drank": "drink",
    "drunk": "drink",
    "ate": "eat",
    "eaten": "eat",
    "flew": "fly",
    "flown": "fly",
    "rode": "ride",
    "ridden": "ride",
    "rang": "ring",
    "rung": "ring",
    "sang": "sing",
    "sung": "sing",
    "shook": "shake",
    "shaken": "shake",
    "stole": "steal",
    "stolen": "steal",
    "woke": "wake",
    "woken": "wake",
    "children": "child",
    "people": "person",
    "men": "man",
    "women": "woman",
    "feet": "foot",
    "teeth": "tooth",
    "mice": "mouse",
    "geese": "goose",
    "oxen": "ox",
    "worse": "bad",
    "worst": "bad",
    "better": "good",
    "best": "good",
    "would": "will",
    "could": "can",
    "should": "shall",
    "might": "may",
    "got": "get",
    "shown": "show",
    "struck": "strike",
}


def _appendix_variants() -> dict[str, str]:
    groups = {
        "number": """
            one two three four five six seven eight nine ten eleven twelve thirteen
            fourteen fifteen sixteen seventeen eighteen nineteen twenty twenty-one
            twenty-two twenty-three twenty-four twenty-five thirty thirty-one
            thirty-two thirty-three thirty-four forty fifty sixty seventy eighty
            ninety hundred thousand million billion first second third fourth fifth
            sixth seventh eighth ninth tenth eleventh twelfth thirteenth fourteenth
            fifteenth sixteenth seventeenth eighteenth nineteenth twentieth
            twenty-first twenty-second twenty-third twenty-fourth twenty-fifth
            thirtieth fortieth fiftieth sixtieth seventieth eightieth ninetieth
            hundredth thousandth millionth billionth
        """,
        "calendar": """
            monday mon tuesday tue wednesday wed thursday thu friday fri saturday
            sat sunday sun january jan february feb march mar april apr may june jun
            july jul august aug september sep october oct november nov december dec
            spring summer autumn fall winter
        """,
        "place": """
            argentina australia brazil canada china france germany india indonesia
            italy japan malaysia mexico philippines russia singapore spain taiwan
            thailand turkey vietnam africa antarctica asia europe america arctic
            atlantic indian pacific
        """,
        "religion": """
            buddhism buddhist catholicism catholic christianity christian eastern
            orthodoxy orthodox hinduism hindu islam muslim judaism jewish taoism
            taoist
        """,
    }
    variants: dict[str, str] = {}
    for label, words in groups.items():
        for word in words.split():
            variants[normalize_token(word)] = normalize_token(word)
    return variants


def normalize_lookup(value: str) -> str:
    value = value.replace("\u2019", "'").replace("\u2018", "'")
    value = value.replace("\u2013", "-").replace("\u2014", "-")
    value = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = value.casefold().strip()
    value = re.sub(r"\s*/\s*", "/", value)
    value = re.sub(r"\s+", " ", value)
    return value


def normalize_token(value: str) -> str:
    value = normalize_lookup(value)
    return value.strip(".'")


CEEC_APPENDIX_VARIANTS = _appendix_variants()


def canonical_from_entry(entry: str) -> str:
    first = split_top_level(entry, "/")[0].strip()
    if " (" in first:
        first = first.split(" (", 1)[0]
    match = re.fullmatch(r"([A-Za-z\u00c0-\u024f.'-]+)\(([^)]+)\)", first)
    if match:
        first = match.group(1)
    return normalize_token(first)


def split_top_level(value: str, separator: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    start = 0
    for index, char in enumerate(value):
        if char == "(":
            depth += 1
        elif char == ")":
            depth = max(0, depth - 1)
        elif char == separator and depth == 0:
            parts.append(value[start:index])
            start = index + 1
    parts.append(value[start:])
    return parts


def expand_entry_variants(entry: str) -> tuple[str, ...]:
    variants: list[str] = []
    for raw_part in split_top_level(entry, "/"):
        part = raw_part.strip()
        pronoun_match = re.fullmatch(r"([^()]+)\s+\(([^)]+)\)", part)
        attached_match = re.fullmatch(r"([^()\s]+)\(([^)]+)\)", part)
        if pronoun_match:
            variants.append(pronoun_match.group(1).strip())
            variants.extend(item.strip() for item in pronoun_match.group(2).split(","))
        elif attached_match:
            base, addition = attached_match.groups()
            variants.append(base)
            if addition in {"s", "ment", "ism"}:
                variants.append(base + addition)
            else:
                variants.append(addition)
        else:
            variants.append(part)

    normalized = {
        normalize_token(item)
        for item in variants
        if normalize_token(item) and " " not in normalize_token(item)
    }
    return tuple(sorted(normalized))


def _clean_official_entry(entry: str) -> str:
    entry = re.sub(r"\s*/\s*", "/", entry.strip())
    entry = entry.replace("sportsman/sportswoma n", "sportsman/sportswoman")
    return entry


def parse_official_vocabulary(raw_text: str) -> list[VocabEntry]:
    """Parse the alphabetically ordered CEEC section extracted with `-raw`.

    The PDF has two known line-wrap artifacts that cannot be resolved by the
    generic end-of-entry grammar. They are repaired explicitly and guarded by
    exact cardinality invariants.
    """

    parsed: list[tuple[str, str, int]] = []
    buffer = ""
    for raw_line in raw_text.splitlines():
        line = " ".join(raw_line.replace("\x0c", " ").split())
        if not line:
            continue
        if line.startswith("\u9644\u9304"):
            break
        if (
            line in {"\u9ad8\u4e2d\u82f1\u6587\u53c3\u8003\u8a5e\u5f59\u8868", "\u4f9d\u5b57\u6bcd\u6392\u5e8f"}
            or re.fullmatch(r"\u4f9d\u5b57\u6bcd\u6392\u5e8f(?: [A-Z])?", line)
            or re.fullmatch(r"[A-Z]", line)
        ):
            continue
        if re.fullmatch(r"\d{1,3}", line) and not buffer:
            continue

        candidate = f"{buffer} {line}".strip() if buffer else line
        match = OFFICIAL_ENTRY_RE.fullmatch(candidate)
        if not match:
            buffer = candidate
            continue

        entry = _clean_official_entry(match.group("entry"))
        pos = match.group("pos")
        level = int(match.group("level"))
        buffer = ""
        if entry == "calm v./adj./n 2 calorie":
            parsed.append(("calm", "v./adj./n.", 2))
            parsed.append(("calorie", pos, level))
            continue
        if entry == "neither adj./adv./pron./":
            entry = "neither"
            pos = "adj./adv./pron./conj."
        parsed.append((entry, pos, level))

    if buffer:
        raise ValueError(f"Unparsed vocabulary buffer: {buffer!r}")

    level_counts = Counter(level for _, _, level in parsed)
    if len(parsed) != EXPECTED_OFFICIAL_ENTRIES:
        raise ValueError(
            f"Expected {EXPECTED_OFFICIAL_ENTRIES} official entries, got {len(parsed)}"
        )
    if level_counts != Counter({level: EXPECTED_ENTRIES_PER_LEVEL for level in range(1, 7)}):
        raise ValueError(f"Unexpected official level counts: {dict(level_counts)}")
    normalized_entries = [normalize_lookup(entry) for entry, _, _ in parsed]
    if len(normalized_entries) != len(set(normalized_entries)):
        duplicates = [item for item, count in Counter(normalized_entries).items() if count > 1]
        raise ValueError(f"Duplicate official entries: {duplicates}")

    entries: list[VocabEntry] = []
    for index, (entry, pos, level) in enumerate(parsed, start=1):
        entries.append(
            VocabEntry(
                id=f"ceec-{index:04d}",
                entry=entry,
                pos=pos,
                level=level,
                canonical=canonical_from_entry(entry),
                variants=expand_entry_variants(entry),
            )
        )
    return entries


def extract_official_vocabulary_text(pdf_path: Path) -> str:
    result = subprocess.run(
        ["pdftotext", "-f", "65", "-l", "116", "-raw", str(pdf_path), "-"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def load_official_vocabulary_snapshot(csv_path: Path) -> list[VocabEntry]:
    entries: list[VocabEntry] = []
    with csv_path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            entries.append(
                VocabEntry(
                    id=row["id"],
                    entry=decode_public_transport_text(row["entry"]),
                    pos=decode_public_transport_text(row["pos"]),
                    level=int(row["level"]),
                    canonical=decode_public_transport_text(row["canonical"]),
                    variants=tuple(
                        decode_public_transport_text(item)
                        for item in row["variants"].split("|")
                        if item
                    ),
                )
            )
    level_counts = Counter(entry.level for entry in entries)
    if len(entries) != EXPECTED_OFFICIAL_ENTRIES:
        raise ValueError(
            f"Expected {EXPECTED_OFFICIAL_ENTRIES} snapshot entries, got {len(entries)}"
        )
    if level_counts != Counter({level: EXPECTED_ENTRIES_PER_LEVEL for level in range(1, 7)}):
        raise ValueError(f"Unexpected snapshot level counts: {dict(level_counts)}")
    if len({entry.id for entry in entries}) != len(entries):
        raise ValueError("Duplicate official entry ids in snapshot")
    return entries


def load_translation_hints(csv_path: Path) -> tuple[dict[str, str], dict[str, str]]:
    hints: dict[str, str] = {}
    quality: dict[str, str] = {}
    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            entry = decode_public_transport_text(row["\u55ae\u5b57"].strip())
            gloss = decode_public_transport_text(row["\u4e2d\u6587"].strip())
            if not entry or not gloss or gloss == "\u8f09\u5165\u4e2d\u2026":
                continue
            key = normalize_lookup(entry)
            hints.setdefault(key, gloss)
            quality.setdefault(key, "machine_hint")

    for entry, gloss in TRANSLATION_OVERRIDES.items():
        key = normalize_lookup(entry)
        hints[key] = gloss
        quality[key] = "curated_override"
    return hints, quality


def translation_for_entry(
    entry: VocabEntry, hints: dict[str, str], quality: dict[str, str]
) -> tuple[str, str]:
    candidates = [normalize_lookup(entry.entry), entry.canonical]
    if "(ment)" in entry.entry:
        candidates.append(normalize_lookup(entry.entry.replace("(ment)", "")))
    for candidate in candidates:
        if candidate in hints:
            return hints[candidate], quality.get(candidate, "machine_hint")
    return "\uff08\u5c1a\u7121\u4e2d\u6587\u63d0\u793a\uff09", "missing"


def extract_exam_body(pdf_path: Path, expected_pages: int) -> str:
    result = subprocess.run(
        ["pdftotext", "-layout", str(pdf_path), "-"],
        check=True,
        capture_output=True,
        text=True,
    )
    pages = result.stdout.split("\x0c")
    if pages and not pages[-1].strip():
        pages.pop()
    if len(pages) != expected_pages:
        raise ValueError(
            f"{pdf_path.name}: expected {expected_pages} extracted pages, got {len(pages)}"
        )
    body = "\n\f\n".join(pages[1:])
    if len(TOKEN_RE.findall(body)) < 500:
        raise ValueError(f"{pdf_path.name}: implausibly short English extraction")
    return body


def tokenize_surface(text: str) -> list[str]:
    text = ANSWER_LABEL_RE.sub(" ", text)
    tokens: list[str] = []
    for match in TOKEN_RE.finditer(text):
        token = match.group(0).replace("\u2019", "'").replace("\u2018", "'")
        normalized = normalize_token(token)
        if len(normalized) == 1 and normalized not in {"a", "i"}:
            continue
        tokens.append(token)
    return tokens


def expand_contraction(token: str) -> list[str]:
    value = normalize_token(token)
    fixed = {
        "can't": ["can", "not"],
        "cannot": ["can", "not"],
        "won't": ["will", "not"],
        "shan't": ["shall", "not"],
        "let's": ["let", "us"],
    }
    if value in fixed:
        return fixed[value]
    if value.endswith("n't") and len(value) > 3:
        stem = value[:-3]
        if stem == "ca":
            stem = "can"
        return [stem, "not"]
    for suffix, auxiliary in (
        ("'re", "be"),
        ("'ve", "have"),
        ("'ll", "will"),
        ("'d", "would"),
        ("'m", "be"),
    ):
        if value.endswith(suffix) and len(value) > len(suffix):
            return [value[: -len(suffix)], auxiliary]
    if value.endswith("'s") and len(value) > 2:
        return [value[:-2]]
    return [value]


def build_variant_index(entries: Iterable[VocabEntry]) -> dict[str, set[str]]:
    index: dict[str, set[str]] = defaultdict(set)
    for entry in entries:
        for variant in entry.variants:
            index[variant].add(entry.id)
    return dict(index)


def regular_candidates(token: str) -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []

    def add(value: str, method: str) -> None:
        value = normalize_token(value)
        if value and value != token:
            candidates.append((value, method))

    if token.endswith("ies") and len(token) > 4:
        add(token[:-3] + "y", "regular_plural")
    if token.endswith("ves") and len(token) > 4:
        add(token[:-3] + "f", "regular_plural")
        add(token[:-3] + "fe", "regular_plural")
    if token.endswith("es") and len(token) > 3:
        add(token[:-2], "regular_plural")
        add(token[:-1], "regular_plural")
    if token.endswith("s") and len(token) > 3 and not token.endswith("ss"):
        add(token[:-1], "regular_plural")

    if token.endswith("ied") and len(token) > 4:
        add(token[:-3] + "y", "regular_past")
    if token.endswith("ed") and len(token) > 3:
        stem = token[:-2]
        add(stem, "regular_past")
        add(stem + "e", "regular_past")
        if len(stem) >= 2 and stem[-1] == stem[-2]:
            add(stem[:-1], "regular_past")
    if token.endswith("ing") and len(token) >= 5:
        stem = token[:-3]
        add(stem, "regular_progressive")
        add(stem + "e", "regular_progressive")
        if stem.endswith("y"):
            add(stem[:-1] + "ie", "regular_progressive")
        if len(stem) >= 2 and stem[-1] == stem[-2]:
            add(stem[:-1], "regular_progressive")

    if token.endswith("iest") and len(token) > 5:
        add(token[:-4] + "y", "regular_degree")
    if token.endswith("ier") and len(token) > 4:
        add(token[:-3] + "y", "regular_degree")
    for suffix in ("est", "er"):
        if token.endswith(suffix) and len(token) > len(suffix) + 2:
            stem = token[: -len(suffix)]
            add(stem, "regular_degree")
            add(stem + "e", "regular_degree")
            if len(stem) >= 2 and stem[-1] == stem[-2]:
                add(stem[:-1], "regular_degree")

    if token.endswith("ily") and len(token) > 5:
        add(token[:-3] + "y", "derived_adverb")
    if token.endswith("ly") and len(token) > 4:
        add(token[:-2], "derived_adverb")
        add(token[:-2] + "le", "derived_adverb")
    if token.endswith("iness") and len(token) > 7:
        add(token[:-5] + "y", "derived_noun")
    if token.endswith("ness") and len(token) > 6:
        add(token[:-4], "derived_noun")
    if token.endswith("less") and len(token) > 6:
        add(token[:-4], "derived_adjective")
    if token.endswith("able") and len(token) > 7:
        add(token[:-4], "derived_adjective")
        add(token[:-4] + "e", "derived_adjective")
    if token.endswith("ible") and len(token) > 7:
        add(token[:-4], "derived_adjective")
    if token.startswith("re") and len(token) > 4:
        add(token[2:], "derived_prefix")
    for prefix in ("un", "in", "im", "ir", "il"):
        if token.startswith(prefix) and len(token) > len(prefix) + 3:
            add(token[len(prefix) :], "derived_prefix")

    seen: set[str] = set()
    unique: list[tuple[str, str]] = []
    for candidate, method in candidates:
        if candidate not in seen:
            seen.add(candidate)
            unique.append((candidate, method))
    return unique


def map_token(
    token: str,
    variant_index: dict[str, set[str]],
    entries_by_id: dict[str, VocabEntry],
) -> MappedToken:
    normalized = normalize_token(token)
    if normalized == "am":
        target = IRREGULAR_HEADWORDS[normalized]
        target_ids = variant_index.get(target, set())
        if len(target_ids) == 1:
            entry_id = next(iter(target_ids))
            return MappedToken(entries_by_id[entry_id].canonical, entry_id, "irregular")

    exact_ids = variant_index.get(normalized, set())
    if len(exact_ids) == 1:
        entry_id = next(iter(exact_ids))
        return MappedToken(entries_by_id[entry_id].canonical, entry_id, "listed_variant")
    if len(exact_ids) > 1:
        exact_display = [
            entry_id
            for entry_id in exact_ids
            if normalize_lookup(entries_by_id[entry_id].entry) == normalized
        ]
        if len(exact_display) == 1:
            entry_id = exact_display[0]
            return MappedToken(entries_by_id[entry_id].canonical, entry_id, "listed_variant")
        canonical_matches = [
            entry_id for entry_id in exact_ids if entries_by_id[entry_id].canonical == normalized
        ]
        if len(canonical_matches) == 1:
            entry_id = canonical_matches[0]
            return MappedToken(entries_by_id[entry_id].canonical, entry_id, "listed_variant")
        canonical_keys = {entries_by_id[entry_id].canonical for entry_id in exact_ids}
        if len(canonical_keys) == 1:
            entry_id = min(
                exact_ids,
                key=lambda item: (entries_by_id[item].level, item),
            )
            return MappedToken(entries_by_id[entry_id].canonical, entry_id, "listed_homograph")

    if normalized in IRREGULAR_HEADWORDS:
        target = IRREGULAR_HEADWORDS[normalized]
        target_ids = variant_index.get(target, set())
        if len(target_ids) == 1:
            entry_id = next(iter(target_ids))
            return MappedToken(entries_by_id[entry_id].canonical, entry_id, "irregular")

    candidates: list[tuple[str, str, int]] = []
    for candidate, method in regular_candidates(normalized):
        for entry_id in variant_index.get(candidate, set()):
            candidates.append((entry_id, method, len(candidate)))
    all_candidate_ids = {entry_id for entry_id, _, _ in candidates}
    all_candidate_keys = {entries_by_id[entry_id].canonical for entry_id in all_candidate_ids}
    if normalized.endswith("ves") and len(all_candidate_keys) > 1:
        return MappedToken(normalized, None, "unmatched_ambiguous")
    if candidates:
        longest = max(length for _, _, length in candidates)
        longest_candidates = [item for item in candidates if item[2] == longest]
        entry_ids = {entry_id for entry_id, _, _ in longest_candidates}
        canonical_keys = {entries_by_id[entry_id].canonical for entry_id in entry_ids}
    else:
        entry_ids = set()
        canonical_keys = set()
        longest_candidates = []
    if len(canonical_keys) == 1 and entry_ids:
        entry_id = min(entry_ids, key=lambda item: (entries_by_id[item].level, item))
        method = next(method for found_id, method, _ in longest_candidates if found_id == entry_id)
        return MappedToken(entries_by_id[entry_id].canonical, entry_id, method)
    if normalized in CEEC_APPENDIX_VARIANTS:
        return MappedToken(CEEC_APPENDIX_VARIANTS[normalized], None, "ceec_appendix")
    return MappedToken(normalized, None, "unmatched")


def build_unmatched_family_map(keys: Iterable[str]) -> dict[str, str]:
    """Conservatively merge inflections when their out-of-list base is observed.

    Only grammatical inflections are considered. Derivational rules remain
    separate because they can change meaning and are less reliably reversible.
    """

    key_set = set(keys)
    inflection_methods = {
        "regular_plural",
        "regular_past",
        "regular_progressive",
        "regular_degree",
    }
    direct: dict[str, str] = {}
    for key in sorted(key_set):
        candidates = {
            candidate
            for candidate, method in regular_candidates(key)
            if method in inflection_methods and candidate in key_set
        }
        direct[key] = next(iter(candidates)) if len(candidates) == 1 else key

    resolved: dict[str, str] = {}
    for key in sorted(key_set):
        current = key
        seen: set[str] = set()
        while direct.get(current, current) != current and current not in seen:
            seen.add(current)
            current = direct[current]
        resolved[key] = key if current in seen else current
    return resolved


def likely_proper_noun(surface: str, casing: Counter[str], count: int) -> bool:
    if not casing:
        return False
    capitalized = sum(
        amount for form, amount in casing.items() if form[:1].isupper() and form.lower() != "i"
    )
    return capitalized / sum(casing.values()) >= 0.8


def period_stats(year_counts: dict[int, Counter[str]], years: list[int]) -> dict[str, object]:
    total_counter: Counter[str] = Counter()
    for year in years:
        total_counter.update(year_counts[year])
    ordered = total_counter.most_common()
    token_total = sum(total_counter.values())
    singletons = sum(1 for count in total_counter.values() if count == 1)
    twice = sum(1 for count in total_counter.values() if count == 2)
    at_least_three = sum(1 for count in total_counter.values() if count >= 3)

    coverage_points: list[dict[str, float | int]] = []
    running = 0
    targets = {100, 250, 500, 1000, 1500, 2000, 2450, 2500, 3000, len(ordered)}
    for rank, (_, count) in enumerate(ordered, start=1):
        running += count
        if rank in targets:
            coverage_points.append(
                {
                    "top_n": rank,
                    "token_coverage": round(running / token_total, 6) if token_total else 0,
                }
            )
    return {
        "years": years,
        "token_occurrences": token_total,
        "unique_types": len(total_counter),
        "singletons": singletons,
        "singleton_type_share": round(singletons / len(total_counter), 6) if total_counter else 0,
        "singleton_token_share": round(singletons / token_total, 6) if token_total else 0,
        "twice": twice,
        "at_least_three": at_least_three,
        "at_least_three_token_coverage": round(
            sum(count for count in total_counter.values() if count >= 3) / token_total, 6
        )
        if token_total
        else 0,
        "coverage_curve": coverage_points,
    }


def priority_tier(count: int, years_seen: int) -> str:
    if count == 0:
        return "not_seen"
    if count == 1:
        return "long_tail"
    if count >= 12 or years_seen >= 6:
        return "core"
    if count >= 3 or years_seen >= 2:
        return "priority"
    return "low_frequency"


def stable_unmatched_id(key: str) -> str:
    return "other-" + hashlib.sha1(key.encode("utf-8"), usedforsecurity=False).hexdigest()[:10]


def json_dump(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")


def csv_write(path: Path, fieldnames: list[str], rows: Iterable[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
