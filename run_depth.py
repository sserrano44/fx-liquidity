"""Measure each coin's tradeable depth: the notional at which a round trip costs 1%.

Pool TVL from an indexer is the wrong yardstick twice over -- discovery is capped at
the first page of pools, and reserves count both sides of a pool whose liquidity may
sit nowhere near the current price. This instead binary-searches the actual quoter:
the largest round trip that still clears at 1% all-in. It is the number a treasury
desk needs, and it comes from the same pool state as everything else here.
"""
import json
import time
from concurrent.futures import ThreadPoolExecutor

import run_quotes as RQ

TARGET = 0.01          # 1% all-in round-trip cost
LO, HI = 200, 20_000_000
ITERS = 15
OUT = "depth.json"


def cost_at(chain, token, tdec, size, live):
    r = RQ.round_trip(chain, token, tdec, size, live)
    if not r or r.get("round_trip") is None:
        return None
    return -r["round_trip"]


def depth_for(chain, token, tdec, live):
    """Largest notional whose round trip still costs <= TARGET, by bisection."""
    c_lo = cost_at(chain, token, tdec, LO, live)
    if c_lo is None:
        # A route exists but the pool cannot even fill the floor size. That is a
        # measured zero, not an unmeasured coin, and must not read as "unknown".
        return dict(depth_usd=0, note=f"pool too small to quote ${LO:,} at all",
                    cost_at_floor=None)
    if c_lo > TARGET:
        return dict(depth_usd=0, note=f"even ${LO:,} costs {c_lo*100:.1f}%",
                    cost_at_floor=c_lo)
    c_hi = cost_at(chain, token, tdec, HI, live)
    if c_hi is not None and c_hi <= TARGET:
        return dict(depth_usd=HI, note="deeper than the search ceiling")

    lo, hi = LO, HI
    for _ in range(ITERS):
        mid = (lo * hi) ** 0.5           # geometric bisection: depth spans 5 orders
        c = cost_at(chain, token, tdec, mid, live)
        if c is None or c > TARGET:
            hi = mid
        else:
            lo = mid
    return dict(depth_usd=lo, note=None)


def main():
    quotes = json.load(open("quotes.json"))
    pools = RQ.load_pools()
    rows = [r for r in quotes["rows"] if "symbol" in r]

    # Best chain per coin, by $10k round trip. Coins whose pool is too small to
    # quote $10k at all still get measured — on those the floor result ("even
    # $200 costs N%") is the whole story, so dropping them would hide it.
    best = {}
    for r in rows:
        c = ((r.get("sizes") or {}).get("10000") or {}).get("round_trip")
        has_route = bool(r.get("dollar_legs")) or bool(r.get("direct_pools"))
        if c is None and not has_route:
            continue
        cur = best.get(r["symbol"])
        if cur is None:
            best[r["symbol"]] = r
            continue
        cur_c = ((cur.get("sizes") or {}).get("10000") or {}).get("round_trip")
        if cur_c is None or (c is not None and c > cur_c):
            best[r["symbol"]] = r

    jobs = list(best.items())
    print(f"measuring 1% depth for {len(jobs)} coins\n", flush=True)

    def work(item):
        sym, r = item
        chain, addr = r["chain"], r["address"]
        try:
            live = RQ.find_live_routes(chain, addr, pools.get((sym, chain)))
            d = depth_for(chain, addr, r["decimals"], live)
        except Exception as e:
            print(f"  {sym:<8} error {e}", flush=True)
            return dict(symbol=sym, chain=chain, error=str(e))
        out = dict(symbol=sym, currency=r["currency"], group=r["group"],
                   chain=chain, **(d or {}))
        print(f'  {sym:<8}@{chain:<11} 1% depth = '
              f'${(d or {}).get("depth_usd", 0):>12,.0f}  {(d or {}).get("note") or ""}', flush=True)
        return out

    with ThreadPoolExecutor(max_workers=6) as ex:
        results = list(ex.map(work, jobs))

    json.dump(dict(generated=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                   target=TARGET, rows=results), open(OUT, "w"), indent=1)
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
