# Secure Zerodha configuration — local research only

The module is an owner-authorized read-only integration slice. It does not
implement backtesting, scheduled downloads or order execution. Zerodha is the
only permitted paid market-data provider; nothing here buys a subscription.

## First login and credential entry

The application uses the existing `data/research.sqlite3` database. Migrations
add Django authentication/session and broker tables without resetting research
data. A default account/password is deliberately not created.

In PowerShell, inside `C:\Automations\Trading`, create your local administrator:

```powershell
.\.venv\Scripts\python.exe manage.py createsuperuser
```

Choose the username and password in that interactive terminal. These are local
application credentials, not your Zerodha account login. Do not send passwords,
API secrets, OTPs or tokens to chat. Then:

1. Open **http://127.0.0.1:8001/settings/broker/** and sign in.
2. Enter your existing Zerodha API Key and API Secret. Both inputs render blank
   after saving; the saved API key is masked to its last four characters.
3. Keep the redirect URL exactly **http://127.0.0.1:8001/kite/callback**, with no
   trailing slash. Set the same URL for this API app in the Zerodha developer
   console. Check **Enable read-only broker access**, then save.
4. Click **Login with Zerodha**. Enter your broker login and OTP only on the
   official `kite.zerodha.com` page. Keep the same browser/session throughout.
5. The callback verifies the initiating administrator, Django session, one-time
   state, settings revision and ten-minute timeout before exchanging the request
   token on the server. It immediately redirects to the clean settings URL.
6. Click **Test Connection** after successful login. It calls only the profile
   endpoint, displays a generic result and does not display account details.

Leaving API Secret blank during updates preserves the existing encrypted value;
leaving API Key blank preserves that value too. Replacing credentials, changing
the callback or changing enabled state clears local active/pending sessions.
**Save alone does not contact Zerodha.** Such local invalidation does not revoke
an old remote token; use **Disconnect before replacing credentials** when remote
revocation is wanted. Disconnect attempts remote token revocation, then always
clears local tokens. If revocation cannot be confirmed, the page says so. Delete
requires its checkbox and also clears saved API credentials while retaining safe
audit events. Existing backups may still contain encrypted old credentials.

The broker can invalidate sessions at any time. The app expires tokens at the next
06:00 IST boundary, conservatively also for pre-06:00 logins. Reauthentication is
interactive; there is no refresh-token, CAPTCHA, password or OTP automation.
Logging out of Django ends dashboard access, not the broker session; use
Disconnect to end broker API access explicitly.

## Key storage and fail-closed behavior

`scripts/security_keys.py init` creates two independent secrets: a random Django
signing key and a Fernet broker keyring. On Windows their bundle is encrypted by
current-user DPAPI and stored at:

```text
%LOCALAPPDATA%\TradingResearch\<workspace-path-hash>\security.dpapi
```

The keyring is **not in SQLite/PostgreSQL, the repository, .env, or a database
backup**. DPAPI ties the local vault to the current Windows identity/profile.
It does not protect against malicious code already running as that same user.
Do not share the Windows account or expose the localhost server through a proxy.

Credentials use authenticated Fernet ciphertext with a version/purpose envelope;
secret ciphertext cannot be substituted for access-token ciphertext. Encryption
occurs before database persistence. Plaintext is only used briefly by server-side
code. Python does not guarantee zeroization of immutable strings in memory.
Only the public API key is stored unencrypted as requested; pages mask it. The
official login redirect must send that public API key to Zerodha.

No plaintext fallback exists. A missing/invalid broker key blocks encryption and
decryption. A missing Django signing key blocks startup. `init` never regenerates
an existing damaged key vault. Restore the matching separate key backup. If the
broker key is permanently lost, encrypted credentials cannot be recovered;
delete and re-enter them after deliberate key recovery/reinitialization.

Advanced installations may supply `DJANGO_SECRET_KEY` and `BROKER_FERNET_KEYS`
through a protected process environment. The latter is a JSON array of Fernet
keys, newest first. The app does not load `.env`, does not generate environment
keys, and rejects use of Django's signing key as a broker key. Do not paste real
keys into commands saved in shell history, source, documentation or chat.

## Rotation and separate key backup

For the default Windows vault, stop broker activity and run:

```powershell
.\.venv\Scripts\python.exe scripts/security_keys.py add-key
.\.venv\Scripts\python.exe manage.py rotate_broker_keys
```

The first command prepends a new primary key while retaining previous keys. The
second atomically re-encrypts all saved secrets/tokens using that primary; an
unreadable row rolls back all database ciphertext changes. A crash between these
steps leaves old ciphertext readable because old keys remain. Do not discard old
keys while old database backups still need them. The keyring supports 32 keys;
old-key retirement is a deliberate separate maintenance task, not automatic.

For portable recovery, export an **encrypted key-only** backup to an owner-chosen
location separate from the database backup:

```powershell
# Replace the example path with your approved secure backup destination.
.\.venv\Scripts\python.exe scripts/security_keys.py export --file D:\SeparateKeyBackup\trading.keybackup
```

The command prompts for a new backup passphrase in the terminal; it never prints
keys. It uses scrypt-derived Fernet authenticated encryption, refuses to overwrite
an existing file and refuses a backup path inside this project. Store the
passphrase separately. Export again after rotation. The DPAPI file alone is not
a reliable portable backup across Windows profiles/computers.

Back up the database separately while the server/import commands are stopped,
using SQLite's backup API (or your approved database backup tooling). Preserve
the raw research archive separately if needed. Do not copy the key bundle into
that database archive. A database backup contains API keys and encrypted
credentials, so it is private even without its decryption keys.

On a new machine/profile, install dependencies, restore the approved database
backup, and **before initializing a new vault**, run:

```powershell
.\.venv\Scripts\python.exe scripts/security_keys.py import --file D:\SeparateKeyBackup\trading.keybackup
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py shell -c "from django.contrib.sessions.models import Session; Session.objects.all().delete()"
```

Import asks for the backup passphrase and creates a new DPAPI vault for this
Windows user. It refuses to overwrite an existing vault. The last command logs
out all restored local browser sessions; it does not delete users or research
data. After restore, log in interactively to Zerodha again. Do not assume an old
backed-up access token remains valid. Moving the workspace changes its vault
namespace; use the same export/import process or a protected environment provider.

## Safety and service boundaries

- Settings require an active staff superuser. Mutations require POST and valid
  CSRF; cookie sessions are HTTP-only and SameSite=Lax. The HTTP callback needs a
  top-level cross-site navigation. Secure-cookie flags are not used on plain
  loopback HTTP; non-loopback requests and binds are rejected.
- The callback's request token necessarily arrives in the official browser URL,
  but is never rendered into a page/JavaScript/REST response or persisted locally.
  Pending state is stored only as a hash and is bound to the authenticated browser.
- `BrokerReadOnlyClient` exposes profile, instruments, historical candles,
  quotes and snapshot market depth. There is no public generic SDK proxy or order
  method. Index depth can be absent and remains `None`. There is no tick streaming
  worker or automatic research-database ingestion in this module.
- Two allowlists guard SDK route/method and actual HTTPS destination/path. Only
  `api.kite.trade` is accepted; redirects, proxies/netrc, disabled TLS validation,
  orders, modifications and cancellations are blocked. Authentication exchange
  and token revocation are the only non-GET requests allowed.
- One local process is paced to at most one request per 1.05 seconds. Read GETs
  retry once for transient network/5xx/429 failures. Token exchange/revocation are
  never automatically retried. History calls are bounded to 30 days and explicit
  aware timestamps; quotes are bounded to 100 instruments. For multi-process
  workers, replace the process-local limiter with a shared limiter first.
- Upstream error text is discarded in favor of fixed safe messages/codes. The
  development-server log filter removes URL queries, bodies and exception text.
  SDK/HTTP debug logs are disabled. Audit rows store only event, outcome, safe
  error code, local administrator reference and timestamps.
- The key initialization/backup commands and Django setup need local console
  access. There is no browser endpoint that displays, exports or rotates keys.

## Verification

All broker tests use dummy credentials and mocked network responses. No real
login, profile request, historical download, quote or order operation was made
during implementation. Run:

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py test --verbosity 1
.\.venv\Scripts\python.exe scripts/smoke_test.py
```

Observed final results on 1 November 2026:

| Verification | Result |
|---|---|
| Full test suite | **79 tests passed in 15.324 seconds**: 44 research + 35 broker/security tests |
| Django system check | No issues, zero silenced |
| Migration drift | No changes detected |
| Dependency check | No broken requirements found |
| Migrations | All auth, contenttypes, broker and session migrations applied successfully |
| Existing research data | All five research tables retained identical row counts and SHA-256 content hashes |
| Existing candles | 950 total: 750 × 1m, 150 × 5m, 50 × 15m; zero quality issues |
| Real HTTP on port 8001 | Dashboard 200; anonymous broker settings/callback redirect to administrator login; login page 200 with CSRF form |
| Real HTTP CSRF check | Settings POST without CSRF rejected with 403 |
| Existing smoke test | Passed, including safety/demo labels, chart, root POST 405 and missing order route 404 |
| Live broker verification | Not attempted; automated broker responses mocked |
| Owner setup remaining | Zero local administrator accounts and zero saved broker connections; owner creates account and enters credentials |

Executed upgrade commands included `manage.py migrate --noinput`, `manage.py
check`, `manage.py showmigrations`, `manage.py makemigrations --check --dry-run`,
`manage.py test --verbosity 1`, `python -m pip check`, and the smoke command above,
all through `.venv\Scripts\python.exe`. `scripts/security_keys.py init` created
the external DPAPI vault without displaying any key. The verified local server
was restarted on `127.0.0.1:8001` and left running for owner use.

Before migration, SQLite's backup API created
`data/backups/before-broker-20261101T145402505670.sqlite3` containing the pre-broker
database. Preservation metadata lives in `data/broker-upgrade-preservation.json`;
both are ignored by Git. No unrelated database was opened or changed. No account
password was generated, no credential was requested in chat, and no code was
staged, committed or pushed.

## Primary references checked 1 November 2026

- [Official Kite authentication, redirect parameters and token expiry](https://kite.trade/docs/connect/v3/user/)
- [Kite errors and endpoint rate limits](https://kite.trade/docs/connect/v3/exceptions/)
- [Official Python SDK](https://github.com/zerodha/pykiteconnect)
- [Fernet and key rotation](https://cryptography.io/en/latest/fernet/)

The primary SDK and authentication documentation informed the adapter and state
round-trip. The stricter local timeout, single-process pacing and pre-06:00 expiry
behavior are application safeguards, not claims of broker guarantees.
