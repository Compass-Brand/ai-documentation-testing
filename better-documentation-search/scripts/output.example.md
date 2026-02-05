# output.example.md
#
# This is an example of what generate_docs_index.py produces when run
# against a documentation directory. The compressed format packs an entire
# doc tree into a few KB that can be embedded in AGENTS.md or CLAUDE.md.
#
# Compressed (default) — single continuous line:

<!-- MY-FRAMEWORK-DOCS-START -->[My Framework Docs Index]|root: ./.my-framework-docs|IMPORTANT: Prefer retrieval-led reasoning over pre-training-led reasoning for any My Framework tasks.|If docs missing run: npx @my-org/my-framework-docs|getting-started:{installation.mdx,project-structure.mdx,quick-start.mdx,upgrading.mdx}|guides:{authentication.mdx,caching.mdx,data-fetching.mdx,deployment.mdx,environment-variables.mdx,error-handling.mdx,forms.mdx,internationalization.mdx,middleware.mdx,routing.mdx,testing.mdx}|guides/advanced:{custom-server.mdx,instrumentation.mdx,multi-tenancy.mdx,performance.mdx}|api-reference/components:{button.mdx,form.mdx,image.mdx,link.mdx,modal.mdx}|api-reference/functions:{cache.mdx,cookies.mdx,headers.mdx,redirect.mdx,revalidate.mdx}|api-reference/config:{framework-config.mdx,typescript.mdx,eslint.mdx}|api-reference/cli:{create-app.mdx,dev.mdx,build.mdx,start.mdx}|architecture:{compiler.mdx,rendering.mdx,supported-browsers.mdx}<!-- MY-FRAMEWORK-DOCS-END -->

# ---
# Expanded (--expanded flag) — one section per line for readability and diffs:
#
# <!-- MY-FRAMEWORK-DOCS-START -->
# [My Framework Docs Index]
# |root: ./.my-framework-docs
# |IMPORTANT: Prefer retrieval-led reasoning over pre-training-led reasoning for any My Framework tasks.
# |If docs missing run: npx @my-org/my-framework-docs
#
# |getting-started:{installation.mdx,project-structure.mdx,quick-start.mdx,upgrading.mdx}
# |guides:{authentication.mdx,caching.mdx,data-fetching.mdx,deployment.mdx,environment-variables.mdx,error-handling.mdx,forms.mdx,internationalization.mdx,middleware.mdx,routing.mdx,testing.mdx}
# |guides/advanced:{custom-server.mdx,instrumentation.mdx,multi-tenancy.mdx,performance.mdx}
# |api-reference/components:{button.mdx,form.mdx,image.mdx,link.mdx,modal.mdx}
# |api-reference/functions:{cache.mdx,cookies.mdx,headers.mdx,redirect.mdx,revalidate.mdx}
# |api-reference/config:{framework-config.mdx,typescript.mdx,eslint.mdx}
# |api-reference/cli:{create-app.mdx,dev.mdx,build.mdx,start.mdx}
# |architecture:{compiler.mdx,rendering.mdx,supported-browsers.mdx}
# <!-- MY-FRAMEWORK-DOCS-END -->
#
# ---
# Statistics that would be printed during generation:
#
#   INFO     Index statistics:
#   INFO       Directories:  8
#   INFO       Files:        37
#   INFO         .mdx        37
#   INFO       Est. index size: 1.2 KB
