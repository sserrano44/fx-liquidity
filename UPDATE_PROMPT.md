# Prompt: refresh the FX stablecoin liquidity study

Paste everything below the line into a new session.

---

Update the FX stablecoin liquidity research in `/Users/sserrano44/projects/wfiat/fx-liquidity`.

This reproduces dcposch's non-USD stablecoin study (https://x.com/dcposch/status/2089099387360461096)
for Ripio's wFiat family against its LATAM competitors: buy each coin with the chain's
dollar stablecoin at the best on-chain route, sell it straight back, report the round-trip
cost. Everything is `eth_call` against live pool state — no aggregators, no indexer prices.

**Read `README.md` in that directory first.** It documents the pipeline, the two non-obvious
implementation decisions (plural dollar legs; local v3 swap maths for pools with no callable
quoter), and the known limits. Don't re-derive any of that.

## Run it

```bash
source venv/bin/activate
python3 test_v3math.py        # must print ALL MATCH before trusting any number
python3 discover_pools.py     # incremental; --all to refetch every pool
python3 run_quotes.py         # ~15 min, writes quotes.json
python3 run_depth.py          # ~15 min, writes depth.json
python3 build_report.py       # console tables
python3 build_html.py         # report.html
```

Run the long stages in the background and wait on a completion marker — they exceed the
foreground timeout. GeckoTerminal rate-limits hard; keep discovery incremental unless pool
membership genuinely needs refreshing.

## Verify before publishing

The failure mode that matters is a coin looking untradeable because measurement failed, not
because the market is thin. Check all of these:

- `test_v3math.py` printed ALL MATCH
- `run_quotes.py` exited 0 and printed **no** `WARNING:` lines (missing rows / errored pairs)
- `python3 -c "import json;q=json.load(open('quotes.json'));print(sum(1 for r in q['rows'] if r.get('error')))"` → 0
- every `depth.json` row has a `depth_usd` (a coin that can't fill the floor size must record
  a measured `0` with a note, never a missing field)
- row count in `quotes.json` equals the coin·chain pairs in `tokens.py`
- spot-check against dcposch's published figures where they overlap (EURC/Base ≈ −0.02%,
  tGBP/Ethereum ≈ −0.59%, AUDM/Ethereum ≈ −0.58%, wARS/Base ≈ −1.0%). Large drift means a
  methodology break, not a market move.

Repair any errored pair by re-running just that pair through `run_quotes.do_pair` and merging
into `quotes.json` — don't leave a hole and don't re-run the whole sweep.

## Refresh the registry before running

Competitors ship fast and their own docs lag. In `tokens.py`:

1. **Twin Finance** — the closest competitor, same currencies as wFiat. Re-check
   `docs.twin.finance/operations/contracts-addresses`, but treat it as unreliable: it has been
   stale by months, documents only Base/Polygon, and Twin reuses the same address on different
   chains for *different* tokens. Re-enumerate their deployer
   `0x3f5c58f0b2400cd82ea7ea6c3b5794a1228f3df9` by CREATE nonce (recipe in README) to catch new
   deployments and new chains. **PRYt (PYG), URYt (UYU) and VENt (VES) were deployed with zero
   supply — check whether they have launched.** Exclude ERC-4626 vaults over a token (sARGt and
   friends); their balances are claims the underlying's `totalSupply` already counts.
2. **wFiat** — any new chain deployments, and whether Gnosis still has no pools.
3. **New entrants** — check DefiLlama's non-USD list and CoinGecko for LATAM stablecoins not yet
   in `tokens.py`. Anything with no market won't be on an indexer, so absence there is not
   evidence of absence.
4. **New chains** — a chain needs an entry in `chains.py` (RPCs, dollar legs, quoter addresses)
   before its pairs will be quoted at all.

## Publish

Update the existing artifact, do not create a new one:

```
Artifact(file_path=".../report.html", url="https://claude.ai/code/artifact/8b46e619-6323-47ec-b719-59f7415f158d",
         favicon="💱", label="<short-change-note>")
```

Then tell me, in prose: what moved since last time, what's new in the registry, and anything
that changes the competitive read. Lead with what changed, not with the method.

## What the last run (2026-08-17) found, for comparison

- wARS best wFiat coin: −1.02% at $10k on Base; ranked 4 of 21 at $100k (−3.49%), first among
  all LATAM coins — its book is shallow but degrades far more gently than rivals'
- MXNB (Bitso/Juno) deepest LATAM book: −0.11% at $10k on Base, $63.2k moves at 1%
- wFiat family: $14.0k of depth at 1% against $8.3M float (0.17%)
- Twin: $9.3M float — more than all of wFiat — and 0 of 7 live coins tradeable; two pools
  totalling under $1k
- wFiat's other five coins effectively untradeable at $10k: wBRL −2.19%, wCOP −7.39%,
  wPEN −7.59%, wMXN −14.32%, wCLP −50.49%
