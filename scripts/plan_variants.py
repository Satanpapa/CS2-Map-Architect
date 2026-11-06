#!/usr/bin/env python3
"""Generate JSON route analysis and SVG previews for T approaches to A/B."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cs2_map_architect.io.map_io import load_spec
from cs2_map_architect.planning import LayoutAnalyzer, RouteVariantGenerator
from cs2_map_architect.render.svg_renderer import SvgRenderer
from cs2_map_architect.validation.spec_validator import SpecValidator


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "examples" / "de_quartz.json")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "output" / "route_variants")
    parser.add_argument("--variants", type=int, default=3)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--paths-per-site", type=int, default=5)
    parser.add_argument("--speed-mps", type=float, default=None,
                        help="optional user-supplied scenario speed; no CS2 default is assumed")
    args = parser.parse_args()
    spec = load_spec(args.input)
    validation = SpecValidator(spec).validate()
    print(validation.summary())
    if not validation.ok:
        return 1

    analyzer = LayoutAnalyzer(spec, movement_speed_mps=args.speed_mps)
    paths = analyzer.paths_to_bombsites(k=args.paths_per_site)
    variants = RouteVariantGenerator(analyzer).generate(
        count=args.variants, seed=args.seed, paths_per_site=args.paths_per_site
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "map_id": spec.map_id,
        "methodology": {
            "edge_distance": "3D Euclidean distance between zone centers",
            "interpretation": "geometric proxy, not a measured walkable path",
            "time": "proxy distance / user-supplied speed" if args.speed_mps else "not calculated",
            "limitations": ["no doorway/centerline geometry", "no player movement physics",
                            "no combat exposure, visibility or grenade simulation"],
        },
        "paths_from_t_spawn": {k: [p.to_dict() for p in v] for k, v in paths.items()},
        "variants": [v.to_dict() for v in variants],
    }
    (args.output_dir / "layout_analysis.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    for variant in variants:
        preview = variant.apply_to_spec(spec)
        check = SpecValidator(preview).validate()
        if not check.ok:
            print(check.summary())
            return 1
        path = args.output_dir / f"{variant.variant_id}.svg"
        SvgRenderer(preview).save(path)
        print(f"{variant.variant_id}: {path}")
        print(f"  A: {' -> '.join(variant.route_to_a.zone_path)} ({variant.route_to_a.distance_m:.1f} m proxy)")
        print(f"  B: {' -> '.join(variant.route_to_b.zone_path)} ({variant.route_to_b.distance_m:.1f} m proxy)")
    print("Note: route alternatives do not alter room geometry or prove competitive balance.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
