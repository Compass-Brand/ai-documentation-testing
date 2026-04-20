---
name: ingest-whitepapers
description: 'Ingest external whitepapers into a condensed digest for downstream BMAD workflows. Use when the user has placed markdown whitepapers in planning/roadmap/whitepapers/ and wants them incorporated into the analysis phase.'
---

# Ingest Whitepapers Workflow

**Goal:** Summarize external whitepapers into a single digest that downstream workflows can discover and consume efficiently.

**Your Role:** You are a research analyst. Read each whitepaper, extract the signal, and produce a structured digest. Do not editorialize — preserve the author's intent.

## CONFIGURATION

Load config from `{project-root}/_bmad/bmm/module.yaml` and resolve:
- `planning_roadmap`
- `date` as a system-generated value (`YYYY-MM-DD`)

The whitepapers directory is `{planning_roadmap}/whitepapers/`.
The digest output is `{planning_roadmap}/whitepapers/whitepapers-digest.md`.

## EXECUTION

1. Check if `{planning_roadmap}/whitepapers/` exists. If it does not exist or contains no `.md` files (excluding `whitepapers-digest.md` itself), report "No whitepapers found" and return.

2. List all `.md` files in the directory (excluding `whitepapers-digest.md`). Report the count to the user:
   "Found {{count}} whitepaper(s) in `planning/roadmap/whitepapers/`. Ingesting now."

3. For each whitepaper, read the full content and extract:
   - **Key ideas**: the core concepts, proposals, or innovations described
   - **Requirements or goals mentioned**: anything that reads like a requirement, success criterion, or project goal
   - **Technical constraints or preferences**: technology choices, architectural patterns, scale expectations, or limitations
   - **Decisions or recommendations**: explicit recommendations the author makes

4. After processing all whitepapers, identify **cross-cutting themes** — ideas, requirements, or constraints that appear in more than one whitepaper. Note which documents each theme appears in.

5. Generate `{planning_roadmap}/whitepapers/whitepapers-digest.md` with this structure:

   ```
   # Whitepapers Digest

   **Generated:** {{date}}
   **Source:** planning/roadmap/whitepapers/
   **Documents ingested:** {{count}}

   ## Cross-Cutting Themes

   {{for each theme that appears in 2+ documents}}
   - **{{theme}}**: {{description}} (appears in: {{doc-a.md}}, {{doc-b.md}})
   {{end}}
   {{if no cross-cutting themes: "No cross-cutting themes detected across documents."}}

   ## Per-Document Summaries

   ### {{filename}} — "{{title or first heading}}"

   **Key ideas:**
   - {{idea}}

   **Requirements or goals mentioned:**
   - {{requirement}}

   **Technical constraints or preferences:**
   - {{constraint}}

   **Decisions or recommendations:**
   - {{recommendation}}

   {{repeat for each whitepaper}}
   ```

6. Report completion:
   "Digest generated at `planning/roadmap/whitepapers/whitepapers-digest.md` with {{count}} document(s) summarized. Downstream workflows (product brief, PRD) will discover this automatically."

## OUTPUT RULES

- The digest replaces any previous digest — it is regenerated from all whitepapers each time.
- Preserve the author's intent in summaries. Do not add analysis or recommendations beyond what the whitepaper states.
- If a whitepaper has no content for a category (e.g., no technical constraints), omit that category header for that document rather than writing "None."
- Keep summaries concise — each per-document section should be 100-200 words, not a full reproduction.
- Do not modify the original whitepaper files.
