import dataclasses
import decimal
import math
from decimal import Decimal
from enum import IntEnum

from eth_abi.packed import encode_packed
from eth_utils import keccak
from pytypes.contracts.test.MockTimeUniswapV3Pool import MockTimeUniswapV3Pool
from pytypes.contracts.test.MockTimeUniswapV3PoolDeployer import \
    MockTimeUniswapV3PoolDeployer
from pytypes.contracts.test.TestERC20 import TestERC20
from pytypes.contracts.test.TestUniswapV3Callee import TestUniswapV3Callee
from pytypes.contracts.UniswapV3Factory import UniswapV3Factory
from woke.testing import *

decimal.setcontext(decimal.Context(prec=40))

MAX_UINT_256 = 2**256 - 1
MAX_UINT_128 = 2**128 - 1
MIN_SQRT_RATIO = 4295128739
MAX_SQRT_RATIO = 1461446703485210103287273052203988822378723970342
TEST_POOL_START_TIME = 1601906400


class FeeAmount(IntEnum):
    LOW = 500
    MEDIUM = 3000
    HIGH = 10000


class TickSpacings(IntEnum):
    LOW = 10
    MEDIUM = 60
    HIGH = 200


def get_min_tick(tick_spacing):
    return math.ceil(-887272 / tick_spacing) * tick_spacing


def get_max_tick(tick_spacing):
    return math.floor(887272 / tick_spacing) * tick_spacing


def get_max_liquidity_per_tick(tick_spacing):
    return Decimal(MAX_UINT_128) / int(
        (get_max_tick(tick_spacing) - get_min_tick(tick_spacing)) / tick_spacing + 1
    )


def expand_to_18_decimals(n):
    return n * 10**18


def encode_price_sqrt(reserve1, reserve0):
    return int(
        (Decimal.from_float(reserve1) / Decimal.from_float(reserve0)).sqrt() * 2**96
    )


def get_position_key(address: str, lower_tick: int, upper_tick: int) -> bytes:
    packed_data = encode_packed(
        ["address", "int24", "int24"], [address, lower_tick, upper_tick]
    )
    return keccak(packed_data)


def check_observation_equals(observation, expected_observation):
    assert dataclasses.asdict(observation) == dataclasses.asdict(expected_observation)


def check_tick_is_clear(pool, tick):
    tick_info = pool.ticks(tick)
    assert tick_info.liquidityGross == 0
    assert tick_info.feeGrowthOutside0X128 == 0
    assert tick_info.feeGrowthOutside1X128 == 0
    assert tick_info.liquidityNet == 0


def check_tick_is_not_clear(pool, tick):
    assert pool.ticks(tick).liquidityGross != 0


def create_pool(fee, tick_spacing, first_token, second_token, factory):
    mock_time_pool_deployer = MockTimeUniswapV3PoolDeployer.deploy(
        from_=default_chain.accounts[0]
    )
    tx = mock_time_pool_deployer.deploy_(
        factory.address,
        first_token.address,
        second_token.address,
        fee.value,
        tick_spacing.value,
        from_=default_chain.accounts[0],
    )

    return MockTimeUniswapV3Pool(tx.events[0].pool)


class PoolHelper:
    def __init__(
        self,
        token0: TestERC20,
        token1: TestERC20,
        factory: UniswapV3Factory,
        pool: MockTimeUniswapV3Pool,
        tick_spacing,
        swap_target: TestUniswapV3Callee,
    ):
        self.token0 = token0
        self.token1 = token1
        self.factory = factory
        self.swap_target = swap_target
        self.pool = pool
        self.tick_spacing = tick_spacing
        self.min_tick = get_min_tick(tick_spacing)
        self.max_tick = get_max_tick(tick_spacing)

    def swap(self, input_token, amount_in, amount_out, to, sqrt_price_limit_x96=None):
        exact_input = amount_out == 0
        method = None
        if input_token == self.token0:
            method = (
                self.swap_target.swapExact0For1
                if exact_input
                else self.swap_target.swap0ForExact1
            )
        else:
            method = (
                self.swap_target.swapExact1For0
                if exact_input
                else self.swap_target.swap1ForExact0
            )

        if sqrt_price_limit_x96 is None:
            sqrt_price_limit_x96 = (
                MIN_SQRT_RATIO + 1 if input_token == self.token0 else MAX_SQRT_RATIO - 1
            )
        input_token.approve(self.swap_target.address, MAX_UINT_256)
        to_address = to if isinstance(to, str) else to.address
        return method(
            self.pool.address,
            amount_in if exact_input else amount_out,
            to_address,
            sqrt_price_limit_x96,
        )

    def mint(self, recipient, tick_lower, tick_upper, liquidity):
        self.token0.approve(self.swap_target.address, MAX_UINT_256)
        self.token1.approve(self.swap_target.address, MAX_UINT_256)
        return self.swap_target.mint(
            self.pool.address, recipient, tick_lower, tick_upper, liquidity
        )

    def flash(self, amount0, amount1, to, pay0=None, pay1=None):
        fee = self.pool.fee()
        if pay0 is None:
            pay0 = (amount0 * fee + 10**6 - 1) // 10**6 + amount0
        if pay1 is None:
            pay1 = (amount1 * fee + 10**6 - 1) // 10**6 + amount1
        return self.swap_target.flash(
            self.pool.address,
            to if isinstance(to, str) else to.address,
            amount0,
            amount1,
            pay0,
            pay1,
        )

    def swap_to_sqrt_price(self, input_token, target_price, to):
        method = (
            self.swap_target.swapToLowerSqrtPrice
            if input_token == self.token0
            else self.swap_target.swapToHigherSqrtPrice
        )
        input_token.approve(self.swap_target.address, MAX_UINT_256)
        to_address = to if isinstance(to, str) else to.address
        return method(self.pool.address, target_price, to_address)

    def swap_to_lower_price(self, sqrt_price_x96, to):
        return self.swap_to_sqrt_price(self.token0, sqrt_price_x96, to)

    def swap_to_higher_price(self, sqrt_price_x96, to):
        return self.swap_to_sqrt_price(self.token1, sqrt_price_x96, to)

    def swap_exact_0_for_1(self, amount, to, sqrt_price_limit_x96=None):
        return self.swap(self.token0, amount, 0, to, sqrt_price_limit_x96)

    def swap_0_for_exact_1(self, amount, to, sqrt_price_limit_x96=None):
        return self.swap(self.token0, 0, amount, to, sqrt_price_limit_x96)

    def swap_exact_1_for_0(self, amount, to, sqrt_price_limit_x96=None):
        return self.swap(self.token1, amount, 0, to, sqrt_price_limit_x96)

    def swap_1_for_exact_0(self, amount, to, sqrt_price_limit_x96=None):
        return self.swap(self.token1, 0, amount, to, sqrt_price_limit_x96)
