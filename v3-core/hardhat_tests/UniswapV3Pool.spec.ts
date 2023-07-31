import { ethers, waffle } from 'hardhat'
import { BigNumber, BigNumberish, constants, Wallet } from 'ethers'
import { TestERC20 } from '../typechain/TestERC20'
import { UniswapV3Factory } from '../typechain/UniswapV3Factory'
import { MockTimeUniswapV3Pool } from '../typechain/MockTimeUniswapV3Pool'
import { TestUniswapV3SwapPay } from '../typechain/TestUniswapV3SwapPay'
import checkObservationEquals from './shared/checkObservationEquals'
import { expect } from './shared/expect'

import { poolFixture, TEST_POOL_START_TIME } from './shared/fixtures'

import {
  expandTo18Decimals,
  FeeAmount,
  getPositionKey,
  getMaxTick,
  getMinTick,
  encodePriceSqrt,
  TICK_SPACINGS,
  createPoolFunctions,
  SwapFunction,
  MintFunction,
  getMaxLiquidityPerTick,
  FlashFunction,
  MaxUint128,
  MAX_SQRT_RATIO,
  MIN_SQRT_RATIO,
  SwapToPriceFunction,
} from './shared/utilities'
import { TestUniswapV3Callee } from '../typechain/TestUniswapV3Callee'
import { TestUniswapV3ReentrantCallee } from '../typechain/TestUniswapV3ReentrantCallee'
import { TickMathTest } from '../typechain/TickMathTest'
import { SwapMathTest } from '../typechain/SwapMathTest'

const createFixtureLoader = waffle.createFixtureLoader

type ThenArg<T> = T extends PromiseLike<infer U> ? U : T

describe('UniswapV3Pool', () => {
  let wallet: Wallet, other: Wallet

  let token0: TestERC20
  let token1: TestERC20
  let token2: TestERC20

  let factory: UniswapV3Factory
  let pool: MockTimeUniswapV3Pool

  let swapTarget: TestUniswapV3Callee

  let swapToLowerPrice: SwapToPriceFunction
  let swapToHigherPrice: SwapToPriceFunction
  let swapExact0For1: SwapFunction
  let swap0ForExact1: SwapFunction
  let swapExact1For0: SwapFunction
  let swap1ForExact0: SwapFunction

  let feeAmount: number
  let tickSpacing: number

  let minTick: number
  let maxTick: number

  let mint: MintFunction
  let flash: FlashFunction

  let loadFixture: ReturnType<typeof createFixtureLoader>
  let createPool: ThenArg<ReturnType<typeof poolFixture>>['createPool']

  before('create fixture loader', async () => {
    ;[wallet, other] = await (ethers as any).getSigners()
    loadFixture = createFixtureLoader([wallet, other])
  })

  beforeEach('deploy fixture', async () => {
    ;({ token0, token1, token2, factory, createPool, swapTargetCallee: swapTarget } = await loadFixture(poolFixture))
    const oldCreatePool = createPool
    createPool = async (_feeAmount, _tickSpacing) => {
      const pool = await oldCreatePool(_feeAmount, _tickSpacing)
      ;({
        swapToLowerPrice,
        swapToHigherPrice,
        swapExact0For1,
        swap0ForExact1,
        swapExact1For0,
        swap1ForExact0,
        mint,
        flash,
      } = createPoolFunctions({
        token0,
        token1,
        swapTarget,
        pool,
      }))
      minTick = getMinTick(_tickSpacing)
      maxTick = getMaxTick(_tickSpacing)
      feeAmount = _feeAmount
      tickSpacing = _tickSpacing
      return pool
    }

    // default to the 30 bips pool
    pool = await createPool(FeeAmount.MEDIUM, TICK_SPACINGS[FeeAmount.MEDIUM])
  })

  it('constructor initializes immutables', async () => {
    expect(await pool.factory()).to.eq(factory.address)
    expect(await pool.token0()).to.eq(token0.address)
    expect(await pool.token1()).to.eq(token1.address)
    expect(await pool.maxLiquidityPerTick()).to.eq(getMaxLiquidityPerTick(tickSpacing))
  })

  describe('#initialize', () => {
    it('fails if already initialized', async () => {
      await pool.initialize(encodePriceSqrt(1, 1))
      await expect(pool.initialize(encodePriceSqrt(1, 1))).to.be.reverted
    })
    it('fails if starting price is too low', async () => {
      await expect(pool.initialize(1)).to.be.revertedWith('R')
      await expect(pool.initialize(MIN_SQRT_RATIO.sub(1))).to.be.revertedWith('R')
    })
    it('fails if starting price is too high', async () => {
      await expect(pool.initialize(MAX_SQRT_RATIO)).to.be.revertedWith('R')
      await expect(pool.initialize(BigNumber.from(2).pow(160).sub(1))).to.be.revertedWith('R')
    })
    it('can be initialized at MIN_SQRT_RATIO', async () => {
      await pool.initialize(MIN_SQRT_RATIO)
      expect((await pool.slot0()).tick).to.eq(getMinTick(1))
    })
    it('can be initialized at MAX_SQRT_RATIO - 1', async () => {
      await pool.initialize(MAX_SQRT_RATIO.sub(1))
      expect((await pool.slot0()).tick).to.eq(getMaxTick(1) - 1)
    })
    it('sets initial variables', async () => {
      const price = encodePriceSqrt(1, 2)
      await pool.initialize(price)

      const { sqrtPriceX96, observationIndex } = await pool.slot0()
      expect(sqrtPriceX96).to.eq(price)
      expect(observationIndex).to.eq(0)
      expect((await pool.slot0()).tick).to.eq(-6932)
    })
    it('initializes the first observations slot', async () => {
      await pool.initialize(encodePriceSqrt(1, 1))
      checkObservationEquals(await pool.observations(0), {
        secondsPerLiquidityCumulativeX128: 0,
        initialized: true,
        blockTimestamp: TEST_POOL_START_TIME,
        tickCumulative: 0,
      })
    })
    it('emits a Initialized event with the input tick', async () => {
      const sqrtPriceX96 = encodePriceSqrt(1, 2)
      await expect(pool.initialize(sqrtPriceX96)).to.emit(pool, 'Initialize').withArgs(sqrtPriceX96, -6932)
    })
  })

  describe('#increaseObservationCardinalityNext', () => {
    it('can only be called after initialize', async () => {
      await expect(pool.increaseObservationCardinalityNext(2)).to.be.revertedWith('LOK')
    })
    it('emits an event including both old and new', async () => {
      await pool.initialize(encodePriceSqrt(1, 1))
      await expect(pool.increaseObservationCardinalityNext(2))
        .to.emit(pool, 'IncreaseObservationCardinalityNext')
        .withArgs(1, 2)
    })
    it('does not emit an event for no op call', async () => {
      await pool.initialize(encodePriceSqrt(1, 1))
      await pool.increaseObservationCardinalityNext(3)
      await expect(pool.increaseObservationCardinalityNext(2)).to.not.emit(pool, 'IncreaseObservationCardinalityNext')
    })
    it('does not change cardinality next if less than current', async () => {
      await pool.initialize(encodePriceSqrt(1, 1))
      await pool.increaseObservationCardinalityNext(3)
      await pool.increaseObservationCardinalityNext(2)
      expect((await pool.slot0()).observationCardinalityNext).to.eq(3)
    })
    it('increases cardinality and cardinality next first time', async () => {
      await pool.initialize(encodePriceSqrt(1, 1))
      await pool.increaseObservationCardinalityNext(2)
      const { observationCardinality, observationCardinalityNext } = await pool.slot0()
      expect(observationCardinality).to.eq(1)
      expect(observationCardinalityNext).to.eq(2)
    })
  })

  describe('#mint', () => {
    it('fails if not initialized', async () => {
      await expect(mint(wallet.address, -tickSpacing, tickSpacing, 1)).to.be.revertedWith('LOK')
    })
    describe('after initialization', () => {
      beforeEach('initialize the pool at price of 10:1', async () => {
        await pool.initialize(encodePriceSqrt(1, 10))
        await mint(wallet.address, minTick, maxTick, 3161)
      })

      describe('failure cases', () => {
        it('fails if tickLower greater than tickUpper', async () => {
          // should be TLU but...hardhat
          await expect(mint(wallet.address, 1, 0, 1)).to.be.reverted
        })
        it('fails if tickLower less than min tick', async () => {
          // should be TLM but...hardhat
          await expect(mint(wallet.address, -887273, 0, 1)).to.be.reverted
        })
        it('fails if tickUpper greater than max tick', async () => {
          // should be TUM but...hardhat
          await expect(mint(wallet.address, 0, 887273, 1)).to.be.reverted
        })
        it('fails if amount exceeds the max', async () => {
          // these should fail with 'LO' but hardhat is bugged
          const maxLiquidityGross = await pool.maxLiquidityPerTick()
          await expect(mint(wallet.address, minTick + tickSpacing, maxTick - tickSpacing, maxLiquidityGross.add(1))).to
            .be.reverted
          await expect(mint(wallet.address, minTick + tickSpacing, maxTick - tickSpacing, maxLiquidityGross)).to.not.be
            .reverted
        })
        it('fails if total amount at tick exceeds the max', async () => {
          // these should fail with 'LO' but hardhat is bugged
          await mint(wallet.address, minTick + tickSpacing, maxTick - tickSpacing, 1000)

          const maxLiquidityGross = await pool.maxLiquidityPerTick()
          await expect(
            mint(wallet.address, minTick + tickSpacing, maxTick - tickSpacing, maxLiquidityGross.sub(1000).add(1))
          ).to.be.reverted
          await expect(
            mint(wallet.address, minTick + tickSpacing * 2, maxTick - tickSpacing, maxLiquidityGross.sub(1000).add(1))
          ).to.be.reverted
          await expect(
            mint(wallet.address, minTick + tickSpacing, maxTick - tickSpacing * 2, maxLiquidityGross.sub(1000).add(1))
          ).to.be.reverted
          await expect(mint(wallet.address, minTick + tickSpacing, maxTick - tickSpacing, maxLiquidityGross.sub(1000)))
            .to.not.be.reverted
        })
        it('fails if amount is 0', async () => {
          await expect(mint(wallet.address, minTick + tickSpacing, maxTick - tickSpacing, 0)).to.be.reverted
        })
      })

      describe('success cases', () => {
        it('initial balances', async () => {
          expect(await token0.balanceOf(pool.address)).to.eq(9996)
          expect(await token1.balanceOf(pool.address)).to.eq(1000)
        })

        it('initial tick', async () => {
          expect((await pool.slot0()).tick).to.eq(-23028)
        })

        describe('above current price', () => {
          it('transfers token0 only', async () => {
            await expect(mint(wallet.address, -22980, 0, 10000))
              .to.emit(token0, 'Transfer')
              .withArgs(wallet.address, pool.address, 21549)
              .to.not.emit(token1, 'Transfer')
            expect(await token0.balanceOf(pool.address)).to.eq(9996 + 21549)
            expect(await token1.balanceOf(pool.address)).to.eq(1000)
          })

          it('max tick with max leverage', async () => {
            await mint(wallet.address, maxTick - tickSpacing, maxTick, BigNumber.from(2).pow(102))
            expect(await token0.balanceOf(pool.address)).to.eq(9996 + 828011525)
            expect(await token1.balanceOf(pool.address)).to.eq(1000)
          })

          it('works for max tick', async () => {
            await expect(mint(wallet.address, -22980, maxTick, 10000))
              .to.emit(token0, 'Transfer')
              .withArgs(wallet.address, pool.address, 31549)
            expect(await token0.balanceOf(pool.address)).to.eq(9996 + 31549)
            expect(await token1.balanceOf(pool.address)).to.eq(1000)
          })

          it('removing works', async () => {
            await mint(wallet.address, -240, 0, 10000)
            await pool.burn(-240, 0, 10000)
            const { amount0, amount1 } = await pool.callStatic.collect(wallet.address, -240, 0, MaxUint128, MaxUint128)
            expect(amount0, 'amount0').to.eq(120)
            expect(amount1, 'amount1').to.eq(0)
          })

          it('adds liquidity to liquidityGross', async () => {
            await mint(wallet.address, -240, 0, 100)
            expect((await pool.ticks(-240)).liquidityGross).to.eq(100)
            expect((await pool.ticks(0)).liquidityGross).to.eq(100)
            expect((await pool.ticks(tickSpacing)).liquidityGross).to.eq(0)
            expect((await pool.ticks(tickSpacing * 2)).liquidityGross).to.eq(0)
            await mint(wallet.address, -240, tickSpacing, 150)
            expect((await pool.ticks(-240)).liquidityGross).to.eq(250)
            expect((await pool.ticks(0)).liquidityGross).to.eq(100)
            expect((await pool.ticks(tickSpacing)).liquidityGross).to.eq(150)
            expect((await pool.ticks(tickSpacing * 2)).liquidityGross).to.eq(0)
            await mint(wallet.address, 0, tickSpacing * 2, 60)
            expect((await pool.ticks(-240)).liquidityGross).to.eq(250)
            expect((await pool.ticks(0)).liquidityGross).to.eq(160)
            expect((await pool.ticks(tickSpacing)).liquidityGross).to.eq(150)
            expect((await pool.ticks(tickSpacing * 2)).liquidityGross).to.eq(60)
          })

          it('removes liquidity from liquidityGross', async () => {
            await mint(wallet.address, -240, 0, 100)
            await mint(wallet.address, -240, 0, 40)
            await pool.burn(-240, 0, 90)
            expect((await pool.ticks(-240)).liquidityGross).to.eq(50)
            expect((await pool.ticks(0)).liquidityGross).to.eq(50)
          })

          it('clears tick lower if last position is removed', async () => {
            await mint(wallet.address, -240, 0, 100)
            await pool.burn(-240, 0, 100)
            const { liquidityGross, feeGrowthOutside0X128, feeGrowthOutside1X128 } = await pool.ticks(-240)
            expect(liquidityGross).to.eq(0)
            expect(feeGrowthOutside0X128).to.eq(0)
            expect(feeGrowthOutside1X128).to.eq(0)
          })

          it('clears tick upper if last position is removed', async () => {
            await mint(wallet.address, -240, 0, 100)
            await pool.burn(-240, 0, 100)
            const { liquidityGross, feeGrowthOutside0X128, feeGrowthOutside1X128 } = await pool.ticks(0)
            expect(liquidityGross).to.eq(0)
            expect(feeGrowthOutside0X128).to.eq(0)
            expect(feeGrowthOutside1X128).to.eq(0)
          })
          it('only clears the tick that is not used at all', async () => {
            await mint(wallet.address, -240, 0, 100)
            await mint(wallet.address, -tickSpacing, 0, 250)
            await pool.burn(-240, 0, 100)

            let { liquidityGross, feeGrowthOutside0X128, feeGrowthOutside1X128 } = await pool.ticks(-240)
            expect(liquidityGross).to.eq(0)
            expect(feeGrowthOutside0X128).to.eq(0)
            expect(feeGrowthOutside1X128).to.eq(0)
            ;({ liquidityGross, feeGrowthOutside0X128, feeGrowthOutside1X128 } = await pool.ticks(-tickSpacing))
            expect(liquidityGross).to.eq(250)
            expect(feeGrowthOutside0X128).to.eq(0)
            expect(feeGrowthOutside1X128).to.eq(0)
          })

          it('does not write an observation', async () => {
            checkObservationEquals(await pool.observations(0), {
              tickCumulative: 0,
              blockTimestamp: TEST_POOL_START_TIME,
              initialized: true,
              secondsPerLiquidityCumulativeX128: 0,
            })
            await pool.advanceTime(1);
            await mint(wallet.address, -240, 0, 100)
            checkObservationEquals(await pool.observations(0), {
              tickCumulative: 0,
              blockTimestamp: TEST_POOL_START_TIME,
              initialized: true,
              secondsPerLiquidityCumulativeX128: 0,
            })
          })
        })

        describe('including current price', () => {
          it('price within range: transfers current price of both tokens', async () => {
            await expect(mint(wallet.address, minTick + tickSpacing, maxTick - tickSpacing, 100))
              .to.emit(token0, 'Transfer')
              .withArgs(wallet.address, pool.address, 317)
              .to.emit(token1, 'Transfer')
              .withArgs(wallet.address, pool.address, 32)
            expect(await token0.balanceOf(pool.address)).to.eq(9996 + 317)
            expect(await token1.balanceOf(pool.address)).to.eq(1000 + 32)
          })

          it('initializes lower tick', async () => {
            await mint(wallet.address, minTick + tickSpacing, maxTick - tickSpacing, 100)
            const { liquidityGross } = await pool.ticks(minTick + tickSpacing)
            expect(liquidityGross).to.eq(100)
          })

          it('initializes upper tick', async () => {
            await mint(wallet.address, minTick + tickSpacing, maxTick - tickSpacing, 100)
            const { liquidityGross } = await pool.ticks(maxTick - tickSpacing)
            expect(liquidityGross).to.eq(100)
          })

          it('works for min/max tick', async () => {
            await expect(mint(wallet.address, minTick, maxTick, 10000))
              .to.emit(token0, 'Transfer')
              .withArgs(wallet.address, pool.address, 31623)
              .to.emit(token1, 'Transfer')
              .withArgs(wallet.address, pool.address, 3163)
            expect(await token0.balanceOf(pool.address)).to.eq(9996 + 31623)
            expect(await token1.balanceOf(pool.address)).to.eq(1000 + 3163)
          })

          it('removing works', async () => {
            await mint(wallet.address, minTick + tickSpacing, maxTick - tickSpacing, 100)
            await pool.burn(minTick + tickSpacing, maxTick - tickSpacing, 100)
            const { amount0, amount1 } = await pool.callStatic.collect(
              wallet.address,
              minTick + tickSpacing,
              maxTick - tickSpacing,
              MaxUint128,
              MaxUint128
            )
            expect(amount0, 'amount0').to.eq(316)
            expect(amount1, 'amount1').to.eq(31)
          })

          it('writes an observation', async () => {
            checkObservationEquals(await pool.observations(0), {
              tickCumulative: 0,
              blockTimestamp: TEST_POOL_START_TIME,
              initialized: true,
              secondsPerLiquidityCumulativeX128: 0,
            })
            await pool.advanceTime(1)
            await mint(wallet.address, minTick, maxTick, 100)
            checkObservationEquals(await pool.observations(0), {
              tickCumulative: -23028,
              blockTimestamp: TEST_POOL_START_TIME + 1,
              initialized: true,
              secondsPerLiquidityCumulativeX128: '107650226801941937191829992860413859',
            })
          })
        })

        describe('below current price', () => {
          it('transfers token1 only', async () => {
            await expect(mint(wallet.address, -46080, -23040, 10000))
              .to.emit(token1, 'Transfer')
              .withArgs(wallet.address, pool.address, 2162)
              .to.not.emit(token0, 'Transfer')
            expect(await token0.balanceOf(pool.address)).to.eq(9996)
            expect(await token1.balanceOf(pool.address)).to.eq(1000 + 2162)
          })

          it('min tick with max leverage', async () => {
            await mint(wallet.address, minTick, minTick + tickSpacing, BigNumber.from(2).pow(102))
            expect(await token0.balanceOf(pool.address)).to.eq(9996)
            expect(await token1.balanceOf(pool.address)).to.eq(1000 + 828011520)
          })

          it('works for min tick', async () => {
            await expect(mint(wallet.address, minTick, -23040, 10000))
              .to.emit(token1, 'Transfer')
              .withArgs(wallet.address, pool.address, 3161)
            expect(await token0.balanceOf(pool.address)).to.eq(9996)
            expect(await token1.balanceOf(pool.address)).to.eq(1000 + 3161)
          })

          it('removing works', async () => {
            await mint(wallet.address, -46080, -46020, 10000)
            await pool.burn(-46080, -46020, 10000)
            const { amount0, amount1 } = await pool.callStatic.collect(
              wallet.address,
              -46080,
              -46020,
              MaxUint128,
              MaxUint128
            )
            expect(amount0, 'amount0').to.eq(0)
            expect(amount1, 'amount1').to.eq(3)
          })

          it('does not write an observation', async () => {
            checkObservationEquals(await pool.observations(0), {
              tickCumulative: 0,
              blockTimestamp: TEST_POOL_START_TIME,
              initialized: true,
              secondsPerLiquidityCumulativeX128: 0,
            })
            await pool.advanceTime(1)
            await mint(wallet.address, -46080, -23040, 100)
            checkObservationEquals(await pool.observations(0), {
              tickCumulative: 0,
              blockTimestamp: TEST_POOL_START_TIME,
              initialized: true,
              secondsPerLiquidityCumulativeX128: 0,
            })
          })
        })
      })

      it('protocol fees accumulate as expected during swap', async () => {
        await pool.setFeeProtocol(6, 6)

        await mint(wallet.address, minTick + tickSpacing, maxTick - tickSpacing, expandTo18Decimals(1))
        await swapExact0For1(expandTo18Decimals(1).div(10), wallet.address)
        await swapExact1For0(expandTo18Decimals(1).div(100), wallet.address)

        let { token0: token0ProtocolFees, token1: token1ProtocolFees } = await pool.protocolFees()
        expect(token0ProtocolFees).to.eq('50000000000000')
        expect(token1ProtocolFees).to.eq('5000000000000')
      })

      it('positions are protected before protocol fee is turned on', async () => {
        await mint(wallet.address, minTick + tickSpacing, maxTick - tickSpacing, expandTo18Decimals(1))
        await swapExact0For1(expandTo18Decimals(1).div(10), wallet.address)
        await swapExact1For0(expandTo18Decimals(1).div(100), wallet.address)

        let { token0: token0ProtocolFees, token1: token1ProtocolFees } = await pool.protocolFees()
        expect(token0ProtocolFees).to.eq(0)
        expect(token1ProtocolFees).to.eq(0)

        await pool.setFeeProtocol(6, 6)
        ;({ token0: token0ProtocolFees, token1: token1ProtocolFees } = await pool.protocolFees())
        expect(token0ProtocolFees).to.eq(0)
        expect(token1ProtocolFees).to.eq(0)
      })

      it('poke is not allowed on uninitialized position', async () => {
        await mint(other.address, minTick + tickSpacing, maxTick - tickSpacing, expandTo18Decimals(1))
        await swapExact0For1(expandTo18Decimals(1).div(10), wallet.address)
        await swapExact1For0(expandTo18Decimals(1).div(100), wallet.address)

        // missing revert reason due to hardhat
        await expect(pool.burn(minTick + tickSpacing, maxTick - tickSpacing, 0)).to.be.reverted

        await mint(wallet.address, minTick + tickSpacing, maxTick - tickSpacing, 1)
        let {
          liquidity,
          feeGrowthInside0LastX128,
          feeGrowthInside1LastX128,
          tokensOwed1,
          tokensOwed0,
        } = await pool.positions(getPositionKey(wallet.address, minTick + tickSpacing, maxTick - tickSpacing))
        expect(liquidity).to.eq(1)
        expect(feeGrowthInside0LastX128).to.eq('102084710076281216349243831104605583')
        expect(feeGrowthInside1LastX128).to.eq('10208471007628121634924383110460558')
        expect(tokensOwed0, 'tokens owed 0 before').to.eq(0)
        expect(tokensOwed1, 'tokens owed 1 before').to.eq(0)

        await pool.burn(minTick + tickSpacing, maxTick - tickSpacing, 1)
        ;({
          liquidity,
          feeGrowthInside0LastX128,
          feeGrowthInside1LastX128,
          tokensOwed1,
          tokensOwed0,
        } = await pool.positions(getPositionKey(wallet.address, minTick + tickSpacing, maxTick - tickSpacing)))
        expect(liquidity).to.eq(0)
        expect(feeGrowthInside0LastX128).to.eq('102084710076281216349243831104605583')
        expect(feeGrowthInside1LastX128).to.eq('10208471007628121634924383110460558')
        expect(tokensOwed0, 'tokens owed 0 after').to.eq(3)
        expect(tokensOwed1, 'tokens owed 1 after').to.eq(0)
      })
    })
  })

  describe('#burn', () => {
    beforeEach('initialize at zero tick', () => initializeAtZeroTick(pool))

    async function checkTickIsClear(tick: number) {
      const { liquidityGross, feeGrowthOutside0X128, feeGrowthOutside1X128, liquidityNet } = await pool.ticks(tick)
      expect(liquidityGross).to.eq(0)
      expect(feeGrowthOutside0X128).to.eq(0)
      expect(feeGrowthOutside1X128).to.eq(0)
      expect(liquidityNet).to.eq(0)
    }

    async function checkTickIsNotClear(tick: number) {
      const { liquidityGross } = await pool.ticks(tick)
      expect(liquidityGross).to.not.eq(0)
    }

    it('does not clear the position fee growth snapshot if no more liquidity', async () => {
      // some activity that would make the ticks non-zero
      await pool.advanceTime(10)
      await mint(other.address, minTick, maxTick, expandTo18Decimals(1))
      await swapExact0For1(expandTo18Decimals(1), wallet.address)
      await swapExact1For0(expandTo18Decimals(1), wallet.address)
      await pool.connect(other).burn(minTick, maxTick, expandTo18Decimals(1))
      const {
        liquidity,
        tokensOwed0,
        tokensOwed1,
        feeGrowthInside0LastX128,
        feeGrowthInside1LastX128,
      } = await pool.positions(getPositionKey(other.address, minTick, maxTick))
      expect(liquidity).to.eq(0)
      expect(tokensOwed0).to.not.eq(0)
      expect(tokensOwed1).to.not.eq(0)
      expect(feeGrowthInside0LastX128).to.eq('340282366920938463463374607431768211')
      expect(feeGrowthInside1LastX128).to.eq('340282366920938576890830247744589365')
    })

    it('clears the tick if its the last position using it', async () => {
      const tickLower = minTick + tickSpacing
      const tickUpper = maxTick - tickSpacing
      // some activity that would make the ticks non-zero
      await pool.advanceTime(10)
      await mint(wallet.address, tickLower, tickUpper, 1)
      await swapExact0For1(expandTo18Decimals(1), wallet.address)
      await pool.burn(tickLower, tickUpper, 1)
      await checkTickIsClear(tickLower)
      await checkTickIsClear(tickUpper)
    })

    it('clears only the lower tick if upper is still used', async () => {
      const tickLower = minTick + tickSpacing
      const tickUpper = maxTick - tickSpacing
      // some activity that would make the ticks non-zero
      await pool.advanceTime(10)
      await mint(wallet.address, tickLower, tickUpper, 1)
      await mint(wallet.address, tickLower + tickSpacing, tickUpper, 1)
      await swapExact0For1(expandTo18Decimals(1), wallet.address)
      await pool.burn(tickLower, tickUpper, 1)
      await checkTickIsClear(tickLower)
      await checkTickIsNotClear(tickUpper)
    })

    it('clears only the upper tick if lower is still used', async () => {
      const tickLower = minTick + tickSpacing
      const tickUpper = maxTick - tickSpacing
      // some activity that would make the ticks non-zero
      await pool.advanceTime(10)
      await mint(wallet.address, tickLower, tickUpper, 1)
      await mint(wallet.address, tickLower, tickUpper - tickSpacing, 1)
      await swapExact0For1(expandTo18Decimals(1), wallet.address)
      await pool.burn(tickLower, tickUpper, 1)
      await checkTickIsNotClear(tickLower)
      await checkTickIsClear(tickUpper)
    })
  })

  // the combined amount of liquidity that the pool is initialized with (including the 1 minimum liquidity that is burned)
  const initializeLiquidityAmount = expandTo18Decimals(2)
  async function initializeAtZeroTick(pool: MockTimeUniswapV3Pool): Promise<void> {
    await pool.initialize(encodePriceSqrt(1, 1))
    const tickSpacing = await pool.tickSpacing()
    const [min, max] = [getMinTick(tickSpacing), getMaxTick(tickSpacing)]
    await mint(wallet.address, min, max, initializeLiquidityAmount)
  }

  describe('#observe', () => {
    beforeEach(() => initializeAtZeroTick(pool))

    // zero tick
    it('current tick accumulator increases by tick over time', async () => {
      let {
        tickCumulatives: [tickCumulative],
      } = await pool.observe([0])
      expect(tickCumulative).to.eq(0)
      await pool.advanceTime(10)
      ;({
        tickCumulatives: [tickCumulative],
      } = await pool.observe([0]))
      expect(tickCumulative).to.eq(0)
    })

    it('current tick accumulator after single swap', async () => {
      // moves to tick -1
      await swapExact0For1(1000, wallet.address)
      await pool.advanceTime(4)
      let {
        tickCumulatives: [tickCumulative],
      } = await pool.observe([0])
      expect(tickCumulative).to.eq(-4)
    })

    it('current tick accumulator after two swaps', async () => {
      await swapExact0For1(expandTo18Decimals(1).div(2), wallet.address)
      expect((await pool.slot0()).tick).to.eq(-4452)
      await pool.advanceTime(4)
      await swapExact1For0(expandTo18Decimals(1).div(4), wallet.address)
      expect((await pool.slot0()).tick).to.eq(-1558)
      await pool.advanceTime(6)
      let {
        tickCumulatives: [tickCumulative],
      } = await pool.observe([0])
      // -4452*4 + -1558*6
      expect(tickCumulative).to.eq(-27156)
    })
  })
})