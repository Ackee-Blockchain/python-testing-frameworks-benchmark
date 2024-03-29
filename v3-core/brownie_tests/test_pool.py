import brownie
import pytest
from brownie import (MockTimeUniswapV3Pool, TestERC20, TestUniswapV3Callee,
                     UniswapV3Factory, accounts)

import utils
from brownie_utils import brownie_reverts_fix
from utils import (MAX_SQRT_RATIO, MAX_UINT_128, MIN_SQRT_RATIO,
                   TEST_POOL_START_TIME)


@pytest.fixture(scope="function")
def tokens():
    token0 = TestERC20.deploy(2**255, {"from": accounts[0]})
    token1 = TestERC20.deploy(2**255, {"from": accounts[0]})
    token2 = TestERC20.deploy(2**255, {"from": accounts[0]})

    token0, token1, token2 = sorted(
        [token0, token1, token2], key=lambda token: token.address.lower()
    )
    return token0, token1, token2


@pytest.fixture(scope="function")
def factory():
    return UniswapV3Factory.deploy({"from": accounts[0]})


@pytest.fixture(scope="function")
def pool_fixture(tokens, factory):
    token0, token1, token2 = tokens
    factory = factory
    pool = utils.create_pool(
        utils.FeeAmount.MEDIUM, utils.TickSpacings.MEDIUM, token0, token1, factory
    )
    pool_functions = utils.PoolHelper(
        token0,
        token1,
        factory,
        pool,
        utils.TickSpacings.MEDIUM,
        TestUniswapV3Callee.deploy({"from": accounts[0]}),
    )
    return token0, token1, factory, pool, pool_functions


class TestInitialize:
    def test_constructor_initializes_immutables(self, pool_fixture):
        """
        Constructor initializes immutables
        """
        token0, token1, factory, pool, pool_helper = pool_fixture
        assert pool.factory() == factory.address
        assert pool.token0() == token0.address
        assert pool.token1() == token1.address
        assert pool.maxLiquidityPerTick() == utils.get_max_liquidity_per_tick(
            pool_helper.tick_spacing
        )

    def test_initialize_fails_if_already_initialized(self, pool_fixture):
        """
        Fails if already initialized
        """
        token0, token1, factory, pool, pool_helper = pool_fixture
        pool.initialize(utils.encode_price_sqrt(1, 1), {"from": accounts[0]})
        with brownie.reverts():
            pool.initialize(utils.encode_price_sqrt(1, 1), {"from": accounts[0]})

    def test_initialize_fails_if_starting_price_is_too_low(self, pool_fixture):
        """
        Fails if starting price is too low
        """
        token0, token1, factory, pool, pool_helper = pool_fixture
        with brownie_reverts_fix("R"):
            pool.initialize(1, {"from": accounts[0]})
        with brownie_reverts_fix("R"):
            pool.initialize(MIN_SQRT_RATIO - 1, {"from": accounts[0]})

    def test_initialize_fails_if_starting_price_is_too_high(self, pool_fixture):
        """
        Fails if starting price is too high
        """
        token0, token1, factory, pool, pool_helper = pool_fixture
        with brownie_reverts_fix("R"):
            pool.initialize(MAX_SQRT_RATIO, {"from": accounts[0]})
        with brownie_reverts_fix("R"):
            pool.initialize(2**160 - 1, {"from": accounts[0]})

    def test_initialize_can_be_initialized_at_min_sqrt_ratio(self, pool_fixture):
        """
        Can be initialized at MIN_SQRT_RATIO
        """
        token0, token1, factory, pool, pool_helper = pool_fixture
        pool.initialize(MIN_SQRT_RATIO, {"from": accounts[0]})
        assert pool.slot0()[1] == utils.get_min_tick(1)

    def test_initialize_can_be_initialized_at_max_sqrt_ratio_minus_one(
        self, pool_fixture
    ):
        """
        Can be initialized at MAX_SQRT_RATIO - 1
        """
        token0, token1, factory, pool, pool_helper = pool_fixture
        pool.initialize(MAX_SQRT_RATIO - 1, {"from": accounts[0]})
        assert pool.slot0()[1] == utils.get_max_tick(1) - 1

    def test_initialize_sets_initial_variables(self, pool_fixture):
        """
        Sets initial variables
        """
        token0, token1, factory, pool, pool_helper = pool_fixture
        price = utils.encode_price_sqrt(1, 2)
        pool.initialize(price, {"from": accounts[0]})

        sqrt_price_x96, ticks, observation_index = pool.slot0()[:3]
        assert sqrt_price_x96 == price
        assert observation_index == 0
        assert ticks == -6932

    def test_initializes_the_first_observations_slot(self, pool_fixture):
        """
        Initializes the first observations slot
        """
        token0, token1, factory, pool, pool_helper = pool_fixture
        pool.initialize(utils.encode_price_sqrt(1, 1), {"from": accounts[0]})

        observation = pool.observations(0)
        expected_observation = {
            "tickCumulative": 0,
            "initialized": True,
            "blockTimestamp": TEST_POOL_START_TIME,
            "secondsPerLiquidityCumulativeX128": 0,
        }
        utils.check_observation_equals(observation, expected_observation)

    def test_emits_an_initialized_event_with_the_input_tick(self, pool_fixture):
        """
        Emits an Initialized event with the input tick
        """
        token0, token1, factory, pool, pool_helper = pool_fixture
        sqrt_price_x96 = utils.encode_price_sqrt(1, 2)

        tx = pool.initialize(sqrt_price_x96, {"from": accounts[0]})
        assert "Initialize" in tx.events
        assert tx.events["Initialize"]["sqrtPriceX96"] == sqrt_price_x96
        assert tx.events["Initialize"]["tick"] == -6932


class TestIncreaseObservationCardinalityNext:
    def test_can_only_be_called_after_initialize(self, pool_fixture):
        """
        Can only be called after initialize
        """
        token0, token1, factory, pool, pool_helper = pool_fixture
        with brownie_reverts_fix("LOK"):
            pool.increaseObservationCardinalityNext(2, {"from": accounts[0]})

    def test_emits_an_event_including_both_old_and_new(self, pool_fixture):
        """
        Emits an event including both old and new
        """
        token0, token1, factory, pool, pool_helper = pool_fixture
        pool.initialize(utils.encode_price_sqrt(1, 1), {"from": accounts[0]})
        tx = pool.increaseObservationCardinalityNext(2, {"from": accounts[0]})
        assert "IncreaseObservationCardinalityNext" in tx.events
        assert (
            tx.events["IncreaseObservationCardinalityNext"][
                "observationCardinalityNextOld"
            ]
            == 1
        )
        assert (
            tx.events["IncreaseObservationCardinalityNext"][
                "observationCardinalityNextNew"
            ]
            == 2
        )

    def test_does_not_emit_an_event_for_no_op_call(self, pool_fixture):
        """
        Does not emit an event for no op call
        """
        token0, token1, factory, pool, pool_helper = pool_fixture
        pool.initialize(utils.encode_price_sqrt(1, 1), {"from": accounts[0]})
        pool.increaseObservationCardinalityNext(3, {"from": accounts[0]})
        tx = pool.increaseObservationCardinalityNext(2, {"from": accounts[0]})
        assert "IncreaseObservationCardinalityNext" not in tx.events

    def test_does_not_change_cardinality_next_if_less_than_current(self, pool_fixture):
        """
        Does not change cardinality next if less than current
        """
        token0, token1, factory, pool, pool_helper = pool_fixture
        pool.initialize(utils.encode_price_sqrt(1, 1), {"from": accounts[0]})
        pool.increaseObservationCardinalityNext(3, {"from": accounts[0]})
        pool.increaseObservationCardinalityNext(2, {"from": accounts[0]})
        # observation cardinality is 1
        assert pool.slot0()[4] == 3

    def test_increases_cardinality_and_cardinality_next_first_time(self, pool_fixture):
        """
        Increases cardinality and cardinality next first time
        """
        token0, token1, factory, pool, pool_helper = pool_fixture
        pool.initialize(utils.encode_price_sqrt(1, 1), {"from": accounts[0]})
        pool.increaseObservationCardinalityNext(2, {"from": accounts[0]})
        # observation cardinality is 1
        assert pool.slot0()[3] == 1
        # observation cardinality next is 2
        assert pool.slot0()[4] == 2


class TestMint:
    def test_fails_if_not_initialized(self, pool_fixture):
        """
        Fails if not initialized
        """
        token0, token1, factory, pool, pool_helper = pool_fixture
        with brownie_reverts_fix("LOK"):
            pool_helper.mint(
                accounts[0], -pool_helper.tick_spacing, pool_helper.tick_spacing, 1
            )

    class TestAfterInitialization:
        @pytest.fixture
        def initialized_pool_fixture(self, pool_fixture):
            token0, token1, factory, pool, pool_helper = pool_fixture
            pool.initialize(utils.encode_price_sqrt(1, 10), {"from": accounts[0]})
            pool_helper.mint(
                accounts[0], pool_helper.min_tick, pool_helper.max_tick, 3161
            )
            return token0, token1, factory, pool, pool_helper

        class TestFailureCases:
            def test_fails_if_tick_lower_greater_than_tick_upper(
                self, initialized_pool_fixture
            ):
                """
                Fails if tickLower greater than tickUpper
                """
                token0, token1, factory, pool, pool_helper = initialized_pool_fixture
                with brownie.reverts():
                    pool_helper.mint(accounts[0], 1, 0, 1)

            def test_fails_if_tick_lower_less_than_min_tick(
                self, initialized_pool_fixture
            ):
                """
                Fails if tickLower less than min tick
                """
                token0, token1, factory, pool, pool_helper = initialized_pool_fixture
                with brownie.reverts():
                    pool_helper.mint(accounts[0], -887273, 0, 1)

            def test_fails_if_tick_upper_greater_than_max_tick(
                self, initialized_pool_fixture
            ):
                """
                Fails if tickUpper greater than max tick
                """
                token0, token1, factory, pool, pool_helper = initialized_pool_fixture
                with brownie.reverts():
                    pool_helper.mint(accounts[0], 0, 887273, 1)

            def test_fails_if_amount_exceeds_the_max(self, initialized_pool_fixture):
                """
                Fails if amount exceeds the max
                """
                token0, token1, factory, pool, pool_helper = initialized_pool_fixture
                max_liquidity_gross = pool.maxLiquidityPerTick()
                with brownie.reverts():
                    pool_helper.mint(
                        accounts[0],
                        pool_helper.min_tick + pool_helper.tick_spacing,
                        pool_helper.max_tick - pool_helper.tick_spacing,
                        max_liquidity_gross + 1,
                    )
                pool_helper.mint(
                    accounts[0],
                    pool_helper.min_tick + pool_helper.tick_spacing,
                    pool_helper.max_tick - pool_helper.tick_spacing,
                    max_liquidity_gross,
                )

            def test_fails_if_total_amount_at_tick_exceeds_the_max(
                self, initialized_pool_fixture
            ):
                """
                Fails if total amount at tick exceeds the max
                """
                token0, token1, factory, pool, pool_helper = initialized_pool_fixture
                pool_helper.mint(
                    accounts[0],
                    pool_helper.min_tick + pool_helper.tick_spacing,
                    pool_helper.max_tick - pool_helper.tick_spacing,
                    1000,
                )

                max_liquidity_gross = pool.maxLiquidityPerTick()
                with brownie.reverts():
                    pool_helper.mint(
                        accounts[0],
                        pool_helper.min_tick + pool_helper.tick_spacing,
                        pool_helper.max_tick - pool_helper.tick_spacing,
                        max_liquidity_gross - 1000 + 1,
                    )

                with brownie.reverts():
                    pool_helper.mint(
                        accounts[0],
                        pool_helper.min_tick + pool_helper.tick_spacing * 2,
                        pool_helper.max_tick - pool_helper.tick_spacing,
                        max_liquidity_gross - 1000 + 1,
                    )

                with brownie.reverts():
                    pool_helper.mint(
                        accounts[0],
                        pool_helper.min_tick + pool_helper.tick_spacing,
                        pool_helper.max_tick - pool_helper.tick_spacing * 2,
                        max_liquidity_gross - 1000 + 1,
                    )

                pool_helper.mint(
                    accounts[0],
                    pool_helper.min_tick + pool_helper.tick_spacing,
                    pool_helper.max_tick - pool_helper.tick_spacing,
                    max_liquidity_gross - 1000,
                )

            def test_fails_if_amount_is_zero(self, initialized_pool_fixture):
                """
                Fails if amount is 0
                """
                token0, token1, factory, pool, pool_helper = initialized_pool_fixture
                with brownie.reverts():
                    pool_helper.mint(
                        accounts[0],
                        pool_helper.min_tick + pool_helper.tick_spacing,
                        pool_helper.max_tick - pool_helper.tick_spacing,
                        0,
                    )

        class TestSuccessCases:
            def test_initial_balances(self, initialized_pool_fixture):
                """
                Initial balances
                """
                token0, token1, factory, pool, pool_helper = initialized_pool_fixture
                assert token0.balanceOf(pool.address) == 9996
                assert token1.balanceOf(pool.address) == 1000

            def test_initial_tick(self, initialized_pool_fixture):
                """
                Initial tick
                """
                token0, token1, factory, pool, pool_helper = initialized_pool_fixture
                assert pool.slot0()[1] == -23028

            class TestAboveCurrentPrice:
                def test_transfers_token0_only(self, initialized_pool_fixture):
                    """
                    Transfers token0 only
                    """
                    (
                        token0,
                        token1,
                        factory,
                        pool,
                        pool_helper,
                    ) = initialized_pool_fixture
                    tx = pool_helper.mint(accounts[0], -22980, 0, 10000)
                    assert "Transfer" in tx.events
                    assert tx.events["Transfer"]["from"] == accounts[0]
                    assert tx.events["Transfer"]["to"] == pool.address
                    assert tx.events["Transfer"]["value"] == 21549
                    assert token0.balanceOf(pool.address) == 9996 + 21549
                    assert token1.balanceOf(pool.address) == 1000

                def test_max_tick_with_max_leverage(self, initialized_pool_fixture):
                    """
                    Max tick with max leverage
                    """
                    (
                        token0,
                        token1,
                        factory,
                        pool,
                        pool_helper,
                    ) = initialized_pool_fixture
                    max_tick = utils.get_max_tick(pool_helper.tick_spacing)
                    pool_helper.mint(
                        accounts[0],
                        max_tick - pool_helper.tick_spacing,
                        max_tick,
                        2**102,
                    )
                    assert token0.balanceOf(pool.address) == 9996 + 828011525
                    assert token1.balanceOf(pool.address) == 1000

                def test_works_for_max_tick(self, initialized_pool_fixture):
                    """
                    Works for max tick
                    """
                    (
                        token0,
                        token1,
                        factory,
                        pool,
                        pool_helper,
                    ) = initialized_pool_fixture
                    max_tick = utils.get_max_tick(pool_helper.tick_spacing)
                    tx = pool_helper.mint(accounts[0], -22980, max_tick, 10000)
                    assert "Transfer" in tx.events
                    assert tx.events["Transfer"]["from"] == accounts[0]
                    assert tx.events["Transfer"]["to"] == pool.address
                    assert tx.events["Transfer"]["value"] == 31549
                    assert token0.balanceOf(pool.address) == 9996 + 31549
                    assert token1.balanceOf(pool.address) == 1000

                def test_removing_works(self, initialized_pool_fixture):
                    """
                    Removing works
                    """
                    (
                        token0,
                        token1,
                        factory,
                        pool,
                        pool_helper,
                    ) = initialized_pool_fixture

                    pool_helper.mint(accounts[0], -240, 0, 10000)
                    pool.burn(-240, 0, 10000, {"from": accounts[0]})

                    tx = pool.collect(
                        accounts[0],
                        -240,
                        0,
                        MAX_UINT_128,
                        MAX_UINT_128,
                        {"from": accounts[0]},
                    )

                    amount0 = tx.events["Collect"]["amount0"]
                    amount1 = tx.events["Collect"]["amount1"]
                    assert amount0 == 120
                    assert amount1 == 0

                def test_adds_liquidity_to_liquidity_gross(
                    self, initialized_pool_fixture
                ):
                    """
                    Adds liquidity to liquidityGross
                    """
                    (
                        token0,
                        token1,
                        factory,
                        pool,
                        pool_helper,
                    ) = initialized_pool_fixture
                    pool_helper.mint(accounts[0], -240, 0, 100)
                    assert pool.ticks(-240)[0] == 100
                    assert pool.ticks(0)[0] == 100
                    assert pool.ticks(pool_helper.tick_spacing)[0] == 0
                    assert pool.ticks(pool_helper.tick_spacing * 2)[0] == 0
                    pool_helper.mint(accounts[0], -240, pool_helper.tick_spacing, 150)
                    assert pool.ticks(-240)[0] == 250
                    assert pool.ticks(0)[0] == 100
                    assert pool.ticks(pool_helper.tick_spacing)[0] == 150
                    assert pool.ticks(pool_helper.tick_spacing * 2)[0] == 0
                    pool_helper.mint(accounts[0], 0, pool_helper.tick_spacing * 2, 60)
                    assert pool.ticks(-240)[0] == 250
                    assert pool.ticks(0)[0] == 160
                    assert pool.ticks(pool_helper.tick_spacing)[0] == 150
                    assert pool.ticks(pool_helper.tick_spacing * 2)[0] == 60

                def test_removes_liquidity_from_liquidity_gross(
                    self, initialized_pool_fixture
                ):
                    """
                    Removes liquidity from liquidityGross
                    """
                    (
                        token0,
                        token1,
                        factory,
                        pool,
                        pool_helper,
                    ) = initialized_pool_fixture
                    pool_helper.mint(accounts[0], -240, 0, 100)
                    pool_helper.mint(accounts[0], -240, 0, 40)
                    pool.burn(-240, 0, 90, {"from": accounts[0]})
                    assert pool.ticks(-240)[0] == 50
                    assert pool.ticks(0)[0] == 50

                def test_clears_tick_lower_if_last_position_is_removed(
                    self, initialized_pool_fixture
                ):
                    """
                    Clears tick lower if last position is removed
                    """
                    (
                        token0,
                        token1,
                        factory,
                        pool,
                        pool_helper,
                    ) = initialized_pool_fixture
                    pool_helper.mint(accounts[0], -240, 0, 100)
                    pool.burn(-240, 0, 100, {"from": accounts[0]})
                    (
                        liquidity_gross,
                        _,
                        fee_growth_outside0_x128,
                        fee_growth_outside1_x128,
                    ) = pool.ticks(-240)[:4]
                    assert liquidity_gross == 0
                    assert fee_growth_outside0_x128 == 0
                    assert fee_growth_outside1_x128 == 0

                def test_clears_tick_upper_if_last_position_is_removed(
                    self, initialized_pool_fixture
                ):
                    """
                    Clears tick upper if last position is removed
                    """
                    (
                        token0,
                        token1,
                        factory,
                        pool,
                        pool_helper,
                    ) = initialized_pool_fixture
                    pool_helper.mint(accounts[0], -240, 0, 100)
                    pool.burn(-240, 0, 100, {"from": accounts[0]})
                    (
                        liquidity_gross,
                        _,
                        fee_growth_outside0_x128,
                        fee_growth_outside1_x128,
                    ) = pool.ticks(0)[:4]
                    assert liquidity_gross == 0
                    assert fee_growth_outside0_x128 == 0
                    assert fee_growth_outside1_x128 == 0

                def test_only_clears_the_tick_that_is_not_used_at_all(
                    self, initialized_pool_fixture
                ):
                    """
                    Only clears the tick that is not used at all
                    """
                    (
                        token0,
                        token1,
                        factory,
                        pool,
                        pool_helper,
                    ) = initialized_pool_fixture

                    pool_helper.mint(accounts[0], -240, 0, 100)
                    pool_helper.mint(accounts[0], -pool_helper.tick_spacing, 0, 250)
                    pool.burn(-240, 0, 100, {"from": accounts[0]})

                    (
                        liquidity_gross,
                        _,
                        fee_growth_outside0_x128,
                        fee_growth_outside1_x128,
                    ) = pool.ticks(-240)[:4]
                    assert liquidity_gross == 0
                    assert fee_growth_outside0_x128 == 0
                    assert fee_growth_outside1_x128 == 0

                    (
                        liquidity_gross,
                        _,
                        fee_growth_outside0_x128,
                        fee_growth_outside1_x128,
                    ) = pool.ticks(-pool_helper.tick_spacing)[:4]
                    assert liquidity_gross == 250
                    assert fee_growth_outside0_x128 == 0
                    assert fee_growth_outside1_x128 == 0

                def test_does_not_write_an_observation(self, initialized_pool_fixture):
                    """
                    Does not write an observation
                    """
                    (
                        token0,
                        token1,
                        factory,
                        pool,
                        pool_helper,
                    ) = initialized_pool_fixture
                    observation = pool.observations(0)
                    expected_observation = {
                        "tickCumulative": 0,
                        "blockTimestamp": TEST_POOL_START_TIME,
                        "initialized": True,
                        "secondsPerLiquidityCumulativeX128": 0,
                    }
                    utils.check_observation_equals(observation, expected_observation)
                    pool.advanceTime(1, {"from": accounts[0]})
                    pool_helper.mint(accounts[0], -240, 0, 100)
                    utils.check_observation_equals(
                        pool.observations(0), expected_observation
                    )

            class TestIncludingCurrentPrice:
                def test_price_within_range_transfers_current_price_of_both_tokens(
                    self, initialized_pool_fixture
                ):
                    """
                    Price within range: transfers current price of both tokens
                    """
                    (
                        token0,
                        token1,
                        factory,
                        pool,
                        pool_helper,
                    ) = initialized_pool_fixture
                    min_tick = utils.get_min_tick(pool_helper.tick_spacing)
                    max_tick = utils.get_max_tick(pool_helper.tick_spacing)
                    tick_spacing = pool_helper.tick_spacing

                    tx = pool_helper.mint(
                        accounts[0],
                        min_tick + tick_spacing,
                        max_tick - tick_spacing,
                        100,
                    )
                    assert "Transfer" in tx.events
                    assert tx.events["Transfer"]["from"] == accounts[0]
                    assert tx.events["Transfer"]["to"] == pool.address
                    assert tx.events["Transfer"]["value"] == 317
                    assert token0.balanceOf(pool.address) == 9996 + 317
                    assert token1.balanceOf(pool.address) == 1000 + 32

                def test_initializes_lower_tick(self, initialized_pool_fixture):
                    """
                    Initializes lower tick
                    """
                    (
                        token0,
                        token1,
                        factory,
                        pool,
                        pool_helper,
                    ) = initialized_pool_fixture
                    min_tick = utils.get_min_tick(pool_helper.tick_spacing)
                    max_tick = utils.get_max_tick(pool_helper.tick_spacing)
                    tick_spacing = pool_helper.tick_spacing

                    pool_helper.mint(
                        accounts[0],
                        min_tick + tick_spacing,
                        max_tick - tick_spacing,
                        100,
                    )
                    liquidity_gross = pool.ticks(min_tick + tick_spacing)[0]
                    assert liquidity_gross == 100

                def test_initializes_upper_tick(self, initialized_pool_fixture):
                    """
                    Initializes upper tick
                    """
                    (
                        token0,
                        token1,
                        factory,
                        pool,
                        pool_helper,
                    ) = initialized_pool_fixture
                    min_tick = utils.get_min_tick(pool_helper.tick_spacing)
                    max_tick = utils.get_max_tick(pool_helper.tick_spacing)
                    tick_spacing = pool_helper.tick_spacing

                    pool_helper.mint(
                        accounts[0],
                        min_tick + tick_spacing,
                        max_tick - tick_spacing,
                        100,
                    )
                    liquidity_gross = pool.ticks(max_tick - tick_spacing)[0]
                    assert liquidity_gross == 100

                def test_works_for_min_max_tick(self, initialized_pool_fixture):
                    """
                    Works for min/max tick
                    """
                    (
                        token0,
                        token1,
                        factory,
                        pool,
                        pool_helper,
                    ) = initialized_pool_fixture
                    min_tick = utils.get_min_tick(pool_helper.tick_spacing)
                    max_tick = utils.get_max_tick(pool_helper.tick_spacing)

                    tx = pool_helper.mint(accounts[0], min_tick, max_tick, 10000)
                    assert "Transfer" in tx.events
                    assert tx.events["Transfer"]["from"] == accounts[0]
                    assert tx.events["Transfer"]["to"] == pool.address
                    assert tx.events["Transfer"]["value"] == 31623
                    assert token0.balanceOf(pool.address) == 9996 + 31623
                    assert token1.balanceOf(pool.address) == 1000 + 3163

                def test_removing_works(self, initialized_pool_fixture):
                    """
                    Removing works
                    """
                    (
                        token0,
                        token1,
                        factory,
                        pool,
                        pool_helper,
                    ) = initialized_pool_fixture
                    min_tick = utils.get_min_tick(pool_helper.tick_spacing)
                    max_tick = utils.get_max_tick(pool_helper.tick_spacing)
                    tick_spacing = pool_helper.tick_spacing

                    pool_helper.mint(
                        accounts[0],
                        min_tick + tick_spacing,
                        max_tick - tick_spacing,
                        100,
                    )
                    pool.burn(
                        min_tick + tick_spacing,
                        max_tick - tick_spacing,
                        100,
                        {"from": accounts[0]},
                    )

                    tx = pool.collect(
                        accounts[0],
                        min_tick + tick_spacing,
                        max_tick - tick_spacing,
                        MAX_UINT_128,
                        MAX_UINT_128,
                        {"from": accounts[0]},
                    )
                    amount0 = tx.events["Collect"]["amount0"]
                    amount1 = tx.events["Collect"]["amount1"]
                    assert amount0 == 316
                    assert amount1 == 31

                def test_writes_an_observation(self, initialized_pool_fixture):
                    """
                    Writes an observation
                    """
                    (
                        token0,
                        token1,
                        factory,
                        pool,
                        pool_helper,
                    ) = initialized_pool_fixture
                    min_tick = utils.get_min_tick(pool_helper.tick_spacing)
                    max_tick = utils.get_max_tick(pool_helper.tick_spacing)

                    observation = pool.observations(0)
                    expected_observation = {
                        "tickCumulative": 0,
                        "initialized": True,
                        "blockTimestamp": TEST_POOL_START_TIME,
                        "secondsPerLiquidityCumulativeX128": 0,
                    }
                    utils.check_observation_equals(observation, expected_observation)

                    pool.advanceTime(1, {"from": accounts[0]})
                    pool_helper.mint(accounts[0], min_tick, max_tick, 100)
                    observation = pool.observations(0)
                    expected_observation = {
                        "tickCumulative": -23028,
                        "blockTimestamp": TEST_POOL_START_TIME + 1,
                        "initialized": True,
                        "secondsPerLiquidityCumulativeX128": "107650226801941937191829992860413859",
                    }
                    utils.check_observation_equals(observation, expected_observation)

            class TestBelowCurrentPrice:
                def test_transfers_token1_only(self, initialized_pool_fixture):
                    """
                    Transfers token1 only
                    """
                    (
                        token0,
                        token1,
                        factory,
                        pool,
                        pool_helper,
                    ) = initialized_pool_fixture
                    tx = pool_helper.mint(accounts[0], -46080, -23040, 10000)
                    assert "Transfer" in tx.events
                    assert tx.events["Transfer"]["from"] == accounts[0]
                    assert tx.events["Transfer"]["to"] == pool.address
                    assert tx.events["Transfer"]["value"] == 2162
                    assert token0.balanceOf(pool.address) == 9996
                    assert token1.balanceOf(pool.address) == 1000 + 2162

                def test_min_tick_with_max_leverage(self, initialized_pool_fixture):
                    """
                    Min tick with max leverage
                    """
                    (
                        token0,
                        token1,
                        factory,
                        pool,
                        pool_helper,
                    ) = initialized_pool_fixture
                    min_tick = utils.get_min_tick(pool_helper.tick_spacing)
                    tick_spacing = pool_helper.tick_spacing
                    pool_helper.mint(
                        accounts[0], min_tick, min_tick + tick_spacing, 2**102
                    )
                    assert token0.balanceOf(pool.address) == 9996
                    assert token1.balanceOf(pool.address) == 1000 + 828011520

                def test_works_for_min_tick(self, initialized_pool_fixture):
                    """
                    Works for min tick
                    """
                    (
                        token0,
                        token1,
                        factory,
                        pool,
                        pool_helper,
                    ) = initialized_pool_fixture
                    min_tick = utils.get_min_tick(pool_helper.tick_spacing)
                    tx = pool_helper.mint(accounts[0], min_tick, -23040, 10000)
                    assert "Transfer" in tx.events
                    assert tx.events["Transfer"]["from"] == accounts[0]
                    assert tx.events["Transfer"]["to"] == pool.address
                    assert tx.events["Transfer"]["value"] == 3161
                    assert token0.balanceOf(pool.address) == 9996
                    assert token1.balanceOf(pool.address) == 1000 + 3161

                def test_removing_works(self, initialized_pool_fixture):
                    """
                    Removing works
                    """
                    (
                        token0,
                        token1,
                        factory,
                        pool,
                        pool_helper,
                    ) = initialized_pool_fixture
                    pool_helper.mint(accounts[0], -46080, -46020, 10000)
                    pool.burn(-46080, -46020, 10000, {"from": accounts[0]})

                    tx = pool.collect(
                        accounts[0],
                        -46080,
                        -46020,
                        MAX_UINT_128,
                        MAX_UINT_128,
                        {"from": accounts[0]},
                    )

                    amount0 = tx.events["Collect"]["amount0"]
                    amount1 = tx.events["Collect"]["amount1"]
                    assert amount0 == 0
                    assert amount1 == 3

                def test_does_not_write_an_observation(self, initialized_pool_fixture):
                    """
                    Does not write an observation
                    """
                    (
                        token0,
                        token1,
                        factory,
                        pool,
                        pool_helper,
                    ) = initialized_pool_fixture

                    expected_observation = {
                        "tickCumulative": 0,
                        "blockTimestamp": TEST_POOL_START_TIME,
                        "initialized": True,
                        "secondsPerLiquidityCumulativeX128": 0,
                    }
                    observation = pool.observations(0)
                    utils.check_observation_equals(observation, expected_observation)

                    pool.advanceTime(1, {"from": accounts[0]})
                    pool_helper.mint(accounts[0], -46080, -23040, 100)
                    observation = pool.observations(0)
                    utils.check_observation_equals(observation, expected_observation)

        def test_protocol_fees_accumulate_as_expected_during_swap(
            self, initialized_pool_fixture
        ):
            """
            Protocol fees accumulate as expected during swap
            """
            token0, token1, factory, pool, pool_helper = initialized_pool_fixture
            pool.setFeeProtocol(6, 6, {"from": accounts[0]})

            pool_helper.mint(
                accounts[0],
                pool_helper.min_tick + pool_helper.tick_spacing,
                pool_helper.max_tick - pool_helper.tick_spacing,
                utils.expand_to_18_decimals(1),
            )
            pool_helper.swap_exact_0_for_1(
                utils.expand_to_18_decimals(1) // 10, accounts[0]
            )
            pool_helper.swap_exact_1_for_0(
                utils.expand_to_18_decimals(1) // 100, accounts[0]
            )

            token0_protocol_fees, token1_protocol_fees = pool.protocolFees()
            assert token0_protocol_fees == 50000000000000
            assert token1_protocol_fees == 5000000000000

        def test_positions_are_protected_before_protocol_fee_is_turned_on(
            self, initialized_pool_fixture
        ):
            """
            Positions are protected before protocol fee is turned on
            """
            token0, token1, factory, pool, pool_helper = initialized_pool_fixture
            pool_helper.mint(
                accounts[0],
                pool_helper.min_tick + pool_helper.tick_spacing,
                pool_helper.max_tick - pool_helper.tick_spacing,
                utils.expand_to_18_decimals(1),
            )
            pool_helper.swap_exact_0_for_1(
                utils.expand_to_18_decimals(1) // 10, accounts[0]
            )
            pool_helper.swap_exact_1_for_0(
                utils.expand_to_18_decimals(1) // 100, accounts[0]
            )

            token0_protocol_fees, token1_protocol_fees = pool.protocolFees()
            assert token0_protocol_fees == 0
            assert token1_protocol_fees == 0

            pool.setFeeProtocol(6, 6, {"from": accounts[0]})
            token0_protocol_fees, token1_protocol_fees = pool.protocolFees()
            assert token0_protocol_fees == 0
            assert token1_protocol_fees == 0

        def test_poke_is_not_allowed_on_uninitialized_position(
            self, initialized_pool_fixture
        ):
            """
            Poke is not allowed on uninitialized position
            """
            token0, token1, factory, pool, pool_helper = initialized_pool_fixture
            pool_helper.mint(
                accounts[1],
                pool_helper.min_tick + pool_helper.tick_spacing,
                pool_helper.max_tick - pool_helper.tick_spacing,
                utils.expand_to_18_decimals(1),
            )
            pool_helper.swap_exact_0_for_1(
                utils.expand_to_18_decimals(1) // 10, accounts[0]
            )
            pool_helper.swap_exact_1_for_0(
                utils.expand_to_18_decimals(1) // 100, accounts[0]
            )

            with brownie.reverts():
                pool.burn(
                    pool_helper.min_tick + pool_helper.tick_spacing,
                    pool_helper.max_tick - pool_helper.tick_spacing,
                    0,
                    {"from": accounts[0]},
                )

            pool_helper.mint(
                accounts[0],
                pool_helper.min_tick + pool_helper.tick_spacing,
                pool_helper.max_tick - pool_helper.tick_spacing,
                1,
            )

            position = pool.positions(
                utils.get_position_key(
                    str(accounts[0].address),
                    pool_helper.min_tick + pool_helper.tick_spacing,
                    pool_helper.max_tick - pool_helper.tick_spacing,
                )
            )

            assert position[0] == 1
            assert position[1] == 102084710076281216349243831104605583
            assert position[2] == 10208471007628121634924383110460558
            assert position[3] == 0
            assert position[4] == 0

            pool.burn(
                pool_helper.min_tick + pool_helper.tick_spacing,
                pool_helper.max_tick - pool_helper.tick_spacing,
                1,
                {"from": accounts[0]},
            )
            position = pool.positions(
                utils.get_position_key(
                    str(accounts[0].address),
                    pool_helper.min_tick + pool_helper.tick_spacing,
                    pool_helper.max_tick - pool_helper.tick_spacing,
                )
            )

            assert position[0] == 0
            assert position[1] == 102084710076281216349243831104605583
            assert position[2] == 10208471007628121634924383110460558
            assert position[3] == 3
            assert position[4] == 0


class TestBurn:
    @pytest.fixture
    def initialized_pool_fixture(self, pool_fixture):
        token0, token1, factory, pool, pool_helper = pool_fixture
        pool.initialize(utils.encode_price_sqrt(1, 1), {"from": accounts[0]})
        pool_helper.mint(
            accounts[0],
            pool_helper.min_tick,
            pool_helper.max_tick,
            utils.expand_to_18_decimals(2),
        )
        return token0, token1, factory, pool, pool_helper

    def test_does_not_clear_the_position_fee_growth_snapshot_if_no_more_liquidity(
        self, initialized_pool_fixture
    ):
        """
        Does not clear the position fee growth snapshot if no more liquidity
        """
        token0, token1, factory, pool, pool_helper = initialized_pool_fixture
        pool.advanceTime(10, {"from": accounts[0]})
        pool_helper.mint(
            accounts[1],
            pool_helper.min_tick,
            pool_helper.max_tick,
            utils.expand_to_18_decimals(1),
        )
        pool_helper.swap_exact_0_for_1(utils.expand_to_18_decimals(1), accounts[0])
        pool_helper.swap_exact_1_for_0(utils.expand_to_18_decimals(1), accounts[0])
        pool.burn(
            pool_helper.min_tick,
            pool_helper.max_tick,
            utils.expand_to_18_decimals(1),
            {"from": accounts[1]},
        )

        position_key = utils.get_position_key(
            str(accounts[1].address), pool_helper.min_tick, pool_helper.max_tick
        )

        (
            liquidity,
            fee_growth_inside0_last_x128,
            fee_growth_inside1_last_x128,
            tokens_owed0,
            tokens_owed1,
        ) = pool.positions(position_key)

        assert liquidity == 0
        assert tokens_owed0 != 0
        assert tokens_owed1 != 0
        assert fee_growth_inside0_last_x128 == 340282366920938463463374607431768211
        assert fee_growth_inside1_last_x128 == 340282366920938576890830247744589365

    def test_clears_the_tick_if_its_the_last_position_using_it(
        self, initialized_pool_fixture
    ):
        """
        Clears the tick if its the last position using it
        """
        token0, token1, factory, pool, pool_helper = initialized_pool_fixture
        tick_lower = pool_helper.min_tick + pool_helper.tick_spacing
        tick_upper = pool_helper.max_tick - pool_helper.tick_spacing

        pool.advanceTime(10, {"from": accounts[0]})
        pool_helper.mint(accounts[0], tick_lower, tick_upper, 1)
        pool_helper.swap_exact_0_for_1(utils.expand_to_18_decimals(1), accounts[0])
        pool.burn(tick_lower, tick_upper, 1, {"from": accounts[0]})

        utils.check_tick_is_clear(pool, tick_lower)
        utils.check_tick_is_clear(pool, tick_upper)

    def test_clears_only_the_lower_tick_if_upper_is_still_used(
        self, initialized_pool_fixture
    ):
        """
        Clears only the lower tick if upper is still used
        """
        token0, token1, factory, pool, pool_helper = initialized_pool_fixture
        tick_lower = pool_helper.min_tick + pool_helper.tick_spacing
        tick_upper = pool_helper.max_tick - pool_helper.tick_spacing

        pool.advanceTime(10, {"from": accounts[0]})
        pool_helper.mint(accounts[0], tick_lower, tick_upper, 1)
        pool_helper.mint(
            accounts[0], tick_lower + pool_helper.tick_spacing, tick_upper, 1
        )
        pool_helper.swap_exact_0_for_1(utils.expand_to_18_decimals(1), accounts[0])
        pool.burn(tick_lower, tick_upper, 1, {"from": accounts[0]})

        utils.check_tick_is_clear(pool, tick_lower)
        utils.check_tick_is_not_clear(pool, tick_upper)

    def test_clears_only_the_upper_tick_if_lower_is_still_used(
        self, initialized_pool_fixture
    ):
        """
        Clears only the upper tick if lower is still used
        """
        token0, token1, factory, pool, pool_helper = initialized_pool_fixture
        tick_lower = pool_helper.min_tick + pool_helper.tick_spacing
        tick_upper = pool_helper.max_tick - pool_helper.tick_spacing

        pool.advanceTime(10, {"from": accounts[0]})
        pool_helper.mint(accounts[0], tick_lower, tick_upper, 1)
        pool_helper.mint(
            accounts[0], tick_lower, tick_upper - pool_helper.tick_spacing, 1
        )
        pool_helper.swap_exact_0_for_1(utils.expand_to_18_decimals(1), accounts[0])
        pool.burn(tick_lower, tick_upper, 1, {"from": accounts[0]})

        utils.check_tick_is_not_clear(pool, tick_lower)
        utils.check_tick_is_clear(pool, tick_upper)


class TestObserve:
    @pytest.fixture
    def initialized_pool_fixture(self, pool_fixture):
        token0, token1, factory, pool, pool_helper = pool_fixture
        pool.initialize(utils.encode_price_sqrt(1, 1), {"from": accounts[0]})
        pool_helper.mint(
            accounts[0],
            pool_helper.min_tick,
            pool_helper.max_tick,
            utils.expand_to_18_decimals(2),
        )
        return token0, token1, factory, pool, pool_helper

    def test_current_tick_accumulator_increases_by_tick_over_time(
        self, initialized_pool_fixture
    ):
        """
        Current tick accumulator increases by tick over time
        """
        token0, token1, factory, pool, pool_helper = initialized_pool_fixture
        tick_cumulative = pool.observe([0])[0]
        assert tick_cumulative[0] == 0
        pool.advanceTime(10, {"from": accounts[0]})
        tick_cumulative = pool.observe([0], {"from": accounts[0]})[0]
        assert tick_cumulative[0] == 0

    def test_current_tick_accumulator_after_single_swap(self, initialized_pool_fixture):
        """
        Current tick accumulator after single swap
        """
        token0, token1, factory, pool, pool_helper = initialized_pool_fixture
        pool_helper.swap_exact_0_for_1(1000, accounts[0])
        pool.advanceTime(4, {"from": accounts[0]})
        tick_cumulative = pool.observe([0], {"from": accounts[0]})[0]
        assert tick_cumulative[0] == -4

    def test_current_tick_accumulator_after_two_swaps(self, initialized_pool_fixture):
        """
        Current tick accumulator after two swaps
        """
        token0, token1, factory, pool, pool_helper = initialized_pool_fixture
        pool_helper.swap_exact_0_for_1(utils.expand_to_18_decimals(1) // 2, accounts[0])
        assert pool.slot0()[1] == -4452
        pool.advanceTime(4, {"from": accounts[0]})
        pool_helper.swap_exact_1_for_0(utils.expand_to_18_decimals(1) // 4, accounts[0])
        assert pool.slot0()[1] == -1558
        pool.advanceTime(6, {"from": accounts[0]})
        tick_cumulative = pool.observe([0], {"from": accounts[0]})[0]
        assert tick_cumulative[0] == -27156
