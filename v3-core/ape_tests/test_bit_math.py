import ape
import pytest

from snapshots import match_snapshot


@pytest.fixture(scope="function")
def bit_math(project, accounts):
    return project.BitMathTest.deploy(sender=accounts[0])


class TestBitMath:
    def test_zero(self, bit_math):
        """
        0
        """
        with ape.reverts():
            bit_math.mostSignificantBit(0)

    def test_one(self, bit_math):
        """
        1
        """
        assert bit_math.mostSignificantBit(1) == 0

    def test_two(self, bit_math):
        """
        2
        """
        assert bit_math.mostSignificantBit(2) == 1

    def test_all_powers_of_two(self, bit_math):
        """
        all powers of 2
        """
        results = [bit_math.mostSignificantBit(2**i) for i in range(255)]
        assert results == list(range(255))

    def test_uint256_minus_one(self, bit_math):
        """
        uint256(-1)
        """
        assert bit_math.mostSignificantBit(2**256 - 1) == 255

    def test_gas_cost_smaller_number(self, bit_math):
        """
        gas cost of smaller number
        """
        match_snapshot(
            bit_math.getGasCostOfMostSignificantBit(3568),
            __file__,
            "mostSignificantBit_gas_cost_smaller_number",
        )

    def test_gas_cost_max_uint128(self, bit_math):
        """
        gas cost of max uint128
        """
        match_snapshot(
            bit_math.getGasCostOfMostSignificantBit(2**128 - 1),
            __file__,
            "mostSignificantBit_gas_cost_max_uint128",
        )

    def test_gas_cost_max_uint256(self, bit_math):
        """
        gas cost of max uint256
        """
        match_snapshot(
            bit_math.getGasCostOfMostSignificantBit(2**256 - 1),
            __file__,
            "mostSignificantBit_gas_cost_max_uint256",
        )


class TestLeastSignificantBit:
    def test_zero(self, bit_math):
        """
        0
        """
        with ape.reverts():
            bit_math.leastSignificantBit(0)

    def test_one(self, bit_math):
        """
        1
        """
        assert bit_math.leastSignificantBit(1) == 0

    def test_two(self, bit_math):
        """
        2
        """
        assert bit_math.leastSignificantBit(2) == 1

    def test_all_powers_of_two(self, bit_math):
        """
        all powers of 2
        """
        results = [bit_math.leastSignificantBit(2**i) for i in range(255)]
        assert results == list(range(255))

    def test_uint256_minus_one(self, bit_math):
        """
        uint256(-1)
        """
        assert bit_math.leastSignificantBit(2**256 - 1) == 0

    def test_gas_cost_smaller_number(self, bit_math):
        """
        gas cost of smaller number
        """
        match_snapshot(
            bit_math.getGasCostOfLeastSignificantBit(3568),
            __file__,
            "leastSignificantBit_gas_cost_smaller_number",
        )

    def test_gas_cost_max_uint128(self, bit_math):
        """
        gas cost of max uint128
        """
        match_snapshot(
            bit_math.getGasCostOfLeastSignificantBit(2**128 - 1),
            __file__,
            "leastSignificantBit_gas_cost_max_uint128",
        )

    def test_gas_cost_max_uint256(self, bit_math):
        """
        gas cost of max uint256
        """
        match_snapshot(
            bit_math.getGasCostOfLeastSignificantBit(2**256 - 1),
            __file__,
            "leastSignificantBit_gas_cost_max_uint256",
        )
