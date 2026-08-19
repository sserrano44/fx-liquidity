"""Exact Uniswap-v3 swap simulation from raw pool state.

Quoter contracts only exist for blessed deployments, and several pools that matter
here live on forks with no quoter we can address (a newer Aerodrome CL factory on
Base, Uniswap v3 on Gnosis). This reimplements UniswapV3Pool.swap exactly -- same
fixed-point rounding, same tick-bitmap traversal -- so any v3-style pool on any
chain can be priced from slot0 / liquidity / ticks / tickBitmap alone.

Verified against the on-chain QuoterV2 to the wei in test_v3math.py.
"""
from eth_abi import decode as abi_decode, encode as abi_encode
from eth_utils import keccak

import rpc

Q96 = 1 << 96
MIN_TICK, MAX_TICK = -887272, 887272
MIN_SQRT_RATIO = 4295128739
MAX_SQRT_RATIO = 1461446703485210103287273052203988822378723970342


def _sel(sig):
    return keccak(text=sig)[:4]


SEL = {
    "slot0": _sel("slot0()"),
    "liquidity": _sel("liquidity()"),
    "fee": _sel("fee()"),
    "tickSpacing": _sel("tickSpacing()"),
    "token0": _sel("token0()"),
    "token1": _sel("token1()"),
    "ticks": _sel("ticks(int24)"),
    "tickBitmap": _sel("tickBitmap(int16)"),
}


# ------------------------------------------------------------------ TickMath

def get_sqrt_ratio_at_tick(tick):
    abs_tick = abs(tick)
    if abs_tick > MAX_TICK:
        raise ValueError("tick out of range")
    ratio = 0xfffcb933bd6fad37aa2d162d1a594001 if abs_tick & 0x1 else 0x100000000000000000000000000000000
    for bit, const in (
        (0x2, 0xfff97272373d413259a46990580e213a),
        (0x4, 0xfff2e50f5f656932ef12357cf3c7fdcc),
        (0x8, 0xffe5caca7e10e4e61c3624eaa0941cd0),
        (0x10, 0xffcb9843d60f6159c9db58835c926644),
        (0x20, 0xff973b41fa98c081472e6896dfb254c0),
        (0x40, 0xff2ea16466c96a3843ec78b326b52861),
        (0x80, 0xfe5dee046a99a2a811c461f1969c3053),
        (0x100, 0xfcbe86c7900a88aedcffc83b479aa3a4),
        (0x200, 0xf987a7253ac413176f2b074cf7815e54),
        (0x400, 0xf3392b0822b70005940c7a398e4b70f3),
        (0x800, 0xe7159475a2c29b7443b29c7fa6e889d9),
        (0x1000, 0xd097f3bdfd2022b8845ad8f792aa5825),
        (0x2000, 0xa9f746462d870fdf8a65dc1f90e061e5),
        (0x4000, 0x70d869a156d2a1b890bb3df62baf32f7),
        (0x8000, 0x31be135f97d08fd981231505542fcfa6),
        (0x10000, 0x9aa508b5b7a84e1c677de54f3e99bc9),
        (0x20000, 0x5d6af8dedb81196699c329225ee604),
        (0x40000, 0x2216e584f5fa1ea926041bedfe98),
        (0x80000, 0x48a170391f7dc42444e8fa2),
    ):
        if abs_tick & bit:
            ratio = (ratio * const) >> 128
    if tick > 0:
        ratio = ((1 << 256) - 1) // ratio
    # round up to Q96
    return (ratio >> 32) + (1 if ratio % (1 << 32) else 0)


# ------------------------------------------------------------------ SqrtPriceMath

def _mul_div_round_up(a, b, denom):
    x = a * b
    return x // denom + (1 if x % denom else 0)


def get_amount0_delta(sqrt_a, sqrt_b, liquidity, round_up):
    if sqrt_a > sqrt_b:
        sqrt_a, sqrt_b = sqrt_b, sqrt_a
    num1 = liquidity << 96
    num2 = sqrt_b - sqrt_a
    if round_up:
        return _mul_div_round_up(_mul_div_round_up(num1, num2, sqrt_b), 1, sqrt_a)
    return (num1 * num2 // sqrt_b) // sqrt_a


def get_amount1_delta(sqrt_a, sqrt_b, liquidity, round_up):
    if sqrt_a > sqrt_b:
        sqrt_a, sqrt_b = sqrt_b, sqrt_a
    if round_up:
        return _mul_div_round_up(liquidity, sqrt_b - sqrt_a, Q96)
    return liquidity * (sqrt_b - sqrt_a) // Q96


def get_next_sqrt_price_from_amount0_rounding_up(sqrt_p, liquidity, amount, add):
    if amount == 0:
        return sqrt_p
    num1 = liquidity << 96
    if add:
        product = amount * sqrt_p
        if product // amount == sqrt_p:
            denominator = num1 + product
            if denominator >= num1:
                return _mul_div_round_up(num1, sqrt_p, denominator)
        return _mul_div_round_up(num1, 1, num1 // sqrt_p + amount)
    product = amount * sqrt_p
    denominator = num1 - product
    return _mul_div_round_up(num1, sqrt_p, denominator)


def get_next_sqrt_price_from_amount1_rounding_down(sqrt_p, liquidity, amount, add):
    if add:
        quotient = (amount << 96) // liquidity
        return sqrt_p + quotient
    quotient = _mul_div_round_up(amount, Q96, liquidity)
    return sqrt_p - quotient


def get_next_sqrt_price_from_input(sqrt_p, liquidity, amount_in, zero_for_one):
    if zero_for_one:
        return get_next_sqrt_price_from_amount0_rounding_up(sqrt_p, liquidity, amount_in, True)
    return get_next_sqrt_price_from_amount1_rounding_down(sqrt_p, liquidity, amount_in, True)


def compute_swap_step(sqrt_current, sqrt_target, liquidity, amount_remaining, fee_pips):
    """Exact-input only. Returns (sqrt_next, amount_in, amount_out, fee_amount)."""
    zero_for_one = sqrt_current >= sqrt_target
    amount_remaining_less_fee = amount_remaining * (10 ** 6 - fee_pips) // 10 ** 6

    if zero_for_one:
        amount_in = get_amount0_delta(sqrt_target, sqrt_current, liquidity, True)
    else:
        amount_in = get_amount1_delta(sqrt_current, sqrt_target, liquidity, True)

    if amount_remaining_less_fee >= amount_in:
        sqrt_next = sqrt_target
    else:
        sqrt_next = get_next_sqrt_price_from_input(
            sqrt_current, liquidity, amount_remaining_less_fee, zero_for_one)

    at_max = sqrt_next == sqrt_target

    if zero_for_one:
        amount_in = amount_in if at_max else get_amount0_delta(sqrt_next, sqrt_current, liquidity, True)
        amount_out = get_amount1_delta(sqrt_next, sqrt_current, liquidity, False)
    else:
        amount_in = amount_in if at_max else get_amount1_delta(sqrt_current, sqrt_next, liquidity, True)
        amount_out = get_amount0_delta(sqrt_current, sqrt_next, liquidity, False)

    if not at_max:
        fee_amount = amount_remaining - amount_in
    else:
        fee_amount = _mul_div_round_up(amount_in, fee_pips, 10 ** 6 - fee_pips)
    return sqrt_next, amount_in, amount_out, fee_amount


# ------------------------------------------------------------------ pool state

def _msb(x):
    return x.bit_length() - 1


def _lsb(x):
    return (x & -x).bit_length() - 1


class Pool:
    """Lazily-loaded v3 pool state. Tick words are fetched on demand and cached."""

    def __init__(self, chain, address, block="latest"):
        self.chain = chain
        self.address = address
        self.block = block
        self._words = {}
        self._ticks = {}
        self._descending = True
        res = rpc.batch_call(chain, [
            (address, "0x" + SEL["slot0"].hex()),
            (address, "0x" + SEL["liquidity"].hex()),
            (address, "0x" + SEL["fee"].hex()),
            (address, "0x" + SEL["tickSpacing"].hex()),
            (address, "0x" + SEL["token0"].hex()),
            (address, "0x" + SEL["token1"].hex()),
        ], block=block)
        if not res[0]:
            raise ValueError("no slot0")
        raw = bytes.fromhex(res[0][2:])
        self.sqrt_price = int.from_bytes(raw[0:32], "big")
        tick = int.from_bytes(raw[32:64], "big")
        self.tick = tick - (1 << 256) if tick >= (1 << 255) else tick
        self.liquidity = int(res[1], 16)
        self.fee = int(res[2], 16)
        ts = int(res[3], 16)
        self.tick_spacing = ts - (1 << 256) if ts >= (1 << 255) else ts
        self.token0 = "0x" + res[4][-40:]
        self.token1 = "0x" + res[5][-40:]

    # A swap through a thin pool can cross hundreds of ticks. Fetched one at a
    # time that is hundreds of sequential round trips per quote, so words are
    # pulled in blocks and every initialized tick inside them is loaded at once.
    WORD_BLOCK = 12

    def _load_words(self, start, descending):
        want = [start + (-i if descending else i) for i in range(self.WORD_BLOCK)]
        want = [w for w in want if w not in self._words]
        if not want:
            return
        calls = [(self.address,
                  "0x" + (SEL["tickBitmap"] + (w & 0xFFFF).to_bytes(32, "big")).hex())
                 for w in want]
        res = rpc.batch_call(self.chain, calls, block=self.block)
        ticks_to_load = []
        for w, r in zip(want, res):
            val = int(r, 16) if r and r != "0x" else 0
            self._words[w] = val
            bits = val
            while bits:
                bit = _lsb(bits)
                bits &= bits - 1
                ticks_to_load.append(((w << 8) + bit) * self.tick_spacing)
        self._load_ticks(ticks_to_load)

    def _load_ticks(self, ticks):
        want = [t for t in ticks if t not in self._ticks]
        if not want:
            return
        calls = [(self.address,
                  "0x" + (SEL["ticks"] + (t & ((1 << 256) - 1)).to_bytes(32, "big")).hex())
                 for t in want]
        res = rpc.batch_call(self.chain, calls, block=self.block)
        for t, r in zip(want, res):
            if not r or len(r) < 130:
                self._ticks[t] = 0
                continue
            raw = bytes.fromhex(r[2:])
            net = int.from_bytes(raw[32:64], "big")
            self._ticks[t] = net - (1 << 256) if net >= (1 << 255) else net

    def _word(self, word_pos):
        if word_pos not in self._words:
            self._load_words(word_pos, descending=self._descending)
        if word_pos not in self._words:   # batch failed; fall back to a single read
            arg = word_pos & 0xFFFF
            data = "0x" + (SEL["tickBitmap"] + arg.to_bytes(32, "big")).hex()
            r = rpc.call(self.chain, self.address, data, block=self.block)
            self._words[word_pos] = int(r, 16) if r and r != "0x" else 0
        return self._words[word_pos]

    def _liquidity_net(self, tick):
        if tick not in self._ticks:
            self._load_ticks([tick])
        return self._ticks.get(tick, 0)

    def _next_initialized_tick(self, tick, lte):
        spacing = self.tick_spacing
        compressed = tick // spacing          # Python floor-divides, matching Solidity's
        if tick < 0 and tick % spacing != 0:  # explicit `--compressed` branch
            pass                              # (already floored)
        if lte:
            word_pos, bit_pos = compressed >> 8, compressed & 255
            mask = (1 << bit_pos) - 1 + (1 << bit_pos)
            masked = self._word(word_pos) & mask
            if masked != 0:
                return (compressed - (bit_pos - _msb(masked))) * spacing, True
            return (compressed - bit_pos) * spacing, False
        compressed += 1
        word_pos, bit_pos = compressed >> 8, compressed & 255
        mask = ~((1 << bit_pos) - 1) & ((1 << 256) - 1)
        masked = self._word(word_pos) & mask
        if masked != 0:
            return (compressed + (_lsb(masked) - bit_pos)) * spacing, True
        return (compressed + (255 - bit_pos)) * spacing, False

    def quote_exact_input(self, token_in, amount_in, max_steps=256):
        """amountOut for an exact-input swap, mirroring UniswapV3Pool.swap."""
        zero_for_one = token_in.lower() == self.token0.lower()
        self._descending = zero_for_one   # tick traversal direction, for prefetching
        sqrt_limit = (MIN_SQRT_RATIO + 1) if zero_for_one else (MAX_SQRT_RATIO - 1)

        remaining = amount_in
        amount_out = 0
        sqrt_price = self.sqrt_price
        tick = self.tick
        liquidity = self.liquidity

        steps = 0
        while remaining > 0 and sqrt_price != sqrt_limit:
            steps += 1
            if steps > max_steps:
                break
            next_tick, initialized = self._next_initialized_tick(tick, zero_for_one)
            next_tick = max(MIN_TICK, min(MAX_TICK, next_tick))
            sqrt_next_tick = get_sqrt_ratio_at_tick(next_tick)

            if zero_for_one:
                target = max(sqrt_next_tick, sqrt_limit)
            else:
                target = min(sqrt_next_tick, sqrt_limit)

            if liquidity == 0:
                # no depth in this range: jump the price to the tick edge and carry on
                sqrt_price = target
                if initialized:
                    net = self._liquidity_net(next_tick)
                    liquidity += -net if zero_for_one else net
                tick = next_tick - 1 if zero_for_one else next_tick
                continue

            sqrt_price, step_in, step_out, step_fee = compute_swap_step(
                sqrt_price, target, liquidity, remaining, self.fee)
            remaining -= step_in + step_fee
            amount_out += step_out

            if sqrt_price == sqrt_next_tick:
                if initialized:
                    net = self._liquidity_net(next_tick)
                    liquidity += -net if zero_for_one else net
                    if liquidity < 0:
                        liquidity = 0
                tick = next_tick - 1 if zero_for_one else next_tick
            else:
                tick = tick_at_sqrt_ratio(sqrt_price)
        return amount_out


def tick_at_sqrt_ratio(sqrt_price):
    """Binary search is plenty fast here and avoids porting the log2 routine."""
    lo, hi = MIN_TICK, MAX_TICK
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if get_sqrt_ratio_at_tick(mid) <= sqrt_price:
            lo = mid
        else:
            hi = mid - 1
    return lo
