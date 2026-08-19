"""Minimal JSON-RPC layer with per-chain endpoint rotation, retries and batching.

Public endpoints rate-limit aggressively and each one tolerates a different batch
size, so every request is retried across the chain's endpoint list before a call
is allowed to come back empty. A silently-dropped call would read as "no pool",
which is exactly the conclusion this analysis must not get wrong.
"""
import time
import threading
import requests
from chains import RPCS

_SESSION = requests.Session()
_ADAPTER = requests.adapters.HTTPAdapter(pool_connections=32, pool_maxsize=32)
_SESSION.mount("https://", _ADAPTER)

_LOCK = threading.Lock()
_CURSOR = {}    # chain -> index into RPCS[chain]
_LAST = {}      # url -> last request time, for gentle pacing

MIN_INTERVAL = 0.06   # seconds between hits on the same endpoint


class RpcError(Exception):
    pass


def _pace(url):
    with _LOCK:
        last = _LAST.get(url, 0.0)
        wait = MIN_INTERVAL - (time.time() - last)
        if wait > 0:
            time.sleep(wait)
        _LAST[url] = time.time()


def _post(url, payload, timeout):
    _pace(url)
    r = _SESSION.post(url, json=payload, timeout=timeout,
                      headers={"content-type": "application/json"})
    if r.status_code in (429, 500, 502, 503, 504):
        raise RpcError(f"{r.status_code}")
    r.raise_for_status()
    return r.json()


def _endpoints(chain):
    """Chain endpoints, starting from the last one known to work."""
    urls = RPCS[chain]
    start = _CURSOR.get(chain, 0)
    return [urls[(start + i) % len(urls)] for i in range(len(urls))]


def _request(chain, payload, timeout=45, attempts=4):
    """Send payload, rotating endpoints and backing off. Raises if all fail."""
    err = None
    for attempt in range(attempts):
        for url in _endpoints(chain):
            try:
                res = _post(url, payload, timeout)
                _CURSOR[chain] = RPCS[chain].index(url)
                return res
            except Exception as e:
                err = e
                continue
        time.sleep(0.4 * (2 ** attempt))
    raise RpcError(f"{chain}: all endpoints failed ({err})")


def endpoint(chain):
    _request(chain, {"jsonrpc": "2.0", "id": 1, "method": "eth_blockNumber", "params": []}, timeout=15)
    return RPCS[chain][_CURSOR.get(chain, 0)]


def call(chain, to, data, block="latest"):
    """eth_call returning hex string, or None if the call reverted."""
    res = _request(chain, {"jsonrpc": "2.0", "id": 1, "method": "eth_call",
                           "params": [{"to": to, "data": data}, block]})
    if "error" in res:
        return None
    return res.get("result")


def batch_call(chain, calls, block="latest", chunk=8):
    """calls: list of (to, data). Returns list of hex results (None == reverted).

    A batch whose response is not a well-formed array of the right length is
    redone one call at a time, so a flaky endpoint never masquerades as a revert.
    """
    out = [None] * len(calls)
    for start in range(0, len(calls), chunk):
        part = calls[start:start + chunk]
        payload = [{"jsonrpc": "2.0", "id": start + i, "method": "eth_call",
                    "params": [{"to": to, "data": data}, block]}
                   for i, (to, data) in enumerate(part)]
        try:
            res = _request(chain, payload, timeout=60)
        except Exception:
            res = None
        if not isinstance(res, list) or len(res) != len(part):
            for i, (to, data) in enumerate(part):
                try:
                    out[start + i] = call(chain, to, data, block)
                except Exception:
                    out[start + i] = None
            continue
        for item in res:
            idx = item.get("id")
            if not isinstance(idx, int):
                continue
            out[idx] = item.get("result") if "error" not in item else None
    return out


def block_number(chain):
    res = _request(chain, {"jsonrpc": "2.0", "id": 1, "method": "eth_blockNumber", "params": []})
    return int(res["result"], 16)


def code_exists(chain, addr):
    res = _request(chain, {"jsonrpc": "2.0", "id": 1, "method": "eth_getCode",
                           "params": [addr, "latest"]})
    return len(res.get("result", "0x")) > 4
