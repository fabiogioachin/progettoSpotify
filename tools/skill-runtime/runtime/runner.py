"""
Pipeline Runner — manages skill execution, validation, and state persistence.

This is the active orchestration layer. Claude runs skills; the runner
validates contracts, manages state, and enforces guardrails.

Usage flow:
    1. runner.plan(["code-audit", "ops-reliability"], priority, scenario)
    2. runner.start()  → initializes state on disk
    3. runner.next()   → returns next skill contract + prepared context
    4. [Claude executes the skill]
    5. runner.complete(result)  → validates output, updates state, saves
    6. Repeat 3-5 until runner.is_complete
    7. runner.report() → structured summary + lessons.md entry
"""

from __future__ import annotations

import json
import time
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from runtime.contracts import (
    PipelineState,
    PipelineStep,
    SkillResult,
    Finding,
    Priority,
    Effort,
    StepStatus,
    OutputField,
    Severity,
    SkillPhase,
    InputKind,
    _get_project_root,
    _get_state_dir,
)
from skills.registry import (
    SKILL_REGISTRY,
    get_contract,
    validate_sequence,
    validate_contracts_chain,
    SEQUENCING_INVARIANTS,
)


# ---------------------------------------------------------------------------
# Effort estimation
# ---------------------------------------------------------------------------

def estimate_effort(skill_names: list[str]) -> Effort:
    """Estimate total effort for a pipeline based on skill contracts."""
    total_agents = 0
    for name in skill_names:
        c = get_contract(name)
        if c:
            rounds = c.max_rounds if c.is_iterative else 1
            total_agents += c.estimated_agents * rounds

    if total_agents < 5:
        return Effort.LOW
    elif total_agents < 13:
        return Effort.MED
    elif total_agents < 21:
        return Effort.HIGH
    elif total_agents < 31:
        return Effort.VERY_HIGH
    else:
        return Effort.CRITICAL


# ---------------------------------------------------------------------------
# Early stopping conditions
# ---------------------------------------------------------------------------

def should_stop_early(state: PipelineState) -> str | None:
    """
    Check if the pipeline should stop early.
    Returns reason string if yes, None if no.
    """
    # P0: stop after first skill completes (fix first, audit later)
    if state.priority == Priority.P0:
        completed = state.completed_steps
        if len(completed) >= 1:
            return "P0 fast path: first skill completed. Fix applied — schedule follow-up audit."

    # Critical findings threshold: >5 P0 findings = stop and address
    if state.critical_findings > 5:
        return (
            f"Critical findings threshold exceeded ({state.critical_findings} P0 findings). "
            f"Address existing findings before continuing."
        )

    return None


# ---------------------------------------------------------------------------
# Pipeline Runner
# ---------------------------------------------------------------------------

class PipelineRunner:
    """
    Manages a skill pipeline from plan to completion.

    The runner does NOT execute skills (Claude does). It:
    - Validates the plan (sequence, contracts, invariants)
    - Tracks state on disk
    - Validates outputs against contracts
    - Checks early stopping conditions
    - Generates reports and lessons
    """

    def __init__(self, state: PipelineState | None = None):
        self.state = state

    # ── Plan ──────────────────────────────────────────────────────────

    def plan(
        self,
        skill_names: list[str],
        priority: Priority = Priority.P2,
        scenario: str = "",
    ) -> dict[str, Any]:
        """
        Create and validate a pipeline plan.

        Returns a dict with the plan details and any validation issues.
        Does NOT start execution — call start() for that.
        """
        result: dict[str, Any] = {
            "valid": True,
            "skills": skill_names,
            "priority": priority.value,
            "scenario": scenario,
            "effort": estimate_effort(skill_names).value,
            "sequence_violations": [],
            "contract_issues": [],
            "unknown_skills": [],
            "warnings": [],
        }

        # Check unknown skills
        for name in skill_names:
            if name not in SKILL_REGISTRY:
                result["unknown_skills"].append(name)
                result["valid"] = False

        if result["unknown_skills"]:
            return result

        # Validate sequencing invariants
        violations = validate_sequence(skill_names)
        if violations:
            result["sequence_violations"] = violations
            result["valid"] = False

        # Validate contract chain (I/O compatibility)
        contract_issues = validate_contracts_chain(skill_names)
        if contract_issues:
            result["contract_issues"] = contract_issues
            result["warnings"].extend(contract_issues)

        # Effort warnings
        effort = estimate_effort(skill_names)
        if effort in (Effort.VERY_HIGH, Effort.CRITICAL):
            result["warnings"].append(
                f"Effort is {effort.value} — consider splitting across sessions "
                f"or reducing scope."
            )

        # P0 warnings
        if priority == Priority.P0 and len(skill_names) > 1:
            result["warnings"].append(
                f"P0 priority with {len(skill_names)} skills — fast path will stop "
                f"after the first skill. Remaining skills deferred."
            )

        # Standalone skill warnings
        for name in skill_names:
            c = get_contract(name)
            if c and c.is_standalone and len(skill_names) > 1:
                result["warnings"].append(
                    f"'{name}' is standalone — should not be sequenced with other skills."
                )

        # Show contracts
        result["contracts"] = []
        for name in skill_names:
            c = get_contract(name)
            if c:
                result["contracts"].append({
                    "name": c.name,
                    "phase": c.phase.value,
                    "consumes_pipeline": [i.field.value for i in c.consumes if i.kind == InputKind.PIPELINE],
                    "consumes_ambient": [
                        {"field": i.field.value, "desc": i.description}
                        for i in c.consumes if i.kind == InputKind.AMBIENT
                    ],
                    "consumes_optional": [o.value for o in c.consumes_optional],
                    "produces": [o.value for o in c.produces],
                    "estimated_agents": c.estimated_agents,
                    "max_rounds": c.max_rounds,
                    "iterative": c.is_iterative,
                    "skill_path": c.skill_path,
                })

        return result

    # ── Start ─────────────────────────────────────────────────────────

    def start(
        self,
        skill_names: list[str],
        priority: Priority = Priority.P2,
        scenario: str = "",
    ) -> PipelineState:
        """Initialize pipeline state and persist to disk."""
        plan_id = hashlib.sha256(
            f"{scenario}-{time.time()}".encode()
        ).hexdigest()[:8]

        steps = [
            PipelineStep(skill_name=name, order=i)
            for i, name in enumerate(skill_names)
        ]

        self.state = PipelineState(
            plan_id=plan_id,
            priority=priority,
            scenario=scenario,
            steps=steps,
        )
        self.state.save()
        return self.state

    # ── Next ──────────────────────────────────────────────────────────

    def next(self) -> dict[str, Any] | None:
        """
        Get the next skill to execute.

        Returns a dict with:
        - contract details
        - available inputs from previous skills
        - scope command to run
        - skill path to read

        Returns None if pipeline is complete or stopped.
        """
        if not self.state:
            raise RuntimeError("Pipeline not started. Call start() first.")

        if self.state.stopped or self.state.is_complete:
            return None

        # Check early stopping
        stop_reason = should_stop_early(self.state)
        if stop_reason:
            self.state.stop_early(stop_reason)
            return None

        step = self.state.current_step
        if not step:
            return None

        contract = get_contract(step.skill_name)
        if not contract:
            return None

        # Mark as running
        step.status = StepStatus.RUNNING
        step.started_at = time.time()
        self.state.save()

        # Resolve skill_path to absolute path
        project_root = _get_project_root()
        absolute_skill_path = str(project_root / contract.skill_path) if contract.skill_path else ""

        # Build context for Claude
        context: dict[str, Any] = {
            "step": step.order + 1,
            "total_steps": len(self.state.steps),
            "skill_name": contract.name,
            "description": contract.description,
            "phase": contract.phase.value,
            "skill_path": absolute_skill_path,
            "scope_command": contract.scope_command,
            "consumes": [si.field.value for si in contract.consumes],
            "produces": [o.value for o in contract.produces],
            "available_inputs": list(self.state.available_outputs),
            "max_rounds": contract.max_rounds,
            "is_iterative": contract.is_iterative,
            "priority": self.state.priority.value,
        }

        # Check input satisfaction (only pipeline inputs)
        missing = contract.validate_input(
            {OutputField(o) for o in self.state.available_outputs}
        )
        if missing:
            context["input_warnings"] = (
                f"Missing pipeline inputs: {missing}. "
                f"These must be produced by a previous skill in the chain."
            )

        # Show ambient inputs (informational)
        if contract.ambient_inputs:
            context["ambient_inputs"] = [
                {"field": ai.field.value, "description": ai.description}
                for ai in contract.ambient_inputs
            ]

        # Add accumulated findings summary for audit skills
        if contract.phase == SkillPhase.AUDIT:
            prev_findings = self._get_accumulated_findings()
            if prev_findings:
                context["previous_findings_summary"] = (
                    f"{len(prev_findings)} findings from previous skills. "
                    f"Critical: {sum(1 for f in prev_findings if f.get('severity') == 'P0')}. "
                    f"Use these for cross-referencing."
                )

        return context

    # ── Complete ──────────────────────────────────────────────────────

    def complete(self, result: SkillResult) -> dict[str, Any]:
        """
        Record skill completion, validate output, update state.

        Returns validation report.
        """
        if not self.state:
            raise RuntimeError("Pipeline not started.")

        step = self.state.current_step
        if not step or step.skill_name != result.skill_name:
            # Find the matching step
            step = None
            for s in self.state.steps:
                if s.skill_name == result.skill_name and s.status == StepStatus.RUNNING:
                    step = s
                    break
            if not step:
                raise ValueError(f"No running step for '{result.skill_name}'")

        contract = get_contract(step.skill_name)
        validation_report: dict[str, Any] = {
            "skill": step.skill_name,
            "status": "ok",
            "validation_errors": [],
            "warnings": [],
        }

        # Validate output against contract
        if contract and result.status == StepStatus.COMPLETED:
            errors = contract.validate_output(result)
            if errors:
                validation_report["validation_errors"] = errors
                validation_report["status"] = "warning"
                step.validation_errors = errors

        # Update step
        step.status = result.status
        step.result = result
        step.completed_at = time.time()
        result.duration_seconds = step.completed_at - step.started_at

        # Update available outputs
        if contract and result.status == StepStatus.COMPLETED:
            for output in contract.produces:
                self.state.available_outputs.add(output.value)

        # Count findings
        if "findings" in result.outputs and isinstance(result.outputs["findings"], list):
            findings = result.outputs["findings"]
            self.state.total_findings += len(findings)
            critical = sum(
                1 for f in findings
                if isinstance(f, dict) and f.get("severity") in ("P0", "P0_CRITICAL")
            )
            self.state.critical_findings += critical

            if critical > 0:
                validation_report["warnings"].append(
                    f"{critical} critical (P0) findings detected."
                )

        self.state.save()

        # Check early stopping after completion — auto-stop if triggered
        stop_reason = should_stop_early(self.state)
        if stop_reason:
            self.state.stop_early(stop_reason)
            validation_report["early_stop"] = stop_reason

        return validation_report

    # ── Skip ──────────────────────────────────────────────────────────

    def skip(self, skill_name: str, reason: str = "") -> None:
        """Skip a pending step."""
        if not self.state:
            raise RuntimeError("Pipeline not started.")

        for step in self.state.steps:
            if step.skill_name == skill_name and step.status in (StepStatus.PENDING, StepStatus.RUNNING):
                step.status = StepStatus.SKIPPED
                step.validation_errors = [f"Skipped: {reason}"] if reason else []
                break

        self.state.save()

    # ── Report ────────────────────────────────────────────────────────

    def report(self) -> str:
        """Generate structured pipeline report as markdown."""
        if not self.state:
            return "No pipeline state."

        lines = [
            f"# Pipeline Report: {self.state.scenario}",
            f"**ID**: {self.state.plan_id}",
            f"**Priority**: {self.state.priority.value}",
            f"**Status**: {'Stopped — ' + self.state.stop_reason if self.state.stopped else 'Complete' if self.state.is_complete else 'In Progress'}",
            "",
            "## Steps",
            "",
        ]

        for step in self.state.steps:
            icon = {
                StepStatus.COMPLETED: "V",
                StepStatus.FAILED: "X",
                StepStatus.SKIPPED: ">>",
                StepStatus.STOPPED_EARLY: "STOP",
                StepStatus.RUNNING: "...",
                StepStatus.PENDING: "--",
            }.get(step.status, "?")

            duration = ""
            if step.completed_at and step.started_at:
                dur = step.completed_at - step.started_at
                duration = f" ({dur:.0f}s)"

            lines.append(f"[{icon}] **{step.skill_name}** — {step.status.value}{duration}")

            if step.validation_errors:
                for err in step.validation_errors:
                    lines.append(f"   ! {err}")

            if step.result and step.result.notes:
                lines.append(f"   > {step.result.notes}")

            lines.append("")

        # Summary
        lines.extend([
            "## Summary",
            f"- Total findings: {self.state.total_findings}",
            f"- Critical findings: {self.state.critical_findings}",
            f"- Steps completed: {len(self.state.completed_steps)}/{len(self.state.steps)}",
            f"- Available outputs: {', '.join(sorted(self.state.available_outputs)) or 'none'}",
            "",
        ])

        if self.state.lessons:
            lines.append("## Lessons")
            for lesson in self.state.lessons:
                lines.append(f"- {lesson}")
            lines.append("")

        return "\n".join(lines)

    def lessons_entry(self) -> str:
        """Generate a lessons.md entry for post-pipeline feedback."""
        if not self.state:
            return ""

        now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        skills_run = [s.skill_name for s in self.state.completed_steps]

        # Find most impactful skill (most critical findings)
        most_impactful = ""
        max_critical = 0
        for step in self.state.completed_steps:
            if step.result and "findings" in step.result.outputs:
                findings = step.result.outputs["findings"]
                critical = sum(
                    1 for f in findings
                    if isinstance(f, dict) and f.get("severity") in ("P0", "P0_CRITICAL")
                )
                if critical > max_critical:
                    max_critical = critical
                    most_impactful = step.skill_name

        effort_actual = sum(
            1 for s in self.state.steps if s.status == StepStatus.COMPLETED
        )
        effort_estimated = estimate_effort(skills_run).value

        lines = [
            f"## Pipeline: {now} — {self.state.scenario}",
            "### What ran",
            f"Skills: {' -> '.join(skills_run)}",
            f"Priority: {self.state.priority.value}",
            f"Effort: {effort_actual} steps (estimated {effort_estimated})",
            "",
            "### Most impactful skill",
            f"{most_impactful or 'N/A'}: {max_critical} critical findings" if most_impactful else "No critical findings detected.",
            "",
            "### Sequencing issues",
            "- (to be filled by operator)",
            "",
            "### Anti-patterns violated",
            "- (to be filled by operator)",
            "",
            "### Signal matching accuracy",
            f"- Actual skills: {', '.join(skills_run)}",
            "- Delta: (to be filled by operator)",
            "",
        ]

        return "\n".join(lines)

    # ── Status ────────────────────────────────────────────────────────

    def status(self) -> dict[str, Any]:
        """Quick status summary."""
        if not self.state:
            return {"error": "No pipeline state."}

        return {
            "plan_id": self.state.plan_id,
            "scenario": self.state.scenario,
            "priority": self.state.priority.value,
            "stopped": self.state.stopped,
            "complete": self.state.is_complete,
            "current_step": self.state.current_step.skill_name if self.state.current_step else None,
            "progress": f"{len(self.state.completed_steps)}/{len(self.state.steps)}",
            "total_findings": self.state.total_findings,
            "critical_findings": self.state.critical_findings,
        }

    # ── Internals ─────────────────────────────────────────────────────

    def _get_accumulated_findings(self) -> list[dict]:
        """Collect all findings from completed steps."""
        findings = []
        if not self.state:
            return findings
        for step in self.state.completed_steps:
            if step.result and "findings" in step.result.outputs:
                for f in step.result.outputs["findings"]:
                    if isinstance(f, dict):
                        findings.append(f)
        return findings

    # ── Load ──────────────────────────────────────────────────────────

    @classmethod
    def load(cls, state_path: str | Path) -> PipelineRunner:
        """Resume a pipeline from saved state."""
        state = PipelineState.load(state_path)
        return cls(state=state)

    @classmethod
    def find_latest(cls) -> PipelineRunner | None:
        """Find and load the most recent pipeline state file."""
        state_dir = _get_state_dir()
        state_files = sorted(
            state_dir.glob("pipeline-state-*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if state_files:
            return cls.load(state_files[0])
        return None
