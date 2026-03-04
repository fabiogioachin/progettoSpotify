"""
Skill Registry — maps skill names to typed SkillContracts.

Contains all 34+ skills from the skill-orchestrator across 8 categories:
Planning (3), Implementation (13), Audit (6), Launch (1), Post-Launch (1),
Outreach (3), Content (2), Automation & Creative (5).

Plus 4 project-specific skills for this Spotify analytics project.
"""

from __future__ import annotations

from runtime.contracts import (
    SkillContract,
    SkillPhase,
    OutputField as O,
    SkillInput,
    InputKind,
)

# Shortcuts for readability
def _pipe(field: O, desc: str = "") -> SkillInput:
    """Input that must come from a previous skill in the pipeline."""
    return SkillInput(field=field, kind=InputKind.PIPELINE, description=desc)

def _ambient(field: O, desc: str = "") -> SkillInput:
    """Input that exists in the environment (codebase on disk, API, etc.)."""
    return SkillInput(field=field, kind=InputKind.AMBIENT, description=desc)


# Commonly used ambient inputs
CODEBASE = _ambient(O.CODE_CHANGES, "existing codebase on disk")

# Skill docs base path (relative to project root)
_SKILL_DOCS = "tools/skill-runtime/skill-docs"

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

SKILL_REGISTRY: dict[str, SkillContract] = {}


def _reg(c: SkillContract) -> None:
    SKILL_REGISTRY[c.name] = c


# ── Planning ──────────────────────────────────────────────────────────────

_reg(SkillContract(
    name="product-definition",
    phase=SkillPhase.PLANNING,
    description="PRD, personas, user stories, roadmap from user brief",
    consumes=[],
    produces=[O.DOCUMENTS, O.STRUCTURED_DATA],
    skill_path="",
))

_reg(SkillContract(
    name="business-model",
    phase=SkillPhase.PLANNING,
    description="Lean Canvas, pricing model, unit economics",
    consumes=[],
    consumes_optional=[O.DOCUMENTS],
    produces=[O.DOCUMENTS, O.STRUCTURED_DATA],
    skill_path="",
))

_reg(SkillContract(
    name="system-design",
    phase=SkillPhase.PLANNING,
    description="ADRs, schema, API spec, system diagram",
    consumes=[],
    consumes_optional=[O.DOCUMENTS],
    produces=[O.DOCUMENTS, O.STRUCTURED_DATA],
    skill_path="",
))

# ── Implementation ────────────────────────────────────────────────────────

_reg(SkillContract(
    name="project-scaffold",
    phase=SkillPhase.IMPLEMENTATION,
    description="Runnable project skeleton from ADRs/tech stack",
    consumes=[],
    consumes_optional=[O.DOCUMENTS],
    produces=[O.CODE_CHANGES, O.DOCUMENTS],
    skill_path="",
))

_reg(SkillContract(
    name="oauth-patterns",
    phase=SkillPhase.IMPLEMENTATION,
    description="Auth flow implementation patterns (Spotify OAuth2 PKCE)",
    consumes=[CODEBASE],
    produces=[O.CODE_CHANGES],
    skill_path=f"{_SKILL_DOCS}/oauth-patterns/SKILL.md",
    scope_command='git ls-files -- "*/auth*" "*/middleware*" "*.env*" "*session*" "*token*" | head -30',
))

_reg(SkillContract(
    name="chart-dashboard",
    phase=SkillPhase.IMPLEMENTATION,
    description="Dashboard components and data visualization (Recharts + custom SVG)",
    consumes=[CODEBASE],
    produces=[O.CODE_CHANGES],
    skill_path=f"{_SKILL_DOCS}/chart-dashboard/SKILL.md",
    scope_command='git ls-files -- "*/chart*" "*/dashboard*" "*/viz*" "*/graph*" "*theme*" "*Chart*" "*Radar*" | head -30',
))

_reg(SkillContract(
    name="saas-patterns",
    phase=SkillPhase.IMPLEMENTATION,
    description="SaaS building blocks: Stripe, multi-tenancy, etc.",
    consumes=[CODEBASE],
    produces=[O.CODE_CHANGES],
    skill_path="",
))

_reg(SkillContract(
    name="infra-patterns",
    phase=SkillPhase.IMPLEMENTATION,
    description="IaC, Docker, K8s, deployment patterns",
    consumes=[CODEBASE],
    produces=[O.CODE_CHANGES, O.DOCUMENTS],
    skill_path="",
    scope_command='git ls-files -- "Dockerfile*" "docker-compose*" ".github/workflows/*" "scripts/deploy*" | head -20',
))

_reg(SkillContract(
    name="testing-strategy",
    phase=SkillPhase.IMPLEMENTATION,
    description="Test config, test suites, testing pyramid",
    consumes=[CODEBASE],
    produces=[O.CODE_CHANGES, O.DOCUMENTS],
    skill_path="",
    scope_command='git ls-files -- "*/test*" "*/__tests__/*" "*.test.*" "jest.config*" "playwright.config*" "pytest*" "conftest*" | head -40',
))

_reg(SkillContract(
    name="data-pipeline",
    phase=SkillPhase.IMPLEMENTATION,
    description="ETL scripts, data cleaning, API ingestion",
    consumes=[],
    produces=[O.CODE_CHANGES, O.STRUCTURED_DATA],
    skill_path="",
))

_reg(SkillContract(
    name="financial-analysis",
    phase=SkillPhase.IMPLEMENTATION,
    description="Portfolio analytics, risk metrics, valuation",
    consumes=[],
    consumes_optional=[O.STRUCTURED_DATA],
    produces=[O.STRUCTURED_DATA, O.REPORT, O.METRICS],
    skill_path="",
))

_reg(SkillContract(
    name="research-synthesis",
    phase=SkillPhase.IMPLEMENTATION,
    description="Multi-source research synthesis and evidence maps",
    consumes=[],
    produces=[O.REPORT, O.STRUCTURED_DATA],
    skill_path="",
))

_reg(SkillContract(
    name="webapp-testing",
    phase=SkillPhase.IMPLEMENTATION,
    description="Browser-based app testing with Playwright",
    consumes=[CODEBASE],
    consumes_optional=[O.DOCUMENTS],
    produces=[O.FINDINGS, O.STRUCTURED_DATA],
    skill_path=f"{_SKILL_DOCS}/webapp-testing/SKILL.md",
))

_reg(SkillContract(
    name="website-builder",
    phase=SkillPhase.IMPLEMENTATION,
    description="Landing page build + Netlify deploy",
    consumes=[],
    produces=[O.CODE_CHANGES, O.URLS],
    skill_path="",
))

_reg(SkillContract(
    name="frontend-design",
    phase=SkillPhase.IMPLEMENTATION,
    description="High-quality UI components and pages",
    consumes=[CODEBASE],
    produces=[O.CODE_CHANGES],
    skill_path=f"{_SKILL_DOCS}/frontend-design/SKILL.md",
    scope_command='git ls-files -- "*/components/*" "*/pages/*" "*/styles/*" "*.css" "tailwind.config*" | head -40',
))

_reg(SkillContract(
    name="mcp-builder",
    phase=SkillPhase.IMPLEMENTATION,
    description="Build MCP server integrations (Python/TS)",
    consumes=[],
    consumes_optional=[O.DOCUMENTS],
    produces=[O.CODE_CHANGES, O.DOCUMENTS],
    skill_path="",
))

_reg(SkillContract(
    name="api-documentation",
    phase=SkillPhase.IMPLEMENTATION,
    description="OpenAPI/Swagger generation, changelog, versioning docs",
    consumes=[CODEBASE],
    produces=[O.DOCUMENTS, O.STRUCTURED_DATA],
    skill_path="",
    scope_command='git ls-files -- "*/routes/*" "*/routers/*" "*/api/*" "openapi*" "swagger*" | head -30',
))

_reg(SkillContract(
    name="observability-setup",
    phase=SkillPhase.IMPLEMENTATION,
    description="Install logging, tracing (OTel), error tracking (Sentry), alerting",
    consumes=[CODEBASE],
    produces=[O.CODE_CHANGES, O.DOCUMENTS],
    skill_path="",
    scope_command='git ls-files -- "*logger*" "*sentry*" "*otel*" "*tracing*" "*monitoring*" | head -20',
))

_reg(SkillContract(
    name="ci-cd-builder",
    phase=SkillPhase.IMPLEMENTATION,
    description="Build CI/CD pipelines from scratch (GitHub Actions, GitLab CI)",
    consumes=[CODEBASE],
    produces=[O.CODE_CHANGES, O.DOCUMENTS],
    skill_path="",
    scope_command='git ls-files -- ".github/workflows/*" ".gitlab-ci.yml" "Makefile" "Dockerfile*" | head -20',
))

_reg(SkillContract(
    name="db-migration",
    phase=SkillPhase.IMPLEMENTATION,
    description="Safe production schema migrations, rollback, backfill patterns",
    consumes=[CODEBASE],
    produces=[O.CODE_CHANGES, O.DOCUMENTS],
    skill_path="",
    scope_command='git ls-files -- "*/migrations/*" "*/prisma/*" "*/drizzle/*" "*/alembic/*" | head -30',
))

# ── Audit ─────────────────────────────────────────────────────────────────

_reg(SkillContract(
    name="platform-architecture",
    phase=SkillPhase.AUDIT,
    description="Architectural review: extensibility, coupling, API, DB",
    consumes=[CODEBASE],
    produces=[O.FINDINGS, O.REPORT],
    estimated_agents=4,
    skill_path=f"{_SKILL_DOCS}/platform-architecture/SKILL.md",
    scope_command='git ls-files -- "*/routers/*" "*/routes/*" "*/controllers/*" "*/models/*" "*/schemas/*" "*/services/*" | head -60',
))

_reg(SkillContract(
    name="ux-audit",
    phase=SkillPhase.AUDIT,
    description="UX/UI review: usability, visual, IA, domain",
    consumes=[CODEBASE],
    consumes_optional=[O.FINDINGS],
    produces=[O.FINDINGS, O.REPORT],
    estimated_agents=4,
    skill_path=f"{_SKILL_DOCS}/ux-audit/SKILL.md",
    scope_command='git ls-files -- "*/pages/*" "*/views/*" "*/components/*" "*/layout/*" "*App.*" | head -60',
))

_reg(SkillContract(
    name="code-audit",
    phase=SkillPhase.AUDIT,
    description="Code quality: bugs, perf, security, maintainability",
    consumes=[CODEBASE],
    consumes_optional=[O.FINDINGS],
    produces=[O.FINDINGS, O.REPORT, O.CODE_CHANGES],
    estimated_agents=4,
    max_rounds=4,
    is_iterative=True,
    skill_path=f"{_SKILL_DOCS}/code-audit/SKILL.md",
    scope_command='git ls-files -- "backend/app/" "frontend/src/" | head -100',
))

_reg(SkillContract(
    name="ops-reliability",
    phase=SkillPhase.AUDIT,
    description="DevOps, observability, reliability audit",
    consumes=[CODEBASE],
    produces=[O.FINDINGS, O.REPORT],
    estimated_agents=3,
    skill_path=f"{_SKILL_DOCS}/ops-reliability/SKILL.md",
    scope_command='git ls-files -- "Dockerfile*" "docker-compose*" ".github/workflows/*" "*.env*" | head -20',
))

_reg(SkillContract(
    name="dx-knowledge",
    phase=SkillPhase.AUDIT,
    description="Developer experience, docs, dependency health",
    consumes=[CODEBASE],
    produces=[O.FINDINGS, O.REPORT, O.DOCUMENTS],
    estimated_agents=3,
    skill_path=f"{_SKILL_DOCS}/dx-knowledge/SKILL.md",
    scope_command='git ls-files -- "README*" "CHANGELOG*" "CONTRIBUTING*" "docs/*" "package.json" "requirements.txt" | head -20',
))

_reg(SkillContract(
    name="security-compliance",
    phase=SkillPhase.AUDIT,
    description="Security posture + compliance (GDPR, SOC2, OWASP)",
    consumes=[CODEBASE],
    produces=[O.FINDINGS, O.REPORT],
    estimated_agents=3,
    skill_path="",
    scope_command='git ls-files -- "*.env*" "*/auth/*" "*cors*" "*rate*limit*" "*token*" | head -30',
))

# ── Launch & Post-Launch ──────────────────────────────────────────────────

_reg(SkillContract(
    name="launch-checklist",
    phase=SkillPhase.LAUNCH,
    description="Pre-launch readiness: SEO, analytics, onboarding, legal",
    consumes=[CODEBASE],
    consumes_optional=[O.FINDINGS],
    produces=[O.REPORT, O.STRUCTURED_DATA],
    skill_path="",
))

_reg(SkillContract(
    name="growth-analytics",
    phase=SkillPhase.POST_LAUNCH,
    description="Funnel analysis, A/B testing, retention, metrics",
    consumes=[],
    consumes_optional=[O.STRUCTURED_DATA, O.METRICS],
    produces=[O.REPORT, O.STRUCTURED_DATA, O.METRICS],
    skill_path="",
))

# ── Outreach ──────────────────────────────────────────────────────────────

_reg(SkillContract(
    name="lead-scraper",
    phase=SkillPhase.OUTREACH,
    description="LinkedIn scrape + email enrichment",
    consumes=[],
    produces=[O.STRUCTURED_DATA],
    skill_path="",
))

_reg(SkillContract(
    name="cold-email-campaigns",
    phase=SkillPhase.OUTREACH,
    description="Instantly campaign creation",
    consumes=[_pipe(O.STRUCTURED_DATA, "enriched lead list from lead-scraper")],
    produces=[O.STRUCTURED_DATA, O.REPORT],
    skill_path="",
))

_reg(SkillContract(
    name="follow-up-nurture",
    phase=SkillPhase.OUTREACH,
    description="Context-aware follow-up emails",
    consumes=[_pipe(O.STRUCTURED_DATA, "lead DB + campaign history")],
    produces=[O.REPORT],
    skill_path="",
))

# ── Content & Ops ─────────────────────────────────────────────────────────

_reg(SkillContract(
    name="content-repurposer",
    phase=SkillPhase.CONTENT,
    description="Transcript -> tweet thread, LinkedIn, newsletter",
    consumes=[],
    produces=[O.DOCUMENTS],
    skill_path="",
))

_reg(SkillContract(
    name="meeting-notes",
    phase=SkillPhase.CONTENT,
    description="Transcript -> action items with owners and deadlines",
    consumes=[],
    produces=[O.ACTION_ITEMS, O.STRUCTURED_DATA],
    is_standalone=True,
    skill_path="",
))

_reg(SkillContract(
    name="inbox-cleaner",
    phase=SkillPhase.AUTOMATION,
    description="Gmail triage — identify important, mark rest as read",
    consumes=[],
    produces=[O.REPORT],
    is_standalone=True,
    skill_path="",
))

_reg(SkillContract(
    name="invoice-extractor",
    phase=SkillPhase.AUTOMATION,
    description="PDF invoice -> structured JSON",
    consumes=[],
    produces=[O.STRUCTURED_DATA],
    is_standalone=True,
    skill_path="",
))

# ── Automation & Creative ─────────────────────────────────────────────────

_reg(SkillContract(
    name="amazon-shopping",
    phase=SkillPhase.AUTOMATION,
    description="Amazon product research + purchase",
    consumes=[],
    produces=[O.STRUCTURED_DATA],
    is_standalone=True,
    skill_path="",
))

_reg(SkillContract(
    name="wework-booking",
    phase=SkillPhase.AUTOMATION,
    description="Bulk WeWork desk booking",
    consumes=[],
    produces=[O.STRUCTURED_DATA],
    is_standalone=True,
    skill_path="",
))

_reg(SkillContract(
    name="thumbnail-generator",
    phase=SkillPhase.AUTOMATION,
    description="YouTube thumbnail generation with face swap",
    consumes=[],
    produces=[O.DOCUMENTS],
    is_standalone=True,
    skill_path="",
))


# ══════════════════════════════════════════════════════════════════════════
# Project-Specific Skills — Spotify Listening Intelligence
# ══════════════════════════════════════════════════════════════════════════

_reg(SkillContract(
    name="spotify-api-audit",
    phase=SkillPhase.AUDIT,
    description="Audit Spotify API usage: deprecated endpoints, rate limits, error handling, token management",
    consumes=[CODEBASE],
    produces=[O.FINDINGS, O.REPORT],
    estimated_agents=2,
    skill_path=f"{_SKILL_DOCS}/spotify-api-audit/SKILL.md",
    scope_command='git ls-files -- "backend/app/services/*" "backend/app/routers/*" "backend/app/utils/*" | head -30',
))

_reg(SkillContract(
    name="async-service-review",
    phase=SkillPhase.AUDIT,
    description="Review asyncio patterns: gather error handling, Semaphore, race conditions, SpotifyAuthError propagation",
    consumes=[CODEBASE],
    produces=[O.FINDINGS, O.REPORT],
    estimated_agents=2,
    skill_path=f"{_SKILL_DOCS}/async-service-review/SKILL.md",
    scope_command='git ls-files -- "backend/app/services/*" "backend/app/routers/*" | head -30',
))

_reg(SkillContract(
    name="frontend-component-review",
    phase=SkillPhase.AUDIT,
    description="Review React components: hooks, Tailwind, Italian localization, custom SVG, accessibility",
    consumes=[CODEBASE],
    produces=[O.FINDINGS, O.REPORT],
    estimated_agents=2,
    skill_path=f"{_SKILL_DOCS}/frontend-component-review/SKILL.md",
    scope_command='git ls-files -- "frontend/src/pages/*" "frontend/src/components/*" "frontend/src/hooks/*" "frontend/src/styles/*" | head -40',
))

_reg(SkillContract(
    name="data-integrity-check",
    phase=SkillPhase.AUDIT,
    description="Verify no hardcoded fake data, proper fallback flags, API response transparency",
    consumes=[CODEBASE],
    produces=[O.FINDINGS, O.REPORT],
    estimated_agents=1,
    skill_path=f"{_SKILL_DOCS}/data-integrity-check/SKILL.md",
    scope_command='git ls-files -- "backend/app/services/*" "backend/app/models/*" "backend/app/schemas.py" | head -20',
))


# ---------------------------------------------------------------------------
# Sequencing invariants (hard rules)
# ---------------------------------------------------------------------------

SEQUENCING_INVARIANTS: list[tuple[str, str, str]] = [
    # (before, after, reason)
    # Cross-phase
    ("product-definition", "business-model", "PRD feeds business model"),
    ("product-definition", "system-design", "PRD feeds architecture"),
    # Implementation
    ("project-scaffold", "oauth-patterns", "scaffold provides codebase"),
    ("project-scaffold", "saas-patterns", "scaffold provides codebase"),
    ("project-scaffold", "infra-patterns", "scaffold provides codebase"),
    ("project-scaffold", "chart-dashboard", "scaffold provides codebase"),
    ("project-scaffold", "testing-strategy", "scaffold provides codebase"),
    ("oauth-patterns", "chart-dashboard", "auth before authenticated viz"),
    ("testing-strategy", "code-audit", "test first, audit test quality"),
    ("frontend-design", "ux-audit", "design first, audit after"),
    ("frontend-design", "chart-dashboard", "design system before viz"),
    ("oauth-patterns", "mcp-builder", "auth before MCP if both selected"),
    # Audit ordering
    ("platform-architecture", "ux-audit", "architecture before UX"),
    ("platform-architecture", "code-audit", "architecture before code"),
    ("ux-audit", "code-audit", "UX findings create code tasks"),
    # Cross-phase
    ("testing-strategy", "webapp-testing", "strategy defines what to test"),
    ("website-builder", "ux-audit", "build before audit"),
    # Outreach
    ("lead-scraper", "cold-email-campaigns", "need leads before emailing"),
    ("cold-email-campaigns", "follow-up-nurture", "campaign before follow-up"),
    # Launch
    ("code-audit", "launch-checklist", "audit before launch"),
    ("security-compliance", "launch-checklist", "security before launch"),
    ("launch-checklist", "growth-analytics", "launch before post-launch"),
    # New skills
    ("project-scaffold", "ci-cd-builder", "scaffold provides codebase for CI"),
    ("project-scaffold", "api-documentation", "scaffold provides routes for docs"),
    ("project-scaffold", "observability-setup", "scaffold provides app for instrumentation"),
    ("project-scaffold", "db-migration", "scaffold provides schema for migrations"),
    ("db-migration", "code-audit", "migrations before code audit if both selected"),
    ("api-documentation", "dx-knowledge", "API docs before DX audit if both selected"),
    ("observability-setup", "ops-reliability", "setup observability before auditing it"),
    ("ci-cd-builder", "ops-reliability", "build CI before auditing it"),
    # Project-specific
    ("spotify-api-audit", "async-service-review", "API patterns before async patterns"),
    ("async-service-review", "data-integrity-check", "fix async issues before checking data flow"),
    ("data-integrity-check", "code-audit", "data integrity before general code audit"),
    ("frontend-component-review", "ux-audit", "component review before full UX audit"),
]


def get_contract(name: str) -> SkillContract | None:
    """Look up a skill contract by name."""
    return SKILL_REGISTRY.get(name)


def validate_sequence(skill_names: list[str]) -> list[str]:
    """
    Validate a proposed skill sequence against invariants.
    Returns list of violations (empty = valid).
    """
    violations = []
    name_to_index = {name: i for i, name in enumerate(skill_names)}

    for before, after, reason in SEQUENCING_INVARIANTS:
        if before in name_to_index and after in name_to_index:
            if name_to_index[before] > name_to_index[after]:
                violations.append(
                    f"Invariant violated: '{before}' must come before '{after}' ({reason})"
                )
    return violations


def validate_contracts_chain(skill_names: list[str]) -> list[str]:
    """
    Validate that the output of each skill satisfies the PIPELINE input of the next.
    Ambient inputs (codebase on disk, APIs) are not checked — they exist independently.
    Returns list of issues (empty = valid).
    """
    issues = []
    available: set[O] = set()

    for name in skill_names:
        contract = get_contract(name)
        if contract is None:
            issues.append(f"Unknown skill: '{name}'")
            continue

        missing = contract.validate_input(available)
        if missing:
            issues.append(
                f"'{name}' requires pipeline inputs {missing} but previous skills don't produce them. "
                f"Available: {[o.value for o in available] if available else 'nothing'}"
            )

        # Add this skill's outputs to available set
        available.update(contract.produces)

    return issues
