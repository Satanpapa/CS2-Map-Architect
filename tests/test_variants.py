from pathlib import Path

from cs2_map_architect.io.map_io import load_spec
from cs2_map_architect.models.enums import RouteCategory
from cs2_map_architect.planning import LayoutAnalyzer, RouteVariantGenerator
from cs2_map_architect.validation.spec_validator import SpecValidator

SPEC = Path(__file__).resolve().parents[1] / "examples" / "de_quartz.json"


def test_variants_are_seed_reproducible():
    spec = load_spec(SPEC)
    generator = RouteVariantGenerator(LayoutAnalyzer(spec))
    a = [v.to_dict() for v in generator.generate(count=3, seed=2026)]
    b = [v.to_dict() for v in generator.generate(count=3, seed=2026)]
    assert a == b


def test_variant_does_not_mutate_source_and_keeps_ct_rotations():
    spec = load_spec(SPEC)
    original = list(spec.routes)
    variant = RouteVariantGenerator(LayoutAnalyzer(spec)).generate(count=1)[0]
    preview = variant.apply_to_spec(spec)
    assert spec.routes == original
    assert all(r.category == RouteCategory.ROTATION for r in preview.routes[:3])
    assert SpecValidator(preview).validate().ok


def test_variant_pair_targets_both_sites():
    spec = load_spec(SPEC)
    variant = RouteVariantGenerator(LayoutAnalyzer(spec)).generate(count=1)[0]
    site_ids = {s.label: s.zone_id for s in spec.bombsites}
    assert variant.route_to_a.zone_path[-1] == site_ids["A"]
    assert variant.route_to_b.zone_path[-1] == site_ids["B"]
