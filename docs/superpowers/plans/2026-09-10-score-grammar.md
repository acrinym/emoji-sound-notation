# Beadtrain 6 Score Grammar Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform ESN from a flat event timeline into a notation-first multi-track score composer with sections, independent musical context, polyphony, chords, 432 Hz tuning, and real-browser cat-heavy qualification.

**Architecture:** Add an isolated ESN/2 score domain beside ESN/1, with deterministic migration and adapters into existing render/playback/interchange layers. The browser gains the same score-domain logic and evolves the existing editor into tracks/sections while preserving realization separation and legacy project loading.

**Tech Stack:** Python 3.11+ standard library, dependency-free browser JavaScript/HTML/CSS, Web Audio, JSON Schema 2020-12, unittest, Node test runner, Playwright/Edge for customer qualification.

---

## Chunk 1: Score grammar core

### Task 1: ESN/2 schema, validation, migration, and harmony

**Files:**
- Create: `docs/esn-2.schema.json`
- Create: `docs/ESN-2.md`
- Create: `src/esn/score.py`
- Create: `tests/test_score.py`
- Modify: `src/esn/model.py`

- [ ] Write failing tests for factory defaults, track/section validation, independent context, chord expansion, and ESN/1 migration.
- [ ] Run `python -m unittest tests.test_score -v` and verify failures are attributable to missing ESN/2 code.
- [ ] Implement `score.py` with canonical ESN/2 validation, context helpers, chord interval expansion, flattening adapters, and migration.
- [ ] Replace implicit 440-based Hz conversion with tuning-aware helpers whose default reference is A4=432 Hz.
- [ ] Add schema/docs and run the score tests green.
- [ ] Commit the score-domain unit.

### Task 2: Adapt rendering, playback, cue, and MIDI surfaces

**Files:**
- Modify: `src/esn/playback.py`
- Modify: `src/esn/interchange.py`
- Modify: `src/esn/render.py`
- Modify: `src/esn/cli.py`
- Modify: `tests/test_playback.py`
- Modify: `tests/test_interchange.py`
- Modify: `tests/test_visual.py`

- [ ] Add failing ESN/2 regression tests proving independent track tempo, cat-chord playback, and loss-aware interchange.
- [ ] Preserve all ESN/1 deterministic receipts byte-for-byte.
- [ ] Adapt render/playback through score-domain flattening rather than teaching each subsystem the entire ESN/2 schema.
- [ ] Derive seconds per flattened object from its track musical context and A4 tuning reference.
- [ ] Export ESN/2 MIDI at accurate clock timing while reporting track-local meter/tempo semantics that MIDI cannot faithfully encode.
- [ ] Run legacy and ESN/2 rendering/interchange tests green.
- [ ] Commit the adapter unit.

## Chunk 2: Browser composer

### Task 3: Browser ESN/2 domain

**Files:**
- Create: `web/score-domain.js`
- Modify: `tests/web_domain.test.js`

- [ ] Write failing Node tests for validation, migration, track splitting, chord expansion/explosion, context inheritance, and 432 tuning.
- [ ] Implement browser score-domain helpers matching Python behavior.
- [ ] Verify Node domain tests green and cross-runtime fixtures agree.
- [ ] Commit the browser domain unit.

### Task 4: Multi-track notation editor and chord workflow

**Files:**
- Modify: `web/index.html`
- Modify: `web/editor.js`
- Modify: `web/styles.css`
- Modify: `tests/test_web_editor.py`

- [ ] Add failing wiring/regression tests for track controls, section split controls, chord controls, and ESN/2 save/open.
- [ ] Replace the single scene timeline rendering with track rows and explicit section bands while keeping the existing editor shell and realization controls.
- [ ] Add score defaults plus selected-track tempo, meter, key/scale, and tuning controls; factory defaults are 96 BPM, 4/4, C major, A4=432.
- [ ] Add track creation, explicit section splitting/source assignment, note/event placement, chord creation, chord selection, and chord explosion.
- [ ] Preserve drag X for musical placement and drag Y for semitone pitch/root transposition with the existing click-vs-drag regression intact.
- [ ] Preserve sound-pack/local-sample realization precedence while resolving section source identities.
- [ ] Run Python wiring tests and Node behavior tests green.
- [ ] Commit the editor product unit.

## Chunk 3: Product proof and closure

### Task 5: Cat counterpoint reference product and docs

**Files:**
- Create: `examples/cat-counterpoint.esn.json`
- Modify: `README.md`
- Modify: `docs/CONSUMER-AUDIT.md`
- Modify: `pyproject.toml`
- Modify: `src/esn/__init__.py`
- Modify: `.github/workflows/ci.yml`

- [ ] Add an ESN/2 reference composition with a pitched cat chord, independent cat notes, piano, weather, and at least one split section.
- [ ] Make the browser load the ESN/2 cat composition as its bundled example.
- [ ] Bump the package to 0.6.0 and document ESN/2 plus migration behavior.
- [ ] Extend CI with ESN/2 validation, migration, rendering, browser-domain, and deterministic regression checks.
- [ ] Run the complete local Python/Node/CLI qualification and `git diff --check`.
- [ ] Commit the product/documentation unit.

### Task 6: Beads, real-browser qualification, screenshots, and PR

**Files:**
- Create: `.beads/beadtrain_6_score_grammar.beadtrain`
- Modify: `.beads/interactions.jsonl` through `bd`
- Modify: `docs/CONSUMER-AUDIT.md`

- [ ] Create a Beadtrain 6 epic and cars covering score domain, adapters, browser composer, product proof, and exact-head qualification.
- [ ] Validate all Beadtrain manifests against the canonical Beadtrains validator.
- [ ] Launch the real local product and drive Microsoft Edge with Playwright through a customer journey: add/select cats, create/explode a cat chord, split a track, assign a source, edit track context, save/open, preview, and export.
- [ ] Capture screenshots from the real browser showing the cat-heavy score and a selected cat chord/track context.
- [ ] Record browser assertions, console/page/request errors, responsive checks, and deterministic receipts in the consumer audit.
- [ ] Run the entire local qualification again on the final product tree.
- [ ] Push the branch, open a PR, and wait for independent GitHub CI/review on the exact pushed head.
- [ ] Close qualification Beads only after exact-head GitHub qualification, commit closure metadata, and requalify the closure head.
- [ ] Do not merge Train 6 without a fresh Justin merge whistle.
