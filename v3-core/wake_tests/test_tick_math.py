import decimal
import math
from decimal import Decimal

import pytest
from pytypes.contracts.test.TickMathTest import TickMathTest
from wake.testing import *

import wake_tests.utils as utils
from wake_tests.snapshots import match_snapshot
from wake_tests.utils import MAX_SQRT_RATIO, MIN_SQRT_RATIO

MIN_TICK = -887272
MAX_TICK = 887272

decimal.setcontext(decimal.Context(prec=500))


@pytest.fixture(scope="module")
def tick_math():
    default_chain.set_default_accounts(default_chain.accounts[0])
    tick_math = TickMathTest.deploy(from_=default_chain.accounts[0])

    return tick_math


@pytest.fixture(scope="module", autouse=True)
def chain():
    with default_chain.connect():
        yield default_chain


class TestGetSqrtRatioAtTick:
    def test_throws_too_low(self, tick_math):
        """
        throws for too low
        """
        with must_revert(Error("T")):
            tick_math.getSqrtRatioAtTick(MIN_TICK - 1)

    def test_throws_too_high(self, tick_math):
        """
        throws for too high
        """
        with must_revert(Error("T")):
            tick_math.getSqrtRatioAtTick(MAX_TICK + 1)

    def test_min_tick(self, tick_math):
        """
        min tick
        """
        assert tick_math.getSqrtRatioAtTick(MIN_TICK) == 4295128739

    def test_min_tick_plus_one(self, tick_math):
        """
        min tick + 1
        """
        assert tick_math.getSqrtRatioAtTick(MIN_TICK + 1) == 4295343490

    def test_max_tick_minus_one(self, tick_math):
        """
        max tick - 1
        """
        assert (
            tick_math.getSqrtRatioAtTick(MAX_TICK - 1)
            == 1461373636630004318706518188784493106690254656249
        )

    def test_min_tick_ratio_less_than_js(self, tick_math):
        """
        min tick ratio is less than js implementation
        """
        assert tick_math.getSqrtRatioAtTick(MIN_TICK) < utils.encode_price_sqrt(
            1, 2**127
        )

    def test_max_tick_ratio_greater_than_js(self, tick_math):
        """
        max tick ratio is greater than js implementation
        """
        assert tick_math.getSqrtRatioAtTick(MAX_TICK) > utils.encode_price_sqrt(
            2**127, 1
        )

    def test_max_tick(self, tick_math):
        """
        max tick
        """
        assert (
            tick_math.getSqrtRatioAtTick(MAX_TICK)
            == 1461446703485210103287273052203988822378723970342
        )

    @pytest.mark.parametrize(
        "tick",
        [
            -50,
            50,
            -100,
            100,
            -250,
            250,
            -500,
            500,
            -1000,
            1000,
            -2500,
            2500,
            -3000,
            3000,
            -4000,
            4000,
            -5000,
            5000,
            -50000,
            50000,
            -150000,
            150000,
            -250000,
            250000,
            -500000,
            500000,
            -738203,
            738203,
        ],
    )
    def test_tick_off_by_one(self, tick_math, tick):
        """
        tick is at most off by 1/100th of a bips
        """
        js_result = (1.0001**tick) ** 0.5 * 2**96
        result = tick_math.getSqrtRatioAtTick(tick)
        abs_diff = abs(Decimal(result) - Decimal(js_result))
        assert (abs_diff / Decimal(js_result)) < 0.000001

    @pytest.mark.parametrize(
        "tick",
        [
            -50,
            50,
            -100,
            100,
            -250,
            250,
            -500,
            500,
            -1000,
            1000,
            -2500,
            2500,
            -3000,
            3000,
            -4000,
            4000,
            -5000,
            5000,
            -50000,
            50000,
            -150000,
            150000,
            -250000,
            250000,
            -500000,
            500000,
            -738203,
            738203,
        ],
    )
    def test_tick_result(self, tick_math, tick):
        """
        result of tick
        """
        result = tick_math.getSqrtRatioAtTick(tick)
        match_snapshot(
            result,
            __file__,
            f"getSqrtRatioAtTick_tick_{tick}",
        )

    @pytest.mark.parametrize(
        "tick",
        [
            -50,
            50,
            -100,
            100,
            -250,
            250,
            -500,
            500,
            -1000,
            1000,
            -2500,
            2500,
            -3000,
            3000,
            -4000,
            4000,
            -5000,
            5000,
            -50000,
            50000,
            -150000,
            150000,
            -250000,
            250000,
            -500000,
            500000,
            -738203,
            738203,
        ],
    )
    def test_tick_gas(self, tick_math, tick):
        """
        gas cost of tick
        """
        match_snapshot(
            tick_math.getGasCostOfGetSqrtRatioAtTick(tick),
            __file__,
            f"getGasCostOfGetSqrtRatioAtTick_tick_{tick}",
        )

    def test_min_sqrt_ratio(self, tick_math):
        """
        equals #getSqrtRatioAtTick(MIN_TICK)
        """
        min_sqrt = tick_math.getSqrtRatioAtTick(MIN_TICK)
        assert min_sqrt == tick_math.MIN_SQRT_RATIO()
        assert min_sqrt == MIN_SQRT_RATIO

    def test_max_sqrt_ratio(self, tick_math):
        """
        equals #getSqrtRatioAtTick(MAX_TICK)
        """
        max_sqrt = tick_math.getSqrtRatioAtTick(MAX_TICK)
        assert max_sqrt == tick_math.MAX_SQRT_RATIO()
        assert max_sqrt == MAX_SQRT_RATIO


class TestGetTickAtSqrtRatio:
    def test_throws_too_low(self, tick_math):
        """
        throws for too low
        """
        with must_revert(Error("R")):
            tick_math.getTickAtSqrtRatio(MIN_SQRT_RATIO - 1)

    def test_throws_too_high(self, tick_math):
        """
        throws for too high
        """
        with must_revert(Error("R")):
            tick_math.getTickAtSqrtRatio(MAX_SQRT_RATIO)

    def test_ratio_min_tick(self, tick_math):
        """
        ratio of min tick
        """
        assert tick_math.getTickAtSqrtRatio(MIN_SQRT_RATIO) == MIN_TICK

    def test_ratio_min_tick_plus_one(self, tick_math):
        """
        ratio of min tick + 1
        """
        assert tick_math.getTickAtSqrtRatio(4295343490) == MIN_TICK + 1

    def test_ratio_max_tick_minus_one(self, tick_math):
        """
        ratio of max tick - 1
        """
        assert (
            tick_math.getTickAtSqrtRatio(
                1461373636630004318706518188784493106690254656249
            )
            == MAX_TICK - 1
        )

    def test_ratio_closest_max_tick(self, tick_math):
        """
        ratio closest to max tick
        """
        assert tick_math.getTickAtSqrtRatio(MAX_SQRT_RATIO - 1) == MAX_TICK - 1

    @pytest.mark.parametrize(
        "ratio",
        [
            MIN_SQRT_RATIO,
            utils.encode_price_sqrt(10**12, 1),
            utils.encode_price_sqrt(10**6, 1),
            utils.encode_price_sqrt(1, 64),
            utils.encode_price_sqrt(1, 8),
            utils.encode_price_sqrt(1, 2),
            utils.encode_price_sqrt(1, 1),
            utils.encode_price_sqrt(2, 1),
            utils.encode_price_sqrt(8, 1),
            utils.encode_price_sqrt(64, 1),
            utils.encode_price_sqrt(1, 10**6),
            utils.encode_price_sqrt(1, 10**12),
            MAX_SQRT_RATIO - 1,
        ],
    )
    def test_ratio_off_by_one(self, tick_math, ratio):
        """
        ratio is at most off by 1
        """
        js_result = math.floor(
            (
                math.log((Decimal(ratio) / (Decimal(2) ** Decimal(96))) ** Decimal(2))
                / math.log(Decimal(1.0001))
            )
        )
        result = tick_math.getTickAtSqrtRatio(ratio)
        abs_diff = abs((result) - (js_result))
        assert abs_diff <= 1

    @pytest.mark.parametrize(
        "ratio",
        [
            MIN_SQRT_RATIO,
            utils.encode_price_sqrt(10**12, 1),
            utils.encode_price_sqrt(10**6, 1),
            utils.encode_price_sqrt(1, 64),
            utils.encode_price_sqrt(1, 8),
            utils.encode_price_sqrt(1, 2),
            utils.encode_price_sqrt(1, 1),
            utils.encode_price_sqrt(2, 1),
            utils.encode_price_sqrt(8, 1),
            utils.encode_price_sqrt(64, 1),
            utils.encode_price_sqrt(1, 10**6),
            utils.encode_price_sqrt(1, 10**12),
            MAX_SQRT_RATIO - 1,
        ],
    )
    def test_ratio_between_tick_and_tick_plus_one(self, tick_math, ratio):
        """
        ratio is between the tick and tick+1
        """
        tick = tick_math.getTickAtSqrtRatio(ratio)
        ratio_of_tick = tick_math.getSqrtRatioAtTick(tick)
        ratio_of_tick_plus_one = tick_math.getSqrtRatioAtTick(tick + 1)
        assert ratio >= ratio_of_tick
        assert ratio < ratio_of_tick_plus_one

    @pytest.mark.parametrize(
        "ratio",
        [
            MIN_SQRT_RATIO,
            utils.encode_price_sqrt(10**12, 1),
            utils.encode_price_sqrt(10**6, 1),
            utils.encode_price_sqrt(1, 64),
            utils.encode_price_sqrt(1, 8),
            utils.encode_price_sqrt(1, 2),
            utils.encode_price_sqrt(1, 1),
            utils.encode_price_sqrt(2, 1),
            utils.encode_price_sqrt(8, 1),
            utils.encode_price_sqrt(64, 1),
            utils.encode_price_sqrt(1, 10**6),
            utils.encode_price_sqrt(1, 10**12),
            MAX_SQRT_RATIO - 1,
        ],
    )
    def test_ratio_result(self, tick_math, ratio):
        """
        ratio result
        """
        result = tick_math.getTickAtSqrtRatio(ratio)
        match_snapshot(
            result,
            __file__,
            f"getTickAtSqrtRatio_ratio_{ratio}",
        )

    @pytest.mark.parametrize(
        "ratio",
        [
            MIN_SQRT_RATIO,
            utils.encode_price_sqrt(10**12, 1),
            utils.encode_price_sqrt(10**6, 1),
            utils.encode_price_sqrt(1, 64),
            utils.encode_price_sqrt(1, 8),
            utils.encode_price_sqrt(1, 2),
            utils.encode_price_sqrt(1, 1),
            utils.encode_price_sqrt(2, 1),
            utils.encode_price_sqrt(8, 1),
            utils.encode_price_sqrt(64, 1),
            utils.encode_price_sqrt(1, 10**6),
            utils.encode_price_sqrt(1, 10**12),
            MAX_SQRT_RATIO - 1,
        ],
    )
    def test_ratio_gas(self, tick_math, ratio):
        """
        ratio gas cost
        """
        match_snapshot(
            tick_math.getGasCostOfGetTickAtSqrtRatio(ratio),
            __file__,
            f"getGasCostOfGetTickAtSqrtRatio_ratio_{ratio}",
        )
