from collections import defaultdict
from typing import Dict, List, Optional, Set, Type

from vnpy.event import EventEngine, Event
from vnpy.trader.engine import BaseEngine, MainEngine
from vnpy.trader.event import EVENT_TICK, EVENT_TIMER, EVENT_ORDER, EVENT_TRADE
from vnpy.trader.constant import Direction, Offset, OrderType, Exchange
from vnpy.trader.object import (
    SubscribeRequest,
    OrderRequest,
    LogData,
    ContractData,
    OrderData,
    TickData,
    TradeData,
    CancelRequest,
)
from vnpy.trader.utility import round_to

from .template import AlgoTemplate
from .base import EVENT_ALGO_LOG, EVENT_ALGO_UPDATE, APP_NAME, AlgoStatus


class AlgoEngine(BaseEngine):
    """Algorithmic engine"""

    def __init__(self, main_engine: MainEngine, event_engine: EventEngine) -> None:
        """Constructor"""
        super().__init__(main_engine, event_engine, APP_NAME)

        self.algo_templates: Dict[str, Type[AlgoTemplate]] = {}

        self.algos: Dict[str, AlgoTemplate] = {}
        self.symbol_algo_map: Dict[str, Set[AlgoTemplate]] = defaultdict(set)
        self.orderid_algo_map: Dict[str, AlgoTemplate] = {}

        self.load_algo_template()
        self.register_event()

    def init_engine(self) -> None:
        """Initializing the engine"""
        self.write_log("Algorithmic trading engine started")

    def close(self) -> None:
        """Shut down the engine"""
        self.stop_all()

    def load_algo_template(self) -> None:
        """Load algorithm class"""
        from .algos.twap_algo import TwapAlgo
        from .algos.iceberg_algo import IcebergAlgo
        from .algos.sniper_algo import SniperAlgo
        from .algos.stop_algo import StopAlgo
        from .algos.best_limit_algo import BestLimitAlgo

        self.add_algo_template(TwapAlgo)
        self.add_algo_template(IcebergAlgo)
        self.add_algo_template(SniperAlgo)
        self.add_algo_template(StopAlgo)
        self.add_algo_template(BestLimitAlgo)

    def add_algo_template(self, template: AlgoTemplate) -> None:
        """Add Algorithm class"""
        self.algo_templates[template.__name__] = template

    def get_algo_template(self) -> dict:
        """Get Algorithm class"""
        return self.algo_templates

    def register_event(self) -> None:
        """Registering event listeners"""
        self.event_engine.register(EVENT_TICK, self.process_tick_event)
        self.event_engine.register(EVENT_TIMER, self.process_timer_event)
        self.event_engine.register(EVENT_ORDER, self.process_order_event)
        self.event_engine.register(EVENT_TRADE, self.process_trade_event)

    def process_tick_event(self, event: Event) -> None:
        """Handling of market events"""
        tick: TickData = event.data
        algos: Set[AlgoTemplate] = self.symbol_algo_map[tick.vt_symbol]

        for algo in algos:
            algo.update_tick(tick)

    def process_timer_event(self, event: Event) -> None:
        """Handling timed events"""
        # Generating lists to avoid dictionary changes
        algos: List[AlgoTemplate] = list(self.algos.values())

        for algo in algos:
            algo.update_timer()

    def process_trade_event(self, event: Event) -> None:
        """Handling of closing events"""
        trade: TradeData = event.data

        algo: Optional[AlgoTemplate] = self.orderid_algo_map.get(trade.vt_orderid, None)
        if algo:
            algo.update_trade(trade)

    def process_order_event(self, event: Event) -> None:
        """Handling order events"""
        order: OrderData = event.data

        algo: Optional[AlgoTemplate] = self.orderid_algo_map.get(order.vt_orderid, None)
        if algo:
            algo.update_order(order)

    def start_algo(
        self,
        template_name: str,
        vt_symbol: str,
        direction: Direction,
        offset: Offset,
        price: float,
        volume: int,
        setting: dict,
    ) -> str:
        """Start the algorithm"""
        contract: Optional[ContractData] = self.main_engine.get_contract(vt_symbol)
        if not contract:
            self.write_log(
                f"The algorithm failed to start and the contract could not be found: {vt_symbol}"
            )
            return ""

        algo_template: AlgoTemplate = self.algo_templates[template_name]

        # Creating an Algorithm example
        algo_template._count += 1
        algo_name: str = f"{algo_template.__name__}_{algo_template._count}"
        algo: AlgoTemplate = algo_template(
            self, algo_name, vt_symbol, direction, offset, price, volume, setting
        )

        # Subscribe to quotes
        algos: set = self.symbol_algo_map[algo.vt_symbol]
        if not algos:
            self.subscribe(contract.symbol, contract.exchange, contract.gateway_name)
        algos.add(algo)

        # Start the algorithm
        algo.start()
        self.algos[algo_name] = algo

        return algo_name

    def pause_algo(self, algo_name: str) -> None:
        """Pause the algorithm"""
        algo: Optional[AlgoTemplate] = self.algos.get(algo_name, None)
        if algo:
            algo.pause()

    def resume_algo(self, algo_name: str) -> None:
        """Resume the algorithm"""
        algo: Optional[AlgoTemplate] = self.algos.get(algo_name, None)
        if algo:
            algo.resume()

    def stop_algo(self, algo_name: str) -> None:
        """Stop the algorithm"""
        algo: Optional[AlgoTemplate] = self.algos.get(algo_name, None)
        if algo:
            algo.stop()

    def stop_all(self) -> None:
        """Stop all algorithms"""
        for algo_name in list(self.algos.keys()):
            self.stop_algo(algo_name)

    def subscribe(self, symbol: str, exchange: Exchange, gateway_name: str) -> None:
        """Subscribe to quotes"""
        req: SubscribeRequest = SubscribeRequest(symbol=symbol, exchange=exchange)
        self.main_engine.subscribe(req, gateway_name)

    def send_order(
        self,
        algo: AlgoTemplate,
        direction: Direction,
        price: float,
        volume: float,
        order_type: OrderType,
        offset: Offset,
    ) -> str:
        """Place an order"""
        contract: Optional[ContractData] = self.main_engine.get_contract(algo.vt_symbol)
        volume: float = round_to(volume, contract.min_volume)
        if not volume:
            return ""

        req: OrderRequest = OrderRequest(
            symbol=contract.symbol,
            exchange=contract.exchange,
            direction=direction,
            type=order_type,
            volume=volume,
            price=price,
            offset=offset,
            reference=f"{APP_NAME}_{algo.algo_name}",
        )
        vt_orderid: str = self.main_engine.send_order(req, contract.gateway_name)

        self.orderid_algo_map[vt_orderid] = algo
        return vt_orderid

    def cancel_order(self, algo: AlgoTemplate, vt_orderid: str) -> None:
        """Cancel the order"""
        order: Optional[OrderData] = self.main_engine.get_order(vt_orderid)

        if not order:
            self.write_log(
                f"Order cancellation failed and the order could not be found:{vt_orderid}",
                algo,
            )
            return

        req: CancelRequest = order.create_cancel_request()
        self.main_engine.cancel_order(req, order.gateway_name)

    def get_tick(self, algo: AlgoTemplate) -> Optional[TickData]:
        """Get tick"""
        tick: Optional[TickData] = self.main_engine.get_tick(algo.vt_symbol)

        if not tick:
            self.write_log(
                f"Failed to query the ticker, the ticker could not be found:{algo.vt_symbol}",
                algo,
            )

        return tick

    def get_contract(self, algo: AlgoTemplate) -> Optional[ContractData]:
        """Get contract"""
        contract: Optional[ContractData] = self.main_engine.get_contract(algo.vt_symbol)

        if not contract:
            self.write_log(
                f"Failed to get contract, contract not found: {algo.vt_symbol}", algo
            )

        return contract

    def write_log(self, msg: str, algo: AlgoTemplate = None) -> None:
        """Output log"""
        if algo:
            msg: str = f"{algo.algo_name}：{msg}"

        log: LogData = LogData(msg=msg, gateway_name=APP_NAME)
        event: Event = Event(EVENT_ALGO_LOG, data=log)
        self.event_engine.put(event)

    def put_algo_event(self, algo: AlgoTemplate, data: dict) -> None:
        """Push Updates"""
        # Remove end-of-run algorithm instances
        if algo in self.algos.values() and algo.status in [
            AlgoStatus.STOPPED,
            AlgoStatus.FINISHED,
        ]:
            self.algos.pop(algo.algo_name)

            for algos in self.symbol_algo_map.values():
                if algo in algos:
                    algos.remove(algo)

        event: Event = Event(EVENT_ALGO_UPDATE, data)
        self.event_engine.put(event)
