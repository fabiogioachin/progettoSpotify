---
name: ux-audit
description: Single-pass 4-agent UX/UI review covering usability, visual consistency, information architecture, and domain fitness. Use for frontend reviews, pre-launch UX checks, or after major UI changes. Always run AFTER platform-architecture, BEFORE code-audit.
---

# UX Audit Skill

Single-pass 4-agent UX review. Evaluates usability, visual quality, navigation, and domain-specific appropriateness.

## When to Use

- Frontend UX/UI review
- After major UI redesign
- Before launch (UX readiness check)
- After adding new pages or components
- When users report confusion or friction

## Agents

| Agent | Focus | Finding Prefix |
|-------|-------|---------------|
| **Usability** | Navigation flow, error states, loading states, empty states, responsive behavior, form UX | USAB-xx |
| **Visual** | Color consistency, typography, spacing, alignment, contrast, dark theme quality | VIS-xx |
| **Information Architecture** | Page hierarchy, route structure, sidebar nav, breadcrumbs, content grouping | IA-xx |
| **Domain Expert** | Does the UI make sense for the domain? Missing features? Misleading data? | DOM-xx |

## Scoping

Pass only frontend files — pages, components, layout, styles:

```bash
git ls-files -- "frontend/src/pages/*" "frontend/src/components/*" "frontend/src/styles/*" "frontend/src/App.*" | head -60
```

## Subagent Prompt Template

```
You are a {ROLE} reviewing the UX/UI of a {STACK} web application.

PROJECT CONTEXT:
{describe the app, its users, its purpose}

YOUR TASK:
Review from a {PERSPECTIVE} perspective. Think like a real user.
Ask: "Would I understand this page in 5 seconds? Can I complete my task without confusion?"

OUTPUT FORMAT (strict):
For each finding:
- **ID**: {PREFIX}-{number} (e.g., USAB-01, VIS-03)
- **Impact**: CRITICAL (blocks user task) | HIGH (significant friction) | MEDIUM (minor confusion) | LOW (polish)
- **Page/Component**: which page or component
- **Issue**: one-line description
- **Recommendation**: concrete UX fix (screenshot reference, component change, copy change)

Sort by Impact. End with: "{N} findings: {x} CRITICAL, {y} HIGH, {z} MEDIUM, {w} LOW"
```

## Protocol

1. Launch 4 agents in parallel (single round only)
2. Merge & deduplicate findings
3. Fix CRITICAL and HIGH findings immediately
4. Present MEDIUM/LOW to user for prioritization
5. **No re-audit** — single pass is sufficient for UX

## Domain-Specific Notes (Spotify Analytics)

The Domain Expert agent should evaluate:
- Do music analytics terms make sense to non-technical users?
- Are Spotify-specific concepts explained (time ranges, popularity score)?
- Is the Italian localization consistent across all pages?
- Do fallback states explain WHY data is missing (deprecated API, no history)?
- Are the 7 pages (Dashboard, Discovery, Taste Evolution, Temporal, Artist Network, Playlist Analytics, Playlist Compare) logically organized in the sidebar?

## Output Format

```
## UX Audit Results

### CRITICAL ({count})
[blocks user task — fix immediately]

### HIGH ({count})
[significant friction — fix before launch]

### MEDIUM ({count})
[minor confusion — schedule fix]

### LOW ({count})
[polish — nice to have]

### Applied Fixes
- {component}: {description of fix}
```
