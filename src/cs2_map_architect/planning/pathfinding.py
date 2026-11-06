"""Graph route analysis. Distances are zone-center proxies, not walkable path lengths."""
from __future__ import annotations

import heapq
import math
from dataclasses import asdict, dataclass

from cs2_map_architect.models.enums import TeamSide
from cs2_map_architect.models.map_spec import MapSpec


@dataclass(frozen=True)
class PathEstimate:
    zone_path: tuple[str, ...]
    connection_ids: tuple[str, ...]
    distance_m: float
    travel_time_s: float | None
    min_connection_width_m: float | None

    @property
    def hops(self) -> int:
        return len(self.connection_ids)

    def to_dict(self) -> dict[str, object]:
        return asdict(self) | {"hops": self.hops}


class LayoutAnalyzer:
    """Dijkstra + Yen K-shortest simple paths over MapSpec connections.

    Edge cost is 3D Euclidean distance between zone centers. It is an early
    topology proxy until doorway and corridor-centerline geometry is modeled.
    Time is omitted unless the caller supplies a scenario speed in metres/sec.
    """

    def __init__(self, spec: MapSpec, movement_speed_mps: float | None = None):
        if movement_speed_mps is not None and (
            not math.isfinite(movement_speed_mps) or movement_speed_mps <= 0
        ):
            raise ValueError("movement_speed_mps must be finite and > 0")
        self.spec = spec
        self.speed = movement_speed_mps
        self.zones = {z.id: z for z in spec.zones}
        self.arcs: dict[str, list[tuple[str, str, float, float]]] = {z: [] for z in self.zones}
        for edge in spec.connections:
            if edge.zone_a not in self.zones or edge.zone_b not in self.zones:
                continue
            a, b = self.zones[edge.zone_a], self.zones[edge.zone_b]
            ac, bc = a.rect.center, b.rect.center
            cost = math.dist((ac.x, ac.y, a.elevation_m), (bc.x, bc.y, b.elevation_m))
            self.arcs[edge.zone_a].append((edge.zone_b, edge.id, cost, edge.width_m))
            if edge.bidirectional:
                self.arcs[edge.zone_b].append((edge.zone_a, edge.id, cost, edge.width_m))
        for arcs in self.arcs.values():
            arcs.sort(key=lambda x: (x[0], x[1]))

    def shortest_path(self, start: str, target: str, *, excluded_zones: set[str] | None = None):
        paths = self.k_shortest_paths(start, target, 1, excluded_zones=excluded_zones)
        return paths[0] if paths else None

    def k_shortest_paths(
        self, start: str, target: str, k: int = 3, *, excluded_zones: set[str] | None = None
    ) -> list[PathEstimate]:
        if k < 1:
            raise ValueError("k must be >= 1")
        for zone in (start, target):
            if zone not in self.zones:
                raise KeyError(f"unknown zone: {zone}")
        blocked = set(excluded_zones or ())
        unknown = blocked - self.zones.keys()
        if unknown:
            raise KeyError(f"unknown excluded zones: {', '.join(sorted(unknown))}")
        if start in blocked or target in blocked:
            return []
        first = self._dijkstra(start, target, blocked, set())
        if first is None:
            return []
        accepted = [first]
        accepted_nodes = {first[0]}
        candidates = {}
        while len(accepted) < k:
            nodes, edges, _ = accepted[-1]
            for i in range(len(nodes) - 1):
                root_nodes, root_edges = nodes[:i + 1], edges[:i]
                banned_edges = {
                    (p[0][i], p[0][i + 1]) for p in accepted
                    if len(p[0]) > i and p[0][:i + 1] == root_nodes
                }
                spur = self._dijkstra(root_nodes[-1], target, blocked | set(root_nodes[:-1]), banned_edges)
                if spur is None:
                    continue
                sn, se, sc = spur
                total_nodes = root_nodes[:-1] + sn
                if total_nodes in accepted_nodes or total_nodes in candidates:
                    continue
                root_cost = sum(self._edge_cost(root_nodes[j], root_nodes[j + 1], root_edges[j])
                                for j in range(len(root_edges)))
                candidates[total_nodes] = (total_nodes, root_edges + se, root_cost + sc)
            if not candidates:
                break
            chosen = min(candidates.values(), key=lambda p: (p[2], p[0]))
            accepted.append(chosen)
            accepted_nodes.add(chosen[0])
            candidates.pop(chosen[0])
        return [self._estimate(n, e) for n, e, _ in accepted]

    def paths_to_bombsites(self, side: TeamSide = TeamSide.T, k: int = 3):
        opponent = TeamSide.CT if side == TeamSide.T else TeamSide.T
        start = self.spec.spawn_zone_id(side)
        excluded = {self.spec.spawn_zone_id(opponent)}
        return {
            site.label: self.k_shortest_paths(start, site.zone_id, k, excluded_zones=excluded)
            for site in sorted(self.spec.bombsites, key=lambda s: s.label)
        }

    def _edge_cost(self, a: str, b: str, edge_id: str) -> float:
        for nxt, eid, cost, _ in self.arcs[a]:
            if nxt == b and eid == edge_id:
                return cost
        raise RuntimeError(f"missing graph edge {a}->{b} ({edge_id})")

    def _dijkstra(self, start, target, banned_nodes, banned_edges):
        if start in banned_nodes or target in banned_nodes:
            return None
        dist = {start: 0.0}
        previous = {}
        queue = [(0.0, start)]
        while queue:
            cost, node = heapq.heappop(queue)
            if cost > dist.get(node, math.inf) + 1e-12:
                continue
            if node == target:
                break
            for nxt, edge_id, weight, _ in self.arcs[node]:
                if nxt in banned_nodes or (node, nxt) in banned_edges:
                    continue
                candidate = cost + weight
                if candidate + 1e-12 < dist.get(nxt, math.inf):
                    dist[nxt] = candidate
                    previous[nxt] = (node, edge_id)
                    heapq.heappush(queue, (candidate, nxt))
        if target not in dist:
            return None
        nodes, edges, cursor = [target], [], target
        while cursor != start:
            parent, edge_id = previous[cursor]
            nodes.append(parent)
            edges.append(edge_id)
            cursor = parent
        return tuple(reversed(nodes)), tuple(reversed(edges)), dist[target]

    def _estimate(self, nodes, edges):
        distance = sum(self._edge_cost(nodes[i], nodes[i + 1], edges[i]) for i in range(len(edges)))
        widths = {e.id: e.width_m for e in self.spec.connections}
        return PathEstimate(
            tuple(nodes), tuple(edges), distance,
            distance / self.speed if self.speed is not None else None,
            min((widths[e] for e in edges), default=None),
        )
