import ape
import pytest

from snapshots import match_snapshot


@pytest.fixture(scope="function")
def liquidity_math(project, accounts):
    return project.LiquidityMathTest.deploy(sender=accounts[0])


class TestLiquidityMath:
    def test_add_zero(self, liquidity_math):
        """
        1 + 0
        """
        assert liquidity_math.addDelta(1, 0) == 1

    def test_add_negative(self, liquidity_math):
        """
        1 + -1
        """
        assert liquidity_math.addDelta(1, -1) == 0

    def test_add_positive(self, liquidity_math):
        """
        1 + 1
        """
        assert liquidity_math.addDelta(1, 1) == 2

    def test_overflow(self, liquidity_math):
        """
        2**128-15 + 15 overflows
        """
        with ape.reverts():
            liquidity_math.addDelta(2**128 - 15, 15)

    def test_underflow(self, liquidity_math):
        """
        0 + -1 underflows
        """
        with ape.reverts():
            liquidity_math.addDelta(0, -1)

    def test_underflow_with_values(self, liquidity_math):
        """
        3 + -4 underflows
        """
        with ape.reverts():
            liquidity_math.addDelta(3, -4)

    def test_gas_add(self, liquidity_math):
        """
        gas add
        """
        match_snapshot(
            liquidity_math.getGasCostOfAddDelta(15, 4),
            __file__,
            "addDelta_gas_add",
        )

    def test_gas_sub(self, liquidity_math):
        """
        gas sub
        """
        match_snapshot(
            liquidity_math.getGasCostOfAddDelta(15, -4),
            __file__,
            "addDelta_gas_sub",
        )
