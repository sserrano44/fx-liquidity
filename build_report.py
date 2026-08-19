"""Aggregate quotes.json + pools.json into the three panels, and print them.

Panels mirror dcposch's: best route per coin, cost by coin and chain, and supply
versus tradeable depth. Adds a depth curve ($1k / $10k / $100k), which is what
actually separates a coin you can trade from one you can only hold.
"""
import json
from collections import defaultdict

from chains import DOLLARS
from tokens import TOKENS

Q = json.load(open("quotes.json"))
P = json.load(open("pools.json"))

ROWS = Q["rows"]
POOLS = {(r["symbol"], r["chain"]): r["pools"] for r in P["rows"]}
META = {t["symbol"]: t for t in TOKENS}

CHAIN_ORDER = ["ethereum", "base", "polygon", "arbitrum", "bsc", "gnosis",
               "celo", "worldchain", "avalanche", "optimism"]


def rt(row, size="10000"):
    s = (row.get("sizes") or {}).get(size) or {}
    return s.get("round_trip")


import build_html as BH   # single source of truth for price, supply and depth


def price_of(row):
    """USD price per token unit, taken from the smallest (least-slipped) quote."""
    for size in ("1000", "10000", "100000"):
        s = (row.get("sizes") or {}).get(size) or {}
        if s.get("implied_px_usd"):
            return s["implied_px_usd"]
    return None


def coin_price(symbol):
    return BH.price(symbol)


def coin_rows(symbol):
    return [r for r in ROWS if r.get("symbol") == symbol]


def supply_usd(symbol):
    """Total supply across chains, in USD, using one FX price for the coin."""
    px = coin_price(symbol)
    total = sum((r.get("total_supply") or 0) for r in coin_rows(symbol))
    return total, (total * px if px is not None else None)


def best_route(symbol):
    """Chain with the tightest $10k round trip."""
    best = None
    for r in coin_rows(symbol):
        c = rt(r)
        if c is None:
            continue
        if best is None or c > rt(best):
            best = r
    return best


def fmt_pct(x):
    return "     —" if x is None else f"{x*100:+6.2f}%"


def fmt_usd(x):
    if x is None:
        return "—"
    for unit, div in (("B", 1e9), ("M", 1e6), ("k", 1e3)):
        if abs(x) >= div:
            return f"${x/div:,.1f}{unit}"
    return f"${x:,.0f}"


def main():
    symbols = [t["symbol"] for t in TOKENS if coin_rows(t["symbol"])]

    print("=" * 108)
    print("PANEL 1 — best route per coin: $10,000 round trip, dollars in -> coin -> dollars out")
    print("=" * 108)
    print(f'{"coin":<8}{"ccy":<5}{"issuer":<18}{"best chain":<12}{"venue":<22}'
          f'{"vs":<8}{"$1k":>8}{"$10k":>8}{"$100k":>9}')
    order = sorted(symbols, key=lambda s: -(rt(best_route(s)) if best_route(s) else -9))
    for s in order:
        r = best_route(s)
        if not r:
            m = META[s]
            print(f'{s:<8}{m["currency"]:<5}{m["issuer"][:17]:<18}{"— no on-chain dollar route —":<42}')
            continue
        sz = r["sizes"]
        venue = f'{(sz["10000"] or {}).get("buy_venue","")}/{(sz["10000"] or {}).get("buy_param","")}'
        print(f'{s:<8}{r["currency"]:<5}{r["issuer"][:17]:<18}{r["chain"]:<12}{venue[:21]:<22}'
              f'{(sz["10000"] or {}).get("dollar",""):<8}'
              f'{fmt_pct(rt(r,"1000")):>8}{fmt_pct(rt(r)):>8}{fmt_pct(rt(r,"100000")):>9}')

    print()
    print("=" * 108)
    print("PANEL 2 — $10k round-trip cost by coin and chain")
    print("=" * 108)
    chains = [c for c in CHAIN_ORDER if any(r["chain"] == c for r in ROWS)]
    print(f'{"coin":<8}' + "".join(f"{c[:9]:>11}" for c in chains))
    for s in symbols:
        line = f"{s:<8}"
        for c in chains:
            r = next((x for x in coin_rows(s) if x["chain"] == c), None)
            if r is None:
                line += f'{"":>11}'
            elif rt(r) is None:
                line += f'{"no pool":>11}'
            else:
                line += f"{rt(r)*100:>10.2f}%"
        print(line)

    print()
    print("=" * 108)
    print("PANEL 3 — supply versus tradeable depth")
    print("=" * 108)
    print(f'{"coin":<8}{"ccy":<5}{"supply (all chains)":>21}{"1% depth":>12}'
          f'{"depth/supply":>14}  {"where":<20}')
    rows3 = []
    for s in symbols:
        _units, usd = supply_usd(s)
        d = BH.DEPTH.get(s) or {}
        depth = d.get("depth_usd")
        if depth is None and s not in BH.DEPTH and BH.supply_units(s):
            depth = 0
        ratio = (depth / usd) if (usd and depth) else (0 if depth == 0 else None)
        rows3.append((s, usd, depth, ratio, d))
    for s, usd, depth, ratio, d in sorted(rows3, key=lambda x: -(x[1] or 0)):
        print(f'{s:<8}{META[s]["currency"]:<5}{fmt_usd(usd):>21}'
              f'{(fmt_usd(depth) if depth else "$0") if depth is not None else "—":>12}'
              f'{"" if ratio is None else f"{ratio*100:.2f}%":>14}  {(d.get("chain") or "—"):<20}')

    json.dump(dict(
        generated=Q["generated"],
        panel1=[dict(symbol=s, row=best_route(s)) for s in order],
        panel3=[dict(symbol=s, supply_usd=u, depth_usd=d, ratio=r) for s, u, d, r, _m in rows3],
    ), open("report.json", "w"), indent=1, default=str)
    print("\nwrote report.json")


if __name__ == "__main__":
    main()
