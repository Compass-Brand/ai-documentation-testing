"""Tests for Bug #178: CompositeVariant must apply ALL axes, not just one.

Currently all 47+ variants default to PipelineRole.PRIMARY, so
CompositeVariant picks only the lowest-axis variant (format) and
silently discards the other 9 axes.  Taguchi screening results are
meaningless for those 9 factors.

The fix: variants declare correct pipeline roles via category-based
inference, and the base class provides smart pre_render/post_render
defaults for PRE_RENDER/POST_RENDER-classified variants.
"""

from __future__ import annotations

from datetime import UTC, datetime

from agent_evals.variants.base import IndexVariant, PipelineRole, VariantMetadata
from agent_evals.variants.composite import CompositeVariant
from agent_index.models import DocFile, DocTree

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_doc_tree() -> DocTree:
    """Create a 4-file doc tree for testing."""
    files: dict[str, DocFile] = {}
    specs = [
        ("api/auth.md", "API", "required", "JWT authentication"),
        ("api/cache.md", "API", "recommended", "Response caching"),
        ("guides/setup.md", "Guides", "required", "Getting started"),
        ("guides/deploy.md", "Guides", "reference", "Deployment guide"),
    ]
    for rel_path, section, tier, content in specs:
        files[rel_path] = DocFile(
            rel_path=rel_path,
            content=content,
            size_bytes=len(content),
            token_count=50,
            tier=tier,
            section=section,
        )
    return DocTree(
        files=files,
        scanned_at=datetime(2026, 1, 1, tzinfo=UTC),
        source="/test",
        total_tokens=200,
    )


class _CategoryStub(IndexVariant):
    """Stub variant with configurable category and marker output."""

    def __init__(self, name: str, axis: int, category: str) -> None:
        self._name = name
        self._axis = axis
        self._category = category

    def metadata(self) -> VariantMetadata:
        return VariantMetadata(
            name=self._name,
            axis=self._axis,
            category=self._category,
            description=f"Stub {self._category}",
            token_estimate=100,
        )

    def render(self, doc_tree: DocTree) -> str:
        lines = [f"[{self._category}:{self._name}]"]
        for p in sorted(doc_tree.files):
            lines.append(f"- {p}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tests: Category-based pipeline role inference
# ---------------------------------------------------------------------------


class TestCategoryPipelineRole:
    """Variants should infer pipeline_role from their category."""

    def test_format_category_is_primary(self):
        v = _CategoryStub("fmt", 3, "format")
        assert v.pipeline_role() == PipelineRole.PRIMARY

    def test_scale_category_is_pre_render(self):
        v = _CategoryStub("s50", 6, "scale")
        assert v.pipeline_role() == PipelineRole.PRE_RENDER

    def test_noise_category_is_post_render(self):
        v = _CategoryStub("n50", 7, "noise")
        assert v.pipeline_role() == PipelineRole.POST_RENDER

    def test_position_category_is_post_render(self):
        v = _CategoryStub("bluf", 4, "position")
        assert v.pipeline_role() == PipelineRole.POST_RENDER

    def test_temporal_category_is_post_render(self):
        v = _CategoryStub("tmp", 10, "temporal")
        assert v.pipeline_role() == PipelineRole.POST_RENDER

    def test_xref_category_is_post_render(self):
        v = _CategoryStub("xr", 9, "xref")
        assert v.pipeline_role() == PipelineRole.POST_RENDER

    def test_metadata_category_is_post_render(self):
        v = _CategoryStub("meta", 5, "metadata")
        assert v.pipeline_role() == PipelineRole.POST_RENDER

    def test_transform_category_is_post_render(self):
        v = _CategoryStub("xform", 8, "transform")
        assert v.pipeline_role() == PipelineRole.POST_RENDER

    def test_structure_category_is_post_render(self):
        v = _CategoryStub("flat", 1, "structure")
        assert v.pipeline_role() == PipelineRole.POST_RENDER

    def test_granularity_category_is_post_render(self):
        v = _CategoryStub("file", 2, "granularity")
        assert v.pipeline_role() == PipelineRole.POST_RENDER

    def test_unknown_category_defaults_to_primary(self):
        v = _CategoryStub("custom", 13, "my_custom")
        assert v.pipeline_role() == PipelineRole.PRIMARY


# ---------------------------------------------------------------------------
# Tests: CompositeVariant applies all axes
# ---------------------------------------------------------------------------


class TestCompositeAppliesAllAxes:
    """CompositeVariant must not silently discard non-primary axes."""

    def test_post_render_axes_contribute_to_output(self):
        """POST_RENDER axes should appear in the composite output."""
        doc_tree = _make_doc_tree()
        fmt = _CategoryStub("format-yaml", 3, "format")
        temporal = _CategoryStub("temporal-modified", 10, "temporal")
        xref = _CategoryStub("xref-light", 9, "xref")

        composite = CompositeVariant(components={
            3: fmt, 9: xref, 10: temporal,
        })
        output = composite.render(doc_tree)

        # Primary output present
        assert "[format:format-yaml]" in output
        # POST_RENDER axes contribute
        assert "temporal" in output.lower()
        assert "xref" in output.lower()

    def test_pre_render_scale_filters_tree(self):
        """Scale PRE_RENDER should filter the tree for the primary renderer."""
        doc_tree = _make_doc_tree()

        class ScaleStub(IndexVariant):
            """Renders only first 2 files."""
            def metadata(self) -> VariantMetadata:
                return VariantMetadata(
                    name="scale-2", axis=6, category="scale",
                    description="2 files", token_estimate=50,
                )

            def render(self, doc_tree: DocTree) -> str:
                paths = sorted(doc_tree.files)[:2]
                return "\n".join(f"- {p}" for p in paths)

            def pre_render(self, doc_tree: DocTree) -> DocTree:
                paths = sorted(doc_tree.files)[:2]
                filtered = {k: doc_tree.files[k] for k in paths}
                return doc_tree.model_copy(update={"files": filtered})

        fmt = _CategoryStub("format-yaml", 3, "format")
        scale = ScaleStub()

        composite = CompositeVariant(components={3: fmt, 6: scale})
        output = composite.render(doc_tree)

        # Only 2 files should appear in the primary render
        assert "api/auth.md" in output
        assert "api/cache.md" in output
        assert "guides/setup.md" not in output
        assert "guides/deploy.md" not in output

    def test_post_render_axes_all_contribute(self):
        """All POST_RENDER axes should appear in the composite output."""
        doc_tree = _make_doc_tree()

        # POST_RENDER axes (appended as annotation sections)
        post_axes = {
            1: ("structure-flat", "structure"),
            2: ("granularity-file", "granularity"),
            4: ("position-bluf", "position"),
            5: ("metadata-tokens", "metadata"),
            7: ("noise-0", "noise"),
            8: ("transform-tagged", "transform"),
            9: ("xref-light", "xref"),
            10: ("temporal-modified", "temporal"),
        }
        # PRIMARY axis
        components: dict[int, IndexVariant] = {
            3: _CategoryStub("format-yaml", 3, "format"),
        }
        for ax, (name, cat) in post_axes.items():
            components[ax] = _CategoryStub(name, ax, cat)

        composite = CompositeVariant(components=components)
        output = composite.render(doc_tree)

        # Primary output present
        assert "[format:format-yaml]" in output
        # Every POST_RENDER axis marker should appear
        for ax, (name, cat) in post_axes.items():
            assert cat in output.lower(), (
                f"Axis {ax} ({cat}) not found in composite output"
            )

    def test_pre_render_axis_modifies_tree(self):
        """PRE_RENDER scale axis should modify what the primary renders."""
        doc_tree = _make_doc_tree()  # 4 files

        class Scale2Stub(IndexVariant):
            """Renders and filters to first 2 files."""
            def metadata(self) -> VariantMetadata:
                return VariantMetadata(
                    name="scale-2", axis=6, category="scale",
                    description="2 files", token_estimate=50,
                )

            def render(self, doc_tree: DocTree) -> str:
                # Only includes first 2 paths -> generic pre_render filters
                paths = sorted(doc_tree.files)[:2]
                return "\n".join(f"- {p}" for p in paths)

        fmt = _CategoryStub("format-yaml", 3, "format")
        scale = Scale2Stub()

        composite = CompositeVariant(components={3: fmt, 6: scale})
        output = composite.render(doc_tree)

        # Scale filtered to 2 files before format rendered
        assert "api/auth.md" in output
        assert "api/cache.md" in output
        assert "guides/setup.md" not in output
        assert "guides/deploy.md" not in output


# ---------------------------------------------------------------------------
# Tests: Backward compatibility
# ---------------------------------------------------------------------------


class TestCompositeBackwardCompat:
    """Pipeline role changes must not break existing single-axis usage."""

    def test_single_primary_renders_normally(self):
        doc_tree = _make_doc_tree()
        fmt = _CategoryStub("format-yaml", 3, "format")
        composite = CompositeVariant(components={3: fmt})
        output = composite.render(doc_tree)
        expected = fmt.render(doc_tree)
        assert output == expected

    def test_explicit_pipeline_role_still_works(self):
        """Variants that explicitly override pipeline_role() are respected."""

        class ExplicitPre(IndexVariant):
            def metadata(self) -> VariantMetadata:
                return VariantMetadata(
                    name="explicit-pre", axis=6, category="custom",
                    description="test", token_estimate=50,
                )

            def pipeline_role(self) -> PipelineRole:
                return PipelineRole.PRE_RENDER

            def pre_render(self, doc_tree: DocTree) -> DocTree:
                paths = sorted(doc_tree.files)[:2]
                return doc_tree.model_copy(
                    update={"files": {k: doc_tree.files[k] for k in paths}}
                )

            def render(self, doc_tree: DocTree) -> str:
                return "explicit-pre-render"

        doc_tree = _make_doc_tree()
        fmt = _CategoryStub("format", 3, "format")
        pre = ExplicitPre()
        composite = CompositeVariant(components={3: fmt, 6: pre})
        output = composite.render(doc_tree)

        # Pre-render filtered to 2 files
        assert "api/auth.md" in output
        assert "guides/deploy.md" not in output
