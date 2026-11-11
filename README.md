# micro-sim

[![CI](https://github.com/MehrdadDastouri/micro-sim/actions/workflows/ci.yml/badge.svg)](https://github.com/MehrdadDastouri/micro-sim/actions)
[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Deterministic discrete-event network latency, queue transit race resolution, and in-flight market impact simulator for high-frequency trading systems.

---

## Architectural Highlights

- **Discrete-Event Simulation (DES):** Min-heap event scheduling guaranteeing non-leaking, causal progression of market messages without continuous tick polling.
- **Asymmetric Stochastic Network Jitter:** Wire transit latencies modeled via calibrated log-normal distributions to reproduce positive queuing tails and packet delay variation.
- **In-Flight Cancellation Races:** Accurately resolves race conditions where aggressive order fills hit matching engines before incoming cancellation packets arrive.
- **Square-Root Market Impact & Transit Drift:** Evaluates slippage during one-way transit delays combining Brownian fair-value drift with the Square-Root Law of market impact.

---

## Benchmarks

Benchmarked over 200,000 discrete event lifecycle dispatches (new order, matching, fill reports):

| Metric | Measured Value |
| :--- | :--- |
| **Throughput** | ~780,000 events/sec |
| **Mean Scheduling Latency** | 0.88 µs (880 ns) |
| **P50 Latency (Median)** | 0.75 µs (750 ns) |
| **P90 Latency** | 1.10 µs |
| **P99 Latency** | 1.95 µs |
| **P99.9 Latency** | 3.40 µs |

---

## Quickstart

```python
from micro_sim.simulator import DiscreteEventSimulator
from micro_sim.latency import NetworkLatencyModel
from micro_sim.slippage import MarketImpactModel
from micro_sim.models import LatencyProfile, OrderIntent, Side

# Configure 200 microsecond wire delay with jitter
profile = LatencyProfile(base_wire_delay_ns=200_000, jitter_mu_ns=15_000, jitter_sigma_ns=0.25)
sim = DiscreteEventSimulator(
    inbound_latency=NetworkLatencyModel(profile),
    outbound_latency=NetworkLatencyModel(profile),
    slippage_model=MarketImpactModel(),
    on_client_report=lambda rep, ts: print(f"Client got {rep.status.name} @ {rep.fill_price} at {ts}ns"),
)

# Fire market order at t = 0
sim.submit_new_order(
    OrderIntent(client_order_id=1, side=Side.BID, price=105.0, quantity=50.0, client_timestamp_ns=0)
)
sim.run_all()
```

## Testing & Benchmarks

```bash
pip install -e .[dev]
pytest -v
python benchmarks/run_benchmark.py
```

## License

MIT License. Designed and engineered by Seyed Mehrdad Dastouri.
