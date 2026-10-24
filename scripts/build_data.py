#!/usr/bin/env python3
"""Build public aggregate artifacts from the pinned local source cache."""

from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from pathlib import Path

from scripts.gsat_data import (
    VocabEntry,
    build_unmatched_family_map,
    build_variant_index,
    csv_write,
    decode_public_transport_text,
    expand_contraction,
    json_dump,
    likely_proper_noun,
    load_official_vocabulary_snapshot,
    load_translation_hints,
    map_token,
    period_stats,
    priority_tier,
    sha256_file,
    stable_unmatched_id,
    translation_for_entry,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "data" / "sources" / "exams.json"
PUBLIC_DATA = ROOT / "public" / "data"
LEGACY_PATH = ROOT / "data" / "sources" / "legacy-2024-summary.json"


def main() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    official_meta = manifest["vocabulary"]["official"]
    transcription_meta = manifest["vocabulary"]["transcription"]
    official_snapshot_meta = official_meta["entry_snapshot"]
    token_snapshot_meta = manifest["exam_token_snapshot"]
    official_snapshot = ROOT / official_snapshot_meta["local_path"]
    token_snapshot_path = ROOT / token_snapshot_meta["local_path"]
    translation_csv = ROOT / transcription_meta["local_path"]
    if sha256_file(official_snapshot) != official_snapshot_meta["sha256"]:
        raise SystemExit("Official vocabulary snapshot hash does not match the source manifest")
    if sha256_file(token_snapshot_path) != token_snapshot_meta["sha256"]:
        raise SystemExit("Exam token snapshot hash does not match the source manifest")
    if sha256_file(translation_csv) != transcription_meta["sha256"]:
        raise SystemExit("Vocabulary transcription hash does not match the source manifest")

    entries = load_official_vocabulary_snapshot(official_snapshot)
    token_snapshot = json.loads(token_snapshot_path.read_text(encoding="utf-8"))
    entries_by_id = {entry.id: entry for entry in entries}
    entry_groups: dict[str, list[VocabEntry]] = defaultdict(list)
    for entry in entries:
        entry_groups[entry.canonical].append(entry)
    variant_index = build_variant_index(entries)
    hints, translation_quality = load_translation_hints(translation_csv)

    year_surface: dict[int, Counter[str]] = {}
    year_study: dict[int, Counter[str]] = {}
    year_official: dict[int, Counter[str]] = {}
    year_appendix: dict[int, Counter[str]] = {}
    year_unmatched: dict[int, Counter[str]] = {}
    surface_casing: dict[str, Counter[str]] = defaultdict(Counter)
    official_forms: dict[str, Counter[str]] = defaultdict(Counter)
    appendix_forms: dict[str, Counter[str]] = defaultdict(Counter)
    raw_unmatched_forms: dict[str, Counter[str]] = defaultdict(Counter)
    mapping_methods: Counter[str] = Counter()

    for exam in manifest["exams"]:
        year = int(exam["year"])
        snapshot_year = token_snapshot["years"].get(str(year))
        if snapshot_year is None:
            raise SystemExit(f"Missing token snapshot for exam year {year}")
        surface_counter = Counter(
            {
                decode_public_transport_text(str(token)): int(count)
                for token, count in snapshot_year["surface_counts"].items()
            }
        )
        for surface, forms in snapshot_year["surface_casing"].items():
            decoded_surface = decode_public_transport_text(surface)
            surface_casing[decoded_surface].update(
                {
                    decode_public_transport_text(str(form)): int(count)
                    for form, count in forms.items()
                }
            )
        official_counter: Counter[str] = Counter()
        appendix_counter: Counter[str] = Counter()
        unmatched_counter: Counter[str] = Counter()
        for surface, amount in surface_counter.items():
            for component in expand_contraction(surface):
                mapped = map_token(component, variant_index, entries_by_id)
                mapping_methods[mapped.method] += amount
                if mapped.entry_id:
                    official_counter[mapped.key] += amount
                    official_forms[mapped.key][surface] += amount
                elif mapped.method == "ceec_appendix":
                    appendix_counter[mapped.key] += amount
                    appendix_forms[mapped.key][surface] += amount
                else:
                    unmatched_counter[mapped.key] += amount
                    raw_unmatched_forms[mapped.key][surface] += amount
        year_surface[year] = surface_counter
        year_official[year] = official_counter
        year_appendix[year] = appendix_counter
        year_unmatched[year] = unmatched_counter

    years = sorted(year_surface)
    if years != list(range(manifest["year_range"][0], manifest["year_range"][1] + 1)):
        raise SystemExit(f"Non-contiguous exam years: {years}")

    unmatched_keys = {key for counter in year_unmatched.values() for key in counter}
    unmatched_family_map = build_unmatched_family_map(unmatched_keys)
    normalized_year_unmatched: dict[int, Counter[str]] = {}
    unmatched_forms: dict[str, Counter[str]] = defaultdict(Counter)
    unmatched_casing: dict[str, Counter[str]] = defaultdict(Counter)
    merged_unmatched_tokens = 0
    for key, forms in raw_unmatched_forms.items():
        family = unmatched_family_map[key]
        unmatched_forms[family].update(forms)
        for form, amount in forms.items():
            unmatched_casing[family].update(
                {original: count for original, count in surface_casing.get(form, {}).items()}
            )
        if family != key:
            merged_unmatched_tokens += sum(forms.values())
    for year in years:
        normalized = Counter()
        for key, count in year_unmatched[year].items():
            normalized[unmatched_family_map[key]] += count
        normalized_year_unmatched[year] = normalized
        combined = Counter(year_official[year])
        combined.update(year_appendix[year])
        combined.update(normalized)
        year_study[year] = combined
    mapping_methods["unmatched_inflection_merged"] = merged_unmatched_tokens

    exam_by_year = {int(exam["year"]): exam for exam in manifest["exams"]}
    year_rows: list[dict[str, object]] = []
    for year in years:
        surface_counter = year_surface[year]
        study_counter = year_study[year]
        year_rows.append(
            {
                "year": year,
                "surface_tokens": sum(surface_counter.values()),
                "surface_types": len(surface_counter),
                "surface_singletons": sum(1 for count in surface_counter.values() if count == 1),
                "study_tokens": sum(study_counter.values()),
                "study_types": len(study_counter),
                "study_singletons": sum(1 for count in study_counter.values() if count == 1),
                "source_url": exam_by_year[year]["source_url"],
                "source_sha256": exam_by_year[year]["sha256"],
            }
        )

    total_surface: Counter[str] = Counter()
    total_study: Counter[str] = Counter()
    total_official: Counter[str] = Counter()
    total_appendix: Counter[str] = Counter()
    total_unmatched: Counter[str] = Counter()
    for year in years:
        total_surface.update(year_surface[year])
        total_study.update(year_study[year])
        total_official.update(year_official[year])
        total_appendix.update(year_appendix[year])
        total_unmatched.update(normalized_year_unmatched[year])

    official_records: list[dict[str, object]] = []
    entry_translation_rows = {
        entry.id: translation_for_entry(entry, hints, translation_quality) for entry in entries
    }
    for canonical, family_entries in sorted(entry_groups.items()):
        family_entries = sorted(family_entries, key=lambda item: (item.level, item.id))
        primary = family_entries[0]
        counts_by_year = {str(year): year_official[year][canonical] for year in years}
        count = sum(counts_by_year.values())
        seen_years = [year for year in years if counts_by_year[str(year)] > 0]
        recent_count = sum(counts_by_year[str(year)] for year in years if year >= 111)
        glosses: list[str] = []
        qualities: list[str] = []
        for entry in family_entries:
            gloss, quality = entry_translation_rows[entry.id]
            if gloss not in glosses:
                glosses.append(gloss)
            qualities.append(quality)
        gloss_quality = "curated_override" if "curated_override" in qualities else qualities[0]
        score = round(math.log1p(count) * 12 + len(seen_years) * 3 + math.log1p(recent_count) * 2, 3)
        forms = [form for form, _ in official_forms[canonical].most_common(12)]
        levels = sorted({entry.level for entry in family_entries})
        official_records.append(
            {
                "id": primary.id,
                "headword": canonical,
                "display_entry": " · ".join(entry.entry for entry in family_entries),
                "level": levels[0],
                "levels": levels,
                "official_entry_ids": [entry.id for entry in family_entries],
                "pos": " / ".join(dict.fromkeys(entry.pos for entry in family_entries)),
                "zh_hint": "；".join(glosses),
                "translation_quality": gloss_quality,
                "source_kind": "ceec_reference",
                "count": count,
                "years_seen": len(seen_years),
                "first_year": min(seen_years) if seen_years else None,
                "last_year": max(seen_years) if seen_years else None,
                "recent_count": recent_count,
                "priority_tier": priority_tier(count, len(seen_years)),
                "priority_score": score,
                "forms": forms,
                "year_counts": counts_by_year,
            }
        )

    appendix_records: list[dict[str, object]] = []
    unmatched_records: list[dict[str, object]] = []
    for key, count in total_appendix.most_common():
        counts_by_year = {str(year): year_appendix[year][key] for year in years}
        seen_years = [year for year in years if counts_by_year[str(year)] > 0]
        forms = [form for form, _ in appendix_forms[key].most_common(12)]
        appendix_records.append(
            {
                "id": "appendix-" + key.replace("'", ""),
                "headword": key,
                "display_entry": key,
                "level": None,
                "levels": [],
                "official_entry_ids": [],
                "pos": "",
                "zh_hint": "\uff08\u5927\u8003\u4e2d\u5fc3\u9644\u9304\u8a5e\u5f59\uff09",
                "translation_quality": "source_label",
                "source_kind": "ceec_appendix",
                "count": count,
                "years_seen": len(seen_years),
                "first_year": min(seen_years),
                "last_year": max(seen_years),
                "recent_count": sum(counts_by_year[str(year)] for year in years if year >= 111),
                "priority_tier": priority_tier(count, len(seen_years)),
                "priority_score": round(math.log1p(count) * 10 + len(seen_years) * 2, 3),
                "forms": forms,
                "year_counts": counts_by_year,
            }
        )

    for key, count in total_unmatched.most_common():
        counts_by_year = {str(year): normalized_year_unmatched[year][key] for year in years}
        seen_years = [year for year in years if counts_by_year[str(year)] > 0]
        forms = [form for form, _ in unmatched_forms[key].most_common(12)]
        proper = likely_proper_noun(key, unmatched_casing.get(key, Counter()), count)
        source_kind = "likely_proper_noun" if proper else "unmatched_surface"
        if "-" in key:
            source_kind = "hyphenated_or_compound"
        unmatched_records.append(
            {
                "id": stable_unmatched_id(key),
                "headword": key,
                "display_entry": key,
                "level": None,
                "levels": [],
                "official_entry_ids": [],
                "pos": "",
                "zh_hint": "\uff08\u8a5e\u8868\u5916\uff0f\u5c08\u540d\u6216\u8a5e\u5f62\u5f85\u5224\u8b80\uff09",
                "translation_quality": "not_available",
                "source_kind": source_kind,
                "count": count,
                "years_seen": len(seen_years),
                "first_year": min(seen_years),
                "last_year": max(seen_years),
                "recent_count": sum(counts_by_year[str(year)] for year in years if year >= 111),
                "priority_tier": priority_tier(count, len(seen_years)),
                "priority_score": round(math.log1p(count) * 10 + len(seen_years) * 2, 3),
                "forms": forms,
                "year_counts": counts_by_year,
            }
        )

    all_records = official_records + appendix_records + unmatched_records
    all_records.sort(
        key=lambda row: (-float(row["priority_score"]), -int(row["count"]), str(row["headword"]))
    )
    for rank, record in enumerate(all_records, start=1):
        record["rank"] = rank

    level_summary: list[dict[str, object]] = []
    for level in range(1, 7):
        level_entries = [entry for entry in entries if entry.level == level]
        level_families = {entry.canonical for entry in level_entries}
        primary_level_families = {
            canonical
            for canonical, family_entries in entry_groups.items()
            if min(entry.level for entry in family_entries) == level
        }
        level_summary.append(
            {
                "level": level,
                "official_entries": len(level_entries),
                "official_families": len(level_families),
                "observed_entries": sum(
                    1 for entry in level_entries if total_official[entry.canonical] > 0
                ),
                "observed_families": sum(
                    1 for canonical in level_families if total_official[canonical] > 0
                ),
                "token_occurrences": sum(
                    total_official[canonical] for canonical in primary_level_families
                ),
            }
        )

    legacy = json.loads(LEGACY_PATH.read_text(encoding="utf-8"))
    summary = {
        "schema_version": 1,
        "generated_from_manifest_sha256": sha256_file(MANIFEST_PATH),
        "year_range": [years[0], years[-1]],
        "exam_count": len(years),
        "official_vocabulary_entries": len(entries),
        "official_vocabulary_families": len(entry_groups),
        "official_entries_per_level": 1002,
        "translation_hint_coverage": {
            "available": sum(
                1 for gloss, quality in entry_translation_rows.values() if quality != "missing"
            ),
            "missing": sum(
                1 for gloss, quality in entry_translation_rows.values() if quality == "missing"
            ),
            "warning": "Chinese glosses are machine hints unless marked curated_override.",
        },
        "surface": {
            "full": period_stats(year_surface, years),
            "original_period": period_stats(year_surface, [year for year in years if year <= 113]),
            "recent_111_115": period_stats(year_surface, [year for year in years if year >= 111]),
        },
        "study_families": {
            "full": period_stats(year_study, years),
            "original_period": period_stats(year_study, [year for year in years if year <= 113]),
            "recent_111_115": period_stats(year_study, [year for year in years if year >= 111]),
        },
        "mapping_methods": dict(sorted(mapping_methods.items())),
        "level_summary": level_summary,
        "unmatched": {
            "records": len(unmatched_records),
            "token_occurrences": sum(int(row["count"]) for row in unmatched_records),
            "likely_proper_nouns": sum(
                1 for row in unmatched_records if row["source_kind"] == "likely_proper_noun"
            ),
        },
        "appendix": {
            "observed_records": len(appendix_records),
            "token_occurrences": sum(int(row["count"]) for row in appendix_records),
        },
        "legacy_2024": legacy,
        "method_notes": [
            "Surface forms preserve inflections and compounds but remove answer-choice labels and standalone letter artifacts.",
            "Study families use one canonical family identity across summary and downloads; official homographs retain all source entry ids.",
            "Out-of-list inflections merge only when exactly one observed out-of-list base exists; ambiguous forms remain unmatched.",
            "Study token totals can exceed surface totals because contractions such as can't expand into two study units.",
            "Counts describe the selected exam corpus and do not predict a guaranteed GSAT score.",
        ],
    }

    compact_records = []
    for row in all_records:
        compact_records.append(
            {
                "id": row["id"],
                "h": row["headword"],
                "d": row["display_entry"],
                "l": row["level"],
                "u": row["levels"],
                "e": row["official_entry_ids"],
                "p": row["pos"],
                "z": row["zh_hint"],
                "q": row["translation_quality"],
                "s": row["source_kind"],
                "c": row["count"],
                "y": row["years_seen"],
                "f": row["first_year"],
                "t": row["last_year"],
                "r": row["recent_count"],
                "b": row["priority_tier"],
                "o": row["priority_score"],
                "x": row["forms"],
                "n": row["year_counts"],
                "k": row["rank"],
            }
        )

    json_dump(PUBLIC_DATA / "summary.json", summary)
    json_dump(PUBLIC_DATA / "vocabulary.json", compact_records)
    json_dump(PUBLIC_DATA / "year-stats.json", year_rows)

    csv_fields = [
        "rank",
        "headword",
        "display_entry",
        "level",
        "levels",
        "official_entry_ids",
        "pos",
        "zh_hint",
        "translation_quality",
        "count",
        "years_seen",
        "first_year",
        "last_year",
        "recent_count",
        "priority_tier",
        "source_kind",
        "forms",
    ] + [f"year_{year}" for year in years]
    csv_rows = []
    for row in all_records:
        csv_row = {field: row.get(field, "") for field in csv_fields}
        csv_row["forms"] = "|".join(row["forms"])
        csv_row["levels"] = "|".join(str(level) for level in row["levels"])
        csv_row["official_entry_ids"] = "|".join(row["official_entry_ids"])
        for year in years:
            csv_row[f"year_{year}"] = row["year_counts"][str(year)]
        csv_rows.append(csv_row)
    csv_write(PUBLIC_DATA / "gsat-vocabulary-frequency.csv", csv_fields, csv_rows)

    print(
        json.dumps(
            {
                "years": [years[0], years[-1]],
                "exams": len(years),
                "official_entries": len(entries),
                "records": len(all_records),
                "surface_types": summary["surface"]["full"]["unique_types"],
                "study_types": summary["study_families"]["full"]["unique_types"],
                "singletons": summary["study_families"]["full"]["singletons"],
                "translation_missing": summary["translation_hint_coverage"]["missing"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
