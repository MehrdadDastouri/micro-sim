"""High-resolution throughput and latency benchmark for Discrete-Event Simulator heap."""

import gc
import statistics
import time
from typing import List
from micro_sim.latency import NetworkLatencyModel
from micro_sim.models import LatencyProfile, OrderIntent, Side
from micro_sim.simulator import DiscreteEventSimulator


def run_benchmark(num_orders: int = 100_000) -> None:
    profile = LatencyProfile(base_wire_delay_ns=50_000, jitter_mu_ns=5_000.0, jitter_sigma_ns=0.2)
    inbound = NetworkLatencyModel(profile, seed=42)
    outbound = NetworkLatencyModel(profile, seed=84)

    sim = DiscreteEventSimulator(inbound_latency=inbound, outbound_latency=outbound)

    latencies_ns: List[int] = [0] * num_orders

    print(f"[*] Benchmarking {num_orders:,} discrete-event order dispatches...")
    print("[*] Disabling GC for deterministic sub-microsecond profiling...")

    gc.disable()
    start_wall = time.perf_counter_ns()

    for i in range(num_orders):
        t0 = time.perf_counter_ns()
        order = OrderIntent(
            client_order_id=i + 1,
            side=Side.BID if i % 2 == 0 else Side.ASK,
            price=105.0 if i % 2 == 0 else 95.0,  # Aggressive crosses
            quantity=1.0,
            client_timestamp_ns=i * 1_000,
        )
        sim.submit_new_order(order)
        t1 = time.perf_counter_ns()
        latencies_ns[i] = t1 - t0

    # Drain all scheduled events through heap
    drain_start = time.perf_counter_ns()
    sim.run_all()
    drain_end = time.perf_counter_ns()

    gc.enable()

    total_duration_sec = (drain_end - start_wall) / 1e9
    total_events = num_orders * 2  # Each order generates inbound + outbound events
    throughput = total_events / total_duration_sec

    latencies_ns.sort()
    p50 = latencies_ns[int(num_orders * 0.50)]
    p90 = latencies_ns[int(num_orders * 0.90)]
    p99 = latencies_ns[int(num_orders * 0.99)]
    p99_9 = latencies_ns[int(num_orders * 0.999)]
    mean_lat = statistics.mean(latencies_ns)

    print("\n" + "=" * 55)
    print("           MICRO-SIM BENCHMARK RESULTS")
    print("=" * 55)
    print(f"Processed Events         : {total_events:,}")
    print(f"Total Wall Duration      : {total_duration_sec:.4f} sec")
    print(f"Event Throughput         : {throughput:,.0f} events/sec")
    print("-" * 55)
    print(f"Mean Schedule Latency    : {mean_lat / 1000.0:.2f} µs ({mean_lat:.0f} ns)")
    print(f"P50 Latency (Median)     : {p50 / 1000.0:.2f} µs ({p50:.0f} ns)")
    print(f"P90 Latency              : {p90 / 1000.0:.2f} µs ({p90:.0f} ns)")
    print(f"P99 Latency              : {p99 / 1000.0:.2f} µs ({p99:.0f} ns)")
    print(f"P99.9 Latency (Tail)     : {p99_9 / 1000.0:.2f} µs ({p99_9:.0f} ns)")
    print("=" * 55)


if __name__ == "__main__":
    run_benchmark(num_orders=100_000)
