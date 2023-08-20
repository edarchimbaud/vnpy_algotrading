from random import uniform

from vnpy.trader.constant import Direction
from vnpy.trader.object import TradeData, OrderData, TickData
from vnpy.trader.engine import BaseEngine

from ..template import AlgoTemplate


class BestLimitAlgo(AlgoTemplate):
    """Class of Best Limit Algo"""

    display_name: str = "BestLimit"

    default_setting: dict = {
        "min_volume": 0,
        "max_volume": 0,
    }

    variables: list = ["vt_orderid", "order_price"]

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
        self.min_volume: float = setting["min_volume"]
        self.max_volume: float = setting["max_volume"]

        # Variables
        self.vt_orderid: str = ""
        self.order_price: float = 0

        self.put_event()

        # Check Maximum/Minimum Pending Order Volume
        if self.min_volume <= 0:
            self.write_log(
                "Minimum pending order must be greater than 0, algorithm failed to start"
            )
            self.finish()
            return

        if self.max_volume < self.min_volume:
            self.write_log(
                "Maximum pending order volume must not be less than minimum commission volume, algorithm startup fails"
            )
            self.finish()
            return

    def on_tick(self, tick: TickData) -> None:
        """Tick callback"""
        if self.direction == Direction.LONG:
            if not self.vt_orderid:
                self.buy_best_limit(tick.bid_price_1)
            elif self.order_price != tick.bid_price_1:
                self.cancel_all()
        else:
            if not self.vt_orderid:
                self.sell_best_limit(tick.ask_price_1)
            elif self.order_price != tick.ask_price_1:
                self.cancel_all()

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

    def on_order(self, order: OrderData) -> None:
        """Order callback"""
        if not order.is_active():
            self.vt_orderid = ""
            self.order_price = 0
            self.put_event()

    def buy_best_limit(self, bid_price_1: float) -> None:
        """Buy at the best price"""
        volume_left: float = self.volume - self.traded

        rand_volume: int = self.generate_rand_volume()
        order_volume: float = min(rand_volume, volume_left)

        self.order_price = bid_price_1
        self.vt_orderid = self.buy(self.order_price, order_volume, offset=self.offset)

    def sell_best_limit(self, ask_price_1: float) -> None:
        """Sell at the best price"""
        volume_left: float = self.volume - self.traded

        rand_volume: int = self.generate_rand_volume()
        order_volume: float = min(rand_volume, volume_left)

        self.order_price = ask_price_1
        self.vt_orderid = self.sell(self.order_price, order_volume, offset=self.offset)

    def generate_rand_volume(self) -> int:
        """Randomly generate the order quantity"""
        rand_volume: float = uniform(self.min_volume, self.max_volume)
        return int(rand_volume)
