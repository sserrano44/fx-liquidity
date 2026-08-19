"""Discover every on-chain pool per (token, chain) via GeckoTerminal.

Gives us two things the quoter cannot: the deepest pool's USD reserves (panel 3),
and the set of quote assets each coin is actually paired against — which is how we
learn that XSGD on Polygon trades against bridged USDC.e, not native USDC.
"""
import json
import os
import sys
import time
import requests

from chains import GT_NETWORK
from tokens import TOKENS

GT = "https://api.geckoterminal.com/api/v2"
HDRS = {"accept": "application/json;version=20230302"}
OUT = "pools.json"


def get(url, params=None, tries=5):
    for i in range(tries):
        r = requests.get(url, params=params, headers=HDRS, timeout=40)
        if r.status_code == 429:
            time.sleep(3 + 3 * i)
            continue
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()
    return None


def pools_for(chain, addr):
    net = GT_NETWORK[chain]
    js = get(f"{GT}/networks/{net}/tokens/{addr}/pools", {"page": 1})
    if not js:
        return []
    included = {i["id"]: i for i in js.get("included", [])}
    out = []
    for p in js.get("data", []):
        a = p["attributes"]
        rel = p.get("relationships", {})

        def side(key):
            ref = (rel.get(key) or {}).get("data")
            if not ref:
                return None, None
            inc = included.get(ref["id"])
            if not inc:
                return ref["id"].split("_")[-1], None
            return inc["attributes"].get("address"), inc["attributes"].get("symbol")

        b_addr, b_sym = side("base_token")
        q_addr, q_sym = side("quote_token")
        out.append(dict(
            name=a.get("name"), address=a.get("address"),
            dex=(rel.get("dex") or {}).get("data", {}).get("id"),
            reserve_usd=float(a.get("reserve_in_usd") or 0),
            vol24=float((a.get("volume_usd") or {}).get("h24") or 0),
            base=b_sym, base_addr=b_addr, quote=q_sym, quote_addr=q_addr,
            price_usd=a.get("base_token_price_usd"),
        ))
    return out


def main():
    # Incremental by default: GeckoTerminal rate-limits hard, and pool membership
    # changes far more slowly than the reserves we no longer depend on. Pass
    # --all to force a full refetch.
    full = "--all" in sys.argv
    existing = {}
    if not full and os.path.exists(OUT):
        prev = json.load(open(OUT))
        existing = {(r["symbol"], r["chain"]): r for r in prev["rows"]}
        print(f"reusing {len(existing)} known token-chain rows; fetching only new ones")

    rows = []
    for tok in TOKENS:
        for chain, addr in tok["addrs"].items():
            if chain not in GT_NETWORK:
                continue
            key = (tok["symbol"], chain)
            if key in existing:
                rows.append(existing[key])
                continue
            try:
                ps = pools_for(chain, addr)
            except Exception as e:
                print(f'{tok["symbol"]}@{chain}: error {e}')
                continue
            ps.sort(key=lambda p: -p["reserve_usd"])
            rows.append(dict(symbol=tok["symbol"], currency=tok["currency"],
                             group=tok["group"], chain=chain, address=addr, pools=ps))
            if ps:
                top = ps[0]
                desc = f'${top["reserve_usd"]:>12,.0f}  {top["dex"]}  {top["name"]}'
            else:
                desc = "-"
            print(f'{tok["symbol"]:<6}@{chain:<11} pools={len(ps):<3} deepest={desc}', flush=True)
            time.sleep(2.2)   # GeckoTerminal free tier: 30 calls/min
    json.dump(dict(generated=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                   rows=rows), open(OUT, "w"), indent=1)
    print(f"\nwrote {OUT}: {len(rows)} token-chain rows")


if __name__ == "__main__":
    main()
