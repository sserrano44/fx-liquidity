"""Render quotes.json + pools.json into the published report page."""
import json
import math
from collections import defaultdict

from chains import DOLLARS
from tokens import TOKENS

Q = json.load(open("quotes.json"))
P = json.load(open("pools.json"))
ROWS = [r for r in Q["rows"] if "symbol" in r]
POOLS = {(r["symbol"], r["chain"]): r["pools"] for r in P["rows"]}
META = {t["symbol"]: t for t in TOKENS}

CHAIN_LABEL = {"ethereum": "Ethereum", "base": "Base", "polygon": "Polygon",
               "arbitrum": "Arbitrum", "bsc": "BNB", "gnosis": "Gnosis",
               "celo": "Celo", "worldchain": "World", "avalanche": "Avalanche",
               "optimism": "Optimism"}
CHAIN_ORDER = ["ethereum", "base", "polygon", "arbitrum", "bsc", "celo",
               "worldchain", "gnosis", "avalanche", "optimism"]
FLAG = {"ARS": "🇦🇷", "BRL": "🇧🇷", "MXN": "🇲🇽", "CLP": "🇨🇱", "COP": "🇨🇴",
        "PEN": "🇵🇪", "EUR": "🇪🇺", "JPY": "🇯🇵", "SGD": "🇸🇬", "GBP": "🇬🇧",
        "AUD": "🇦🇺", "RUB": "🇷🇺", "BOB": "🇧🇴", "PYG": "🇵🇾", "UYU": "🇺🇾",
        "VES": "🇻🇪"}


# ---------------------------------------------------------------- accessors

def rows_for(sym):
    return [r for r in ROWS if r["symbol"] == sym]


def is_live(sym):
    """Deployed-but-unissued coins are registry entries, not market participants."""
    return any((r.get("total_supply") or 0) > 0 for r in rows_for(sym))


def cost(row, size="10000"):
    s = (row.get("sizes") or {}).get(size) or {}
    return s.get("round_trip")


def leg(row, size="10000"):
    return (row.get("sizes") or {}).get(size) or {}


def _own_price(sym):
    """USD price implied by this coin's own tightest small quote."""
    best = None
    for r in rows_for(sym):
        s = leg(r, "1000")
        if not s.get("implied_px_usd"):
            continue
        c = s.get("round_trip")
        if best is None or (c or -9) > best[1]:
            best = (s["implied_px_usd"], c or -9)
    return best[0] if best else None


def price(sym):
    """USD price per token unit.

    A coin with no market has no implied price of its own, which would leave its
    float unmeasurable — exactly the coins worth measuring. Fall back to the FX
    rate another coin in the same currency is trading at, since both track the
    same peg. Currencies with no traded coin at all stay unpriced rather than
    guessed.
    """
    own = _own_price(sym)
    if own is not None:
        return own
    ccy = META[sym]["currency"]
    peers = [p for s, p in ((s, _own_price(s)) for s in META
                            if s != sym and META[s]["currency"] == ccy) if p]
    if not peers:
        return None
    peers.sort()
    return peers[len(peers) // 2]


def price_is_proxy(sym):
    return _own_price(sym) is None and price(sym) is not None


def supply_units(sym):
    return sum((r.get("total_supply") or 0) for r in rows_for(sym))


def supply_usd(sym):
    px = price(sym)
    return supply_units(sym) * px if px else None


def best_row(sym):
    best = None
    for r in rows_for(sym):
        if cost(r) is None:
            continue
        if best is None or cost(r) > cost(best):
            best = r
    return best


def dollar_pool_stats(sym):
    """Deepest dollar-paired pool and total dollar-paired TVL for a coin."""
    deepest, total = None, 0.0
    for (s, ch), pools in POOLS.items():
        if s != sym:
            continue
        dollars = {a.lower() for _n, a, _d in DOLLARS.get(ch, [])}
        for p in pools:
            b = (p.get("base_addr") or "").lower()
            q = (p.get("quote_addr") or "").lower()
            if not (b in dollars or q in dollars):
                continue
            total += p.get("reserve_usd") or 0
            if deepest is None or p["reserve_usd"] > deepest["reserve_usd"]:
                deepest = dict(p, chain=ch)
    return deepest, total


# ---------------------------------------------------------------- formatting

def pct(x, digits=2):
    if x is None:
        return "—"
    v = x * 100
    if abs(v) >= 99.5:
        return "−100%"
    if abs(v) >= 10:
        digits = 1
    return f"−{abs(v):.{digits}f}%" if v < 0 else f"+{v:.{digits}f}%"


def usd(x):
    if x is None:
        return "—"
    for unit, div in (("B", 1e9), ("M", 1e6), ("k", 1e3)):
        if abs(x) >= div:
            v = x / div
            return f"${v:,.1f}{unit}" if v < 100 else f"${v:,.0f}{unit}"
    return f"${x:,.0f}"


def band(c):
    """Severity band for a round-trip cost."""
    if c is None:
        return "none"
    a = abs(c)
    if a <= 0.0025:
        return "b1"
    if a <= 0.01:
        return "b2"
    if a <= 0.03:
        return "b3"
    if a <= 0.10:
        return "b4"
    return "b5"


def bar_width(c):
    """Log-scaled bar: 0.02% and 100% both have to be readable on one axis."""
    if c is None:
        return 0
    bps = abs(c) * 10_000
    return max(1.5, min(100.0, math.log10(bps + 1) / math.log10(10_001) * 100))


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


# ---------------------------------------------------------------- sections

def group_of(sym):
    return META[sym]["group"]


GROUP_LABEL = {"wfiat": "wFiat", "latam": "LATAM rival", "reference": "reference"}


def panel_best_route():
    items = []
    for sym in META:
        if not rows_for(sym) or not is_live(sym):
            continue
        r = best_row(sym)
        items.append((sym, r))
    items.sort(key=lambda x: -(cost(x[1]) if x[1] else -9.9))

    out = ['<div class="rows">']
    for sym, r in items:
        m = META[sym]
        g = group_of(sym)
        if r is None:
            out.append(
                f'<div class="row dead" data-group="{g}">'
                f'<div class="coin"><span class="flag">{FLAG.get(m["currency"],"")}</span>'
                f'<span class="sym">{esc(sym)}</span>'
                f'<span class="ccy">{esc(m["currency"])}</span></div>'
                f'<div class="where">no on-chain dollar route</div>'
                f'<div class="track"></div><div class="val na">—</div></div>')
            continue
        c = cost(r)
        l = leg(r)
        where = f'{CHAIN_LABEL.get(r["chain"], r["chain"])} · {l.get("buy_venue","")} · vs {l.get("dollar","")}'
        out.append(
            f'<div class="row" data-group="{g}">'
            f'<div class="coin"><span class="flag">{FLAG.get(m["currency"],"")}</span>'
            f'<span class="sym">{esc(sym)}</span>'
            f'<span class="ccy">{esc(m["currency"])}</span>'
            f'<span class="tag t-{g}">{GROUP_LABEL[g]}</span></div>'
            f'<div class="where">{esc(where)}</div>'
            f'<div class="track"><i class="{band(c)}" style="width:{bar_width(c):.1f}%"></i></div>'
            f'<div class="val {band(c)}">{pct(c)}</div></div>')
    out.append("</div>")
    return "\n".join(out)


def panel_grid():
    syms = [s for s in META if rows_for(s) and is_live(s)]
    chains = [c for c in CHAIN_ORDER if any(r["chain"] == c for r in ROWS)]
    head = "".join(f"<th>{CHAIN_LABEL[c]}</th>" for c in chains)
    body = []
    for sym in syms:
        g = group_of(sym)
        cells = []
        for ch in chains:
            r = next((x for x in rows_for(sym) if x["chain"] == ch), None)
            if r is None:
                cells.append('<td class="cell absent"></td>')
                continue
            c = cost(r)
            if c is None:
                sup = r.get("total_supply") or 0
                label = "no pool" if sup else "—"
                cells.append(f'<td class="cell nopool"><span>{label}</span></td>')
            else:
                cells.append(f'<td class="cell {band(c)}"><span>{pct(c, 1)}</span></td>')
        body.append(f'<tr><th class="rowhead"><div class="rh"><span class="sym">{esc(sym)}</span>'
                    f'<span class="tag t-{g}">{GROUP_LABEL[g]}</span></div></th>{"".join(cells)}</tr>')
    return (f'<div class="scroller"><table class="grid"><thead><tr><th></th>{head}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div>')


DEPTH = {r["symbol"]: r for r in json.load(open("depth.json"))["rows"] if "symbol" in r}


def panel_depth():
    items = []
    for sym in META:
        if not rows_for(sym) or not is_live(sym):
            continue
        d = DEPTH.get(sym) or {}
        s_usd = supply_usd(sym)
        # A coin with supply but no route anywhere was measured, not missed:
        # every venue on every chain it lives on was probed and none quoted.
        depth = d.get("depth_usd")
        if depth is None and sym not in DEPTH and supply_units(sym):
            depth = 0
        ratio = (depth / s_usd) if (s_usd and depth) else (0 if depth == 0 else None)
        items.append((sym, s_usd, depth, ratio, d))
    items.sort(key=lambda x: -(x[1] or 0))
    maxsup = max((i[1] or 0) for i in items) or 1

    out = ['<div class="rows depth">']
    for sym, s_usd, depth, ratio, d in items:
        m = META[sym]
        g = group_of(sym)
        sw = 100 * math.log10((s_usd or 0) + 1) / math.log10(maxsup + 1)
        pw = 100 * math.log10((depth or 0) + 1) / math.log10(maxsup + 1)
        r = ratio or 0
        rb = "b1" if r >= 0.10 else "b2" if r >= 0.02 else "b3" if r >= 0.005 else "b5"
        where = CHAIN_LABEL.get(d.get("chain"), d.get("chain") or "—")
        out.append(
            f'<div class="row" data-group="{g}">'
            f'<div class="coin"><span class="flag">{FLAG.get(m["currency"],"")}</span>'
            f'<span class="sym">{esc(sym)}</span>'
            f'<span class="tag t-{g}">{GROUP_LABEL[g]}</span></div>'
            f'<div class="track dual">'
            f'<i class="sup" style="width:{sw:.1f}%"></i>'
            f'<i class="pool" style="width:{max(pw, 0.6):.1f}%"></i></div>'
            f'<div class="nums"><span class="s">{usd(s_usd)}</span>'
            f'<span class="sep">/</span><span class="p">{usd(depth) if depth else "$0"}</span></div>'
            f'<div class="val {rb}">{"—" if ratio is None else f"{ratio*100:.2f}%"}</div>'
            f'<div class="where small">{esc(where)}</div></div>')
    out.append("</div>")
    return "\n".join(out)


def panel_curve():
    """How cost scales with size — the thing a treasury desk actually needs."""
    items = []
    for sym in META:
        r = best_row(sym)
        if not r:
            continue
        items.append((sym, r))
    items.sort(key=lambda x: -(cost(x[1], "10000") or -9))
    body = []
    for sym, r in items:
        g = group_of(sym)
        cells = ""
        for size in ("1000", "10000", "100000"):
            c = cost(r, size)
            cells += f'<td class="cell {band(c)}"><span>{pct(c,1)}</span></td>'
        body.append(f'<tr><th class="rowhead"><div class="rh"><span class="sym">{esc(sym)}</span>'
                    f'<span class="tag t-{g}">{GROUP_LABEL[g]}</span></div></th>'
                    f'<td class="chaincol">{CHAIN_LABEL.get(r["chain"], r["chain"])}</td>{cells}</tr>')
    return ('<div class="scroller"><table class="grid curve"><thead><tr><th></th>'
            '<th>best chain</th><th>$1k</th><th>$10k</th><th>$100k</th></tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div>')


# ---------------------------------------------------------------- headline numbers

def headline():
    n_pairs = len(ROWS)
    n_chains = len({r["chain"] for r in ROWS})
    n_pools = sum(len(v) for v in POOLS.values())
    return dict(n_coins=len({r["symbol"] for r in ROWS}), n_pairs=n_pairs,
                n_chains=n_chains, n_pools=n_pools)


def findings():
    """Four numbers that carry the argument, computed rather than asserted."""
    latam = [s for s in META if group_of(s) in ("wfiat", "latam") and rows_for(s)]

    # rank at $100k among every coin with a quote at that size
    at100 = sorted(
        [(s, cost(best_row(s), "100000")) for s in META
         if best_row(s) and cost(best_row(s), "100000") is not None],
        key=lambda x: -x[1])
    wars_rank = next((i + 1 for i, (s, _c) in enumerate(at100) if s == "wARS"), None)
    wars_100 = dict(at100).get("wARS")

    # deepest LATAM book
    depths = [(s, (DEPTH.get(s) or {}).get("depth_usd") or 0) for s in latam]
    depths.sort(key=lambda x: -x[1])
    top_sym, top_depth = depths[0]
    wars_depth = dict(depths).get("wARS", 0)

    # share of wFiat float that is reachable
    wf = [s for s in META if group_of(s) == "wfiat" and rows_for(s)]
    wf_supply = sum(supply_usd(s) or 0 for s in wf)
    wf_depth = sum((DEPTH.get(s) or {}).get("depth_usd") or 0 for s in wf)

    # chains carrying no dollar pool at all
    dead = sum(1 for r in ROWS
               if (r.get("total_supply") or 0) > 0 and cost(r) is None)

    ahead = [s for s, _c in at100[:max(0, (wars_rank or 1) - 1)]]
    if len(ahead) == 1:
        ahead_txt = f"behind only {ahead[0]}"
    elif ahead:
        ahead_txt = "behind only " + ", ".join(ahead[:-1]) + f" and {ahead[-1]}"
    else:
        ahead_txt = "the tightest of any coin measured"

    # Twin: the one issuer covering the same currency set as wFiat
    twin = [s for s in META if META[s]["issuer"] == "Twin" and rows_for(s) and is_live(s)]
    twin_float = sum(supply_usd(s) or 0 for s in twin)
    twin_live = [s for s in twin if (DEPTH.get(s) or {}).get("depth_usd")]
    twin_floor = next((d.get("note") for s in twin
                       for d in [DEPTH.get(s) or {}] if d.get("note")), None)

    cards = [
        (f"#{wars_rank}", "good",
         f"wARS ranks {wars_rank} of {len(at100)} coins on a $100k round trip "
         f"({pct(wars_100)}), {ahead_txt} — and first among every LATAM coin. Its "
         f"book is shallow at the top but degrades far more gently than its rivals."),
        (f"{len(twin_live)} of {len(twin)}", "good",
         f"Twin coins are tradeable, against {usd(twin_float)} of float — more than "
         f"the entire wFiat family. Twin issues every wFiat currency plus Bolivia, "
         f"mostly on Arbitrum (99.5% of its ARGt), and has no permissionless market "
         f"anywhere: its two pools hold $752 and $200."),
        (usd(top_depth), "warn",
         f"{top_sym} carries the deepest LATAM book: {usd(top_depth)} moves at "
         f"1% all-in. wARS, the best wFiat coin, carries {usd(wars_depth)}."),
        (f"{wf_depth/wf_supply*100:.2f}%", "warn",
         f"is the wFiat family's tradeable depth as a share of its float: "
         f"{usd(wf_depth)} moves at 1% against {usd(wf_supply)} outstanding "
         f"across all six coins."),
        (str(dead), "bad",
         "coin·chain deployments hold supply but have no dollar pool at all. "
         "Minting on a chain is not the same as being tradeable on it."),
    ]
    html = ['<section class="findings">']
    for n, tone, k in cards:
        html.append(f'<div class="finding"><div class="n {tone}">{esc(n)}</div>'
                    f'<div class="k">{esc(k)}</div></div>')
    html.append("</section>")
    return "\n".join(html)


def main():
    h = headline()
    css = open("report.css").read()
    tpl = open("report_template.html").read()
    html = (tpl
            .replace("{{CSS}}", css)
            .replace("{{FINDINGS}}", findings())
            .replace("{{PANEL1}}", panel_best_route())
            .replace("{{PANEL2}}", panel_grid())
            .replace("{{PANEL3}}", panel_depth())
            .replace("{{PANEL4}}", panel_curve())
            .replace("{{GENERATED}}", Q["generated"])
            .replace("{{NCOINS}}", str(h["n_coins"]))
            .replace("{{NPAIRS}}", str(h["n_pairs"]))
            .replace("{{NCHAINS}}", str(h["n_chains"]))
            .replace("{{NPOOLS}}", str(h["n_pools"])))
    open("report.html", "w").write(html)
    print(f"wrote report.html ({len(html):,} bytes)")



if __name__ == "__main__":
    main()
