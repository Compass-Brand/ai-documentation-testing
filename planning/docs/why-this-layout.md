# Why This Layout Exists

This document explains why planning is organized under `framework/` with `current`, `previous`, `lessons`, and `roadmap`.

## Brownfield Continuity Problem

BMAD can generate strong first-pass artifacts, but brownfield teams often struggle with continuity after initial cycles:

- Current architecture context is fragmented.
- Prior decisions are hard to trace.
- New phases overwrite active folders without clear history.
- Learning from prior phases is inconsistent.

## Design Response

The framework separates planning by intent and time horizon:

- `current/`: active work only.
- `previous/`: historical phase snapshots.
- `lessons/`: reusable guidance extracted from history.
- `roadmap/`: cross-phase direction and backlog evolution.

This reduces ambiguity and makes transitions between phases explicit.

## Why `roadmap/archive/` Is Separate

Roadmap archives are not phase snapshots. They capture superseded cross-phase materials. Keeping them separate from `previous/` avoids mixing timeline-level artifacts with phase-level execution artifacts.

## Decision Principles

1. One source of truth per concern.
2. Explicit lifecycle transitions.
3. Stable paths for automation and agent prompts.
4. Low cognitive overhead for contributors.

## Tradeoffs

- More folders means more navigation overhead.
- Teams must maintain naming discipline.
- Closeout requires process rigor.

These tradeoffs are intentional to gain traceability, repeatability, and safer multi-cycle planning.
