---
name: implementation-review
description: Comprehensive implementation review using Playwright MCP for visual testing, followed by simplification cascades and code review
when_to_use: After implementing features, before creating PRs, or when reviewing significant codebase changes
version: 1.0.0
---

# Implementation Review

A comprehensive review process that combines visual testing, simplification analysis, and code review to ensure implementation quality before PR creation.

## Overview

This skill orchestrates a multi-phase review of implemented changes:

1. **Visual Testing** - Use MCP Docker Playwright to capture screenshots and verify UI changes
2. **Issue Detection** - Identify visual bugs, console errors, and functional problems
3. **Simplification Cascade** - Analyze for over-engineering and opportunities to reduce complexity
4. **Code Review** - Full code review against Elivro constitution standards
5. **Fix & Iterate** - Address identified issues and verify fixes

## Phase 1: Visual Testing with Playwright MCP

### Prerequisites

Ensure the development server is running:
```bash
npm run dev
```

### MCP Docker Playwright Tools

Use these browser tools to interact with the application:

**Navigation:**
```
mcp__MCP_DOCKER__browser_navigate - Navigate to a URL
mcp__MCP_DOCKER__browser_navigate_back - Go back
```

**Snapshots & Screenshots:**
```
mcp__MCP_DOCKER__browser_snapshot - Get accessibility snapshot (PREFERRED for actions)
mcp__MCP_DOCKER__browser_take_screenshot - Capture visual screenshot
```

**Interactions:**
```
mcp__MCP_DOCKER__browser_click - Click elements
mcp__MCP_DOCKER__browser_type - Type into fields
mcp__MCP_DOCKER__browser_fill_form - Fill multiple form fields
mcp__MCP_DOCKER__browser_select_option - Select dropdown options
```

**Debugging:**
```
mcp__MCP_DOCKER__browser_console_messages - View console logs/errors
mcp__MCP_DOCKER__browser_network_requests - View network activity
```

### Important: Docker URL Mapping

When accessing the dev server from MCP Docker Playwright, use:
- `http://host.docker.internal:3001` (NOT `localhost:3001`)

For authentication testing, use `/admin/login` (Payload admin) instead of `/login` (BankID).

### Visual Testing Workflow

1. **Navigate to the feature:**
   ```
   Use mcp__MCP_DOCKER__browser_navigate to http://host.docker.internal:3001/[feature-path]
   ```

2. **Wait for page load:**
   ```
   Use mcp__MCP_DOCKER__browser_wait_for for any dynamic content
   ```

3. **Capture initial state:**
   ```
   Use mcp__MCP_DOCKER__browser_take_screenshot for visual record
   Use mcp__MCP_DOCKER__browser_snapshot for accessibility tree
   ```

4. **Test interactions:**
   - Click buttons, fill forms, navigate between pages
   - Capture screenshots at each significant state change

5. **Check for errors:**
   ```
   Use mcp__MCP_DOCKER__browser_console_messages with onlyErrors: true
   ```

6. **Test responsive behavior:**
   ```
   Use mcp__MCP_DOCKER__browser_resize to test different viewport sizes
   ```

### Pages to Review

Based on git status, identify changed components and their routes:

| Changed File Pattern | Likely Routes to Test |
|---------------------|----------------------|
| `src/app/(app)/[feature]/*` | `/{feature}` |
| `src/components/[feature]/*` | Pages using that component |
| `src/actions/*` | Test forms/interactions using that action |

## Phase 2: Issue Detection

### Create Issue List

After visual testing, document issues found:

| Issue | Severity | Location | Description |
|-------|----------|----------|-------------|
| Visual bug | Critical/Important/Minor | URL or file:line | What's wrong |
| Console error | Critical/Important | URL | Error message |
| Functional problem | Critical/Important | Action/flow | What doesn't work |

### Severity Classification

- **Critical**: Blocks user, security issue, data loss risk
- **Important**: Poor UX, incorrect behavior, missing validation
- **Minor**: Visual polish, non-critical console warnings

## Phase 3: Simplification Cascade Analysis

After identifying functional issues, analyze for complexity:

### Checklist

1. **Multiple implementations of same concept?**
   - Search for similar patterns across the codebase
   - Look for repeated logic that could be abstracted

2. **Growing special case handling?**
   - Check for `if/else` chains that keep growing
   - Look for exception-based logic patterns

3. **Over-engineered for current needs?**
   - Features built for hypothetical future requirements
   - Complex abstractions for one-time operations

4. **Excessive configuration?**
   - Many options that could have sensible defaults
   - Configuration that's rarely changed

### Questions to Ask

- "What if these are all the same thing underneath?"
- "Can one insight eliminate multiple components?"
- "What's the minimum code needed for current requirements?"

### Document Cascade Opportunities

| Current State | Potential Simplification | Components Eliminated |
|---------------|-------------------------|----------------------|
| [What exists] | [Unified approach] | [What can be removed] |

## Phase 4: Code Review

### Review Against Constitution (v1.4.0)

**1. TDD Compliance (NON-NEGOTIABLE):**
- Are tests written BEFORE implementation code?
- Do tests initially fail (RED phase)?
- Does implementation use minimum code to pass (GREEN phase)?

**2. Payload-First Architecture:**
- All database operations use `getPayload({ config })` from `payload`?
- NO direct SQL queries (except complex analytics)?
- Using Payload auto-generated types?

**3. Type Safety:**
- NO `any` types without justification?
- All function parameters and returns explicitly typed?

**4. Security & OWASP:**
- Input validation present?
- No hardcoded secrets?
- XSS/SQL injection prevention?

**5. Code Quality:**
- Functions small and focused (single responsibility)?
- Complex logic documented?
- NO `eslint-disable`, `@ts-ignore`, `@ts-expect-error`, or `as any`?

### Git Range Review

```bash
# Get changed files
git diff --stat origin/develop..HEAD

# Review specific changes
git diff origin/develop..HEAD -- src/
```

### Forbidden Patterns Check

```bash
# Must all return 0 results
git diff origin/develop..HEAD | grep -c "eslint-disable"
git diff origin/develop..HEAD | grep -c "@ts-ignore"
git diff origin/develop..HEAD | grep -c "@ts-expect-error"
git diff origin/develop..HEAD | grep -c "as any"
```

## Phase 5: Fix & Iterate

### Priority Order

1. **Critical issues** - Fix immediately
2. **Important issues** - Fix before proceeding
3. **Simplification opportunities** - Implement if clear win
4. **Minor issues** - Note for later or fix if quick

### After Each Fix

1. Re-run visual tests to verify fix
2. Check no regressions introduced
3. Run automated checks:
   ```bash
   npm run check:quick  # Lint + type-check
   npm run test:unit    # Unit tests
   ```

### Final Verification

Before considering review complete:

1. All Critical/Important issues resolved
2. Simplification changes implemented (if any)
3. All tests passing
4. No forbidden patterns in code
5. Final screenshot comparison shows expected state

## Quick Reference: MCP Playwright Commands

```
# Navigation
browser_navigate(url) - Go to URL
browser_snapshot() - Get accessibility tree (best for finding elements)
browser_take_screenshot(filename) - Save visual screenshot

# Interactions
browser_click(element, ref) - Click element
browser_type(element, ref, text) - Type into field
browser_fill_form(fields) - Fill multiple fields

# Debugging
browser_console_messages() - Get console output
browser_console_messages(onlyErrors: true) - Get only errors

# Cleanup
browser_close() - Close browser session
```

## Output Template

After completing the review, provide:

```markdown
## Implementation Review Summary

### Visual Testing Results
- Pages tested: [list]
- Screenshots captured: [count]
- Console errors found: [count]

### Issues Found
#### Critical
[List or "None"]

#### Important
[List or "None"]

#### Minor
[List or "None"]

### Simplification Opportunities
[Cascades identified or "None - implementation is appropriately simple"]

### Code Review Assessment
- TDD Compliance: [Pass/Fail]
- Type Safety: [Pass/Fail]
- Forbidden Patterns: [0 found / X found]
- Constitution Compliance: [Pass/Needs fixes]

### Fixes Applied
[List of changes made during review]

### Final Status
**Ready for PR:** [Yes/No/After fixes]
**Reasoning:** [Brief assessment]
```
