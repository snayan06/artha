# Excalidraw Architecture Board Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the formal architecture infographic with a raw, developer-authored Excalidraw canvas while keeping Artha's trust boundaries accurate and the source editable.

**Architecture:** Author the scene with Excalidraw's programmatic skeleton API, convert it to native editable elements, and export the same scene through Excalidraw's official `exportToSvg` API. Keep generation tooling temporary so documentation artwork does not add runtime dependencies to Artha.

**Tech Stack:** Excalidraw 0.18.1, JavaScript, official SVG export API, JSON/XML validation, browser rendering

---

## File map

- Create `docs/assets/artha-architecture.excalidraw`: native editable scene.
- Replace `docs/assets/artha-architecture.svg`: official light-canvas export of that scene.
- Modify `README.md`: link the editable board below the embedded export.
- Modify `docs/artifacts/architecture/README.md`: record the maintained board source and export.
- Modify `docs/PROJECT-CHECKPOINT.md`, `docs/SPRINT-BOARD.md`, and `docs/TASKS.md`: replace stale AI release/CI wording with the verified merged and deployed state.

### Task 1: Build one native Excalidraw scene

- [ ] **Step 1: Create a temporary Excalidraw exporter outside the repository**

Use `@excalidraw/excalidraw@0.18.1` with a temporary Vite browser page. The page must call `convertToExcalidrawElements(scene, { regenerateIds: false })` and expose the native elements and `exportToSvg` result for collection.

- [ ] **Step 2: Author the raw developer canvas**

Use uneven sticky notes and free-positioned annotations for these exact concepts: natural-language capture, Gemini plus household context, unsaved draft, required human review, confirmed ledger truth, exact-text manual recovery, read-only Ask Artha, React/FastAPI/Supabase deployment, and no direct Gemini-to-ledger connection.

- [ ] **Step 3: Export both files from the same native scene**

Write the converted scene as `docs/assets/artha-architecture.excalidraw` and the official export as `docs/assets/artha-architecture.svg`, using a warm off-white background, embedded scene metadata and 28 px export padding.

- [ ] **Step 4: Validate source and export structure**

Run:

```bash
node -e 'const fs=require("fs"); const p="docs/assets/artha-architecture.excalidraw"; const x=JSON.parse(fs.readFileSync(p,"utf8")); if(x.type!=="excalidraw"||x.version!==2||!Array.isArray(x.elements)||x.elements.length<20) process.exit(1); console.log(x.elements.length)'
python3 -c 'import xml.etree.ElementTree as ET; ET.parse("docs/assets/artha-architecture.svg"); print("valid svg")'
```

Expected: at least 20 editable elements and `valid svg`.

- [ ] **Step 5: Commit the board files**

```bash
git add docs/assets/artha-architecture.excalidraw docs/assets/artha-architecture.svg
git commit -m "docs: replace architecture graphic with Excalidraw board"
```

### Task 2: Connect the editable artifact to the documentation

- [ ] **Step 1: Update README architecture copy**

Keep the embedded SVG and add one short link immediately below it: `Open the editable Excalidraw board.` Do not repeat the architecture explanation.

- [ ] **Step 2: Update the architecture artifact index**

Add the editable source and rendered export as the first two maintained sources in `docs/artifacts/architecture/README.md`.

- [ ] **Step 3: Check links and formatting**

Run:

```bash
python3 scripts/check_docs_links.py
git diff --check
```

Expected: both commands exit 0.

- [ ] **Step 4: Commit documentation links**

```bash
git add README.md docs/artifacts/architecture/README.md
git commit -m "docs: link editable architecture board"
```

### Task 3: Correct the stale release board

- [ ] **Step 1: Record verified release facts**

Update the three tracking documents to state: PR #20 is merged, main CI and CodeQL passed on merge commit `69e44a8`, both Vercel deployments succeeded, and authenticated production Gemini capture plus read-only assistant were manually verified with fictional data.

- [ ] **Step 2: Keep unverified gates open**

Do not close two-owner isolation, full-browser-close session persistence, final-domain encrypted restore, real-data privacy/log-redaction, forced provider-unavailable production acceptance, or a fresh hosted-evaluation rerun.

- [ ] **Step 3: Check status wording for contradictions**

Run:

```bash
rg -n "not deployed|Restore reliable GitHub Actions|Deploy the AI-primary candidate|Latest improvements are not deployed" docs/TASKS.md docs/SPRINT-BOARD.md docs/PROJECT-CHECKPOINT.md
git diff --check
```

Expected: the search finds no stale active-status claims and `git diff --check` exits 0.

- [ ] **Step 4: Commit the release evidence update**

```bash
git add docs/PROJECT-CHECKPOINT.md docs/SPRINT-BOARD.md docs/TASKS.md
git commit -m "docs: record deployed AI-primary release"
```

### Task 4: Visually verify and publish the documentation change

- [ ] **Step 1: Render the SVG on representative canvases**

Open the export at 736 px and 390 px against light and dark page backgrounds. Confirm no clipping, overlap, tiny unreadable labels, or horizontal overflow.

- [ ] **Step 2: Verify the complete repository**

Run:

```bash
make check
```

Expected: lint, type checks, web/API tests, build, SQL contracts and AI contract evaluations all pass.

- [ ] **Step 3: Inspect the final diff and branch state**

Run:

```bash
git diff origin/main...HEAD --check
git status --short
```

Expected: no whitespace errors and no uncommitted project changes.

- [ ] **Step 4: Push and open a documentation pull request**

Push `codex/release-evidence-v2`, open a PR summarizing the real Excalidraw replacement and corrected release status, then wait for CI before merge.
