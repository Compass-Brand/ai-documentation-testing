# Legacy Document Project Router

<critical>This workflow is retained for backward compatibility.</critical>
<critical>Primary docs migration workflow is now: {delegated_workflow}</critical>
<critical>Communicate all responses in {communication_language}</critical>

## Behavior

1. Inform the user that `document-project` is now an alias for docs initialization in the Compass docs framework.
2. Load and execute `{delegated_workflow}`.
3. Return output paths from the delegated workflow, especially under `{docs_root}`.

## Compatibility Note

The original brownfield scan assets in this folder remain available for internal extraction support, but command routing should use `init-docs` semantics.
