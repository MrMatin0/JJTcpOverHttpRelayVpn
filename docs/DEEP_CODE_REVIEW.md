# Deep code review snapshot

This document records the review of commit `dc6cb3e3150efb8d6c84a3bf2318fdd11e1452df`.

## Architecture understood

The active runtime starts in `main.py`, creates `ProxyServer`, and lets `DomainFronter` carry HTTP requests over a fronted TLS connection to Apps Script. HTTP CONNECT requests are either piped directly, upgraded into local MITM TLS, or sent through the HTTP relay depending on host and port policy. SOCKS5 requests are negotiated locally and use `DomainFronter.tcp_tunnel_action()` to forward action JSON through Apps Script to `cloudflare_worker_tcp.js`, where one Durable Object owns the upstream TCP socket.

The repository also contains an older, separate `src/proxy/tcp_tunnel.py` implementation. It is not wired into `ProxyServer.start()` and should not be treated as the active TCP path without further consolidation.

## High-impact findings

### 1. Legacy TCP module and its tests are out of sync

`tests/test_tcp_tunnel.py` expects attributes and APIs that the current `TCPTunnelServer` does not expose, including `host`, `port`, `tunnels_created`, `tunnels_closed`, and `relay_tcp_tunnel`. The cleanup test also awaits a method that is designed as an infinite background loop. This makes the suite fail before it can provide useful regression coverage.

**Recommendation:** either remove the legacy module and its tests, or rewrite them around the active `ProxyServer._relay_tcp_over_http()` path. Do not maintain two competing TCP implementations.

### 2. SOCKS5 reports success before the upstream connection is open

`negotiate_socks5()` sends a success reply immediately after parsing CONNECT. If the Cloudflare/Apps Script open action fails, the client has already received success and then sees a close. A better contract is to negotiate the request first, establish upstream connectivity, then send the success reply, or send a protocol failure reply when opening fails.

### 3. Redirect handling in `tcp_tunnel_action()` is fragile

The response reader returns headers as a dictionary, while the redirect loop in the TCP action path iterates them like `(key, value)` byte pairs and references `urllib.parse` without importing the `urllib` module. A redirect can therefore raise at runtime instead of being followed safely.

**Recommendation:** centralize redirect handling in one helper that consumes the actual `dict[str, str]` contract and uses the already imported `urlparse` function.

### 4. HTTP header parsing is intentionally lossy

Several paths store headers in a plain dictionary. Duplicate headers can be overwritten, and `Set-Cookie` needs special handling. The response parser handles some cookie cases, but request and response header policy should be made explicit and tested for duplicate values, hop-by-hop fields, and oversized values.

### 5. The TCP Worker keeps socket state only in instance memory

The Durable Object is the right ownership boundary, but `TcpTunnel` state is not persisted. A DO restart or hibernation loses the live socket and buffered bytes. This is acceptable for a best-effort tunnel, but it should be documented as a limitation and surfaced as a clean closed/error response.

### 6. The TCP Worker has no per-tunnel authentication beyond the shared key

Anyone who obtains the shared key and a tunnel ID can attempt actions. Tunnel IDs are random on the Python side, which helps, but this is not a replacement for authorization, expiry, origin restrictions, or abuse controls. Keep the Worker endpoint private where possible and rotate the shared secret if it leaks.

## Medium-priority findings

- `main.py` converts several environment overrides directly with `int(...)`; malformed values produce an uncaught traceback instead of a friendly configuration error.
- `setup.py` accepts invalid ports and silently falls back to defaults. It should validate the range `1..65535` and reject collisions.
- CA private-key loading and certificate generation should catch malformed or partially written files and fail with a clear repair path.
- The local SOCKS5 server has no authentication by design. The README now calls this out prominently.
- The repository contains multiple deployment targets and old terminology. The rewritten README now points beginners to the active Apps Script plus TCP Worker path and names optional components separately.

## Review conclusion

The active architecture is understandable and technically ambitious, but the project needs consolidation before claiming a clean deep refactor. The most urgent engineering work is to remove or repair the legacy TCP module/tests, fix the TCP redirect path, and delay SOCKS5 success until the upstream tunnel is actually usable. The new README documents the real setup flow and the security/quota trade-offs instead of hiding them.
