#!/usr/bin/env python3
"""
Skill Pipeline CLI — active orchestration for Claude's skill system.

Commands:
    plan     Validate a pipeline plan and show contracts
    start    Initialize and persist pipeline state
    next     Get the next skill to execute (contract + context)
    complete Record skill completion with validated output
    skip     Skip a pending step
    status   Show current pipeline state
    report   Generate full pipeline report
    lessons  Generate lessons.md entry
    list     List all registered skills
    check    Validate a skill sequence
    resume   Resume context from previous sessions

Examples:
    python pipeline.py plan code-audit ops-reliability --priority P1 --scenario "pre-deploy check"
    python pipeline.py start code-audit ops-reliability --priority P1 --scenario "pre-deploy check"
    python pipeline.py next
    python pipeline.py complete code-audit --output result.json
    python pipeline.py status
    python pipeline.py report
    python pipeline.py list
    python pipeline.py check platform-architecture ux-audit code-audit
    python pipeline.py resume --project-root ../..
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure the skill-runtime root is in the path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from runtime.contracts import (
    Priority,
    PipelineState,
    SkillResult,
    StepStatus,
    InputKind,
    _get_project_root,
    _get_state_dir,
)
from runtime.runner import PipelineRunner, estimate_effort
from skills.registry import (
    SKILL_REGISTRY,
    validate_sequence,
    validate_contracts_chain,
)


def cmd_plan(args: argparse.Namespace) -> None:
    """Validate a pipeline plan."""
    runner = PipelineRunner()
    result = runner.plan(
        skill_names=args.skills,
        priority=Priority(args.priority),
        scenario=args.scenario or " + ".join(args.skills),
    )
    print(json.dumps(result, indent=2))

    if not result["valid"]:
        sys.exit(1)


def cmd_start(args: argparse.Namespace) -> None:
    """Initialize pipeline and persist state."""
    runner = PipelineRunner()

    # Validate first
    plan = runner.plan(
        skill_names=args.skills,
        priority=Priority(args.priority),
        scenario=args.scenario or " + ".join(args.skills),
    )

    if not plan["valid"]:
        print("Plan invalid. Fix issues before starting:")
        print(json.dumps(plan, indent=2))
        sys.exit(1)

    # Print warnings
    if plan["warnings"]:
        print("Warnings:")
        for w in plan["warnings"]:
            print(f"   {w}")
        print()

    state = runner.start(
        skill_names=args.skills,
        priority=Priority(args.priority),
        scenario=args.scenario or " + ".join(args.skills),
    )

    print(f"Pipeline started: {state.plan_id}")
    print(f"   State file: {state.state_file}")
    print(f"   Steps: {len(state.steps)}")
    print(f"   Priority: {state.priority.value}")
    print(f"   Effort: {estimate_effort(args.skills).value}")
    print(f"\nRun `python pipeline.py next` to get the first skill.")


def cmd_next(args: argparse.Namespace) -> None:
    """Get next skill to execute."""
    runner = _load_runner()
    context = runner.next()

    if context is None:
        if runner.state and runner.state.stopped:
            print(f"Pipeline stopped: {runner.state.stop_reason}")
        elif runner.state and runner.state.is_complete:
            print("Pipeline complete. Run `python pipeline.py report` for summary.")
        else:
            print("No next step available.")
        return

    print(json.dumps(context, indent=2))


def cmd_complete(args: argparse.Namespace) -> None:
    """Record skill completion."""
    runner = _load_runner()

    # Load result from file or create minimal one
    if args.output and Path(args.output).exists():
        result = SkillResult.from_json_file(args.output)
    else:
        result = SkillResult(
            skill_name=args.skill,
            status=StepStatus.COMPLETED,
            outputs={},
            notes=args.notes or "",
        )

    # If findings file provided, load it
    if args.findings and Path(args.findings).exists():
        with open(args.findings) as f:
            result.outputs["findings"] = json.load(f)

    result.skill_name = args.skill

    validation = runner.complete(result)
    print(json.dumps(validation, indent=2))

    if "early_stop" in validation:
        print(f"\nEarly stop triggered: {validation['early_stop']}")


def cmd_skip(args: argparse.Namespace) -> None:
    """Skip a pending step."""
    runner = _load_runner()
    runner.skip(args.skill, args.reason or "")
    print(f"Skipped: {args.skill}")


def cmd_status(args: argparse.Namespace) -> None:
    """Show pipeline status."""
    runner = _load_runner()
    print(json.dumps(runner.status(), indent=2))


def cmd_report(args: argparse.Namespace) -> None:
    """Generate full report."""
    runner = _load_runner()
    report = runner.report()
    print(report)

    if args.save:
        path = Path(args.save)
        path.write_text(report)
        print(f"\nSaved to {path}")


def cmd_lessons(args: argparse.Namespace) -> None:
    """Generate lessons.md entry."""
    runner = _load_runner()
    entry = runner.lessons_entry()
    print(entry)

    if args.append:
        path = Path(args.append)
        existing = path.read_text() if path.exists() else ""
        path.write_text(existing + "\n" + entry)
        print(f"\nAppended to {path}")


def cmd_list(args: argparse.Namespace) -> None:
    """List all registered skills."""
    for name, contract in sorted(SKILL_REGISTRY.items()):
        pipeline_in = ", ".join(i.field.value for i in contract.consumes if i.kind == InputKind.PIPELINE) or "-"
        ambient_in = ", ".join(i.field.value for i in contract.consumes if i.kind == InputKind.AMBIENT)
        produces = ", ".join(o.value for o in contract.produces) or "-"
        standalone = " [standalone]" if contract.is_standalone else ""
        iterative = " [iterative]" if contract.is_iterative else ""
        ambient_tag = f" [ambient: {ambient_in}]" if ambient_in else ""
        has_skill_md = " *" if contract.skill_path else ""
        print(
            f"  {contract.phase.value:15s}  {name:25s}  "
            f"IN: {pipeline_in:20s}  OUT: {produces}{standalone}{iterative}{ambient_tag}{has_skill_md}"
        )
    print(f"\n  Total: {len(SKILL_REGISTRY)} skills (* = has SKILL.md)")


def cmd_check(args: argparse.Namespace) -> None:
    """Validate a skill sequence."""
    violations = validate_sequence(args.skills)
    chain_issues = validate_contracts_chain(args.skills)

    if not violations and not chain_issues:
        print(f"Sequence valid: {' -> '.join(args.skills)}")
    else:
        if violations:
            print("Sequencing violations:")
            for v in violations:
                print(f"   {v}")
        if chain_issues:
            print("Contract chain issues:")
            for i in chain_issues:
                print(f"   {i}")
        sys.exit(1)


def cmd_resume(args: argparse.Namespace) -> None:
    """
    Resume context from previous sessions.

    Reads:
    - Latest pipeline-state JSON (if any)
    - tasks/lessons.md (if exists)
    - tasks/todo.md (if exists)
    - docs/PRD.md (if exists)

    Outputs a structured context brief for the current session.
    """
    from datetime import datetime, timezone

    project_root = Path(args.project_root).resolve() if args.project_root else _get_project_root()
    output_lines: list[str] = []

    output_lines.append("# Session Resume Brief")
    output_lines.append(f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    output_lines.append(f"Project root: {project_root}")
    output_lines.append("")

    # ── 1. Pipeline state ──────────────────────────────────────────────
    state_dir = project_root / "tools" / "skill-runtime" / "state"
    state_files = sorted(
        list(state_dir.glob("pipeline-state-*.json")) if state_dir.exists() else [],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    if state_files:
        latest = state_files[0]
        try:
            state = PipelineState.load(latest)
            output_lines.append("## Last Pipeline")
            output_lines.append(f"**ID**: {state.plan_id}")
            output_lines.append(f"**Scenario**: {state.scenario}")
            output_lines.append(f"**Priority**: {state.priority.value}")

            if state.stopped:
                output_lines.append(f"**Status**: Stopped — {state.stop_reason}")
            elif state.is_complete:
                output_lines.append("**Status**: Complete")
            else:
                output_lines.append(f"**Status**: In Progress — next: {state.current_step.skill_name if state.current_step else 'none'}")

            output_lines.append(f"**Progress**: {len(state.completed_steps)}/{len(state.steps)}")
            output_lines.append(f"**Findings**: {state.total_findings} total, {state.critical_findings} critical")
            output_lines.append("")

            for step in state.steps:
                icon = {"completed": "[V]", "failed": "[X]", "skipped": "[>>]",
                        "stopped_early": "[STOP]", "running": "[...]", "pending": "[--]"}.get(step.status.value, "[?]")
                output_lines.append(f"  {icon} {step.skill_name} — {step.status.value}")

            output_lines.append("")

            if not state.is_complete and not state.stopped:
                output_lines.append("**Suggested action**: Continue pipeline — run `python pipeline.py next`")
            elif state.stopped and state.priority == Priority.P0:
                remaining = [s.skill_name for s in state.steps if s.status.value == "stopped_early"]
                if remaining:
                    output_lines.append(f"**Suggested action**: P0 resolved. Schedule follow-up: `python pipeline.py start {' '.join(remaining)} --priority P2 --scenario 'follow-up from {state.plan_id}'`")
            elif state.is_complete and state.critical_findings > 0:
                output_lines.append(f"**Suggested action**: {state.critical_findings} critical findings need resolution.")
            output_lines.append("")
        except Exception as e:
            output_lines.append(f"Could not load pipeline state: {e}")
            output_lines.append("")
    else:
        output_lines.append("## Last Pipeline")
        output_lines.append("No pipeline state found.")
        output_lines.append("")

    # ── 2. Lessons ─────────────────────────────────────────────────────
    lessons_paths = [
        project_root / "tasks" / "lessons.md",
        project_root / "lessons.md",
    ]
    lessons_content = None
    for lp in lessons_paths:
        if lp.exists():
            lessons_content = lp.read_text().strip()
            break

    output_lines.append("## Lessons Learned")
    if lessons_content:
        entries = lessons_content.split("## ")
        recent = entries[-2:] if len(entries) > 2 else entries[1:] if len(entries) > 1 else entries
        for entry in recent:
            entry = entry.strip()
            if entry:
                lines = entry.split("\n")[:10]
                output_lines.append(f"### {lines[0]}")
                output_lines.extend(lines[1:])
                if len(entry.split("\n")) > 10:
                    output_lines.append("  (...truncated)")
                output_lines.append("")
    else:
        output_lines.append("No lessons.md found.")
    output_lines.append("")

    # ── 3. Todo ────────────────────────────────────────────────────────
    todo_paths = [
        project_root / "tasks" / "todo.md",
        project_root / "todo.md",
    ]
    todo_content = None
    for tp in todo_paths:
        if tp.exists():
            todo_content = tp.read_text().strip()
            break

    output_lines.append("## Open Tasks")
    if todo_content:
        unchecked = [line for line in todo_content.split("\n") if line.strip().startswith("- [ ]")]
        checked = [line for line in todo_content.split("\n") if line.strip().startswith("- [x]")]
        if unchecked:
            output_lines.append(f"**Open**: {len(unchecked)} | **Done**: {len(checked)}")
            for item in unchecked[:15]:
                output_lines.append(item)
            if len(unchecked) > 15:
                output_lines.append(f"  ...and {len(unchecked) - 15} more")
        else:
            output_lines.append("All tasks complete!")
    else:
        output_lines.append("No todo.md found.")
    output_lines.append("")

    # ── 4. PRD context ─────────────────────────────────────────────────
    prd_path = project_root / "docs" / "PRD.md"
    if prd_path.exists():
        output_lines.append("## Project Context (docs/PRD.md)")
        content = prd_path.read_text().strip()
        lines = content.split("\n")[:20]
        output_lines.extend(lines)
        if len(content.split("\n")) > 20:
            output_lines.append("  (...truncated, see docs/PRD.md for full context)")
        output_lines.append("")

    # ── 5. CLAUDE.md context ───────────────────────────────────────────
    claude_md = project_root / "CLAUDE.md"
    if claude_md.exists():
        output_lines.append("## Project Instructions (CLAUDE.md)")
        content = claude_md.read_text().strip()
        lines = content.split("\n")[:20]
        output_lines.extend(lines)
        if len(content.split("\n")) > 20:
            output_lines.append("  (...truncated, see CLAUDE.md for full context)")
        output_lines.append("")

    # ── Output ─────────────────────────────────────────────────────────
    brief = "\n".join(output_lines)
    print(brief)

    if args.save:
        Path(args.save).write_text(brief)
        print(f"\nSaved to {args.save}")


def _load_runner() -> PipelineRunner:
    """Load the most recent pipeline state."""
    runner = PipelineRunner.find_latest()
    if not runner:
        print("No pipeline state found. Run `python pipeline.py start` first.")
        sys.exit(1)
    return runner


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Skill Pipeline CLI — active orchestration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # plan
    p = sub.add_parser("plan", help="Validate a pipeline plan")
    p.add_argument("skills", nargs="+", help="Skill names in order")
    p.add_argument("--priority", default="P2", choices=["P0", "P1", "P2"])
    p.add_argument("--scenario", default="", help="Human-readable description")
    p.set_defaults(func=cmd_plan)

    # start
    p = sub.add_parser("start", help="Initialize pipeline")
    p.add_argument("skills", nargs="+", help="Skill names in order")
    p.add_argument("--priority", default="P2", choices=["P0", "P1", "P2"])
    p.add_argument("--scenario", default="", help="Human-readable description")
    p.set_defaults(func=cmd_start)

    # next
    p = sub.add_parser("next", help="Get next skill to execute")
    p.set_defaults(func=cmd_next)

    # complete
    p = sub.add_parser("complete", help="Record skill completion")
    p.add_argument("skill", help="Skill name that completed")
    p.add_argument("--output", help="Path to result JSON file")
    p.add_argument("--findings", help="Path to findings JSON file")
    p.add_argument("--notes", default="", help="Execution notes")
    p.set_defaults(func=cmd_complete)

    # skip
    p = sub.add_parser("skip", help="Skip a pending step")
    p.add_argument("skill", help="Skill name to skip")
    p.add_argument("--reason", default="", help="Why skipping")
    p.set_defaults(func=cmd_skip)

    # status
    p = sub.add_parser("status", help="Show pipeline status")
    p.set_defaults(func=cmd_status)

    # report
    p = sub.add_parser("report", help="Generate pipeline report")
    p.add_argument("--save", help="Save report to file")
    p.set_defaults(func=cmd_report)

    # lessons
    p = sub.add_parser("lessons", help="Generate lessons.md entry")
    p.add_argument("--append", help="Append to file (e.g. tasks/lessons.md)")
    p.set_defaults(func=cmd_lessons)

    # list
    p = sub.add_parser("list", help="List all registered skills")
    p.set_defaults(func=cmd_list)

    # check
    p = sub.add_parser("check", help="Validate a skill sequence")
    p.add_argument("skills", nargs="+", help="Skill names in order")
    p.set_defaults(func=cmd_check)

    # resume
    p = sub.add_parser("resume", help="Resume context from previous sessions")
    p.add_argument("--project-root", default=None, help="Project root directory")
    p.add_argument("--save", help="Save brief to file")
    p.set_defaults(func=cmd_resume)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
