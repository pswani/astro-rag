"""The default feature set (design §7.3)."""

from __future__ import annotations

from astro.calc.dasha.vimshottari import DashaActive, Vimshottari
from astro.calc.engine import CachePort, Engine
from astro.calc.features.friendship import Friendship
from astro.calc.features.houses import Houses
from astro.calc.features.panchanga import Panchanga
from astro.calc.features.positions import Positions
from astro.calc.features.relations import Relations
from astro.calc.features.vargas import Vargas
from astro.calc.transits.eclipses import Eclipses
from astro.calc.transits.events import TransitEvents
from astro.calc.transits.positions import TransitPositions
from astro.calc.transits.states import TransitStates


def default_features() -> list:
    return [Positions(), Houses(), Relations(), Friendship(), Vargas(), Panchanga(),
            Vimshottari(), DashaActive(), TransitPositions(), TransitEvents(), TransitStates(),
            Eclipses()]


def default_engine(cache: CachePort | None = None, extra: list | None = None) -> Engine:
    return Engine([*default_features(), *(extra or [])], cache)
