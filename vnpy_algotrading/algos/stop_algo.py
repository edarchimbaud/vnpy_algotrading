from vnpy.trader.constant import Direction
from vnpy.trader.object import OrderData, TickData
from vnpy.trader.engine import BaseEngine

from ..template import AlgoTemplate


class StopAlgo(AlgoTemplate):
    """条件委托算法类"""

    display_name = "Stop 条件委托"

    default_setting = {
        "price_add": 0.0
    }

    variables = [
        "traded",
        "vt_orderid",
        "order_status",
    ]

    def __init__(
        self,
        algo_engine: BaseEngine,
        algo_name: str,
        vt_symbol: str,
        direction: str,
        offset: str,
        price: float,
        volume: float,
        setting: dict
    ):
        """"""
        super().__init__(algo_engine, algo_name, vt_symbol, direction, offset, price, volume, setting)

        # 参数
        self.price_add = setting["price_add"]

        # 变量
        self.vt_orderid = ""
        self.traded = 0
        self.order_status = ""

        self.put_parameters_event()
        self.put_variables_event()

    def on_tick(self, tick: TickData):
        """Tick行情回调"""
        if self.vt_orderid:
            return

        if self.direction == Direction.LONG:
            if tick.last_price >= self.price:
                price = self.price + self.price_add

                if tick.limit_up:
                    price = min(price, tick.limit_up)

                self.vt_orderid = self.buy(
                    price,
                    self.volume,
                    offset=self.offset
                )
                self.write_log(
                    f"停止单已触发，代码：{self.vt_symbol}，方向：{self.direction}, 价格：{self.price}，数量：{self.volume}，开平：{self.offset}")

        else:
            if tick.last_price <= self.price:
                price = self.price - self.price_add

                if tick.limit_down:
                    price = max(price, tick.limit_down)

                self.vt_orderid = self.sell(
                    price,
                    self.volume,
                    offset=self.offset
                )
                self.write_log(
                    f"停止单已触发，代码：{self.vt_symbol}，方向：{self.direction}, 价格：{self.price}，数量：{self.volume}，开平：{self.offset}")

        self.put_variables_event()

    def on_order(self, order: OrderData):
        """委托回调"""
        self.traded = order.traded
        self.order_status = order.status

        if not order.is_active():
            self.finish()
        self.put_variables_event()
