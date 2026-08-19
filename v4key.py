"""Recover a Uniswap v4 PoolKey from a pool id.

v4 pools are not contracts, so there is nothing to introspect: a pool is identified
by keccak(PoolKey) inside the singleton. Probing a fixed list of (fee, tickSpacing)
pairs misses pools that chose anything unusual -- the wFiat pool on Celo is
fee 3000 / tickSpacing 30, which no standard list contains. Since discovery hands us
the pool id, we can just solve for the key that hashes to it.
"""
from eth_abi import encode as abi_encode
from eth_utils import keccak, to_checksum_address

ZERO = "0x0000000000000000000000000000000000000000"

FEE_CANDIDATES = [100, 200, 300, 400, 500, 800, 1000, 1500, 2000, 2500,
                  3000, 4000, 5000, 7500, 10000, 20000, 30000, 0]
MAX_TICK_SPACING = 500

_CACHE = {}


def pool_id(c0, c1, fee, tick_spacing, hooks=ZERO):
    return "0x" + keccak(abi_encode(
        ["(address,address,uint24,int24,address)"],
        [(to_checksum_address(c0), to_checksum_address(c1),
          int(fee), int(tick_spacing), to_checksum_address(hooks))])).hex()


def solve(target_id, token_a, token_b, hooks=ZERO):
    """Return (fee, tickSpacing) whose PoolKey hashes to target_id, or None.

    Only zero-hook pools are solvable this way; a pool with a hook contract would
    need the hook address too, and those are skipped rather than guessed at.
    """
    key = (target_id.lower(), token_a.lower(), token_b.lower())
    if key in _CACHE:
        return _CACHE[key]
    c0, c1 = sorted([token_a, token_b], key=lambda a: int(a, 16))
    target = target_id.lower()
    if not target.startswith("0x"):
        target = "0x" + target
    for fee in FEE_CANDIDATES:
        for ts in range(1, MAX_TICK_SPACING + 1):
            if pool_id(c0, c1, fee, ts, hooks) == target:
                _CACHE[key] = (fee, ts)
                return fee, ts
    _CACHE[key] = None
    return None
