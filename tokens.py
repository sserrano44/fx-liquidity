"""Token registry: non-USD stablecoins, by currency, with per-chain addresses.

Sources: CoinGecko platform map (cg_list.json), DefiLlama stablecoin list, and
the wFiat contract addresses from DUNE_DASHBOARDS.md.
"""

# wFiat uses the same address on every chain it is deployed to.
WFIAT_CHAINS = ["ethereum", "base", "polygon", "bsc", "gnosis", "worldchain", "celo"]


def _same(addr, chains=None):
    return {c: addr for c in (chains or WFIAT_CHAINS)}


TOKENS = [
    # ---------------------------------------------------------------- wFiat
    dict(symbol="wARS", currency="ARS", issuer="Ripio", group="wfiat",
         addrs=_same("0x0DC4F92879B7670e5f4e4e6e3c801D229129D90D")),
    dict(symbol="wBRL", currency="BRL", issuer="Ripio", group="wfiat",
         addrs=_same("0xD76f5Faf6888e24D9F04Bf92a0c8B921FE4390e0")),
    dict(symbol="wMXN", currency="MXN", issuer="Ripio", group="wfiat",
         addrs=_same("0x337E7456B420bD3481e7FA61fA9850343d610d34")),
    dict(symbol="wCLP", currency="CLP", issuer="Ripio", group="wfiat",
         addrs=_same("0x61D450a098b6a7f69fC4b98CE68198fe59768651")),
    dict(symbol="wCOP", currency="COP", issuer="Ripio", group="wfiat",
         addrs=_same("0x8a1D45e102e886510e891d2Ec656a708991e2D76")),
    dict(symbol="wPEN", currency="PEN", issuer="Ripio", group="wfiat",
         addrs=_same("0x4F34c8b3b5FB6D98Da888F0feA543d4d9C9F2eBE")),

    # ---------------------------------------------------- LATAM competitors
    dict(symbol="BRLA", currency="BRL", issuer="BRLA Digital", group="latam",
         addrs={"polygon": "0xE6A537a407488807F0bbEb0038B79004f19DDDFb",
                "gnosis":  "0xFEcB3F7c54E2CAAE9dC6Ac9060A822d47E053760",
                "celo":    "0xFEcB3F7c54E2CAAE9dC6Ac9060A822d47E053760"}),
    dict(symbol="BRZ", currency="BRL", issuer="Transfero", group="latam",
         addrs={"ethereum":  "0x01d33FD36ec67c6Ada32cf36b31e88EE190B1839",
                "polygon":   "0x4eD141110F6EeeAbA9A1df36d8c26f684d2475Dc",
                "bsc":       "0x71be881e9C5d4465B3FfF61e89c6f3651E69B5bb",
                "avalanche": "0x491a4eb4f1FC3BfF8E1d2FC856a6A46663aD556f"}),
    dict(symbol="cREAL", currency="BRL", issuer="Mento", group="latam",
         addrs={"celo": "0xe8537a3d056DA446677B9E9d6c5dB704EaAb4787"}),
    dict(symbol="BRL1", currency="BRL", issuer="BRL1 consortium", group="latam",
         addrs={"polygon": "0x5c067C80c00Ecd2345B05e83a3E758Ef799C40b5"}),
    dict(symbol="MXNB", currency="MXN", issuer="Bitso/Juno", group="latam",
         addrs={"arbitrum":  "0xF197FFC28c23E0309B5559e7a166f2c6164C80aA",
                "base":      "0xF197FFC28c23E0309B5559e7a166f2c6164C80aA",
                "polygon":   "0xF197FFC28c23E0309B5559e7a166f2c6164C80aA",
                "ethereum":  "0xF197FFC28c23E0309B5559e7a166f2c6164C80aA",
                "avalanche": "0xF197FFC28c23E0309B5559e7a166f2c6164C80aA"}),
    dict(symbol="MXNe", currency="MXN", issuer="Brale/Etherfuse", group="latam",
         addrs={"base": "0x269caE7Dc59803e5C596c95756faEeBb6030E0aF"}),
    dict(symbol="cCOP", currency="COP", issuer="Mento", group="latam",
         addrs={"celo": "0x8A567e2aE79CA692Bd748aB832081C45de4041eA"}),

    # Twin Finance — the closest analogue to wFiat: the same six currencies plus
    # Bolivia, from one issuer.
    #
    # Twin's published registry (docs.twin.finance/operations/contracts-addresses,
    # last modified 2026-05-12) documents only Base and Polygon, and is stale:
    # Arbitrum minting began 2026-05-13 and now holds the great majority of the
    # float — 99.5% of ARGt. The Arbitrum addresses are undocumented and appear on
    # no token list, so they were recovered by deriving the deployer
    # (0x3f5c58f0b2400cd82ea7ea6c3b5794a1228f3df9) from the CREATE addresses of two
    # known tokens, then enumerating its nonce sequence. Every entry below was
    # verified on-chain for name, symbol, decimals and supply.
    #
    # Deliberately excluded: dust test deployments on Ethereum (ARGt, supply 7) and
    # Polygon (BRAt, supply 1), and three ERC-4626 vaults over ARGt on Arbitrum
    # (sARGt "ARGt Prime" 0x9dD3F844…, an unnamed vault 0x10c49bF6…, and
    # "Test ARGt Prime (wrapped)" 0x133ddc6A…) whose balances are claims on ARGt
    # already counted in its own totalSupply.
    dict(symbol="ARGt", currency="ARS", issuer="Twin", group="latam",
         addrs={"arbitrum": "0x59863989d080B22476DB95656d0C3CC18be92214",
                "base": "0xf016413834E6D1A14F3D628B11D6Ef725a6bdbDD",
                "polygon": "0x50464bE58912745447E24EB3bbDedcee10D3E056"}),
    dict(symbol="BRAt", currency="BRL", issuer="Twin", group="latam",
         addrs={"arbitrum": "0xC4Ed6abA5373d78e160F4dF39E011f078bE54Df8",
                "base": "0xFEE29845569570F8e0119291dff77B7b93283aaB"}),
    dict(symbol="MEXt", currency="MXN", issuer="Twin", group="latam",
         addrs={"arbitrum": "0xB96Aa6bAbccD738d6644aDD4912Fe5EFBEBF5a25",
                "base": "0x59863989d080B22476DB95656d0C3CC18be92214"}),
    dict(symbol="COLt", currency="COP", issuer="Twin", group="latam",
         addrs={"arbitrum": "0xA16d5DB80A45157e0E451750b81fF0cC0b61D558",
                "base": "0xD70ad085684b2A9f4B5d54D7BDB2ecA37a273216"}),
    dict(symbol="CHLt", currency="CLP", issuer="Twin", group="latam",
         addrs={"arbitrum": "0xE8dbC4680235CCAEFf48E4c0b0eaCEEBb89E5E17",
                "base": "0x95ef2370166b250e7CE3b8F236c7e7E9feD12c2e"}),
    dict(symbol="PERt", currency="PEN", issuer="Twin", group="latam",
         addrs={"arbitrum": "0x899438713F62b04d6cd8e8709986f7256Fb6e3d9",
                "base": "0xD09ABA2969B822d66DC4Bc3bB58eE520Bcf9f0C3"}),
    dict(symbol="BOLt", currency="BOB", issuer="Twin", group="latam",
         addrs={"arbitrum": "0x1edF5E61b6A4fE19FEf3a695328f61AAA07728eA",
                "base": "0x1d2E8C1Fe82ab2AD8dc43eD98A2F507Dfb5b4995"}),
    # Deployed and ready, zero supply as of this run — Twin's next three markets.
    # Carried here so the roadmap is recorded; the report skips zero-supply coins.
    dict(symbol="PRYt", currency="PYG", issuer="Twin", group="latam",
         addrs={"arbitrum": "0x6bB883b61d58f3531CD2E15563F2cDD0e9b24e32"}),
    dict(symbol="URYt", currency="UYU", issuer="Twin", group="latam",
         addrs={"arbitrum": "0x2ECc8c60C881436D43b9AE8EEC7bC226d5404E71"}),
    dict(symbol="VENt", currency="VES", issuer="Twin", group="latam",
         addrs={"arbitrum": "0x8c4106bEE19cB995ABab20f3De6Ba9DF9cF9a17F"}),

    # ------------------------------------------ dcposch reference currencies
    dict(symbol="EURC", currency="EUR", issuer="Circle", group="reference",
         addrs={"ethereum":   "0x1aBaEA1f7C830bD89Acc67eC4af516284b1bC33c",
                "base":       "0x60a3E35Cc302bFA44Cb288Bc5a4F316Fdb1adb42",
                "worldchain": "0x1c60Ba0a0Ed1019e8eb035E6DaF4155a5cE2380b",
                "optimism":   "0xdCB612005417dc906ff72c87dF732E5A90D49E11",
                "avalanche":  "0xC891EB4cbdEFf6e073e859e987815Ed1505c2ACD"}),
    dict(symbol="JPYC", currency="JPY", issuer="JPYC Inc", group="reference",
         addrs={"ethereum": "0x2370f9d504C7a6E775bf6E14B3F12846b594cD53",
                "polygon":  "0x6AE7Dfc73E0dDE2aa99ac063DcF7e8A63265108c",
                "gnosis":   "0x417602f4fbdD471A431Ae29fB5FE0A681964C11b"}),
    dict(symbol="XSGD", currency="SGD", issuer="StraitsX", group="reference",
         addrs={"ethereum":  "0x70e8dE73cE538DA2bEEd35d14187F6959a8ecA96",
                "base":      "0x0a4C9CB2778Ab3302996A34befcf9A8Bc288c33b",
                "polygon":   "0xDC3326e71D45186F113a2F448984CA0e8D201995",
                "arbitrum":  "0xe333e7754a2dC1E020a162eCab019254b9DAB653",
                "avalanche": "0xb2F85b7Ab3c2b6f62DF06dE6aE7D09c010a5096E"}),
    dict(symbol="tGBP", currency="GBP", issuer="Tokenised Money", group="reference",
         addrs={"ethereum": "0x27F6c8289550FCe67f6b50BeD1f519966AfE5287",
                "base":     "0x27F6c8289550FCe67f6b50BeD1f519966AfE5287",
                "polygon":  "0x27F6c8289550FCe67f6b50BeD1f519966AfE5287",
                "arbitrum": "0x27F6c8289550FCe67f6b50BeD1f519966AfE5287",
                "bsc":      "0x27F6c8289550FCe67f6b50BeD1f519966AfE5287",
                "gnosis":   "0x1f34490F8E8e776FFc547B39B864364035EaF44f"}),
    dict(symbol="AUDM", currency="AUD", issuer="Macropod", group="reference",
         addrs={"ethereum": "0x081599E4936D12c46bd48913B2329115cD26cbDD",
                "base":     "0xeDeD6ae915b129b67A4ad49901518f2736427063"}),
    dict(symbol="AUDF", currency="AUD", issuer="Forte", group="reference",
         addrs={"ethereum":  "0xd2a530170D71a9cFE1651fb468e2B98F7ED7456b",
                "base":      "0xd2a530170D71a9cFE1651fb468e2B98F7ED7456b",
                "polygon":   "0xd2a530170D71a9cFE1651fb468e2B98F7ED7456b",
                "avalanche": "0xd2a530170D71a9cFE1651fb468e2B98F7ED7456b"}),
    dict(symbol="A7A5", currency="RUB", issuer="A7A5", group="reference",
         addrs={"ethereum": "0x6fA0BE17E4Bea2fCFa22EF89bF8ac9aAB0Ab0fC9"}),
    # A7A5 itself has no EVM pool; its on-chain trading happens through the
    # wrapper, which is what dcposch measured for the RUB row.
    dict(symbol="wA7A5", currency="RUB", issuer="A7A5 (wrapped)", group="reference",
         addrs={"ethereum": "0xF442Ff10b8dEf89514560A66C0Ad28777094636A"}),
    # JPYC shipped a v2 contract; both are live and each has its own pools.
    dict(symbol="JPYCv1", currency="JPY", issuer="JPYC Inc (v1)", group="reference",
         addrs={"ethereum":  "0x431d5DFf03120AFA4bdF332c61A6e1766eF37BDB",
                "polygon":   "0x431d5DFf03120AFA4bdF332c61A6e1766eF37BDB",
                "gnosis":    "0x431d5DFf03120AFA4bdF332c61A6e1766eF37BDB",
                "avalanche": "0x431d5DFf03120AFA4bdF332c61A6e1766eF37BDB"}),
]

BY_SYMBOL = {t["symbol"]: t for t in TOKENS}
CURRENCIES = sorted({t["currency"] for t in TOKENS})
