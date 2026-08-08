# Excalidraw architecture board design

**Date:** 2026-08-08  
**Status:** proposed for review

## Objective

Replace the current polished dark architecture infographic with a genuine Excalidraw board that feels like a product and engineering team mapped Artha together on a whiteboard. It must remain technically accurate, but should be understandable before it is detailed.

## Chosen approach

Create an editable `.excalidraw` source file and export its light-canvas SVG for the README.

This is preferred over:

- restyling the existing SVG, which would still be an imitation rather than an editable board;
- Mermaid, which is maintainable but looks like generated documentation rather than collaborative thinking;
- a bitmap screenshot, which would not be editable and would lose sharpness when zoomed.

## Board structure

The board uses three loose horizontal zones rather than a dense grid.

### 1. Capture to ledger truth

The main left-to-right story is:

`Write naturally` → `Gemini interprets with household context` → `Review the draft` → `Confirm` → `Ledger updated`

The review and confirmation checkpoint is visually emphasized. A handwritten note says: **AI understands. You decide.**

### 2. Safe recovery and assistant

Two smaller branches sit below the main flow:

- If AI is unavailable or unsure: keep the original sentence, open the manual form, and save nothing.
- Ask Artha: database facts become a safe answer card; the assistant is read-only and cannot write to the ledger.

### 3. Production boundary

A compact footer strip shows:

`React PWA / Vercel` → `FastAPI / Vercel` → `Supabase Postgres + RLS`

FastAPI also calls Gemini. A crossed-out direct arrow and short note make it clear that Gemini never connects directly to the ledger.

## Visual direction

- warm off-white Excalidraw canvas;
- Excalidraw's handwritten typography;
- rough, imperfect strokes and curved arrows;
- pale green, blue, yellow, and coral sticky-note fills;
- dark ink instead of a dark background;
- generous whitespace and no decorative container around the entire board;
- short phrases only, with deeper implementation detail left in the architecture docs.

## Deliverables

- `docs/assets/artha-architecture.excalidraw` — editable source;
- `docs/assets/artha-architecture.svg` — README export;
- README architecture caption/alt text updated only if needed for clarity;
- architecture artifact guide updated to point to both source and export.

## Acceptance checks

- the `.excalidraw` file opens as valid editable Excalidraw JSON;
- the SVG is a real export of the editable board, not a separately drawn approximation;
- the whole story is readable at normal README width;
- the primary flow remains understandable at 390 px without horizontal overflow;
- the board remains legible on both light and dark GitHub themes because it carries its own light canvas;
- no labels are clipped and arrows do not cover text;
- the diagram preserves the review-before-save, read-only assistant, RLS, and no-direct-AI-ledger boundaries.
