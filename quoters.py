"""On-chain quoting across Uniswap v3/v4, Aerodrome/Velodrome SlipStream, Pancake v3.

Everything is done with eth_call against each venue's Quoter, so the numbers are
real executable depth from pool state — no aggregator, no off-chain market maker.
"""
from eth_abi import encode as abi_encode, decode as abi_decode
from eth_utils import keccak, to_checksum_address

import rpc
from chains import (V3_QUOTERS, V4_QUOTERS, V3_FEES, PANCAKE_FEES,
                    SLIPSTREAM_TICK_SPACINGS, V4_FEE_SPACING)

MIN_SQRT = 4295128740                                        # TickMath.MIN_SQRT_RATIO + 1
MAX_SQRT = 1461446703485210103287273052203988822378723970341  # MAX_SQRT_RATIO - 1


def sel(sig):
    return keccak(text=sig)[:4]


SEL_V3 = sel("quoteExactInputSingle((address,address,uint256,uint24,uint160))")
SEL_SLIP = sel("quoteExactInputSingle((address,address,uint256,int24,uint160))")
SEL_V4 = sel("quoteExactInputSingle(((address,address,uint24,int24,address),bool,uint128,bytes))")
SEL_TOTAL_SUPPLY = sel("totalSupply()")
SEL_DECIMALS = sel("decimals()")
SEL_SYMBOL = sel("symbol()")
SEL_BALANCE_OF = sel("balanceOf(address)")


def _addr(a):
    return to_checksum_address(a)


# ---------------------------------------------------------------- calldata

def cd_v3(token_in, token_out, amount_in, fee):
    limit = MIN_SQRT if int(token_in, 16) < int(token_out, 16) else MAX_SQRT
    body = abi_encode(
        ["(address,address,uint256,uint24,uint160)"],
        [(_addr(token_in), _addr(token_out), int(amount_in), int(fee), limit)],
    )
    return "0x" + (SEL_V3 + body).hex()


def cd_slip(token_in, token_out, amount_in, tick_spacing):
    limit = MIN_SQRT if int(token_in, 16) < int(token_out, 16) else MAX_SQRT
    body = abi_encode(
        ["(address,address,uint256,int24,uint160)"],
        [(_addr(token_in), _addr(token_out), int(amount_in), int(tick_spacing), limit)],
    )
    return "0x" + (SEL_SLIP + body).hex()


def cd_v4(token_in, token_out, amount_in, fee, tick_spacing, hooks="0x" + "00" * 20):
    a, b = int(token_in, 16), int(token_out, 16)
    zero_for_one = a < b
    c0, c1 = (token_in, token_out) if zero_for_one else (token_out, token_in)
    params = (
        (_addr(c0), _addr(c1), int(fee), int(tick_spacing), _addr(hooks)),
        bool(zero_for_one),
        int(amount_in),
        b"",
    )
    body = abi_encode(
        ["((address,address,uint24,int24,address),bool,uint128,bytes)"], [params]
    )
    return "0x" + (SEL_V4 + body).hex()


def cd_erc20(selector, arg=None):
    if arg is None:
        return "0x" + selector.hex()
    return "0x" + (selector + abi_encode(["address"], [_addr(arg)])).hex()


# ---------------------------------------------------------------- decoding

def dec_v3(hexstr):
    if not hexstr or len(hexstr) < 66:
        return None
    try:
        out = abi_decode(["uint256", "uint160", "uint32", "uint256"], bytes.fromhex(hexstr[2:]))
        return out[0]
    except Exception:
        return None


def dec_v4(hexstr):
    if not hexstr or len(hexstr) < 66:
        return None
    try:
        out = abi_decode(["uint256", "uint256"], bytes.fromhex(hexstr[2:]))
        return out[0]
    except Exception:
        return None


def dec_uint(hexstr):
    if not hexstr or hexstr == "0x":
        return None
    try:
        return int(hexstr, 16)
    except Exception:
        return None


# ---------------------------------------------------------------- routes

def enumerate_routes(chain, token_in, token_out, amount_in):
    """All (venue, param, to, calldata, decoder) probes for one directional swap."""
    probes = []
    q = V3_QUOTERS["uniswap-v3"].get(chain)
    if q:
        for fee in V3_FEES:
            probes.append(("uniswap-v3", f"{fee/10000:g}%", q,
                           cd_v3(token_in, token_out, amount_in, fee), dec_v3))
    q = V3_QUOTERS["pancake-v3"].get(chain)
    if q:
        for fee in PANCAKE_FEES:
            probes.append(("pancake-v3", f"{fee/10000:g}%", q,
                           cd_v3(token_in, token_out, amount_in, fee), dec_v3))
    q = V3_QUOTERS["slipstream"].get(chain)
    if q:
        venue = "aerodrome" if chain == "base" else "velodrome"
        for ts in SLIPSTREAM_TICK_SPACINGS:
            probes.append((venue, f"ts{ts}", q,
                           cd_slip(token_in, token_out, amount_in, ts), dec_v3))
    q = V4_QUOTERS.get(chain)
    if q:
        for fee, ts in V4_FEE_SPACING:
            probes.append(("uniswap-v4", f"{fee/10000:g}%", q,
                           cd_v4(token_in, token_out, amount_in, fee, ts), dec_v4))
    return probes


def quote_all(chain, token_in, token_out, amount_in, only=None):
    """Returns list of (venue, param, amount_out) for every route that quotes.

    `only` restricts probing to a set of (venue, param) pairs already known to be
    live, which is what makes sweeping several notionals across several dollar
    legs affordable on public RPCs.
    """
    probes = enumerate_routes(chain, token_in, token_out, amount_in)
    if only is not None:
        probes = [p for p in probes if (p[0], p[1]) in only]
    if not probes:
        return []
    results = rpc.batch_call(chain, [(p[2], p[3]) for p in probes])
    out = []
    for (venue, param, _to, _data, decoder), res in zip(probes, results):
        amt = decoder(res)
        if amt:
            out.append((venue, param, amt))
    return out


def best_quote(chain, token_in, token_out, amount_in, only=None):
    qs = quote_all(chain, token_in, token_out, amount_in, only=only)
    if not qs:
        return None
    return max(qs, key=lambda x: x[2])
