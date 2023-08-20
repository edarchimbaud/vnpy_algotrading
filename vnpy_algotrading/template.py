from typing import Dict, Optional, TYPE_CHECKING

from vnpy.trader.engine import BaseEngine
from vnpy.trader.object import TickData, OrderData, TradeData, ContractData
from vnpy.trader.constant import OrderType, Offset, Direction
from vnpy.trader.utility import virtual

from .base import AlgoStatus

if TYPE_CHECKING:
    from .engine import AlgoEngine


class AlgoTemplate:
    """Algorithm template"""

    _count: int = 0  # 实例计数

    display_name: str = ""  # display name
    default_setting: dict = {}  # default parameters
    variables: list = []  # variable names

    def __init__(
        self,
        algo_engine: "AlgoEngine",
        algo_name: str,
        vt_symbol: str,
        direction: Direction,
        offset: Offset,
        price: float,
        volume: int,
        setting: dict,
    ) -> None:
        """Constructor"""
        self.algo_engine: BaseEngine = algo_engine
        self.algo_name: str = algo_name

        self.vt_symbol: str = vt_symbol
        self.direction: Direction = direction
        self.offset: Offset = offset
        self.price: float = price
        self.volume: int = volume

        self.status: AlgoStatus = AlgoStatus.PAUSED
        self.traded: float = 0
        self.traded_price: float = 0

        self.active_orders: Dict[str, OrderData] = {}  # vt_orderid:order

    def update_tick(self, tick: TickData) -> None:
        """Update tick"""
        if self.status == AlgoStatus.RUNNING:
            self.on_tick(tick)

    def update_order(self, order: OrderData) -> None:
        """Update order"""
        if order.is_active():
            self.active_orders[order.vt_orderid] = order
        elif order.vt_orderid in self.active_orders:
            self.active_orders.pop(order.vt_orderid)

        self.on_order(order)

    def update_trade(self, trade: TradeData) -> None:
        """Update trade"""
        cost: float = self.traded_price * self.traded + trade.price * trade.volume
        self.traded += trade.volume
        self.traded_price = cost / self.traded

        self.on_trade(trade)

    def update_timer(self) -> None:
        """Update timer"""
        if self.status == AlgoStatus.RUNNING:
            self.on_timer()

    @virtual
    def on_tick(self, tick: TickData) -> None:
        """Tick callback"""
        pass

    @virtual
    def on_order(self, order: OrderData) -> None:
        """Order callback"""
        pass

    @virtual
    def on_trade(self, trade: TradeData) -> None:
        """Trade callback"""
        pass

    @virtual
    def on_timer(self) -> None:
        """Timer callback"""
        pass

    def start(self) -> None:
        """Start"""
        self.status = AlgoStatus.RUNNING
        self.put_event()

        self.write_log("Algorithm started")

    def stop(self) -> None:
        """Stop"""
        self.status = AlgoStatus.STOPPED
        self.cancel_all()
        self.put_event()

        self.write_log("Algorithm stopped")

    def finish(self) -> None:
        """Finish"""
        self.status = AlgoStatus.FINISHED
        self.cancel_all()
        self.put_event()

        self.write_log("Algorithm ended")

    def pause(self) -> None:
        """Pause"""
        self.status = AlgoStatus.PAUSED
        self.put_event()

        self.write_log("Algorithm paused")

    def resume(self) -> None:
        """Resume"""
        self.status = AlgoStatus.RUNNING
        self.put_event()

        self.write_log("Algorithm resumed")

    def buy(
        self,
        price: float,
        volume: float,
        order_type: OrderType = OrderType.LIMIT,
        offset: Offset = Offset.NONE,
    ) -> None:
        """"Buy""" ""
        if self.status != AlgoStatus.RUNNING:
            return

        msg: str = f"{self.vt_symbol}, buy {order_type.value}, {volume}@{price}"
        self.write_log(msg)

        return self.algo_engine.send_order(
            self, Direction.LONG, price, volume, order_type, offset
        )

    def sell(
        self,
        price: float,
        volume: float,
        order_type: OrderType = OrderType.LIMIT,
        offset: Offset = Offset.NONE,
    ) -> None:
        """Sell"""
        if self.status != AlgoStatus.RUNNING:
            return

        msg: str = f"{self.vt_symbol}, sell {order_type.value}, {volume}@{price}"
        self.write_log(msg)

        return self.algo_engine.send_order(
            self, Direction.SHORT, price, volume, order_type, offset
        )

    def cancel_order(self, vt_orderid: str) -> None:
        """Cancel order"""
        self.algo_engine.cancel_order(self, vt_orderid)

    def cancel_all(self) -> None:
        """Cancel all orders"""
        if not self.active_orders:
            return

        for vt_orderid in self.active_orders.keys():
            self.cancel_order(vt_orderid)

    def get_tick(self) -> Optional[TickData]:
        """Get latest tick"""
        return self.algo_engine.get_tick(self)

    def get_contract(self) -> Optional[ContractData]:
        """Get contract"""
        return self.algo_engine.get_contract(self)

    def get_parameters(self) -> dict:
        """Getting algo parameters"""
        strategy_parameters: dict = {}
        for name in self.default_setting.keys():
            strategy_parameters[name] = getattr(self, name)
        return strategy_parameters

    def get_variables(self) -> dict:
        """Getting the algo variables"""
        strategy_variables: dict = {}
        for name in self.variables:
            strategy_variables[name] = getattr(self, name)
        return strategy_variables

    def get_data(self) -> dict:
        """Getting algo information"""
        algo_data: dict = {
            "algo_name": self.algo_name,
            "vt_symbol": self.vt_symbol,
            "direction": self.direction,
            "offset": self.offset,
            "price": self.price,
            "volume": self.volume,
            "status": self.status,
            "traded": self.traded,
            "left": self.volume - self.traded,
            "traded_price": self.traded_price,
            "parameters": self.get_parameters(),
            "variables": self.get_variables(),
        }
        return algo_data

    def write_log(self, msg: str) -> None:
        """Output logs"""
        self.algo_engine.write_log(msg, self)

    def put_event(self) -> None:
        """Push update"""
        data: dict = self.get_data()
        self.algo_engine.put_algo_event(self, data)
