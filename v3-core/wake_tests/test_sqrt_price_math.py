import pytest
from pytypes.contracts.test.SqrtPriceMathTest import SqrtPriceMathTest
from wake.testing import *

import wake_tests.utils as utils
from wake_tests.snapshots import match_snapshot
from wake_tests.utils import MAX_UINT_128, MAX_UINT_256


@pytest.fixture(scope="module")
def sqrt_price_math():
    default_chain.set_default_accounts(default_chain.accounts[0])
    sqrt_price_math = SqrtPriceMathTest.deploy(from_=default_chain.accounts[0])

    return sqrt_price_math


@pytest.fixture(scope="module", autouse=True)
def chain():
    with default_chain.connect():
        yield default_chain


class TestGetNextSqrtPriceFromInput:
    def test_zero_price(self, sqrt_price_math):
        """
        fails if price is zero
        """
        with must_revert():
            sqrt_price_math.getNextSqrtPriceFromInput(
                0, 0, int(utils.expand_to_18_decimals(1) / 10), False
            )

    def test_zero_liquidity(self, sqrt_price_math):
        """
        fails if liquidity is zero
        """
        with must_revert():
            sqrt_price_math.getNextSqrtPriceFromInput(
                1, 0, int(utils.expand_to_18_decimals(1) / 10), True
            )

    def test_overflow_price(self, sqrt_price_math):
        """
        fails if input amount overflows the price
        """
        price = 2**160 - 1
        liquidity = 1024
        amount_in = 1024
        with must_revert():
            sqrt_price_math.getNextSqrtPriceFromInput(
                price, liquidity, amount_in, False
            )

    def test_underflow_price(self, sqrt_price_math):
        """
        any input amount cannot underflow the price
        """
        price = 1
        liquidity = 1
        amount_in = 2**255
        assert (
            sqrt_price_math.getNextSqrtPriceFromInput(price, liquidity, amount_in, True)
            == 1
        )

    def test_zero_amount_in_zero_for_one_true(self, sqrt_price_math):
        """
        returns input price if amount in is zero and zeroForOne = true
        """
        price = utils.encode_price_sqrt(1, 1)
        assert (
            sqrt_price_math.getNextSqrtPriceFromInput(
                price, int(utils.expand_to_18_decimals(1) / 10), 0, True
            )
            == price
        )

    def test_zero_amount_in_zero_for_one_false(self, sqrt_price_math):
        """
        returns input price if amount in is zero and zeroForOne = false
        """
        price = utils.encode_price_sqrt(1, 1)
        assert (
            sqrt_price_math.getNextSqrtPriceFromInput(
                price, int(utils.expand_to_18_decimals(1) / 10), 0, False
            )
            == price
        )

    def test_input_max_inputs(self, sqrt_price_math):
        """
        returns the minimum price for max inputs
        """
        sqrt_p = 2**160 - 1
        liquidity = MAX_UINT_128
        # had to sub 1 because of rounding vs ethers BigNumber
        max_amount_no_overflow = MAX_UINT_256 - int((liquidity << 96) / sqrt_p - 1)
        assert (
            sqrt_price_math.getNextSqrtPriceFromInput(
                sqrt_p, liquidity, max_amount_no_overflow, True
            )
            == 1
        )

    def test_small_input_amount_token1(self, sqrt_price_math):
        """
        input amount of 0.1 token1
        """
        assert (
            sqrt_price_math.getNextSqrtPriceFromInput(
                utils.encode_price_sqrt(1, 1),
                utils.expand_to_18_decimals(1),
                int(utils.expand_to_18_decimals(1) / 10),
                False,
            )
            == 87150978765690771352898345369
        )

    def test_small_input_amount_token0(self, sqrt_price_math):
        """
        input amount of 0.1 token0
        """
        assert (
            sqrt_price_math.getNextSqrtPriceFromInput(
                utils.encode_price_sqrt(1, 1),
                utils.expand_to_18_decimals(1),
                int(utils.expand_to_18_decimals(1) / 10),
                True,
            )
            == 72025602285694852357767227579
        )

    def test_large_liquidity_ten(self, sqrt_price_math):
        """
        amountIn > type(uint96).max and zeroForOne = true
        """
        assert (
            sqrt_price_math.getNextSqrtPriceFromInput(
                utils.encode_price_sqrt(1, 1),
                utils.expand_to_18_decimals(10),
                2**100,
                True,
            )
            == 624999999995069620
        )

    def test_half_max_uint_256(self, sqrt_price_math):
        """
        can return 1 with enough amountIn and zeroForOne = true
        """
        assert (
            sqrt_price_math.getNextSqrtPriceFromInput(
                utils.encode_price_sqrt(1, 1), 1, int(MAX_UINT_256 / 2), True
            )
            == 1
        )

    def test_zero_for_one_true_gas(self, sqrt_price_math):
        """
        zeroForOne = true gas
        """
        match_snapshot(
            sqrt_price_math.getGasCostOfGetNextSqrtPriceFromInput(
                utils.encode_price_sqrt(1, 1),
                utils.expand_to_18_decimals(1),
                int(utils.expand_to_18_decimals(1) / 10),
                True,
            ),
            __file__,
            "getGasCostOfGetNextSqrtPriceFromInput_test_zero_for_one_true_gas",
        )

    def test_zero_for_one_false_gas(self, sqrt_price_math):
        """
        zeroForOne = false gas
        """
        match_snapshot(
            sqrt_price_math.getGasCostOfGetNextSqrtPriceFromInput(
                utils.encode_price_sqrt(1, 1),
                utils.expand_to_18_decimals(1),
                int(utils.expand_to_18_decimals(1) / 10),
                False,
            ),
            __file__,
            "getGasCostOfGetNextSqrtPriceFromInput_test_zero_for_one_false_gas",
        )


class TestGetNextSqrtPriceFromOutput(object):
    def test_zero_price(self, sqrt_price_math):
        """
        fails if price is zero
        """
        with must_revert():
            sqrt_price_math.getNextSqrtPriceFromOutput(
                0, 0, int(utils.expand_to_18_decimals(1) / 10), False
            )

    def test_zero_liquidity(self, sqrt_price_math):
        """
        fails if liquidity is zero
        """
        with must_revert():
            sqrt_price_math.getNextSqrtPriceFromOutput(
                1, 0, int(utils.expand_to_18_decimals(1) / 10), True
            )

    def test_virtual_reserves_token0(self, sqrt_price_math):
        """
        fails if output amount is exactly the virtual reserves of token0
        """
        price = 20282409603651670423947251286016
        liquidity = 1024
        amount_out = 4
        with must_revert():
            sqrt_price_math.getNextSqrtPriceFromOutput(
                price, liquidity, amount_out, False
            )

    def test_greater_than_virtual_reserves_token0(self, sqrt_price_math):
        """
        fails if output amount is greater than virtual reserves of token0
        """
        price = 20282409603651670423947251286016
        liquidity = 1024
        amount_out = 5
        with must_revert():
            sqrt_price_math.getNextSqrtPriceFromOutput(
                price, liquidity, amount_out, False
            )

    def test_greater_than_virtual_reserves_token1(self, sqrt_price_math):
        """
        fails if output amount is greater than virtual reserves of token1
        """
        price = 20282409603651670423947251286016
        liquidity = 1024
        amount_out = 262145
        with must_revert():
            sqrt_price_math.getNextSqrtPriceFromOutput(
                price, liquidity, amount_out, True
            )

    def test_virtual_reserves_token1(self, sqrt_price_math):
        """
        fails if output amount is exactly the virtual reserves of token1
        """
        price = 20282409603651670423947251286016
        liquidity = 1024
        amount_out = 262144
        with must_revert():
            sqrt_price_math.getNextSqrtPriceFromOutput(
                price, liquidity, amount_out, True
            )

    def test_just_less_than_virtual_reserves_token1(self, sqrt_price_math):
        """
        succeeds if output amount is just less than the virtual reserves of token1
        """
        price = 20282409603651670423947251286016
        liquidity = 1024
        amount_out = 262143
        sqrtQ = sqrt_price_math.getNextSqrtPriceFromOutput(
            price, liquidity, amount_out, True
        )
        assert sqrtQ == 77371252455336267181195264

    def test_puzzling_echidna(self, sqrt_price_math):
        """
        puzzling echidna test
        """
        price = 20282409603651670423947251286016
        liquidity = 1024
        amount_out = 4
        with must_revert():
            sqrt_price_math.getNextSqrtPriceFromOutput(
                price, liquidity, amount_out, False
            )

    def test_zero_amount_in_zero_for_one(self, sqrt_price_math):
        """
        returns input price if amount in is zero and zeroForOne = true
        """
        price = utils.encode_price_sqrt(1, 1)
        assert (
            sqrt_price_math.getNextSqrtPriceFromOutput(
                price, int(utils.expand_to_18_decimals(1) / 10), 0, True
            )
            == price
        )

    def test_zero_amount_in_one_for_zero(self, sqrt_price_math):
        """
        returns input price if amount in is zero and zeroForOne = false
        """
        price = utils.encode_price_sqrt(1, 1)
        assert (
            sqrt_price_math.getNextSqrtPriceFromOutput(
                price, int(utils.expand_to_18_decimals(1) / 10), 0, False
            )
            == price
        )

    def test_output_amount_of_01_token1(self, sqrt_price_math):
        """
        output amount of 0.1 token1
        """
        sqrtQ = sqrt_price_math.getNextSqrtPriceFromOutput(
            utils.encode_price_sqrt(1, 1),
            utils.expand_to_18_decimals(1),
            int(utils.expand_to_18_decimals(1) / 10),
            False,
        )
        assert sqrtQ == 88031291682515930659493278152

    def test_output_amount_of_01_token2(self, sqrt_price_math):
        """
        output amount of 0.1 token1
        """
        sqrtQ = sqrt_price_math.getNextSqrtPriceFromOutput(
            utils.encode_price_sqrt(1, 1),
            utils.expand_to_18_decimals(1),
            int(utils.expand_to_18_decimals(1) / 10),
            True,
        )
        assert sqrtQ == 71305346262837903834189555302

    def test_impossible_amount_out_zero_for_one(self, sqrt_price_math):
        """
        reverts if amountOut is impossible in zero for one direction
        """
        with must_revert():
            sqrt_price_math.getNextSqrtPriceFromOutput(
                utils.encode_price_sqrt(1, 1), 1, MAX_UINT_256, True
            )

    def test_impossible_amount_out_one_for_zero(self, sqrt_price_math):
        """
        reverts if amountOut is impossible in one for zero direction
        """
        with must_revert():
            sqrt_price_math.getNextSqrtPriceFromOutput(
                utils.encode_price_sqrt(1, 1), 1, MAX_UINT_256, False
            )

    def test_zero_for_one_true_gas(self, sqrt_price_math):
        """
        gas cost for getNextSqrtPriceFromOutput where zeroForOne = true
        """
        match_snapshot(
            sqrt_price_math.getGasCostOfGetNextSqrtPriceFromOutput(
                utils.encode_price_sqrt(1, 1),
                utils.expand_to_18_decimals(1),
                int(utils.expand_to_18_decimals(1) / 10),
                True,
            ),
            __file__,
            "getGasCostOfGetNextSqrtPriceFromOutput_test_zero_for_one_true_gas",
        )

    def test_zero_for_one_false_gas(self, sqrt_price_math):
        """
        gas cost for getNextSqrtPriceFromOutput where zeroForOne = false
        """
        match_snapshot(
            sqrt_price_math.getGasCostOfGetNextSqrtPriceFromOutput(
                utils.encode_price_sqrt(1, 1),
                utils.expand_to_18_decimals(1),
                int(utils.expand_to_18_decimals(1) / 10),
                False,
            ),
            __file__,
            "getGasCostOfGetNextSqrtPriceFromOutput_test_zero_for_one_false_gas",
        )


class TestGetAmount0Delta(object):
    def test_zero_liquidity(self, sqrt_price_math):
        """
        returns 0 if liquidity is 0
        """
        amount0 = sqrt_price_math.getAmount0Delta(
            utils.encode_price_sqrt(1, 1), utils.encode_price_sqrt(2, 1), 0, True
        )
        assert amount0 == 0

    def test_equal_prices(self, sqrt_price_math):
        """
        returns 0 if prices are equal
        """
        amount0 = sqrt_price_math.getAmount0Delta(
            utils.encode_price_sqrt(1, 1), utils.encode_price_sqrt(1, 1), 0, True
        )
        assert amount0 == 0

    def test_price_1_to_1_21(self, sqrt_price_math):
        """
        returns 0.1 amount1 for price of 1 to 1.21
        """
        amount0 = sqrt_price_math.getAmount0Delta(
            utils.encode_price_sqrt(1, 1),
            utils.encode_price_sqrt(121, 100),
            utils.expand_to_18_decimals(1),
            True,
        )
        assert amount0 == 90909090909090910

        amount0_rounded_down = sqrt_price_math.getAmount0Delta(
            utils.encode_price_sqrt(1, 1),
            utils.encode_price_sqrt(121, 100),
            utils.expand_to_18_decimals(1),
            False,
        )
        assert amount0_rounded_down == amount0 - 1

    def test_overflow_prices(self, sqrt_price_math):
        """
        works for prices that overflow
        """
        amount0_up = sqrt_price_math.getAmount0Delta(
            utils.encode_price_sqrt(2**90, 1),
            utils.encode_price_sqrt(2**96, 1),
            utils.expand_to_18_decimals(1),
            True,
        )
        amount0_down = sqrt_price_math.getAmount0Delta(
            utils.encode_price_sqrt(2**90, 1),
            utils.encode_price_sqrt(2**96, 1),
            utils.expand_to_18_decimals(1),
            False,
        )
        assert amount0_up == amount0_down + 1

    def test_cost_true_gas(self, sqrt_price_math):
        """
        gas cost for amount0 where roundUp = true
        """
        match_snapshot(
            sqrt_price_math.getGasCostOfGetAmount0Delta(
                utils.encode_price_sqrt(100, 121),
                utils.encode_price_sqrt(1, 1),
                utils.expand_to_18_decimals(1),
                True,
            ),
            __file__,
            "getGasCostOfGetAmount0Delta_test_gas_cost_true",
        )

    def test_cost_false_gas(self, sqrt_price_math):
        """
        gas cost for amount0 where roundUp = false
        """
        match_snapshot(
            sqrt_price_math.getGasCostOfGetAmount0Delta(
                utils.encode_price_sqrt(100, 121),
                utils.encode_price_sqrt(1, 1),
                utils.expand_to_18_decimals(1),
                False,
            ),
            __file__,
            "getGasCostOfGetAmount0Delta_test_gas_cost_false",
        )


class TestGetAmount1Delta(object):
    def test_zero_liquidity(self, sqrt_price_math):
        """
        returns 0 if liquidity is 0
        """
        amount1 = sqrt_price_math.getAmount1Delta(
            utils.encode_price_sqrt(1, 1), utils.encode_price_sqrt(2, 1), 0, True
        )
        assert amount1 == 0

    def test_equal_prices(self, sqrt_price_math):
        """
        returns 0 if prices are equal
        """
        amount1 = sqrt_price_math.getAmount0Delta(
            utils.encode_price_sqrt(1, 1), utils.encode_price_sqrt(1, 1), 0, True
        )
        assert amount1 == 0

    def test_price_1_to_1_21(self, sqrt_price_math):
        """
        returns 0.1 amount1 for price of 1 to 1.21
        """
        amount1 = sqrt_price_math.getAmount1Delta(
            utils.encode_price_sqrt(1, 1),
            utils.encode_price_sqrt(121, 100),
            utils.expand_to_18_decimals(1),
            True,
        )
        assert amount1 == 100000000000000000
        amount1_rounded_down = sqrt_price_math.getAmount1Delta(
            utils.encode_price_sqrt(1, 1),
            utils.encode_price_sqrt(121, 100),
            utils.expand_to_18_decimals(1),
            False,
        )
        assert amount1_rounded_down == amount1 - 1

    def test_round_up_true_gas(self, sqrt_price_math):
        """
        gas cost for amount0 where roundUp = true
        """
        match_snapshot(
            sqrt_price_math.getGasCostOfGetAmount0Delta(
                utils.encode_price_sqrt(100, 121),
                utils.encode_price_sqrt(1, 1),
                utils.expand_to_18_decimals(1),
                True,
            ),
            __file__,
            "getGasCostOfGetAmount0Delta_test_round_up_true",
        )

    def test_round_up_false_gas(self, sqrt_price_math):
        """
        gas cost for amount0 where roundUp = false
        """
        match_snapshot(
            sqrt_price_math.getGasCostOfGetAmount0Delta(
                utils.encode_price_sqrt(100, 121),
                utils.encode_price_sqrt(1, 1),
                utils.expand_to_18_decimals(1),
                False,
            ),
            __file__,
            "getGasCostOfGetAmount0Delta_test_round_up_false",
        )


class TestSwapComputation(object):
    def test_sqrtp_sqrtq_overflows(self, sqrt_price_math):
        """
        sqrtP * sqrtQ overflows
        """
        sqrtP = 1025574284609383690408304870162715216695788925244
        liquidity = 50015962439936049619261659728067971248
        zeroForOne = True
        amountIn = 406

        sqrtQ = sqrt_price_math.getNextSqrtPriceFromInput(
            sqrtP, liquidity, amountIn, zeroForOne
        )
        assert sqrtQ == 1025574284609383582644711336373707553698163132913

        amount0Delta = sqrt_price_math.getAmount0Delta(sqrtQ, sqrtP, liquidity, True)
        assert amount0Delta == 406
