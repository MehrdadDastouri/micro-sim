import numpy as np
from micro_sim.latency import NetworkLatencyModel
from micro_sim.models import ExecutionReport, LatencyProfile, OrderIntent, OrderStatus, Side
from micro_sim.simulator import DiscreteEventSimulator
from micro_sim.slippage import MarketImpactModel


def test_square_root_slippage_direction():
    model = MarketImpactModel(volatility_daily=0.03, daily_volume=10_000.0, impact_constant=0.6, seed=42)

    # 1. Aggressive Buy experiences adverse upward slippage
    buy_slip = model.compute_slippage(
        decision_price=100.0, quantity=100.0, side=Side.BID, transit_delay_ns=1_000_000
    )
    assert buy_slip.impact_slippage_bps > 0
    assert buy_slip.execution_price > buy_slip.arrival_price

    # 2. Aggressive Sell experiences adverse downward slippage
    sell_slip = model.compute_slippage(
        decision_price=100.0, quantity=100.0, side=Side.ASK, transit_delay_ns=1_000_000
    )
    assert sell_slip.impact_slippage_bps > 0
    assert sell_slip.execution_price < sell_slip.arrival_price


def test_end_to_end_in_flight_slippage_execution():
    reports: list[ExecutionReport] = []
    profile = LatencyProfile(base_wire_delay_ns=500_000, jitter_mu_ns=0.0, jitter_sigma_ns=0.0)
    inbound = NetworkLatencyModel(profile, seed=1)
    outbound = NetworkLatencyModel(profile, seed=1)

    # Deterministic zero-volatility model to isolate permanent impact
    impact_model = MarketImpactModel(
        volatility_daily=0.02, daily_volume=100_000.0, drift_drift_per_sec=0.0, impact_constant=0.5, seed=1
    )

    sim = DiscreteEventSimulator(
        inbound_latency=inbound,
        outbound_latency=outbound,
        slippage_model=impact_model,
        on_client_report=lambda rep, ts: reports.append(rep),
    )

    sim.market_mid_price = 100.0
    order = OrderIntent(
        client_order_id=99,
        side=Side.BID,
        price=105.0,  # Crosses mid
        quantity=1_000.0,
        client_timestamp_ns=0,
    )

    sim.submit_new_order(order)
    sim.run_all()

    assert len(reports) == 1
    rep = reports[0]
    assert rep.status == OrderStatus.FILLED
    # Fill price must be higher than 100.0 due to buyer market impact
    assert rep.fill_price > 100.0
