"""Chain config: RPCs, dollar leg, and DEX quoter deployments."""

# Public, keyless RPCs. Several fallbacks each; first responsive one wins.
RPCS = {
    "ethereum": [
        "https://ethereum-rpc.publicnode.com",
        "https://eth.llamarpc.com",
        "https://rpc.flashbots.net",
        "https://eth.drpc.org",
    ],
    "base": [
        "https://base-rpc.publicnode.com",
        "https://mainnet.base.org",
        "https://base.llamarpc.com",
        "https://base.drpc.org",
        "https://1rpc.io/base",
    ],
    "polygon": [
        "https://polygon-bor-rpc.publicnode.com",
        "https://polygon-rpc.com",
        "https://polygon.drpc.org",
    ],
    "arbitrum": [
        "https://arbitrum-one-rpc.publicnode.com",
        "https://arb1.arbitrum.io/rpc",
        "https://arbitrum.drpc.org",
    ],
    "bsc": [
        "https://bsc-rpc.publicnode.com",
        "https://binance.llamarpc.com",
        "https://bsc.drpc.org",
    ],
    "celo": [
        "https://forno.celo.org",
        "https://celo-rpc.publicnode.com",
        "https://celo.drpc.org",
    ],
    "gnosis": [
        "https://gnosis-rpc.publicnode.com",
        "https://rpc.gnosischain.com",
        "https://gnosis.drpc.org",
    ],
    "worldchain": [
        "https://worldchain-mainnet.g.alchemy.com/public",
        "https://480.rpc.thirdweb.com",
    ],
    "avalanche": [
        "https://avalanche-c-chain-rpc.publicnode.com",
    ],
    "optimism": [
        "https://optimism-rpc.publicnode.com",
    ],
}

# The dollar leg. USDC everywhere it is the canonical dollar; USDT on BSC where
# USDC depth is thin. Decimals matter: 6 nearly everywhere, 18 on BSC/Gnosis(USDC.e varies).
DOLLAR = {
    "ethereum":  ("USDC", "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", 6),
    "base":      ("USDC", "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", 6),
    "polygon":   ("USDC", "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359", 6),
    "arbitrum":  ("USDC", "0xaf88d065e77c8cC2239327C5EDb3A432268e5831", 6),
    "bsc":       ("USDT", "0x55d398326f99059fF775485246999027B3197955", 18),
    "celo":      ("USDC", "0xcebA9300f2b948710d2653dD7B07f33A8B32118C", 6),
    "gnosis":    ("USDC", "0x2a22f9c3b484c3629090FeED35F17Ff8F88f76F0", 6),
    "worldchain":("USDC", "0x79A02482A880bCE3F13e09Da970dC34db4CD24d1", 6),
    "avalanche": ("USDC", "0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E", 6),
    "optimism":  ("USDC", "0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85", 6),
}

# Every credible dollar leg per chain, best-of across them. A router does the same:
# on Polygon the deep XSGD book is against bridged USDC.e, not native USDC, and
# quoting only native USDC would report "no liquidity" for a coin that trades fine.
DOLLARS = {
    "ethereum": [
        ("USDC",  "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", 6),
        ("USDT",  "0xdAC17F958D2ee523a2206206994597C13D831ec7", 6),
        ("DAI",   "0x6B175474E89094C44Da98b954EedeAC495271d0F", 18),
    ],
    "base": [
        ("USDC",  "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", 6),
        ("USDbC", "0xd9aAEc86B65D86f6A7B5B1b0c42FFA531710b6CA", 6),
        ("USDT",  "0xfde4C96c8593536E31F229EA8f37b2ADa2699bb2", 6),
        ("DAI",   "0x50c5725949A6F0c72E6C4a641F24049A917DB0Cb", 18),
    ],
    "polygon": [
        ("USDC",   "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359", 6),
        ("USDC.e", "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174", 6),
        ("USDT",   "0xc2132D05D31c914a87C6611C10748AEb04B58e8F", 6),
        ("DAI",    "0x8f3Cf7ad23Cd3CaDbD9735AFf958023239c6A063", 18),
    ],
    "arbitrum": [
        ("USDC",   "0xaf88d065e77c8cC2239327C5EDb3A432268e5831", 6),
        ("USDC.e", "0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8", 6),
        ("USDT",   "0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9", 6),
        ("DAI",    "0xDA10009cBd5D07dd0CeCc66161FC93D7c9000da1", 18),
    ],
    "bsc": [
        ("USDT",  "0x55d398326f99059fF775485246999027B3197955", 18),
        ("USDC",  "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d", 18),
        ("BUSD",  "0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56", 18),
    ],
    "celo": [
        ("USDC",  "0xcebA9300f2b948710d2653dD7B07f33A8B32118C", 6),
        ("USDT",  "0x48065fbBE25f71C9282ddf5e1cD6D6A887483D5e", 6),
        ("cUSD",  "0x765DE816845861e75A25fCA122bb6898B8B1282a", 18),
    ],
    "gnosis": [
        ("USDC",  "0x2a22f9c3b484c3629090FeED35F17Ff8F88f76F0", 6),
        ("USDC.e","0xDDAfbb505ad214D7b80b1f830fcCc89B60fb7A83", 6),
        ("WXDAI", "0xe91D153E0b41518A2Ce8Dd3D7944Fa863463a97d", 18),
        ("USDT",  "0x4ECaBa5870353805a9F068101A40E0f32ed605C6", 6),
    ],
    "worldchain": [
        ("USDC",  "0x79A02482A880bCE3F13e09Da970dC34db4CD24d1", 6),
    ],
    "avalanche": [
        ("USDC",  "0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E", 6),
        ("USDT",  "0x9702230A8Ea53601f5cD2dc00fDBc13d4dF4A8c7", 6),
    ],
    "optimism": [
        ("USDC",  "0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85", 6),
        ("USDC.e","0x7F5c764cBc14f9669B88837ca1490cCa17c31607", 6),
        ("USDT",  "0x94b008aA00579c1307B0EF2c499aD98a8ce58e58", 6),
    ],
}

# Uniswap v3-style QuoterV2 (quoteExactInputSingle with a fee tier).
# venue -> chain -> quoter address
V3_QUOTERS = {
    "uniswap-v3": {
        "ethereum":  "0x61fFE014bA17989E743c5F6cB21bF9697530B21e",
        "base":      "0x3d4e44Eb1374240CE5F1B871ab261CD16335B76a",
        "polygon":   "0x61fFE014bA17989E743c5F6cB21bF9697530B21e",
        "arbitrum":  "0x61fFE014bA17989E743c5F6cB21bF9697530B21e",
        "bsc":       "0x78D78E420Da98ad378D7799bE8f4AF69033EB077",
        "celo":      "0x82825d0554fA07f7FC52Ab63c961F330fdEFa8E8",
        "avalanche": "0xbe0F5544EC67e9B3b2D979aaA43f18Fd87E6257F",
        "optimism":  "0x61fFE014bA17989E743c5F6cB21bF9697530B21e",
        "worldchain":"0x10158D43e6cc414deE1Bd1eB0EfC6a5cBCfF244c",
    },
    # Aerodrome SlipStream on Base / Velodrome SlipStream on Optimism.
    # Same quoter interface but the pool key uses tickSpacing, not fee.
    "slipstream": {
        "base":     "0x254cF9E1E6e233aa1AC962CB9B05b2cfeAaE15b0",
        "optimism": "0xA2DEcF05c16537C702779083Fe067e308463CE45",
    },
    "pancake-v3": {
        "bsc":      "0xB048Bbc1Ee6b733FFfCFb9e9CeF7375518e25997",
        "base":     "0xB048Bbc1Ee6b733FFfCFb9e9CeF7375518e25997",
        "ethereum": "0xB048Bbc1Ee6b733FFfCFb9e9CeF7375518e25997",
        "arbitrum": "0xB048Bbc1Ee6b733FFfCFb9e9CeF7375518e25997",
    },
}

# Uniswap v4 Quoter (singleton PoolManager). This is where the wFiat pools live.
V4_QUOTERS = {
    "ethereum":   "0x52F0E24D1c21C8A0cB1e5a5dD6198556BD9E1203",
    "base":       "0x0d5e0F971ED27FBfF6c2837bf31316121532048D",
    "polygon":    "0xb3d5c3dFC3a7aEbFF71895a7191796BFFC2c81b9",
    "arbitrum":   "0x3972c00f7ed4885e145823eb7C655375D275A1c5",
    "bsc":        "0x9F75dD27D6664c475B90e105573E550ff69437B0",
    "celo":       "0x28566da1093609182dfF2cB2A91Cfd72e61d66cD",
    "worldchain": "0x55d235b3FF2dAF7c3EDe0Defc9521f1d6fe6c5c0",
    "optimism":   "0x1f3131A13296Fb91c90870043742C3cDBfF1A8D7",
    "avalanche":  "0xbe40675bb704506a3c2ccfb762dcfd1e979845C2",
}

# Standard v4 fee/tickSpacing pairs to probe when hunting for a pool.
V4_FEE_SPACING = [(100, 1), (500, 10), (3000, 60), (10000, 200), (2500, 50), (1000, 20)]

# v3 fee tiers to probe.
V3_FEES = [100, 500, 3000, 10000]
PANCAKE_FEES = [100, 500, 2500, 10000]
SLIPSTREAM_TICK_SPACINGS = [1, 10, 50, 60, 100, 200, 2000]

# GeckoTerminal network slugs, for pool discovery / TVL.
GT_NETWORK = {
    "ethereum": "eth",
    "base": "base",
    "polygon": "polygon_pos",
    "arbitrum": "arbitrum",
    "bsc": "bsc",
    "celo": "celo",
    "gnosis": "xdai",
    "worldchain": "world-chain",
    "avalanche": "avax",
    "optimism": "optimism",
}
