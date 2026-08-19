"""Quote an arbitrary discovered pool, whatever AMM family it belongs to.

Quoter contracts cover only blessed deployments. Pool discovery turns up plenty of
real depth on forks with no quoter we can call: a newer Aerodrome CL factory on
Base, Uniswap v3 on Gnosis, QuickSwap's Algebra pools, solidly-style pairs. This
probes a pool address and prices it with whichever family it turns out to be.

Order of attempts, cheapest and most authoritative first:
  1. getAmountOut(uint256,address)  -- solidly / Aerodrome / Velodrome pairs price
                                       themselves, stable curve included
  2. slot0() + tickSpacing()        -- Uniswap v3 and its forks, via v3math
  3. globalState()                  -- Algebra (QuickSwap v3), v3 math with the
                                       pool's current dynamic fee
  4. getReserves()                  -- plain constant-product pairs
"""
from eth_abi import encode as abi_encode
from eth_utils import keccak

import rpc
import v3math

SEL_GET_AMOUNT_OUT = keccak(text="getAmountOut(uint256,address)")[:4]
SEL_GET_RESERVES = keccak(text="getReserves()")[:4]
SEL_GLOBAL_STATE = keccak(text="globalState()")[:4]
SEL_TOKEN0 = keccak(text="token0()")[:4]
SEL_TOKEN1 = keccak(text="token1()")[:4]
SEL_STABLE = keccak(text="stable()")[:4]

_FAMILY_CACHE = {}


def _call(chain, addr, data):
    try:
        return rpc.call(chain, addr, data)
    except Exception:
        return None


def _uint(h):
    if not h or h == "0x":
        return None
    try:
        return int(h, 16)
    except Exception:
        return None


def detect(chain, pool):
    """Return the AMM family of a pool address: solidly | v3 | algebra | v2 | None."""
    key = (chain, pool.lower())
    if key in _FAMILY_CACHE:
        return _FAMILY_CACHE[key]

    fam = None
    # solidly pairs answer getAmountOut directly
    probe = "0x" + (SEL_GET_AMOUNT_OUT + abi_encode(
        ["uint256", "address"], [1, "0x0000000000000000000000000000000000000001"])).hex()
    if _call(chain, pool, probe) is not None:
        fam = "solidly"
    if fam is None and _call(chain, pool, "0x" + keccak(text="tickSpacing()")[:4].hex()) is not None:
        if _call(chain, pool, "0x" + v3math.SEL["slot0"].hex()) is not None:
            fam = "v3"
        elif _call(chain, pool, "0x" + SEL_GLOBAL_STATE.hex()) is not None:
            fam = "algebra"
    if fam is None and _call(chain, pool, "0x" + SEL_GET_RESERVES.hex()) is not None:
        fam = "v2"
    _FAMILY_CACHE[key] = fam
    return fam


def tokens(chain, pool):
    t0 = _call(chain, pool, "0x" + SEL_TOKEN0.hex())
    t1 = _call(chain, pool, "0x" + SEL_TOKEN1.hex())
    if not t0 or not t1:
        return None, None
    return "0x" + t0[-40:], "0x" + t1[-40:]


def quote(chain, pool, token_in, amount_in, family=None):
    """amountOut for an exact-input swap through one pool, or None."""
    fam = family or detect(chain, pool)
    if fam is None:
        return None
    try:
        if fam == "solidly":
            data = "0x" + (SEL_GET_AMOUNT_OUT + abi_encode(
                ["uint256", "address"], [int(amount_in), token_in])).hex()
            return _uint(_call(chain, pool, data))

        if fam == "v3":
            p = v3math.Pool(chain, pool)
            return p.quote_exact_input(token_in, int(amount_in))

        if fam == "algebra":
            p = _algebra_pool(chain, pool)
            return p.quote_exact_input(token_in, int(amount_in)) if p else None

        if fam == "v2":
            return _v2_quote(chain, pool, token_in, int(amount_in))
    except Exception:
        return None
    return None


def _algebra_pool(chain, pool):
    """Algebra pools are v3 with a dynamic fee reported by globalState()."""
    p = v3math.Pool.__new__(v3math.Pool)
    p.chain, p.address, p.block = chain, pool, "latest"
    p._words, p._ticks = {}, {}
    p._descending = True
    gs = _call(chain, pool, "0x" + SEL_GLOBAL_STATE.hex())
    if not gs:
        return None
    raw = bytes.fromhex(gs[2:])
    p.sqrt_price = int.from_bytes(raw[0:32], "big")
    tick = int.from_bytes(raw[32:64], "big")
    p.tick = tick - (1 << 256) if tick >= (1 << 255) else tick
    p.fee = int.from_bytes(raw[64:96], "big") if len(raw) >= 96 else 3000
    liq = _uint(_call(chain, pool, "0x" + v3math.SEL["liquidity"].hex()))
    if liq is None:
        return None
    p.liquidity = liq
    ts = _uint(_call(chain, pool, "0x" + v3math.SEL["tickSpacing"].hex()))
    p.tick_spacing = ts if ts and ts < 1000 else 60
    t0, t1 = tokens(chain, pool)
    if not t0:
        return None
    p.token0, p.token1 = t0, t1
    return p


def _v2_quote(chain, pool, token_in, amount_in, fee_bps=30):
    r = _call(chain, pool, "0x" + SEL_GET_RESERVES.hex())
    if not r:
        return None
    raw = bytes.fromhex(r[2:])
    r0 = int.from_bytes(raw[0:32], "big")
    r1 = int.from_bytes(raw[32:64], "big")
    t0, _t1 = tokens(chain, pool)
    if not t0 or not r0 or not r1:
        return None
    zero_for_one = token_in.lower() == t0.lower()
    rin, rout = (r0, r1) if zero_for_one else (r1, r0)
    amt = amount_in * (10_000 - fee_bps)
    return (amt * rout) // (rin * 10_000 + amt)
