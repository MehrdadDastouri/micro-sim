"""Stochastic network latency generators with realistic long-tailed jitter."""

import numpy as np
from micro_sim.models import LatencyProfile


class NetworkLatencyModel:
    """Models asymmetric transit delays with log-normal queuing spikes."""

    def __init__(self, profile: LatencyProfile, seed: int = 42) -> None:
        self.profile = profile
        self._rng = np.random.default_rng(seed)

    def sample_delay_ns(self) -> int:
        """Sample one-way transit delay including base wire latency and jitter."""
        if self.profile.jitter_sigma_ns <= 0:
            jitter = self.profile.jitter_mu_ns
        else:
            jitter = self._rng.lognormal(
                mean=np.log(max(1.0, self.profile.jitter_mu_ns)),
                sigma=self.profile.jitter_sigma_ns,
            )

        total_delay = self.profile.base_wire_delay_ns + int(jitter)
        return max(1, total_delay)
