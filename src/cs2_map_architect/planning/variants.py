"""Deterministic route-pair alternatives; this module does not move zone geometry."""
from __future__ import annotations

import random
from dataclasses import dataclass

from cs2_map_architect.models.enums import RouteCategory
from cs2_map_architect.models.map_spec import MapSpec
from cs2_map_architect.models.routes import Route
from cs2_map_architect.planning.pathfinding import LayoutAnalyzer, PathEstimate


@dataclass(frozen=True)
class TacticalVariant:
    variant_number: int
    seed: int
    route_to_a: PathEstimate
    route_to_b: PathEstimate

    @property
    def variant_id(self) -> str:
        return f"route_variant_{self.variant_number:02d}"

    def to_dict(self):
        return {
            "variant_id": self.variant_id,
            "seed": self.seed,
            "method": "seeded_sample_of_k_shortest_simple_paths",
            "scope": "route_selection_only",
            "routes": {"A": self.route_to_a.to_dict(), "B": self.route_to_b.to_dict()},
        }

    def apply_to_spec(self, spec: MapSpec) -> MapSpec:
        retained = [r for r in spec.routes if r.category == RouteCategory.ROTATION]
        generated = [
            Route(
                id=f"{self.variant_id}_t_a", name=f"Вариант {self.variant_number}: подход T на A",
                category=RouteCategory.MAIN, zone_path=list(self.route_to_a.zone_path),
                description="Оценка расстояния по центрам зон; не фактический путь игрока.",
                estimated_time_s=self.route_to_a.travel_time_s,
            ),
            Route(
                id=f"{self.variant_id}_t_b", name=f"Вариант {self.variant_number}: подход T на B",
                category=RouteCategory.MAIN, zone_path=list(self.route_to_b.zone_path),
                description="Оценка расстояния по центрам зон; не фактический путь игрока.",
                estimated_time_s=self.route_to_b.travel_time_s,
            ),
        ]
        return spec.model_copy(update={"routes": retained + generated}, deep=True)


class RouteVariantGenerator:
    def __init__(self, analyzer: LayoutAnalyzer):
        self.analyzer = analyzer

    def generate(self, *, count: int = 3, seed: int = 42, paths_per_site: int = 5):
        if count < 1 or paths_per_site < 1:
            raise ValueError("count and paths_per_site must be >= 1")
        paths = self.analyzer.paths_to_bombsites(k=paths_per_site)
        missing = [site for site in ("A", "B") if not paths.get(site)]
        if missing:
            raise ValueError(f"no route from T spawn to: {', '.join(missing)}")
        pairs = [(a, b) for a in paths["A"] for b in paths["B"]]
        random.Random(seed).shuffle(pairs)
        return [
            TacticalVariant(i, seed, a, b)
            for i, (a, b) in enumerate(pairs[:count], 1)
        ]
