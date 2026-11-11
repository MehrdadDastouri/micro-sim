"""Analytical and stochastic slippage models accounting for in-flight price drift and impact."""

from dataclasses import dataclass
import numpy as np
from micro_sim.models import Side


@dataclass(slots=True)
class SlippageResult:
    """Breakdown of realized slippage components."""
    decision_price: float
    arrival_price: float
    execution_price: float
    drift_slippage_bps: float
    impact_slippage_bps: float
    total_slippage_bps: float


class MarketImpactModel:
    """Computes price progression during network transit using the Square-Root Law."""

    def __init__(
        self,
        volatility_daily: float = 0.02,
        daily_volume: float = 1_000_000.0,
        drift_drift_per_sec: float = 0.0,
        impact_constant: float = 0.5,
        seed: int = 42,
    ) -> None:
        self.vol_daily = volatility_daily
        self.daily_volume = daily_volume
        self.drift_per_sec = drift_drift_per_sec
        self.impact_constant = impact_constant
        self._rng = np.random.default_rng(seed)

        # Microsecond volatility conversion (assuming 86,400 seconds per day)
        self._vol_per_ns = (self.vol_daily / np.sqrt(86_400.0)) / 1e9

    def compute_slippage(
        self,
        decision_price: float,
        quantity: float,
        side: Side,
        transit_delay_ns: int,
    ) -> SlippageResult:
        """
        Evaluate price trajectory from decision timestamp to exchange arrival.
        Total Slippage = In-Flight Transit Drift + Instantaneous Market Impact.
        """
        dt_sec = transit_delay_ns / 1e9

        # 1. Stochastic Brownian drift while the packet travels on the wire
        stochastic_shock = self._rng.normal(
            loc=self.drift_per_sec * dt_sec,
            scale=self._vol_per_ns * np.sqrt(transit_delay_ns),
        )
        arrival_price = decision_price * (1.0 + stochastic_shock)

        # 2. Square-Root Temporary Market Impact at the moment of matching
        # Impact = Y * sigma * sqrt(Q / V)
        participation_fraction = min(1.0, quantity / max(1.0, self.daily_volume))
        impact_pct = self.impact_constant * self.vol_daily * np.sqrt(participation_fraction)

        # Slippage works against the taker: Buy pays more, Sell receives less
        direction = 1.0 if side == Side.BID else -1.0
        execution_price = arrival_price * (1.0 + (direction * impact_pct))

        # Slippage calculations in basis points relative to decision price
        drift_bps = ((arrival_price - decision_price) / decision_price) * 10_000.0 * direction
        impact_bps = impact_pct * 10_000.0
        total_bps = ((execution_price - decision_price) / decision_price) * 10_000.0 * direction

        return SlippageResult(
            decision_price=decision_price,
            arrival_price=arrival_price,
            execution_price=execution_price,
            drift_slippage_bps=float(drift_bps),
            impact_slippage_bps=float(impact_bps),
            total_slippage_bps=float(total_bps),
        )
