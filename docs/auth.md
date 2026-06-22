# Authentication

This guide explains the two kinds of credential Anytype exposes, why this library
needs the stronger one, how to mint it safely, where to store it, and what the
security implications are. Read this before [quickstart.md](quickstart.md).

## The short version

- The Anytype desktop app offers a restricted Local API key (the short challenge
  code you type into a tool). It only grants the limited HTTP scope.
- This library speaks the full internal gRPC API, which needs a full session
  token derived from your account.
- You mint that token once from your recovery phrase with
  `python -m anytype_grpc.auth`, then put it in the `ANYTYPE_TOKEN` environment
  variable.
- The token grants complete access to your local vault. Treat it like a password.

## Two kinds of credential

### Local API key (restricted)

The official Anytype Local HTTP API uses a pairing challenge: the desktop app
shows a code, a client sends it back, and the app returns a short-lived API key.
That key is intentionally scoped to the limited HTTP surface: search, object
creation, properties, and markdown. The block tree, layouts, views, and covers
need the deeper gRPC scope described below.

This library relies on the full session token described below, which reaches the
operations this library exists to provide.

### Full session token (what this library uses)

The internal gRPC service (`anytype-heart`'s `ClientCommands`) is the same layer
the desktop UI uses for every action. To call it you authenticate with a session
token. You obtain that token by passing your account's recovery phrase (the
mnemonic, the words you saved at setup) to the `WalletCreateSession` RPC. The
returned token is then sent as gRPC metadata on every call. It carries the full
scope of your account: everything the desktop app can do.

The client attaches the token automatically. It reads it from the `token`
constructor argument or, if that is omitted, from the `ANYTYPE_TOKEN`
environment variable, and sends it as the `("token", <value>)` metadata pair on
each request.

## Why a session token is needed

The editing that `anytype-grpc` is built for lives in the gRPC service: the block
tree, grids, sets and views, covers and icons, file uploads, and types,
relations, and templates. The gRPC service authenticates with a session token,
so you mint one from your recovery phrase and pass it as `ANYTYPE_TOKEN`.

Note: a few calls work with no token at all, because they are app-level and
operate above any account scope. `at.app_version()` is one. Anything that
touches your space needs the token.

## How to mint the token safely

Run the bundled minting tool:

```bash
python -m anytype_grpc.auth
```

or, if installed as a script:

```bash
anytype-mint-token
```

It prompts for your recovery phrase using hidden input (the characters do not
echo), passes it to `WalletCreateSession`, and prints only the resulting token to
standard output. The recovery phrase is:

- read from hidden stdin, which keeps it out of your shell history and the
  process list,
- never written to disk by the tool,
- discarded from memory after the token is minted.

The Anytype desktop app must be running for this to work, because the tool talks
to the same local gRPC service. If the app is not found, the tool tells you so;
you can also pass an explicit address in code via `mint_token(mnemonic,
address="127.0.0.1:PORT")`.

If minting fails with an authentication error, the recovery phrase was almost
certainly mistyped. The phrase is the exact word list you saved when you created
your Anytype account.

## Where to put the token

Put the printed token in the `ANYTYPE_TOKEN` environment variable. Two common
ways:

Export it in your shell (good for a quick session):

```bash
export ANYTYPE_TOKEN="<the token>"
```

Or keep it in a gitignored `.env` file next to your project and load it (good for
a project). The repo ships an `.env.example` you can copy:

```bash
cp .env.example .env
# then edit .env and fill in ANYTYPE_TOKEN (and optionally ANYTYPE_SPACE_ID)
```

The `.env` file is already listed in `.gitignore`, so it will not be committed.
Load it however you prefer (for example with `python-dotenv`, or by sourcing it
in your shell). The client itself only reads the process environment; it does not
parse `.env` for you.

You can also pass the token directly in code, which overrides the environment and
is useful in tests or when you manage secrets another way:

```python
import anytype_grpc
at = anytype_grpc.Anytype(token="your-session-token")
```

The matching environment variables the client reads are:

- `ANYTYPE_TOKEN`: the full session token (this guide).
- `ANYTYPE_SPACE_ID`: an optional default space id so helpers do not need a
  `space_id` argument every time.
- `ANYTYPE_GRPC_ADDR`: an optional explicit `host:port`; if unset, the client
  auto-discovers the running app's port.

## Security implications

- The recovery phrase and the session token each grant full access to your local
  vault. Anyone holding either can read and change everything in your spaces.
  Never commit them, never paste them into chat or issue trackers, and never log
  them.
- Keep the token in the environment or a gitignored `.env`, which keeps it out of
  source. If you must hardcode it for a one-off script, delete it afterward.
- The gRPC service listens only on the loopback interface (`127.0.0.1`), so it is
  not reachable from other machines by default. The token still matters, because
  anything running on your machine that can read your environment can use it.
- A token is a session credential. If you suspect it leaked, the safe response is
  to treat the account as compromised: the recovery phrase is the root secret,
  and protecting it is what ultimately matters.
- Keep the desktop app updated. The internal gRPC API is a private contract that
  can change between releases, and the vendored protos are pinned to a specific
  Anytype version.

## Next steps

With the token set, continue to [quickstart.md](quickstart.md) to connect and run
the worked examples. For the full list of guides, see [index.md](index.md).
