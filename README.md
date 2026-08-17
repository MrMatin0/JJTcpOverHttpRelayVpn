# JJTcpOverHttpRelayVPN

A local HTTP and SOCKS5 proxy that can relay traffic through Google Apps Script. The optional TCP path uses a Cloudflare Worker Durable Object to keep one real TCP socket alive while Apps Script forwards short HTTP requests.

> **Use responsibly.** This project is an educational networking tool. You are responsible for the traffic you send, the services you deploy, and compliance with Google, Cloudflare, your ISP, and local law.

[راهنمای فارسی و محاوره‌ای](README_FA.md)

## What it does

- **HTTP proxy** on `127.0.0.1:8080` for normal HTTP requests.
- **HTTPS MITM mode** for HTTP traffic inside a CONNECT tunnel. This requires trusting the generated local CA certificate.
- **SOCKS5 proxy** on `127.0.0.1:1080` for end-to-end TCP traffic.
- **Apps Script relay** for the HTTP control plane.
- **Cloudflare Durable Object TCP relay** for persistent TCP connections.
- Optional large-download range splitting, response caching, SNI-based routing, and multiple Apps Script deployments.

The default SOCKS5 listener has no username/password authentication. Keep it bound to localhost unless you deliberately understand the LAN-sharing risk.

## Architecture

```text
HTTP mode:
Browser -> local HTTP proxy -> fronted TLS -> Apps Script -> target URL

TCP mode:
SOCKS5 client -> local proxy -> Apps Script -> Cloudflare Worker/DO -> target TCP socket
                                      ^                         |
                                      +------ JSON actions ----+
```

The TCP actions are `open`, `send`, `poll`, and `close`. The Durable Object owns the live socket; Python uploads client bytes and long-polls for server bytes.

## Requirements

- Python **3.10 or newer**
- Node.js **18 or newer** and npm, only for Cloudflare deployment
- A Google account for Apps Script
- A Cloudflare account if you use the TCP path
- A strong shared secret

## 1. Get the project

```bash
git clone https://github.com/MrMatin0/JJTcpOverHttpRelayVpn.git
cd JJTcpOverHttpRelayVpn
```

## 2. Install the Python side

Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Windows PowerShell:

```powershell
py -3 -m venv .venv
.venv\\Scripts\\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 3. Deploy the TCP Worker

Skip this section if you only need the original HTTP relay.

1. Install Wrangler: `npm install -g wrangler`.
2. Log in: `wrangler login`.
3. Generate a secret:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

4. Open `apps_script/wrangler_tcp.toml` and set the Worker name, `AUTH_KEY`, and Durable Object migration values as needed. Never commit a real secret.
5. Deploy:

```bash
cd apps_script
wrangler deploy --config wrangler_tcp.toml
cd ..
```

6. Save the Worker URL and verify it:

```bash
curl https://YOUR-WORKER.YOUR-SUBDOMAIN.workers.dev
```

You should receive a healthy TCP-worker response.

## 4. Deploy Google Apps Script

1. Open <https://script.google.com> and create a project.
2. Copy all of `apps_script/Code.gs` into the editor.
3. Set `AUTH_KEY` to the same secret used by the Worker.
4. Set `CF_ENDPOINT` to the Worker URL. Remove the trailing slash.
5. Deploy as **Web app** with **Execute as: Me** and access set to **Anyone**.
6. Copy the **deployment ID** from the Web app URL. This is the value for `script_id`, not the Google project’s Script ID.
7. If you changed `Code.gs`, create a new deployment version or update the existing deployment before testing.

## 5. Create `config.json`

```bash
cp config.example.json config.json
```

At minimum, set:

```json
{
  "mode": "apps_script",
  "script_id": "YOUR_APPS_SCRIPT_DEPLOYMENT_ID",
  "auth_key": "THE_SAME_LONG_RANDOM_SECRET",
  "listen_host": "127.0.0.1",
  "listen_port": 8080,
  "socks5_enabled": true,
  "socks5_port": 1080
}
```

The interactive wizard can write this file:

```bash
python setup.py
```

For higher Apps Script capacity, `script_id` can be replaced with `script_ids`, an array of deployment IDs. Keep deployments under accounts you control and use the same `AUTH_KEY` everywhere.

## 6. Start and test

```bash
python main.py
```

HTTP proxy test:

```bash
curl -x http://127.0.0.1:8080 https://example.com
```

SOCKS5 TCP test:

```bash
curl --proxy socks5h://127.0.0.1:1080 https://example.com
```

For Firefox, select **SOCKS v5**, use host `127.0.0.1`, port `1080`, and enable **Proxy DNS when using SOCKS v5**.

Useful commands:

```bash
python main.py --scan
python main.py --install-cert
python main.py --uninstall-cert
python main.py --disable-socks5
```

## Configuration that matters most

| Key | Meaning |
| --- | --- |
| `auth_key` | Shared secret used by Python, Apps Script, and the Worker. |
| `script_id` / `script_ids` | Apps Script Web App deployment ID(s). |
| `google_ip` | Frontend IP used for the TLS connection. `python main.py --scan` can suggest one. |
| `front_domain` | TLS SNI, normally `www.google.com`. |
| `listen_host` | Bind address. Keep `127.0.0.1` unless LAN access is intentional. |
| `lan_sharing` | Binds to all interfaces when enabled. Do not expose this casually. |
| `socks5_enabled` | Enables the unauthenticated local SOCKS5 listener. |
| `relay_timeout` | Maximum time for an HTTP relay request. |
| `chunked_download_*` | Controls parallel range downloads. Reduce these if quotas or memory are tight. |
| `block_hosts` / `bypass_hosts` | Per-host routing policy. |

## Troubleshooting

**`Config not found`**: copy `config.example.json` to `config.json`, or run `python setup.py`.

**`unauthorized`**: compare `auth_key` in `config.json`, `AUTH_KEY` in `Code.gs`, and the Worker secret. They must match byte-for-byte.

**`script id not found`**: use the Apps Script **deployment ID**, deploy as a Web app, and grant access to anyone who needs to call it.

**Browser says the connection closed in HTTP/HTTPS mode**: install the local CA with `python main.py --install-cert`, then restart the browser. SOCKS5 mode does not require the local CA.

**TCP works once and then stops**: inspect Worker logs with `wrangler tail`; check Apps Script and Cloudflare quotas; confirm the Worker URL and secret.

**Slow first request**: the relay warms TLS connections and Apps Script containers. This is expected; later requests should reuse warmed connections.

**Quota exhausted**: long-polling reduces idle TCP polling, but it does not make the quotas infinite. Reduce concurrent tunnels, avoid video streaming through SOCKS5, or distribute load across deployments you own.

## Development

Run the current tests with:

```bash
pytest -q
```

The repository also contains deployment examples under `apps_script/` and exit-node documentation under `docs/exit-node/`.

## License

See [LICENSE](LICENSE).