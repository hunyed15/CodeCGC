import argparse
import json
import re
import sys
from pathlib import Path

from codecgc_artifact_roots import flow_root
from codecgc_console_io import configure_utf8_stdio
from codecgc_console_io import print_json
from codecgc_workflow_runtime import run_json_script

TRACK_HINTS = {
    "frontend": [
        "frontend",
        "ui",
        "browser",
        "client",
        "component",
        "page",
        "render",
        "interaction",
        "state",
        "layout",
    ],
    "backend": [
        "backend",
        "api",
        "server",
        "service",
        "endpoint",
        "database",
        "persistence",
        "job",
        "queue",
        "worker",
    ],
}

TRACK_PROJECTIONS = {
    "frontend": [
        (r"\bfrontend and backend\b", "frontend"),
        (r"\bbackend and frontend\b", "frontend"),
        (r"\bui and api\b", "UI"),
        (r"\bapi and ui\b", "UI"),
        (r"\bbrowser and api\b", "browser"),
        (r"\bapi and browser\b", "browser"),
    ],
    "backend": [
        (r"\bfrontend and backend\b", "backend"),
        (r"\bbackend and frontend\b", "backend"),
        (r"\bui and api\b", "API"),
        (r"\bapi and ui\b", "API"),
        (r"\bbrowser and api\b", "API"),
        (r"\bapi and browser\b", "API"),
    ],
}

WORKSPACE = Path(__file__).resolve().parents[1]
ROADMAP_ROOT = WORKSPACE / "codecgc" / "roadmap"


def slugify(value: str) -> str:
    normalized = value.strip().lower()
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized)
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-")
    if not normalized:
        raise ValueError("Child workflow slug cannot be empty after normalization.")
    return normalized


def strip_date_prefix(slug: str) -> str:
    if re.match(r"^\d{4}-\d{2}-\d{2}-", slug):
        return slug[11:]
    return slug


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Expand a roadmap initiative into child CodeCGC workflows.")
    parser.add_argument("--initiative", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--artifact-class", choices=["product", "fixture"], default="product")
    parser.add_argument("--source-flow", choices=["feature", "issue"], default="feature")
    parser.add_argument("--frontend-flow", choices=["auto", "feature", "issue"], default="auto")
    parser.add_argument("--backend-flow", choices=["auto", "feature", "issue"], default="auto")
    parser.add_argument("--frontend-path", action="append", default=[])
    parser.add_argument("--backend-path", action="append", default=[])
    parser.add_argument("--goal", default="")
    parser.add_argument("--user-story", default="")
    parser.add_argument("--symptom", default="")
    parser.add_argument("--expected", default="")
    parser.add_argument("--actual", default="")
    parser.add_argument("--root-cause", default="")
    parser.add_argument("--preferred-fix", default="")
    parser.add_argument("--rejected-fix", default="")
    parser.add_argument("--context", action="append", default=[])
    parser.add_argument("--in-scope", action="append", default=[])
    parser.add_argument("--risk", action="append", default=[])
    parser.add_argument("--dependency", action="append", default=[])
    parser.add_argument("--assumption", action="append", default=[])
    parser.add_argument("--validation", action="append", default=[])
    parser.add_argument("--rollback", action="append", default=[])
    parser.add_argument("--open-question", action="append", default=[])
    parser.add_argument("--acceptance", action="append", default=[])
    parser.add_argument("--force", action="store_true")
    return parser


def create_child_workflow(
    *,
    flow: str,
    slug: str,
    summary: str,
    kind: str,
    artifact_class: str,
    paths: list[str],
    force: bool,
) -> dict:
    command_args = [
        "--flow",
        flow,
        "--slug",
        slug,
        "--summary",
        summary,
        "--kind",
        kind,
        "--artifact-class",
        artifact_class,
    ]
    for path in paths:
        command_args.extend(["--target-path", path])
    if force:
        command_args.append("--force")
    return run_json_script("init_codecgc_workflow.py", *command_args)


def looks_like_issue_text(value: str) -> bool:
    lowered = value.lower()
    keywords = ["bug", "fix", "issue", "regression", "error", "broken", "failure", "hotfix"]
    return any(keyword in lowered for keyword in keywords)


def infer_track_flow(
    *,
    requested_flow: str,
    source_flow: str,
    summary: str,
    symptom: str,
    expected: str,
    actual: str,
    root_cause: str,
    preferred_fix: str,
    rejected_fix: str,
) -> str:
    if requested_flow in {"feature", "issue"}:
        return requested_flow
    if source_flow == "issue":
        return "issue"
    issue_signals = [
        symptom,
        expected,
        actual,
        root_cause,
        preferred_fix,
        rejected_fix,
        summary,
    ]
    if any(text.strip() and looks_like_issue_text(text) for text in issue_signals):
        return "issue"
    return "feature"


def narrow_items_for_track(kind: str, items: list[str], *, fallback: list[str]) -> list[str]:
    values = [item.strip() for item in items if item.strip()]
    if not values:
        return fallback

    matched: list[str] = []
    for item in values:
        lowered = item.lower()
        if kind == "frontend":
            if "backend" in lowered and "frontend" not in lowered and "ui" not in lowered:
                continue
        if kind == "backend":
            if "frontend" in lowered and "backend" not in lowered and "api" not in lowered:
                continue
        matched.append(item)
    return matched or fallback


def build_track_context(kind: str, context: list[str]) -> list[str]:
    base = [f"这个子工作流是从 roadmap initiative 中拆出的{'前端' if kind == 'frontend' else '后端'} track。"]
    return narrow_items_for_track(kind, context, fallback=base)


def build_track_scope(kind: str, items: list[str], paths: list[str]) -> list[str]:
    if kind == "frontend":
        fallback = [
            "只交付该 roadmap initiative 中前端可见的部分。",
            f"范围限制在已批准的前端 track 路径内：{', '.join(paths)}。",
        ]
    else:
        fallback = [
            "只交付该 roadmap initiative 中后端或 API 的部分。",
            f"范围限制在已批准的后端 track 路径内：{', '.join(paths)}。",
        ]
    return narrow_items_for_track(kind, items, fallback=fallback)


def build_track_validation(kind: str, items: list[str]) -> list[str]:
    if kind == "frontend":
        fallback = [
            "只验证前端 track 的浏览器可见行为。",
            "确认审核证据保持在前端 track 范围内。",
        ]
    else:
        fallback = [
            "只验证后端 track 的 API 或服务行为。",
            "确认审核证据保持在后端 track 范围内。",
        ]
    return narrow_items_for_track(kind, items, fallback=fallback)


def build_track_acceptance(kind: str, items: list[str]) -> list[str]:
    if kind == "frontend":
        fallback = ["前端 track 输出完整、可审核、且范围明确。"]
    else:
        fallback = ["后端 track 输出完整、可审核、且范围明确。"]
    return narrow_items_for_track(kind, items, fallback=fallback)


def build_track_questions(kind: str, items: list[str]) -> list[str]:
    if kind == "frontend":
        fallback = ["前端侧开放问题是否还需要继续拆分？"]
    else:
        fallback = ["后端侧开放问题是否还需要继续拆分？"]
    return narrow_items_for_track(kind, items, fallback=fallback)


def narrow_text_for_track(kind: str, value: str, fallback: str) -> str:
    text = value.strip()
    if not text:
        return fallback
    lowered = text.lower()
    if kind == "frontend" and "backend" in lowered and "frontend" not in lowered and "ui" not in lowered:
        return fallback
    if kind == "backend" and "frontend" in lowered and "backend" not in lowered and "api" not in lowered:
        return fallback
    return text


def track_score(kind: str, value: str) -> int:
    lowered = value.lower()
    return sum(1 for keyword in TRACK_HINTS[kind] if keyword in lowered)


def classify_track_text(value: str) -> str:
    frontend_score = track_score("frontend", value)
    backend_score = track_score("backend", value)
    if frontend_score and not backend_score:
        return "frontend"
    if backend_score and not frontend_score:
        return "backend"
    if frontend_score and backend_score:
        return "shared"
    return "neutral"


def split_sentences(value: str) -> list[str]:
    return [fragment.strip() for fragment in re.split(r"(?<=[.!?])\s+|\s*;\s*", value) if fragment.strip()]


def split_clauses(value: str) -> list[str]:
    return [fragment.strip() for fragment in re.split(r"(?i)\s+(?:and|but|while)\s+|,\s*", value) if fragment.strip()]


def normalize_fragment(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" ,;")


def format_fragments(fragments: list[str]) -> str:
    seen: set[str] = set()
    ordered: list[str] = []
    for fragment in fragments:
        normalized = normalize_fragment(fragment)
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(normalized)
    if not ordered:
        return ""
    joined = "; ".join(ordered)
    if joined[-1] not in ".!?":
        joined += "."
    return joined


def project_shared_issue_text(kind: str, value: str) -> str:
    projected = value.strip()
    for pattern, replacement in TRACK_PROJECTIONS[kind]:
        projected = re.sub(pattern, replacement, projected, flags=re.IGNORECASE)

    selected: list[str] = []
    for clause in split_clauses(projected):
        classification = classify_track_text(clause)
        if classification == kind:
            selected.append(clause)
        elif classification == "neutral":
            opposite = "backend" if kind == "frontend" else "frontend"
            if track_score(opposite, clause) == 0:
                selected.append(clause)

    return format_fragments(selected) or format_fragments([projected])


def narrow_issue_text_for_track(kind: str, value: str, fallback: str) -> str:
    text = value.strip()
    if not text:
        return fallback

    classification = classify_track_text(text)
    if classification in {kind, "neutral"}:
        return text
    if classification == ("backend" if kind == "frontend" else "frontend"):
        return fallback

    selected: list[str] = []
    for sentence in split_sentences(text):
        sentence_class = classify_track_text(sentence)
        if sentence_class == kind:
            selected.append(sentence)
            continue
        if sentence_class != "shared":
            continue
        for clause in split_clauses(sentence):
            if classify_track_text(clause) == kind:
                selected.append(clause)

    narrowed = format_fragments(selected)
    if narrowed:
        return narrowed

    projected = project_shared_issue_text(kind, text)
    projected_class = classify_track_text(projected)
    if projected and projected_class != ("backend" if kind == "frontend" else "frontend"):
        return projected

    return fallback


def bullet_lines(items: list[str], *, fallback: str) -> list[str]:
    values = [item.strip() for item in items if item.strip()]
    if not values:
        return [f"- {fallback}"]
    return [f"- {item}" for item in values]


def replace_section(content: str, heading: str, lines: list[str]) -> str:
    pattern = re.compile(
        rf"(^## {re.escape(heading)}\n\n)(.*?)(?=^## |\Z)",
        flags=re.MULTILINE | re.DOTALL,
    )
    replacement = "\\1" + "\n".join(lines).rstrip() + "\n\n"
    if pattern.search(content):
        return pattern.sub(replacement, content, count=1)
    trimmed = content.rstrip() + "\n\n"
    return trimmed + f"## {heading}\n\n" + "\n".join(lines).rstrip() + "\n"


def summarize_child_paths(paths: list[str]) -> str:
    if not paths:
        return "无"
    if len(paths) == 1:
        return paths[0]
    return f"{paths[0]} 等 {len(paths) - 1} 个路径"


def resolve_child_directory(flow: str, slug: str, artifact_class: str) -> Path:
    return flow_root(flow, artifact_class) / slug


def roadmap_tracking_lines(children: dict[str, dict]) -> tuple[list[str], list[str]]:
    phase_lines: list[str] = []
    delivery_lines: list[str] = []

    for track in ("frontend", "backend"):
        child = children.get(track)
        if not isinstance(child, dict) or not child.get("success"):
            continue
        flow = str(child.get("flow", "feature"))
        slug = str(child.get("slug", "")).strip()
        artifact_class = str(child.get("artifact_class", "product")).strip() or "product"
        directory = resolve_child_directory(flow, slug, artifact_class)
        recommended_command = str(child.get("recommended_command", "")).strip() or "cgc-plan"
        next_step = str(child.get("next", "")).strip() or "继续推进该子工作流。"
        notes = [str(item).strip() for item in child.get("notes", []) if str(item).strip()]
        target_paths = child.get("target_paths")
        path_summary = summarize_child_paths(target_paths) if isinstance(target_paths, list) else "见子工作流产物"

        phase_lines.extend(
            [
                f"- {track.title()} 子工作流: `{slug}`",
                f"  流程: `{flow}`",
                f"  目录: `{directory.relative_to(WORKSPACE).as_posix()}`",
                f"  范围提示: {path_summary}",
            ]
        )
        delivery_lines.extend(
            [
                f"- {track.title()} 子工作流: `{slug}`",
                f"  下一条命令: `{recommended_command}`",
                f"  下一步动作: {next_step}",
                f"  目录: `{directory.relative_to(WORKSPACE).as_posix()}`",
            ]
        )
        for note in notes[:2]:
            delivery_lines.append(f"  备注: {note}")

    return (
        phase_lines or ["- 暂无。"],
        delivery_lines or ["- 目前还没有登记子工作流。"],
    )


def write_roadmap_tracking(*, initiative: str, children: dict[str, dict]) -> None:
    roadmap_dir = ROADMAP_ROOT / initiative
    phases_path = roadmap_dir / "phases.md"
    delivery_plan_path = roadmap_dir / "delivery-plan.md"

    if not phases_path.exists() or not delivery_plan_path.exists():
        return

    phase_lines, delivery_lines = roadmap_tracking_lines(children)
    phases_content = phases_path.read_text(encoding="utf-8")
    delivery_content = delivery_plan_path.read_text(encoding="utf-8")

    phases_path.write_text(
        replace_section(phases_content, "5. 已初始化的子工作流", phase_lines),
        encoding="utf-8",
    )
    delivery_plan_path.write_text(
        replace_section(delivery_content, "6. 工作流跟踪", delivery_lines),
        encoding="utf-8",
    )


def build_track_dependencies(kind: str, items: list[str]) -> list[str]:
    if kind == "frontend":
        fallback = ["前端 track 依赖已具备，或必须在执行前明确确认。"]
    else:
        fallback = ["后端 track 依赖已具备，或必须在执行前明确确认。"]
    return narrow_items_for_track(kind, items, fallback=fallback)


def build_track_risks(kind: str, items: list[str]) -> list[str]:
    if kind == "frontend":
        fallback = ["在扩大 UI 范围前，仍需先审查前端 track 风险。"]
    else:
        fallback = ["在扩大 API 或服务范围前，仍需先审查后端 track 风险。"]
    return narrow_items_for_track(kind, items, fallback=fallback)


def enrich_child_workflow(
    *,
    flow: str,
    slug: str,
    summary: str,
    kind: str,
    artifact_class: str,
    paths: list[str],
    goal: str,
    user_story: str,
    symptom: str,
    expected: str,
    actual: str,
    root_cause: str,
    preferred_fix: str,
    rejected_fix: str,
    context: list[str],
    in_scope: list[str],
    risk: list[str],
    dependency: list[str],
    assumption: list[str],
    validation: list[str],
    rollback: list[str],
    open_question: list[str],
    acceptance: list[str],
    force: bool,
) -> dict:
    command_args = [
        "--flow",
        flow,
        "--slug",
        slug,
        "--summary",
        summary,
        "--kind",
        kind,
        "--artifact-class",
        artifact_class,
        "--goal",
        goal or "TODO",
        "--user-story",
        user_story or "TODO",
    ]
    if symptom:
        command_args.extend(["--symptom", symptom])
    if expected:
        command_args.extend(["--expected", expected])
    if actual:
        command_args.extend(["--actual", actual])
    if root_cause:
        command_args.extend(["--root-cause", root_cause])
    if preferred_fix:
        command_args.extend(["--preferred-fix", preferred_fix])
    if rejected_fix:
        command_args.extend(["--rejected-fix", rejected_fix])
    for path in paths:
        command_args.extend(["--target-path", path])
    for item in context:
        command_args.extend(["--context", item])
    for item in in_scope:
        command_args.extend(["--in-scope", item])
    for item in risk:
        command_args.extend(["--risk", item])
    for item in dependency:
        command_args.extend(["--dependency", item])
    for item in assumption:
        command_args.extend(["--assumption", item])
    for item in validation:
        command_args.extend(["--validation", item])
    for item in rollback:
        command_args.extend(["--rollback", item])
    for item in open_question:
        command_args.extend(["--open-question", item])
    for item in acceptance:
        command_args.extend(["--acceptance", item])
    if force:
        command_args.append("--force")
    return run_json_script("plan_codecgc_workflow.py", *command_args)


def main() -> int:
    configure_utf8_stdio()
    parser = build_parser()
    args = parser.parse_args()

    try:
        initiative_slug = slugify(strip_date_prefix(args.initiative))
        children: dict[str, dict] = {}
        frontend_flow = infer_track_flow(
            requested_flow=args.frontend_flow,
            source_flow=args.source_flow,
            summary=args.summary,
            symptom=args.symptom,
            expected=args.expected,
            actual=args.actual,
            root_cause=args.root_cause,
            preferred_fix=args.preferred_fix,
            rejected_fix=args.rejected_fix,
        )
        backend_flow = infer_track_flow(
            requested_flow=args.backend_flow,
            source_flow=args.source_flow,
            summary=args.summary,
            symptom=args.symptom,
            expected=args.expected,
            actual=args.actual,
            root_cause=args.root_cause,
            preferred_fix=args.preferred_fix,
            rejected_fix=args.rejected_fix,
        )

        if args.frontend_path:
            create_child_workflow(
                flow=frontend_flow,
                slug=f"{initiative_slug}-frontend-track",
                summary=f"{args.summary} Frontend Track",
                kind="frontend",
                artifact_class=args.artifact_class,
                paths=args.frontend_path,
                force=args.force,
            )
            children["frontend"] = enrich_child_workflow(
                flow=frontend_flow,
                slug=f"{initiative_slug}-frontend-track",
                summary=f"{args.summary} Frontend Track",
                kind="frontend",
                artifact_class=args.artifact_class,
                paths=args.frontend_path,
                goal=args.goal,
                user_story=args.user_story,
                symptom=narrow_issue_text_for_track("frontend", args.symptom, "Frontend track symptom still needs clarification."),
                expected=narrow_issue_text_for_track("frontend", args.expected, "Frontend expected behavior still needs clarification."),
                actual=narrow_issue_text_for_track("frontend", args.actual, "Frontend actual behavior still needs clarification."),
                root_cause=narrow_issue_text_for_track("frontend", args.root_cause, "Frontend root cause still needs clarification."),
                preferred_fix=narrow_issue_text_for_track("frontend", args.preferred_fix, "Frontend preferred fix still needs clarification."),
                rejected_fix=narrow_issue_text_for_track("frontend", args.rejected_fix, "Frontend rejected fix still needs clarification."),
                context=build_track_context("frontend", args.context),
                in_scope=build_track_scope("frontend", args.in_scope, args.frontend_path),
                risk=build_track_risks("frontend", args.risk),
                dependency=build_track_dependencies("frontend", args.dependency),
                assumption=args.assumption,
                validation=build_track_validation("frontend", args.validation),
                rollback=args.rollback,
                open_question=build_track_questions("frontend", args.open_question),
                acceptance=build_track_acceptance("frontend", args.acceptance),
                force=True,
            )
            children["frontend"]["artifact_class"] = args.artifact_class
            children["frontend"]["target_paths"] = list(args.frontend_path)

        if args.backend_path:
            create_child_workflow(
                flow=backend_flow,
                slug=f"{initiative_slug}-backend-track",
                summary=f"{args.summary} Backend Track",
                kind="backend",
                artifact_class=args.artifact_class,
                paths=args.backend_path,
                force=args.force,
            )
            children["backend"] = enrich_child_workflow(
                flow=backend_flow,
                slug=f"{initiative_slug}-backend-track",
                summary=f"{args.summary} Backend Track",
                kind="backend",
                artifact_class=args.artifact_class,
                paths=args.backend_path,
                goal=args.goal,
                user_story=args.user_story,
                symptom=narrow_issue_text_for_track("backend", args.symptom, "Backend track symptom still needs clarification."),
                expected=narrow_issue_text_for_track("backend", args.expected, "Backend expected behavior still needs clarification."),
                actual=narrow_issue_text_for_track("backend", args.actual, "Backend actual behavior still needs clarification."),
                root_cause=narrow_issue_text_for_track("backend", args.root_cause, "Backend root cause still needs clarification."),
                preferred_fix=narrow_issue_text_for_track("backend", args.preferred_fix, "Backend preferred fix still needs clarification."),
                rejected_fix=narrow_issue_text_for_track("backend", args.rejected_fix, "Backend rejected fix still needs clarification."),
                context=build_track_context("backend", args.context),
                in_scope=build_track_scope("backend", args.in_scope, args.backend_path),
                risk=build_track_risks("backend", args.risk),
                dependency=build_track_dependencies("backend", args.dependency),
                assumption=args.assumption,
                validation=build_track_validation("backend", args.validation),
                rollback=args.rollback,
                open_question=build_track_questions("backend", args.open_question),
                acceptance=build_track_acceptance("backend", args.acceptance),
                force=True,
            )
            children["backend"]["artifact_class"] = args.artifact_class
            children["backend"]["target_paths"] = list(args.backend_path)
        write_roadmap_tracking(initiative=args.initiative, children=children)
    except Exception as error:
        print_json({"success": False, "error": str(error)}, file=sys.stderr)
        return 1

    print_json({"success": True, "children": children})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
