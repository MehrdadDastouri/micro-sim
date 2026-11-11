from typing import List, Tuple
from micro_sim.latency import NetworkLatencyModel
from micro_sim.models import (
    ExecutionReport,
    LatencyProfile,
    OrderIntent,
    OrderStatus,
    Side,
)
from micro_sim.simulator import DiscreteEventSimulator


def create_deterministic_sim(
    wire_delay_ns: int = 1_000_000,
) -> Tuple[DiscreteEventSimulator, List[Tuple[ExecutionReport, int]]]:
    reports: List[Tuple[ExecutionReport, int]] = []
    profile = LatencyProfile(base_wire_delay_ns=wire_delay_ns, jitter_mu_ns=0.0, jitter_sigma_ns=0.0)
    inbound = NetworkLatencyModel(profile, seed=1)
    outbound = NetworkLatencyModel(profile, seed=1)

    sim = DiscreteEventSimulator(
        inbound_latency=inbound,
        outbound_latency=outbound,
        on_client_report=lambda rep, ts: reports.append((rep, ts)),
    )
    return sim, reports


def test_round_trip_latency_and_ack():
    # 1 ms each way = 2 ms total RTT (2,000,000 ns)
    sim, reports = create_deterministic_sim(wire_delay_ns=1_000_000)

    order = OrderIntent(
        client_order_id=1,
        side=Side.BID,
        price=90.0,
        quantity=10.0,
        client_timestamp_ns=10_000_000,
    )
    sim.submit_new_order(order)
    sim.run_all()

    assert len(reports) == 1
    rep, client_recv_time = reports[0]
    assert rep.status == OrderStatus.ACCEPTED
    assert rep.client_order_id == 1
    assert rep.exchange_timestamp_ns == 11_000_000
    assert client_recv_time == 12_000_000
    assert client_recv_time - order.client_timestamp_ns == 2_000_000


def test_cancellation_race_condition_success():
    sim, reports = create_deterministic_sim(wire_delay_ns=1_000_000)

    order = OrderIntent(
        client_order_id=42,
        side=Side.ASK,
        price=110.0,
        quantity=5.0,
        client_timestamp_ns=0,
    )
    sim.submit_new_order(order)

    # Cancel sent at 2.5ms (after receiving ACK at 2ms)
    sim.submit_cancel_order(client_order_id=42, client_timestamp_ns=2_500_000)
    sim.run_all()

    assert len(reports) == 2
    assert reports[0][0].status == OrderStatus.ACCEPTED
    assert reports[1][0].status == OrderStatus.CANCELLED
    assert reports[1][1] == 4_500_000


def test_cancellation_race_condition_rejected_on_in_flight():
    sim, reports = create_deterministic_sim(wire_delay_ns=1_000_000)

    # Cancel order that does not exist in exchange book
    sim.submit_cancel_order(client_order_id=999, client_timestamp_ns=1_000_000)
    sim.run_all()

    assert len(reports) == 1
    rep, recv_ts = reports[0]
    assert rep.status == OrderStatus.REJECTED
    assert "not found" in rep.reason.lower()
    assert recv_ts == 3_000_000
