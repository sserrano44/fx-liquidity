"""Validate the local v3 swap simulation against on-chain QuoterV2 results.

If these disagree, every number produced from the local math is suspect, so this
runs before any sweep that relies on it.
"""
import sys
from eth_abi import encode as abi_encode
from eth_utils import keccak

import rpc
import quoters as Q
import v3math
from chains import V3_QUOTERS

GET_POOL = keccak(text="getPool(address,address,uint24)")[:4]

CASES = [
    # chain, factory, tokenA, tokenB, fee, amount_in, token_in
    ("ethereum", "0x1F98431c8aD98523631AE4a59f267346ea31F984",
     "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",   # USDC
     "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",   # WETH
     500, 10_000 * 10**6, "usdc"),
    ("ethereum", "0x1F98431c8aD98523631AE4a59f267346ea31F984",
     "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
     "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
     3000, 250_000 * 10**6, "usdc"),
    # a thin FX pool, where tick crossing actually matters
    ("ethereum", "0x1F98431c8aD98523631AE4a59f267346ea31F984",
     "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
     "0x70e8dE73cE538DA2bEEd35d14187F6959a8ecA96",   # XSGD
     500, 10_000 * 10**6, "usdc"),
    ("ethereum", "0x1F98431c8aD98523631AE4a59f267346ea31F984",
     "0xdAC17F958D2ee523a2206206994597C13D831ec7",   # USDT
     "0xF442Ff10b8dEf89514560A66C0Ad28777094636A",   # wA7A5
     500, 10_000 * 10**6, "usdc"),
    ("base", "0x33128a8fC17869897dcE68Ed026d694621f6FDfD",
     "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
     "0x4200000000000000000000000000000000000006",
     500, 50_000 * 10**6, "usdc"),
    # reverse direction
    ("ethereum", "0x1F98431c8aD98523631AE4a59f267346ea31F984",
     "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
     "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
     500, 3 * 10**18, "weth"),
]


def pool_for(chain, factory, a, b, fee):
    data = "0x" + (GET_POOL + abi_encode(["address", "address", "uint24"], [a, b, fee])).hex()
    r = rpc.call(chain, factory, data)
    if not r or int(r, 16) == 0:
        return None
    return "0x" + r[-40:]


def main():
    failures = 0
    for chain, factory, a, b, fee, amount, which in CASES:
        pool_addr = pool_for(chain, factory, a, b, fee)
        if not pool_addr:
            print(f"SKIP {chain} {fee} — no pool")
            continue
        token_in = a if which == "usdc" else b
        token_out = b if which == "usdc" else a

        quoter = V3_QUOTERS["uniswap-v3"][chain]
        onchain = Q.dec_v3(rpc.call(chain, quoter, Q.cd_v3(token_in, token_out, amount, fee)))

        pool = v3math.Pool(chain, pool_addr)
        local = pool.quote_exact_input(token_in, amount)

        if onchain is None:
            print(f"SKIP {chain} {fee} — quoter returned nothing")
            continue
        diff = local - onchain
        rel = abs(diff) / onchain if onchain else 0
        ok = diff == 0
        status = "OK  " if ok else ("close" if rel < 1e-9 else "FAIL")
        if not ok and rel >= 1e-9:
            failures += 1
        print(f"{status} {chain:<9} fee={fee:<6} in={amount:>18,} "
              f"quoter={onchain:>24,} local={local:>24,} diff={diff}")
    print("\n" + ("ALL MATCH" if failures == 0 else f"{failures} MISMATCH(ES)"))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
