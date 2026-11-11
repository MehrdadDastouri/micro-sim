"""Discrete-Event Simulation (DES) harness for end-to-end latency and execution."""

import heapq
from typing import Callable, Dict, List, Optional
from micro_sim.latency import NetworkLatencyModel
from micro_sim.models import (
    DiscreteEvent,
    ExecutionReport,
    OrderIntent,
    OrderStatus,
    PacketType,
    Side,
)


class DiscreteEventSimulator:
    """Deterministic discrete-event simulator resolving order transit and matching races."""

    def __init__(
        self,
        inbound_latency: NetworkLatencyModel,
        outbound_latency: NetworkLatencyModel,
        on_client_report: Optional[Callable[[ExecutionReport, int], None]] = None,
    ) -> None:
        self.inbound_latency = inbound_latency
        self.outbound_latency = outbound_latency
        self.on_client_report = on_client_report

        self.current_time_ns: int = 0
        self._event_queue: List[DiscreteEvent] = []
        self._event_counter: int = 0

        # Simulated exchange state
        self._resting_orders: Dict[int, OrderIntent] = {}
        self._order_id_counter: int = 1000

        # Reference market mid-price used to calculate execution slippage
        self.market_mid_price: float = 100.0

    def schedule_event(self, timestamp_ns: int, event_type: PacketType, payload: object) -> None:
        """Enqueue an event in the min-heap."""
        self._event_counter += 1
        heapq.heappush(
            self._event_queue,
            DiscreteEvent(
                timestamp_ns=timestamp_ns,
                priority=self._event_counter,
                event_type=event_type,
                payload=payload,
            ),
        )

    def submit_new_order(self, order: OrderIntent) -> None:
        """Client sends new order into inbound network wire."""
        transit_delay = self.inbound_latency.sample_delay_ns()
        arrival_at_exchange = order.client_timestamp_ns + transit_delay
        self.schedule_event(arrival_at_exchange, PacketType.NEW_ORDER, order)

    def submit_cancel_order(self, client_order_id: int, client_timestamp_ns: int) -> None:
        """Client sends cancel instruction into inbound network wire."""
        transit_delay = self.inbound_latency.sample_delay_ns()
        arrival_at_exchange = client_timestamp_ns + transit_delay
        self.schedule_event(arrival_at_exchange, PacketType.CANCEL_ORDER, client_order_id)

    def run_until(self, target_time_ns: int) -> None:
        """Step through scheduled events until target time is reached."""
        while self._event_queue and self._event_queue[0].timestamp_ns <= target_time_ns:
            event = heapq.heappop(self._event_queue)
            self.current_time_ns = event.timestamp_ns
            self._process_event(event)

        self.current_time_ns = target_time_ns

    def run_all(self) -> None:
        """Drain all queued events."""
        while self._event_queue:
            event = heapq.heappop(self._event_queue)
            self.current_time_ns = event.timestamp_ns
            self._process_event(event)

    def _process_event(self, event: DiscreteEvent) -> None:
        """Dispatch event handling based on packet type."""
        match event.event_type:
            case PacketType.NEW_ORDER:
                self._handle_exchange_new_order(event.payload)
            case PacketType.CANCEL_ORDER:
                self._handle_exchange_cancel_order(event.payload)
            case (
                PacketType.ORDER_ACK
                | PacketType.ORDER_FILL
                | PacketType.ORDER_CANCELLED
                | PacketType.ORDER_REJECTED
            ):
                self._handle_client_receive_report(event.payload)

    def _handle_exchange_new_order(self, order: OrderIntent) -> None:
        """Exchange gateway processes new order at current_time_ns."""
        exchange_id = self._order_id_counter
        self._order_id_counter += 1

        is_market_cross = (order.side == Side.BID and order.price >= self.market_mid_price) or (
            order.side == Side.ASK and order.price <= self.market_mid_price
        )

        if is_market_cross:
            report = ExecutionReport(
                client_order_id=order.client_order_id,
                exchange_order_id=exchange_id,
                status=OrderStatus.FILLED,
                fill_price=self.market_mid_price,
                fill_quantity=order.quantity,
                exchange_timestamp_ns=self.current_time_ns,
            )
            packet_type = PacketType.ORDER_FILL
        else:
            self._resting_orders[order.client_order_id] = order
            report = ExecutionReport(
                client_order_id=order.client_order_id,
                exchange_order_id=exchange_id,
                status=OrderStatus.ACCEPTED,
                fill_price=0.0,
                fill_quantity=0.0,
                exchange_timestamp_ns=self.current_time_ns,
            )
            packet_type = PacketType.ORDER_ACK

        outbound_delay = self.outbound_latency.sample_delay_ns()
        client_delivery_time = self.current_time_ns + outbound_delay
        self.schedule_event(client_delivery_time, packet_type, report)

    def _handle_exchange_cancel_order(self, client_order_id: int) -> None:
        """Exchange attempts to cancel order from resting book."""
        outbound_delay = self.outbound_latency.sample_delay_ns()
        client_delivery_time = self.current_time_ns + outbound_delay

        if client_order_id in self._resting_orders:
            del self._resting_orders[client_order_id]
            report = ExecutionReport(
                client_order_id=client_order_id,
                exchange_order_id=0,
                status=OrderStatus.CANCELLED,
                fill_price=0.0,
                fill_quantity=0.0,
                exchange_timestamp_ns=self.current_time_ns,
            )
            self.schedule_event(client_delivery_time, PacketType.ORDER_CANCELLED, report)
        else:
            report = ExecutionReport(
                client_order_id=client_order_id,
                exchange_order_id=0,
                status=OrderStatus.REJECTED,
                fill_price=0.0,
                fill_quantity=0.0,
                exchange_timestamp_ns=self.current_time_ns,
                reason="Order already filled or not found",
            )
            self.schedule_event(client_delivery_time, PacketType.ORDER_REJECTED, report)

    def _handle_client_receive_report(self, report: ExecutionReport) -> None:
        """Client strategy receives network packet at current_time_ns."""
        if self.on_client_report is not None:
            self.on_client_report(report, self.current_time_ns)
