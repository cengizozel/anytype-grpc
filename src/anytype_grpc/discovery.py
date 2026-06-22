"""Find the gRPC address of the running Anytype desktop app.

The desktop app starts a local helper process (anytypeHelper) that listens on a
few loopback ports: the JSON HTTP API, gRPC, and gRPC-web. The gRPC port is not
fixed across launches, so we discover it by listing the ports the process holds
and probing each one with a cheap, unauthenticated AppGetVersion call.
"""

import re
import subprocess

import grpc


def candidate_ports(process_hint="anytype"):
    """Return loopback ports held by the anytype helper process.

    Uses ``ss -tlnp`` (Linux). Returns an empty list if ``ss`` is unavailable or
    the process is not found, in which case the caller should fall back to an
    explicit address.
    """
    try:
        out = subprocess.run(
            ["ss", "-tlnp"], capture_output=True, text=True, timeout=5
        ).stdout
    except (FileNotFoundError, subprocess.SubprocessError):
        return []
    ports = set()
    for line in out.splitlines():
        if process_hint.lower() in line.lower():
            for p in re.findall(r"127\.0\.0\.1:(\d+)", line):
                ports.add(int(p))
    return sorted(ports)


def probe(address, timeout=3.0):
    """Return True if ``address`` answers a gRPC AppGetVersion call."""
    # Imported lazily so this module has no import-time dependency on the
    # generated bindings (which require the _pb path set up in __init__).
    from pb.protos.service import service_pb2_grpc
    from pb.protos import commands_pb2 as cmd

    try:
        channel = grpc.insecure_channel(address)
        stub = service_pb2_grpc.ClientCommandsStub(channel)
        stub.AppGetVersion(cmd.Rpc.App.GetVersion.Request(), timeout=timeout)
        return True
    except grpc.RpcError:
        return False
    finally:
        try:
            channel.close()
        except Exception:
            pass


def find_grpc_address(host="127.0.0.1", timeout=3.0):
    """Return "host:port" of the running app's gRPC service, or None.

    Probes every loopback port the helper process holds and returns the first
    that answers gRPC. Returns None if nothing answers (app not running, or
    ``ss`` unavailable).
    """
    for port in candidate_ports():
        address = f"{host}:{port}"
        if probe(address, timeout=timeout):
            return address
    return None
