from __future__ import annotations

import re
from collections import Counter


STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "be",
    "for",
    "from",
    "in",
    "is",
    "of",
    "on",
    "or",
    "the",
    "to",
    "use",
    "using",
    "with",
    "将其",
    "这条",
    "一个",
    "一种",
    "作为",
    "写入",
    "记录",
    "更新",
    "默认",
    "需要",
    "当前",
    "长期",
    "治理",
    "资产",
    "说明",
    "补充",
    "继续",
    "用于",
    "后续",
    "帮助",
    "统一",
    "暴露",
    "输出",
    "命令面",
}


def normalize_text(value: str) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    text = text.replace("`", "")
    replacements = {
        "只暴露": "唯一对外",
        "只使用": "统一使用",
        "命令面": "命令",
        "输出链路": "输出",
        "使用 utf 8": "utf8",
        "utf-8": "utf8",
        "utf 8": "utf8",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(r"[^\w\u4e00-\u9fff]+", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def tokenize(value: str) -> list[str]:
    normalized = normalize_text(value)
    if not normalized:
        return []

    tokens: list[str] = []
    for part in normalized.split():
        if not part or part in STOPWORDS:
            continue
        if re.fullmatch(r"[\u4e00-\u9fff]+", part):
            if len(part) <= 2:
                tokens.append(part)
            else:
                tokens.extend([part[index : index + 2] for index in range(len(part) - 1)])
            continue
        if len(part) <= 1:
            continue
        tokens.append(part)
    return tokens


def extract_entry_summaries(existing: str, field_labels: list[str]) -> list[str]:
    lines = str(existing or "").splitlines()
    summaries: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("### "):
            heading = stripped[4:].strip()
            if heading:
                summaries.append(heading)
            continue
        for label in field_labels:
            marker = f"- {label}:"
            if stripped.startswith(marker):
                value = stripped[len(marker) :].strip()
                if value:
                    summaries.append(value)
    seen: set[str] = set()
    unique: list[str] = []
    for item in summaries:
        key = normalize_text(item)
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(item.strip())
    return unique


def is_semantically_duplicate(candidate: str, existing_items: list[str], *, threshold: float = 0.72) -> bool:
    candidate_tokens = tokenize(candidate)
    if not candidate_tokens:
        return False

    candidate_counter = Counter(candidate_tokens)
    candidate_set = set(candidate_counter)
    candidate_normalized = normalize_text(candidate)

    for item in existing_items:
        item_normalized = normalize_text(item)
        if not item_normalized:
            continue
        if item_normalized == candidate_normalized:
            return True

        item_tokens = tokenize(item)
        if not item_tokens:
            continue
        item_counter = Counter(item_tokens)
        item_set = set(item_counter)
        overlap = candidate_set & item_set
        if not overlap:
            continue

        overlap_count = sum(min(candidate_counter[token], item_counter[token]) for token in overlap)
        similarity = overlap_count / max(len(candidate_tokens), len(item_tokens))
        coverage = len(overlap) / max(1, min(len(candidate_set), len(item_set)))
        candidate_normalized_words = set(normalize_text(candidate).split())
        item_normalized_words = set(item_normalized.split())
        word_overlap = candidate_normalized_words & item_normalized_words
        word_coverage = len(word_overlap) / max(1, min(len(candidate_normalized_words), len(item_normalized_words)))
        if similarity >= threshold or (similarity >= 0.58 and coverage >= 0.8) or (similarity >= 0.42 and word_coverage >= 0.6):
            return True

    return False


def has_existing_governance_entry(existing: str, summary: str, *, field_labels: list[str], threshold: float = 0.72) -> bool:
    summaries = extract_entry_summaries(existing, field_labels)
    return is_semantically_duplicate(summary, summaries, threshold=threshold)
