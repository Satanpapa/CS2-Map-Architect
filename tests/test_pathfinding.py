from pathlib import Path
import pytest

from cs2_map_architect.io.map_io import load_spec
from cs2_map_architect.models.enums import TeamSide
from cs2_map_architect.models.routes import Connection
from cs2_map_architect.planning import LayoutAnalyzer

SPEC = Path(__file__).resolve().parents[1] / "examples" / "de_quartz.json"


@pytest.fixture
def spec():
    return load_spec(SPEC)


def test_shortest_and_k_paths_are_ordered_and_simple(spec):
    analyzer = LayoutAnalyzer(spec)
    paths = analyzer.k_shortest_paths("t_spawn", "a_site", k=5)
    assert paths and paths[0] == analyzer.shortest_path("t_spawn", "a_site")
    assert len({p.zone_path for p in paths}) == len(paths)
    assert [p.distance_m for p in paths] == sorted(p.distance_m for p in paths)
    assert all(len(p.zone_path) == len(set(p.zone_path)) for p in paths)


def test_directionality_is_respected(spec):
    directed = spec.model_copy(update={"connections": [
        Connection(id="one_way", zone_a="t_spawn", zone_b="mid", bidirectional=False)
    ]}, deep=True)
    analyzer = LayoutAnalyzer(directed)
    assert analyzer.shortest_path("t_spawn", "mid") is not None
    assert analyzer.shortest_path("mid", "t_spawn") is None


def test_opponent_spawn_is_excluded_from_team_approaches(spec):
    analyzer = LayoutAnalyzer(spec)
    for paths in analyzer.paths_to_bombsites(TeamSide.T, 10).values():
        assert paths and all("ct_spawn" not in p.zone_path for p in paths)
    for paths in analyzer.paths_to_bombsites(TeamSide.CT, 10).values():
        assert paths and all("t_spawn" not in p.zone_path for p in paths)


def test_optional_time_requires_explicit_scenario_speed(spec):
    path = LayoutAnalyzer(spec).shortest_path("t_spawn", "a_site")
    assert path is not None and path.travel_time_s is None
    timed = LayoutAnalyzer(spec, movement_speed_mps=5).shortest_path("t_spawn", "a_site")
    assert timed is not None and timed.travel_time_s == pytest.approx(timed.distance_m / 5)


@pytest.mark.parametrize("speed", [0, -1, float("inf"), float("nan")])
def test_invalid_speed_is_rejected(spec, speed):
    with pytest.raises(ValueError):
        LayoutAnalyzer(spec, movement_speed_mps=speed)


def test_unknown_zones_and_invalid_k_are_rejected(spec):
    analyzer = LayoutAnalyzer(spec)
    with pytest.raises(KeyError):
        analyzer.shortest_path("missing", "a_site")
    with pytest.raises(ValueError):
        analyzer.k_shortest_paths("t_spawn", "a_site", 0)
