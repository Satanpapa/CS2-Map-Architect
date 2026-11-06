"""CS2 Map Architect local competitive map design toolkit."""
__version__ = "0.2.0"

from cs2_map_architect.models.map_spec import SCHEMA_VERSION, SUPPORTED_SCHEMA_VERSIONS, Calibration, MapSpec
from cs2_map_architect.planning import LayoutAnalyzer, PathEstimate, RouteVariantGenerator, TacticalVariant

__all__ = [
    "__version__", "SCHEMA_VERSION", "SUPPORTED_SCHEMA_VERSIONS", "Calibration", "MapSpec",
    "LayoutAnalyzer", "PathEstimate", "RouteVariantGenerator", "TacticalVariant",
]
