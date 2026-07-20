"""Validate that all 10 eval axes have proper variant implementations registered."""

import sys
sys.path.insert(0, r"C:\Users\Trevor Leigh\Desktop\ai-enhancements\agent-evals\src")
sys.path.insert(0, r"C:\Users\Trevor Leigh\Desktop\ai-enhancements\agent-index\src")

from agent_evals.variants.registry import load_all, get_variants_for_axis, get_all_variants
from agent_evals.variants.baselines import (
    NoIndexBaseline, NoDocsBaseline, OracleBaseline, LengthMatchedRandomBaseline,
)

load_all()

print("=== ALL REGISTERED VARIANTS ===")
all_v = get_all_variants()
for v in all_v:
    m = v.metadata()
    print(f"  Axis {m.axis}: {m.name} (desc: {m.description[:60]})")

print(f"\nTotal registered variants: {len(all_v)}")

print("\n=== VARIANTS BY AXIS ===")
for axis in range(1, 11):
    variants = get_variants_for_axis(axis)
    print(f"\nAxis {axis}: {len(variants)} variants")
    for v in variants:
        m = v.metadata()
        print(f"  - {m.name}: {m.description[:80]}")

print("\n=== BASELINES ===")
baselines = [NoIndexBaseline(), NoDocsBaseline(), OracleBaseline(), LengthMatchedRandomBaseline()]
for b in baselines:
    m = b.metadata()
    print(f"  {m.name}: {m.description[:80]}")

# Verify completeness
missing = []
for axis in range(1, 11):
    if not get_variants_for_axis(axis):
        missing.append(axis)

if missing:
    print(f"\nERROR: Missing variants for axes: {missing}")
else:
    print(f"\nAll 10 axes have variants registered.")

# Additional validation: check that all variants have proper methods
print("\n=== METHOD VALIDATION ===")
issues = []
for v in all_v:
    m = v.metadata()
    has_metadata = hasattr(v, 'metadata') and callable(v.metadata)
    has_render = hasattr(v, 'render') and callable(v.render)
    has_setup = hasattr(v, 'setup') and callable(v.setup)
    has_teardown = hasattr(v, 'teardown') and callable(v.teardown)
    if not has_metadata:
        issues.append(f"  {m.name}: MISSING metadata()")
    if not has_render:
        issues.append(f"  {m.name}: MISSING render()")
    if not has_setup:
        issues.append(f"  {m.name}: MISSING setup()")
    if not has_teardown:
        issues.append(f"  {m.name}: MISSING teardown()")

if issues:
    print("ISSUES FOUND:")
    for issue in issues:
        print(issue)
else:
    print("All variants have metadata(), render(), setup(), and teardown() methods.")

# Summary table
print("\n=== SUMMARY TABLE ===")
print(f"{'Axis':<6} {'Count':<7} {'Variant Names'}")
print(f"{'----':<6} {'-----':<7} {'-------------'}")
for axis in range(0, 11):
    variants = get_variants_for_axis(axis)
    names = ", ".join(v.metadata().name for v in variants)
    label = f"Axis {axis}" if axis > 0 else "Base 0"
    print(f"{label:<6} {len(variants):<7} {names}")

print(f"\n{'Total':<6} {len(all_v):<7}")
