"""Mint a full-scope session token from your Anytype recovery phrase.

Why this exists: the restricted Local API key (from the desktop "enter this
code" challenge) only grants the limited HTTP scope. To call the full gRPC
surface you need a session token derived from your account, which you get by
passing your recovery phrase (mnemonic) to WalletCreateSession.

Security: the mnemonic is read from hidden stdin, never written to disk, and
never passed as a process argument. Only the resulting token is printed. The
token still grants full control of your local vault, so treat it like a
password and never commit it.

Usage:
    python -m anytype_grpc.auth          # prompts for the phrase, prints a token
    anytype-mint-token                   # same, if installed as a script

Then put the printed token in your environment:
    export ANYTYPE_TOKEN="<the token>"
"""

import getpass
import sys

import grpc


def mint_token(mnemonic, address=None, timeout=15.0):
    """Return a full-scope session token for the given recovery phrase.

    Args:
        mnemonic: your Anytype recovery phrase (the words you saved at setup).
        address: gRPC address of the running app. Auto-discovered if None.
        timeout: per-call timeout in seconds.

    Raises:
        RuntimeError: if the app is not reachable or no token is returned.
    """
    from . import discovery
    from .errors import RpcError
    from pb.protos.service import service_pb2_grpc
    from pb.protos import commands_pb2 as cmd

    if address is None:
        address = discovery.find_grpc_address()
    if address is None:
        raise RuntimeError(
            "Could not find the running Anytype app. Is the desktop app open? "
            "You can also pass address='127.0.0.1:PORT' explicitly."
        )
    channel = grpc.insecure_channel(address)
    stub = service_pb2_grpc.ClientCommandsStub(channel)
    resp = stub.WalletCreateSession(
        cmd.Rpc.Wallet.CreateSession.Request(mnemonic=mnemonic), timeout=timeout
    )
    code = getattr(getattr(resp, "error", None), "code", 0)
    if code != 0:
        raise RpcError("WalletCreateSession", code, resp.error.description)
    if not resp.token:
        raise RuntimeError("No token returned. Check that the recovery phrase is correct.")
    return resp.token


def main():
    """CLI entry point: prompt for the recovery phrase and print a token."""
    sys.stderr.write(
        "Paste your Anytype recovery phrase (input hidden), then press Enter.\n> "
    )
    sys.stderr.flush()
    mnemonic = getpass.getpass("")
    try:
        token = mint_token(mnemonic.strip())
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"\nFailed: {exc}\n")
        sys.exit(1)
    finally:
        del mnemonic
    sys.stderr.write("\nSuccess. Set this in your environment as ANYTYPE_TOKEN:\n\n")
    sys.stderr.flush()
    print(token)


if __name__ == "__main__":
    main()
