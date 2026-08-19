"""Quote every (token, chain) pair: metadata, supply, and a round-trip cost curve.

Method, per (token, chain):
  1. Find live routes two ways -- probe every (dollar leg x venue x fee tier) against
     the on-chain Quoters, and take every discovered pool (pools.json) whose other
     side is a dollar stablecoin and price it directly from pool state.
  2. For each notional, buy the coin with dollars on the best live route, then sell
     the coins received back to the same dollar on the best live reverse route.
     round_trip = dollars_back / dollars_in - 1.

Everything is eth_call against pool or quoter state, so this is real executable
depth: no aggregator, no off-chain market maker, no indexer price.
"""
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor

import rpc
import quoters as Q
import poolquote as PQ
import v4key
from chains import DOLLARS, V3_QUOTERS, V4_QUOTERS
from tokens import TOKENS

SIZES = [1_000, 10_000, 100_000]
PROBE_USD = 100
OUT = "quotes.json"
POOLS = "pools.json"


def has_venue(chain):
    return (chain in V3_QUOTERS["uniswap-v3"] or chain in V4_QUOTERS
            or chain in V3_QUOTERS["slipstream"] or chain in V3_QUOTERS["pancake-v3"])


def load_pools():
    if not os.path.exists(POOLS):
        return {}
    data = json.load(open(POOLS))
    return {(r["symbol"], r["chain"]): r["pools"] for r in data["rows"]}


def token_meta(chain, addr, attempts=3):
    """decimals + totalSupply, or None only if there is genuinely no token there.

    A dropped RPC call and an empty address both come back as None, and conflating
    them is how a live token silently becomes "no token at address" — a false
    negative that reads as a real finding. So a miss is retried, and only confirmed
    once the chain says there is no contract at the address at all.
    """
    for attempt in range(attempts):
        res = rpc.batch_call(chain, [
            (addr, Q.cd_erc20(Q.SEL_DECIMALS)),
            (addr, Q.cd_erc20(Q.SEL_TOTAL_SUPPLY)),
        ])
        dec = Q.dec_uint(res[0])
        sup = Q.dec_uint(res[1])
        if dec is not None and dec <= 36:
            return dict(decimals=dec, total_supply_raw=sup,
                        total_supply=(sup / 10 ** dec) if sup is not None else None)
        try:
            if not rpc.code_exists(chain, addr):
                return None          # confirmed: nothing deployed here
        except Exception:
            pass
        time.sleep(0.5 * (attempt + 1))
    raise RuntimeError(f"contract at {addr} exists but metadata calls kept failing")


def dollar_pools(chain, token, gt_pools):
    """Discovered pools pairing this token directly against a dollar stablecoin."""
    by_addr = {a.lower(): (s, d) for s, a, d in DOLLARS.get(chain, [])}
    out = []
    for p in gt_pools or []:
        b, q = (p.get("base_addr") or "").lower(), (p.get("quote_addr") or "").lower()
        t = token.lower()
        if t not in (b, q) or not p.get("address"):
            continue
        other = q if t == b else b
        if other not in by_addr:
            continue
        dsym, ddec = by_addr[other]
        out.append(dict(pool=p["address"], dex=p.get("dex"), dollar=dsym,
                        dollar_addr=other, dollar_dec=ddec,
                        reserve_usd=p.get("reserve_usd", 0)))
    out.sort(key=lambda x: -(x["reserve_usd"] or 0))
    return out[:6]


def find_live_routes(chain, token, gt_pools):
    """dollar symbol -> route sets that actually returned a quote at a small size."""
    live = {}
    for dsym, daddr, ddec in DOLLARS.get(chain, []):
        buys = Q.quote_all(chain, daddr, token, int(PROBE_USD * 10 ** ddec))
        if not buys:
            continue
        coins = max(b[2] for b in buys)
        sells = Q.quote_all(chain, token, daddr, coins) if coins else []
        live[dsym] = dict(addr=daddr, decimals=ddec,
                          buy={(v, p) for v, p, _ in buys},
                          sell={(v, p) for v, p, _ in sells}, pools=[])

    for dp in dollar_pools(chain, token, gt_pools):
        slot_key = dp["dollar"]
        # Uniswap v4 pools are ids, not contracts: recover the PoolKey and add it
        # as a quoter route rather than trying to call the "pool address".
        if (dp.get("dex") or "").startswith("uniswap-v4") and chain in V4_QUOTERS:
            solved = v4key.solve(dp["pool"], token, dp["dollar_addr"])
            if not solved:
                continue
            fee, ts = solved
            probe_amt = int(PROBE_USD * 10 ** dp["dollar_dec"])
            got = Q.dec_v4(rpc.call(chain, V4_QUOTERS[chain],
                                    Q.cd_v4(dp["dollar_addr"], token, probe_amt, fee, ts)))
            if not got:
                continue
            slot = live.setdefault(slot_key, dict(addr=dp["dollar_addr"],
                                                  decimals=dp["dollar_dec"],
                                                  buy=set(), sell=set(), pools=[]))
            slot["v4"] = slot.get("v4", []) + [(fee, ts)]
            continue

        fam = PQ.detect(chain, dp["pool"])
        if fam is None:
            continue
        probe = PQ.quote(chain, dp["pool"], dp["dollar_addr"],
                         int(PROBE_USD * 10 ** dp["dollar_dec"]), family=fam)
        if not probe:
            continue
        slot = live.setdefault(slot_key, dict(addr=dp["dollar_addr"],
                                              decimals=dp["dollar_dec"],
                                              buy=set(), sell=set(), pools=[]))
        slot["pools"].append(dict(dp, family=fam))
    return live


def _best_leg(chain, token_in, token_out, amount_in, info, direction):
    """Best (venue, param, amount_out) across quoter routes and direct pools."""
    cands = []
    only = info["buy"] if direction == "buy" else info["sell"]
    if only:
        cands += Q.quote_all(chain, token_in, token_out, amount_in, only=only)
    for p in info.get("pools", []):
        out = PQ.quote(chain, p["pool"], token_in, amount_in, family=p["family"])
        if out:
            cands.append((p["dex"] or p["family"], p["pool"][:10], out))
    for fee, ts in info.get("v4", []):
        out = Q.dec_v4(rpc.call(chain, V4_QUOTERS[chain],
                                Q.cd_v4(token_in, token_out, amount_in, fee, ts)))
        if out:
            cands.append(("uniswap-v4", f"{fee/10000:g}%/ts{ts}", out))
    if not cands:
        return None
    return max(cands, key=lambda x: x[2])


def round_trip(chain, token, tdec, size_usd, live):
    best = None
    for dsym, info in live.items():
        ddec = info["decimals"]
        amount_in = int(size_usd * 10 ** ddec)
        buy = _best_leg(chain, info["addr"], token, amount_in, info, "buy")
        if not buy:
            continue
        bv, bp, coins = buy
        sell = _best_leg(chain, token, info["addr"], coins, info, "sell")
        cand = dict(size_usd=size_usd, dollar=dsym, buy_venue=bv, buy_param=bp,
                    coins=coins / 10 ** tdec)
        if sell:
            sv, sp, back = sell
            cand.update(sell_venue=sv, sell_param=sp, usd_back=back / 10 ** ddec,
                        round_trip=(back / 10 ** ddec) / size_usd - 1)
        else:
            cand.update(sell_venue=None, sell_param=None, usd_back=None, round_trip=None)
        cand["implied_px_usd"] = (size_usd / cand["coins"]) if cand["coins"] else None
        if best is None or (cand["round_trip"] or -9) > (best["round_trip"] or -9):
            best = cand
    return best


def do_pair(tok, chain, addr, gt_pools):
    tag = f'{tok["symbol"]}@{chain}'
    stub = dict(symbol=tok["symbol"], currency=tok["currency"], issuer=tok["issuer"],
                group=tok["group"], chain=chain, address=addr)
    try:
        meta = token_meta(chain, addr)
    except Exception as e:
        return dict(stub, error=f"meta: {e}")
    if meta is None:
        return dict(stub, error="no contract deployed at address")

    row = dict(symbol=tok["symbol"], currency=tok["currency"], issuer=tok["issuer"],
               group=tok["group"], chain=chain, address=addr, **meta, sizes={})
    if not meta["total_supply"]:
        print(f"  {tag:<18} supply=0 — no quotes", flush=True)
        return row

    try:
        live = find_live_routes(chain, addr, gt_pools)
    except Exception as e:
        row["error"] = f"routes: {e}"
        print(f"  {tag:<18} route discovery failed: {e}", flush=True)
        return row

    row["dollar_legs"] = sorted(live)
    row["direct_pools"] = [p["pool"] for v in live.values() for p in v.get("pools", [])]
    if not live:
        print(f'  {tag:<18} supply={meta["total_supply"]:>16,.0f}  no live route', flush=True)
        return row

    for size in SIZES:
        try:
            row["sizes"][str(size)] = round_trip(chain, addr, meta["decimals"], size, live)
        except Exception as e:
            row["sizes"][str(size)] = None
            print(f"  {tag:<18} size {size}: {e}", flush=True)

    r = row["sizes"].get("10000") or {}
    rt = r.get("round_trip")
    print(f'  {tag:<18} supply={meta["total_supply"]:>16,.0f} '
          f'10k={"n/a" if rt is None else f"{rt*100:+.2f}%":>9} '
          f'{r.get("buy_venue","-")}/{r.get("buy_param","-")} vs {r.get("dollar","-")}', flush=True)
    return row


def main():
    pools = load_pools()
    print(f"loaded {len(pools)} discovered pool sets")
    by_chain = {}
    for tok in TOKENS:
        for chain, addr in tok["addrs"].items():
            if has_venue(chain) or (tok["symbol"], chain) in pools:
                by_chain.setdefault(chain, []).append(
                    (tok, chain, addr, pools.get((tok["symbol"], chain))))
            else:
                print(f'skip {tok["symbol"]}@{chain}: no venue and no discovered pool')
    total = sum(len(v) for v in by_chain.values())
    print(f"{total} (token, chain) pairs across {len(by_chain)} chains\n", flush=True)

    def run_chain(jobs):
        print(f"== {jobs[0][1]} ({len(jobs)} pairs)", flush=True)
        out = []
        for tok, chain, addr, gt in jobs:
            try:
                out.append(do_pair(tok, chain, addr, gt))
            except Exception as e:
                # One bad pair must not take its whole chain's results with it.
                print(f'  {tok["symbol"]}@{chain} FAILED: {e}', flush=True)
                out.append(dict(symbol=tok["symbol"], currency=tok["currency"],
                                issuer=tok["issuer"], group=tok["group"],
                                chain=chain, address=addr, error=str(e)))
        return out

    rows = []
    with ThreadPoolExecutor(max_workers=len(by_chain)) as ex:
        for res in ex.map(run_chain, by_chain.values()):
            rows.extend(res)

    # Every job must produce a row. A silently short result set would look like
    # "these coins have no market" rather than "these coins were never measured".
    missing = {(t["symbol"], c) for jobs in by_chain.values() for t, c, _a, _g in jobs}
    missing -= {(r.get("symbol"), r.get("chain")) for r in rows}
    if missing:
        print(f"\nWARNING: {len(missing)} pairs produced no row: {sorted(missing)}")
    errored = [r for r in rows if r.get("error")]
    if errored:
        print(f"WARNING: {len(errored)} pairs errored: "
              f'{[(r["symbol"], r["chain"], r["error"][:40]) for r in errored]}')

    json.dump(dict(generated=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                   sizes=SIZES, rows=rows), open(OUT, "w"), indent=1)
    print(f"\nwrote {OUT}: {len(rows)} rows")


if __name__ == "__main__":
    main()
