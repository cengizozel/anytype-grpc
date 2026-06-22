"""anytype-grpc: full-control Python client for Anytype over its internal gRPC API.

The official Anytype Local API (HTTP) is intentionally limited: it can read and
create objects, set properties, and patch markdown, but it cannot edit the block
tree, change layouts, edit dataview/set views, or set covers. Those are exactly
the operations this library exposes, because it talks to the same internal gRPC
service (anytype-heart's ClientCommands) that the desktop app itself uses.

Quick start:

    from anytype_grpc import Anytype
    at = Anytype()                  # auto-discovers the port, reads ANYTYPE_TOKEN
    print(at.app_version())         # works without a token
    space = at.default_space        # from ANYTYPE_SPACE_ID, or pass space_id=...

See the README for the full capability list and the docs/ folder for guides.
"""

import os as _os
import sys as _sys

# The generated protobuf modules use absolute imports (for example
# "import pb.protos.commands_pb2"). We vendor them under _pb/ and put that
# directory on sys.path so those imports resolve. This is contained here so
# callers never have to think about it.
_PB_DIR = _os.path.join(_os.path.dirname(__file__), "_pb")
if _PB_DIR not in _sys.path:
    _sys.path.insert(0, _PB_DIR)

from .client import Anytype  # noqa: E402
from .errors import AnytypeError, RpcError  # noqa: E402
from . import discovery  # noqa: E402

__all__ = ["Anytype", "AnytypeError", "RpcError", "discovery"]
__version__ = "0.1.0"
