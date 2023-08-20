from vnpy.trader.constant import Direction
from vnpy.trader.object import TradeData, OrderData, TickData
from vnpy.trader.engine import BaseEngine

from ..template import AlgoTemplate


class IcebergAlgo(AlgoTemplate):
    """"Iceberg algorithm class""" ""

    display_name: str = "Iceberg"

    default_setting: dict = {"display_volume": 0.0, "interval": 0}

    variables: list = ["timer_count", "vt_orderid"]

    def __init__(
        self,
        algo_engine: BaseEngine,
        algo_name: str,
        vt_symbol: str,
        direction: str,
        offset: str,
        price: float,
        volume: float,
        setting: dict,
    ) -> None:
        """Constructor"""
        super().__init__(
            algo_engine, algo_name, vt_symbol, direction, offset, price, volume, setting
        )

        # Parameters
        self.display_volume: float = setting["display_volume"]
        self.interval: int = setting["interval"]

        # Variables
        self.timer_count: int = 0
        self.vt_orderid: str = ""

        self.put_event()

    def on_order(self, order: OrderData) -> None:
        """Order callback"""
        msg: str = (
            f"Order number: {order.vt_orderid}, order status: {order.status.value}"
        )
        self.write_log(msg)

        if not order.is_active():
            self.vt_orderid = ""
            self.put_event()

    def on_trade(self, trade: TradeData) -> None:
        """Trade callback"""
        if self.traded >= self.volume:
            self.write_log(
                f"Traded quantity: {self.traded}, total quantity: {self.volume}"
            )
            self.finish()
        else:
            self.put_event()

    def on_timer(self) -> None:
        """Timing callback"""
        self.timer_count += 1

        if self.timer_count < self.interval:
            self.put_event()
            return

        self.timer_count = 0

        tick: TickData = self.get_tick()
        if not tick:
            return

        # When the order is complete, initiate a new order
        if not self.vt_orderid:
            order_volume: float = self.volume - self.traded
            order_volume = min(order_volume, self.display_volume)

            if self.direction == Direction.LONG:
                self.vt_orderid = self.buy(self.price, order_volume, offset=self.offset)
            else:
                self.vt_orderid = self.sell(
                    self.price, order_volume, offset=self.offset
                )
        # Otherwise check cancelation
        else:
            if self.direction == Direction.LONG:
                if tick.ask_price_1 <= self.price:
                    self.cancel_order(self.vt_orderid)
                    self.vt_orderid = ""
                    self.write_log(
                        "Latest Tick sell one price, lower than the buy commission price, the previous commission may be lost, forced to cancel the order"
                    )
            else:
                if tick.bid_price_1 >= self.price:
                    self.cancel_order(self.vt_orderid)
                    self.vt_orderid = ""
                    self.write_log(
                        "Latest Tick buy one price, higher than the sell order price, the previous order may be lost, forced to cancel the order"
                    )

        self.put_event()
