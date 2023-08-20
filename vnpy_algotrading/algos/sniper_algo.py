from vnpy.trader.constant import Direction
from vnpy.trader.object import TradeData, OrderData, TickData
from vnpy.trader.engine import BaseEngine

from ..template import AlgoTemplate


class SniperAlgo(AlgoTemplate):
    """Sniper Algorithm Class"""

    display_name: str = "Sniper"

    default_setting: dict = {}

    variables: list = ["vt_orderid"]

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

        # Variables
        self.vt_orderid = ""

        self.put_event()

    def on_tick(self, tick: TickData) -> None:
        """Tick callback"""
        if self.vt_orderid:
            self.cancel_all()
            return

        if self.direction == Direction.LONG:
            if tick.ask_price_1 <= self.price:
                order_volume: float = self.volume - self.traded
                order_volume = min(order_volume, tick.ask_volume_1)

                self.vt_orderid = self.buy(self.price, order_volume, offset=self.offset)
        else:
            if tick.bid_price_1 >= self.price:
                order_volume: float = self.volume - self.traded
                order_volume = min(order_volume, tick.bid_volume_1)

                self.vt_orderid = self.sell(
                    self.price, order_volume, offset=self.offset
                )

        self.put_event()

    def on_order(self, order: OrderData) -> None:
        """Order callback"""
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
