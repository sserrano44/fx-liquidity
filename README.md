# FX stablecoin liquidity study

Reproduces [dcposch's non-USD stablecoin liquidity analysis](https://x.com/dcposch/status/2089099387360461096)
(16 Aug 2026) for the full wFiat family and its LATAM competitors.

The question it answers: put $10,000 of dollars in, buy the coin at the best
on-chain route, sell it straight back — what is left? Everything is `eth_call`
against live pool state, so it is executable depth, not indexer volume.

To refresh this study in a later session, paste `UPDATE_PROMPT.md` into a new chat.

## Running it

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

python3 discover_pools.py   # GeckoTerminal -> pools.json  (incremental; --all to refetch)
python3 run_quotes.py       # round-trip cost curve -> quotes.json  (~8 min)
python3 run_depth.py        # 1% depth by bisection -> depth.json   (~10 min)
python3 build_report.py     # console tables -> report.json
python3 build_html.py       # published page -> report.html
python3 test_v3math.py      # verifies the local v3 maths against on-chain quoters
```

Public keyless RPCs only — no API keys anywhere.

## Layout

| File | What it is |
|---|---|
| `chains.py` | RPC endpoints, dollar legs per chain, quoter deployments, fee tiers |
| `tokens.py` | Token registry: wFiat, LATAM rivals, dcposch's reference coins |
| `rpc.py` | JSON-RPC with endpoint rotation, retries, batching |
| `quoters.py` | Calldata + decoding for Uniswap v3/v4, SlipStream, Pancake quoters |
| `v3math.py` | Local Uniswap-v3 swap simulation from raw pool state |
| `v4key.py` | Recovers a v4 PoolKey by brute-forcing (fee, tickSpacing) against a pool id |
| `poolquote.py` | Prices any discovered pool: solidly / v3 / Algebra / constant-product |
| `run_quotes.py` | The sweep: metadata, supply, round-trip cost at $1k / $10k / $100k |
| `run_depth.py` | Bisects for the notional where round-trip cost hits 1% |

## Two things worth knowing about the implementation

**Dollar legs are plural.** Quoting only native USDC reports "no liquidity" for
coins that trade perfectly well against bridged USDC.e or USDT — XSGD on Polygon
and MXNB everywhere are both in that bucket. Each chain carries a list of
credible dollars and the best round trip across all of them wins.

**Not every pool has a quoter.** Real depth sits on forks with no quoter we can
address: a newer Aerodrome CL factory on Base (`0xf8f2eb49…`) holds the deepest
MXNB book, and Uniswap v3 on Gnosis has no published quoter address. `v3math.py`
reimplements `UniswapV3Pool.swap` — same fixed-point rounding, same tick-bitmap
traversal — so those pools get priced rather than silently dropped.
`test_v3math.py` checks it against the on-chain QuoterV2 to the wei.

Similarly, v4 pools are ids rather than contracts, and probing a standard list of
fee tiers misses anything unusual — the wFiat pool on Celo is fee 3000 /
tickSpacing 30. `v4key.py` solves the key from the pool id instead of guessing.

## Coins an indexer won't find

Twin Finance's coins appear on no token list, price feed or DEX aggregator —
CoinGecko, DefiLlama, GeckoTerminal and DexScreener all return nothing.

Their published registry at `docs.twin.finance/operations/contracts-addresses`
covers only Base and Polygon, and was last modified 2026-05-12 — the day before
Arbitrum minting began. It therefore misses where almost all the float sits: 99.5%
of ARGt is on Arbitrum. Worse, addresses are reused across chains for *different*
tokens, so the Base registry read against Arbitrum is actively misleading —
`0x59863989…` is MEXt on Base and ARGt on Arbitrum.

The Arbitrum set was recovered by deriving the deployer
(`0x3f5c58f0b2400cd82ea7ea6c3b5794a1228f3df9`) from the CREATE addresses of two
tokens found by other means, then enumerating its nonce sequence and reading
name/symbol/decimals/supply off every contract it produced. That turns up ten
currencies: the seven live ones plus Paraguay, Uruguay and Venezuela, deployed and
still unissued. Three ERC-4626 vaults over ARGt (`sARGt` "ARGt Prime", an unnamed
vault, and a test wrapper) are excluded — their balances are claims on ARGt that
its own `totalSupply` already counts.

To repeat the deployer trick for another issuer:

```python
import rlp
from eth_utils import keccak
def create_addr(deployer, nonce):
    return "0x" + keccak(rlp.encode([bytes.fromhex(deployer[2:]), nonce]))[-20:].hex()
# scan candidate deployers x nonces until one reproduces a known token address
```

Because they have no market, they also have no implied price, which would leave
their float unmeasurable. `build_html.price()` falls back to the FX rate another
coin in the same currency is trading at — both track the same peg. BOB has no other
on-chain coin, so BOLt's float stays unpriced rather than guessed.

## Known limits

- **Snapshot, not a month.** The original sampled hourly over 30 days; this is one
  pass at current block.
- **On-chain only.** Aggregator fills routed to off-chain market makers leave no
  pool state to read, so coins whose real volume is OTC (A7A5) look worse here
  than they trade.
- **Supply is summed across chains.** The original appears to use single-chain
  supply for some rows, which is why its ARS float reads ~10x smaller than the
  on-chain total.
- Pool discovery is capped at GeckoTerminal's first page per token·chain, which is
  why the published page ranks coins by measured 1% depth rather than pool TVL.
