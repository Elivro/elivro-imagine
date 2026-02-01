---
name: changelog-generator
description: Use when creating customer-facing release notes from git commits between two versions/tags - analyzes commit history, categorizes changes by importance, generates markdown changelog with screenshot recommendations for visual features
---

# Changelog Generator

This skill transforms technical git commits into polished, user-friendly changelogs that your customers and users will actually understand and appreciate.

## When to Use This Skill

- Preparing release notes for a new version
- Creating weekly or monthly product update summaries
- Documenting changes for customers
- Writing changelog entries for app store submissions
- Generating update notifications
- Creating internal release documentation
- Maintaining a public changelog/product updates page

## Workflow

### Step 1: Gather Commit Data

**Run the helper script first** to extract all commit data efficiently:

```bash
python .claude/skills/changelog-generator/get_commits.py
```

Examples:
```bash
# On a release branch - auto-detects and compares against previous tag
python .claude/skills/changelog-generator/get_commits.py
# → On release/v0.6.0, compares v0.5.0..release/v0.6.0

# Single version - auto-finds previous minor/major (skips patches)
python .claude/skills/changelog-generator/get_commits.py v0.5.0
# → Automatically compares against v0.4.0 (not v0.4.1, v0.4.2, etc.)

# Explicit range between two versions
python .claude/skills/changelog-generator/get_commits.py v0.4.0 v0.5.0

# See available tags (when not on a release branch)
python .claude/skills/changelog-generator/get_commits.py
```

The script:
- **Auto-excludes internal changes**: Admin UI, migrations, tests, scripts, CI, etc.
- **Pre-categorizes commits**: Features, fixes, improvements
- **Shows only user-facing changes**: Filters out refactoring, docs, internal paths
- **Smart version detection**: Single arg finds previous minor/major automatically

### Step 2: Analyze and Transform

With the commit data from the script, Claude will:

1. **Filter User-Facing Changes**: Exclude internal commits (refactoring, test updates, CI changes) unless they affect users
2. **Categorize by Importance**: Group into Features, Improvements, Fixes, Breaking Changes, Security
3. **Translate Technical → User-Friendly**: Convert developer language to customer language
4. **Identify Visual Features**: Flag changes that would benefit from screenshots
5. **Apply Consistent Formatting**: Use the project's changelog style

### What to EXCLUDE from changelog descriptions

Even if a commit is included, **never mention** these in the changelog text:

- **Admin/System UI changes**: Payload admin, system-admin pages, superadmin features
- **Backend internals**: Database migrations, collections, hooks, access control
- **API changes**: Internal API endpoints, webhooks (unless public-facing)
- **Developer tooling**: Scripts, CI/CD, tests, linting, type generation
- **Infrastructure**: Monitoring, logging, error tracking setup

**Example**: If a commit says "Add user profile page and update admin dashboard", only write about the user profile page. The admin dashboard change is irrelevant to end users.

### Step 3: Generate Changelog

Output format:

```markdown
# [Version] - [Date]

## [Feature Name]

[1-2 sentence description]

---

## Övrigt

- **[Minor feature]** — [brief description]
```

**DO NOT include** screenshot recommendation tables or internal notes in the output file.

## Example Session

**User**: "Create changelog" (while on release/v1.5.0 branch)

**Claude**:
1. Runs `python .claude/skills/changelog-generator/get_commits.py`
2. Script auto-detects release branch `release/v1.5.0`, compares against `v1.4.0`
3. Analyzes the output and generates:

```markdown
# Elivro v1.5.0 — Teamarbete och snabbare navigering

## Team Workspaces

Du kan nu skapa separata arbetsytor för olika projekt. Bjud in teammedlemmar och kontrollera vem som ser vad.

---

## Tangentbordsgenvägar

Tryck `?` var som helst för att se alla genvägar. Navigera snabbare utan att röra musen.

---

## Övrigt

- **Snabbare synk** — Filer synkas nu 2x snabbare mellan enheter
- **Bättre sök** — Sökning inkluderar nu filinnehåll, inte bara titlar

---

- Fixade problem där stora bilder (>10MB) inte kunde laddas upp
- Löste tidszonsproblem i schemalagda inlägg
```

## Important

**DO NOT commit or push** - only generate the changelog file. The user will review and commit manually.

## Tips

- Always run from the git repository root
- Review the generated changelog before publishing
- Add screenshots for visual features before release
- Check that breaking changes are clearly marked
- Consider your audience (technical vs non-technical users)

## Related Use Cases

- Creating GitHub release notes
- Writing app store update descriptions
- Generating email updates for users
- Creating social media announcement posts
