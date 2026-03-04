"""
Core types for the skill runtime.

SkillContract: declares what a skill consumes and produces.
SkillResult: validated output from a skill execution.
Finding: individual audit/analysis finding.
PipelineState: persistent state across skill executions.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def _get_project_root() -> Path:
    """Walk up from this file to find the git root (directory containing .git/)."""
    current = Path(__file__).resolve().parent
    for ancestor in [current] + list(current.parents):
        if (ancestor / ".git").exists():
            return ancestor
    # Fallback: assume tools/skill-runtime/runtime/ → 3 levels up
    return Path(__file__).resolve().parent.parent.parent.parent


def _get_state_dir() -> Path:
    """Return the state directory for pipeline state files."""
    state_dir = _get_project_root() / "tools" / "skill-runtime" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Priority(str, Enum):
    P0 = "P0"  # Incident — fast path
    P1 = "P1"  # Urgent — shortened pipeline
    P2 = "P2"  # Standard — full pipeline

class Effort(str, Enum):
    LOW = "LOW"           # <5 agent calls
    MED = "MED"           # 5-12
    HIGH = "HIGH"         # 12-20
    VERY_HIGH = "VERY_HIGH"  # 20-30
    CRITICAL = "CRITICAL"    # 30+

class Severity(str, Enum):
    P0_CRITICAL = "P0"
    P1_HIGH = "P1"
    P2_MEDIUM = "P2"
    P3_LOW = "P3"

class SkillPhase(str, Enum):
    PLANNING = "planning"
    IMPLEMENTATION = "implementation"
    AUDIT = "audit"
    LAUNCH = "launch"
    POST_LAUNCH = "post_launch"
    OUTREACH = "outreach"
    CONTENT = "content"
    AUTOMATION = "automation"

class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    STOPPED_EARLY = "stopped_early"


# ---------------------------------------------------------------------------
# Output field types — what a skill can produce
# ---------------------------------------------------------------------------

class OutputField(str, Enum):
    """Canonical output types that skills can produce and consume."""
    FINDINGS = "findings"           # List[Finding]
    REPORT = "report"               # Markdown string
    CODE_CHANGES = "code_changes"   # List of file paths modified
    DOCUMENTS = "documents"         # List of generated doc paths
    STRUCTURED_DATA = "structured_data"  # JSON-serializable dict
    METRICS = "metrics"             # Dict[str, float]
    ACTION_ITEMS = "action_items"   # List of {owner, task, deadline}
    URLS = "urls"                   # List of deployed URLs


class InputKind(str, Enum):
    """Distinguishes where a skill's input comes from."""
    PIPELINE = "pipeline"   # Must be produced by a previous skill in the chain
    AMBIENT = "ambient"     # Exists on disk / environment, not from pipeline


@dataclass(frozen=True)
class SkillInput:
    """A single input requirement with its source kind."""
    field: OutputField
    kind: InputKind = InputKind.PIPELINE
    description: str = ""  # e.g. "existing codebase on disk"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, SkillInput):
            return self.field == other.field and self.kind == other.kind
        return NotImplemented

    def __hash__(self) -> int:
        return hash((self.field, self.kind))


# ---------------------------------------------------------------------------
# Skill Contract
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SkillContract:
    """Typed I/O contract for a skill. Immutable after creation."""

    name: str
    phase: SkillPhase
    description: str

    # What this skill needs to start
    consumes: list[SkillInput]

    # What this skill produces (validated after execution)
    produces: list[OutputField]

    # Optional inputs (always pipeline-sourced)
    consumes_optional: list[OutputField] = field(default_factory=list)

    # Execution metadata
    estimated_agents: int = 1
    max_rounds: int = 1
    is_iterative: bool = False
    is_standalone: bool = False  # Never sequenced with others

    # File scoping command (bash)
    scope_command: str = ""

    # SKILL.md path relative to project root
    skill_path: str = ""

    @property
    def pipeline_inputs(self) -> list[OutputField]:
        """Inputs that must come from a previous skill."""
        return [i.field for i in self.consumes if i.kind == InputKind.PIPELINE]

    @property
    def ambient_inputs(self) -> list[SkillInput]:
        """Inputs that exist in the environment (disk, API, etc.)."""
        return [i for i in self.consumes if i.kind == InputKind.AMBIENT]

    def validate_input(self, available: set[OutputField]) -> list[str]:
        """Check if required PIPELINE inputs are available. Ambient inputs are skipped."""
        missing = []
        for req in self.consumes:
            if req.kind == InputKind.PIPELINE and req.field not in available:
                missing.append(req.field.value)
        return missing

    def validate_output(self, result: SkillResult) -> list[str]:
        """Check if the result contains all required output fields."""
        errors = []
        for req in self.produces:
            if req.value not in result.outputs:
                errors.append(f"Missing required output: {req.value}")
            elif result.outputs[req.value] is None:
                errors.append(f"Output '{req.value}' is None")
            elif isinstance(result.outputs[req.value], list) and len(result.outputs[req.value]) == 0:
                # Empty list is a warning, not an error — skill may legitimately find nothing
                pass
        return errors


# ---------------------------------------------------------------------------
# Finding (audit output)
# ---------------------------------------------------------------------------

@dataclass
class Finding:
    """Single finding from an audit skill."""

    id: str                     # e.g. "SEC-01", "BUG-03"
    severity: Severity
    title: str
    description: str
    file_path: str = ""
    line_range: str = ""        # e.g. "42-58"
    fix_applied: bool = False
    fix_description: str = ""
    skill_source: str = ""      # Which skill produced this

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Finding:
        data["severity"] = Severity(data["severity"])
        return cls(**data)


# ---------------------------------------------------------------------------
# Skill Result
# ---------------------------------------------------------------------------

@dataclass
class SkillResult:
    """Output from a skill execution. Validated against the contract."""

    skill_name: str
    status: StepStatus
    outputs: dict[str, Any] = field(default_factory=dict)
    # outputs keys are OutputField.value strings, values are the actual data

    duration_seconds: float = 0.0
    error_message: str = ""
    notes: str = ""  # Free-form notes from Claude about the execution

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SkillResult:
        data["status"] = StepStatus(data["status"])
        return cls(**data)

    @classmethod
    def from_json_file(cls, path: str | Path) -> SkillResult:
        with open(path) as f:
            return cls.from_dict(json.load(f))

    def save(self, path: str | Path) -> None:
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2, default=str)


# ---------------------------------------------------------------------------
# Pipeline Step (plan entry)
# ---------------------------------------------------------------------------

@dataclass
class PipelineStep:
    """A single step in the pipeline plan."""

    skill_name: str
    order: int
    status: StepStatus = StepStatus.PENDING
    result: SkillResult | None = None
    started_at: float = 0.0
    completed_at: float = 0.0
    validation_errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = {
            "skill_name": self.skill_name,
            "order": self.order,
            "status": self.status.value,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "validation_errors": self.validation_errors,
        }
        if self.result:
            d["result"] = self.result.to_dict()
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PipelineStep:
        result = None
        if "result" in data and data["result"]:
            result = SkillResult.from_dict(data["result"])
        return cls(
            skill_name=data["skill_name"],
            order=data["order"],
            status=StepStatus(data["status"]),
            result=result,
            started_at=data.get("started_at", 0.0),
            completed_at=data.get("completed_at", 0.0),
            validation_errors=data.get("validation_errors", []),
        )


# ---------------------------------------------------------------------------
# Pipeline State (persisted to disk)
# ---------------------------------------------------------------------------

@dataclass
class PipelineState:
    """
    Full pipeline state. Persisted to JSON after every mutation.
    This is the single source of truth for the pipeline's progress.
    """

    plan_id: str
    priority: Priority
    scenario: str  # Human-readable description
    steps: list[PipelineStep] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    # Accumulated outputs available for downstream skills
    available_outputs: set[str] = field(default_factory=set)

    # Early stopping
    stop_reason: str = ""
    stopped: bool = False

    # Lessons captured during execution
    lessons: list[str] = field(default_factory=list)

    # Metadata
    total_findings: int = 0
    critical_findings: int = 0

    @property
    def state_file(self) -> Path:
        return _get_state_dir() / f"pipeline-state-{self.plan_id}.json"

    @property
    def current_step(self) -> PipelineStep | None:
        for step in self.steps:
            if step.status in (StepStatus.PENDING, StepStatus.RUNNING):
                return step
        return None

    @property
    def is_complete(self) -> bool:
        return all(
            s.status in (StepStatus.COMPLETED, StepStatus.SKIPPED, StepStatus.STOPPED_EARLY)
            for s in self.steps
        )

    @property
    def completed_steps(self) -> list[PipelineStep]:
        return [s for s in self.steps if s.status == StepStatus.COMPLETED]

    def save(self) -> Path:
        """Persist state to disk. Called after every mutation."""
        self.updated_at = time.time()
        path = self.state_file
        data = {
            "plan_id": self.plan_id,
            "priority": self.priority.value,
            "scenario": self.scenario,
            "steps": [s.to_dict() for s in self.steps],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "available_outputs": list(self.available_outputs),
            "stop_reason": self.stop_reason,
            "stopped": self.stopped,
            "lessons": self.lessons,
            "total_findings": self.total_findings,
            "critical_findings": self.critical_findings,
        }
        path.write_text(json.dumps(data, indent=2, default=str))
        return path

    @classmethod
    def load(cls, path: str | Path) -> PipelineState:
        """Load state from disk."""
        data = json.loads(Path(path).read_text())
        state = cls(
            plan_id=data["plan_id"],
            priority=Priority(data["priority"]),
            scenario=data["scenario"],
            steps=[PipelineStep.from_dict(s) for s in data["steps"]],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            available_outputs=set(data.get("available_outputs", [])),
            stop_reason=data.get("stop_reason", ""),
            stopped=data.get("stopped", False),
            lessons=data.get("lessons", []),
            total_findings=data.get("total_findings", 0),
            critical_findings=data.get("critical_findings", 0),
        )
        return state

    def stop_early(self, reason: str) -> None:
        """Stop the pipeline. Remaining steps become STOPPED_EARLY."""
        self.stopped = True
        self.stop_reason = reason
        for step in self.steps:
            if step.status == StepStatus.PENDING:
                step.status = StepStatus.STOPPED_EARLY
        self.save()
