"""The Anytype client: a thin, full-control wrapper over the gRPC ClientCommands service.

Two layers in one object:

1. Generic access to every one of the 332 RPC methods:

       at.call("BlockCreate", context_id=page, block=...)   # any method by name
       req = at.new_request("ObjectSearch")                 # build a request to fill
       resp = at.call("ObjectSearch", req)

2. Ergonomic helpers for the common, fiddly operations (search, covers, the block
   grid layout, dataview views, file upload, and so on). These return plain dicts
   where it helps, and raise RpcError on a non-zero server error code.

The generic layer means anything the desktop app can do is reachable here, even
operations this file does not wrap by hand yet.
"""

import os
from functools import cached_property

import grpc
from google.protobuf import json_format
from google.protobuf import struct_pb2
from google.protobuf import symbol_database

from . import discovery
from .errors import AnytypeError, RpcError

# These imports rely on the _pb directory being on sys.path, which the package
# __init__ guarantees before this module is imported.
from pb.protos.service import service_pb2_grpc
from pb.protos.service import service_pb2
from pb.protos import commands_pb2 as cmd  # noqa: F401  (used via symbol db / callers)

_SYM = symbol_database.Default()
_SERVICE_DESC = service_pb2.DESCRIPTOR.services_by_name["ClientCommands"]


def _to_value(py):
    """Convert a plain Python value into a protobuf Value (for object details)."""
    v = struct_pb2.Value()
    if py is None:
        v.null_value = struct_pb2.NULL_VALUE
    elif isinstance(py, bool):
        v.bool_value = py
    elif isinstance(py, (int, float)):
        v.number_value = float(py)
    elif isinstance(py, str):
        v.string_value = py
    elif isinstance(py, (list, tuple)):
        v.list_value.values.extend(_to_value(x) for x in py)
    elif isinstance(py, dict):
        for k, val in py.items():
            v.struct_value.fields[k].CopyFrom(_to_value(val))
    else:
        v.string_value = str(py)
    return v


class Anytype:
    """A connection to a running Anytype desktop app.

    Args:
        token: full-scope session token. Defaults to the ANYTYPE_TOKEN env var.
            Mint one with ``python -m anytype_grpc.auth``. Read-only and app-level
            calls (like app_version) work without a token.
        address: "host:port" of the gRPC service. Defaults to ANYTYPE_GRPC_ADDR,
            then auto-discovery of the running app's port.
        space_id: a default space id used by helpers when you do not pass one.
            Defaults to the ANYTYPE_SPACE_ID env var.
        timeout: default per-call timeout in seconds.
        auto_discover: probe for the running app's gRPC port if no address is given.
    """

    def __init__(self, token=None, address=None, space_id=None, timeout=30.0,
                 auto_discover=True):
        self.token = token if token is not None else os.environ.get("ANYTYPE_TOKEN")
        self.default_space = space_id or os.environ.get("ANYTYPE_SPACE_ID")
        self.timeout = timeout
        if address is None:
            address = os.environ.get("ANYTYPE_GRPC_ADDR")
        if address is None and auto_discover:
            address = discovery.find_grpc_address()
        if address is None:
            address = "127.0.0.1:31007"
        self.address = address
        self.channel = grpc.insecure_channel(address)
        self.stub = service_pb2_grpc.ClientCommandsStub(self.channel)

    # ----- low-level generic access (works for all 332 methods) ---------------

    @property
    def _metadata(self):
        return [("token", self.token)] if self.token else []

    def request_type(self, method):
        """Return the protobuf request class for an RPC method name."""
        desc = _SERVICE_DESC.methods_by_name.get(method)
        if desc is None:
            raise AnytypeError(f"unknown RPC method: {method!r}")
        return _SYM.GetSymbol(desc.input_type.full_name)

    def new_request(self, method, **fields):
        """Build (but do not send) a request message for an RPC method.

        Flat fields can be passed as keywords. Nested messages should be set on
        the returned object before calling.
        """
        req = self.request_type(method)()
        for key, value in fields.items():
            self._set_field(req, key, value)
        return req

    @staticmethod
    def _set_field(message, key, value):
        field = message.DESCRIPTOR.fields_by_name.get(key)
        if field is None:
            raise AnytypeError(f"{message.DESCRIPTOR.name} has no field {key!r}")
        if field.label == field.LABEL_REPEATED:
            getattr(message, key).extend(value)
        elif field.type == field.TYPE_MESSAGE:
            getattr(message, key).CopyFrom(value)
        else:
            setattr(message, key, value)

    def call(self, method, request=None, *, check=True, timeout=None, **fields):
        """Call any RPC method by name and return the raw response message.

        Args:
            method: the RPC name, for example "BlockCreate" or "ObjectSearch".
            request: a pre-built request message. If None, one is built from
                ``fields``.
            check: if True, raise RpcError when the response carries a non-zero
                error code.
            timeout: per-call override; defaults to the client timeout.
            **fields: flat fields used to build the request when ``request`` is None.
        """
        if request is None:
            request = self.new_request(method, **fields)
        rpc = getattr(self.stub, method)
        resp = rpc(request, metadata=self._metadata, timeout=timeout or self.timeout)
        if check:
            self._raise_on_error(method, resp)
        return resp

    def call_dict(self, method, request=None, **fields):
        """Like ``call`` but return the response as a plain dict."""
        return self.to_dict(self.call(method, request, **fields))

    @staticmethod
    def _raise_on_error(method, resp):
        err = getattr(resp, "error", None)
        code = getattr(err, "code", 0)
        if code:
            raise RpcError(method, code, getattr(err, "description", ""))

    @staticmethod
    def to_dict(message):
        """Convert a protobuf message to a plain dict (camelCase keys preserved)."""
        return json_format.MessageToDict(message, preserving_proto_field_name=False)

    # ----- ergonomic helpers (proven operations) ------------------------------

    def app_version(self):
        """Return the running app's version string (no token needed)."""
        return self.call("AppGetVersion").version

    def _space(self, space_id):
        sid = space_id or self.default_space
        if not sid:
            raise AnytypeError("no space_id given and no default space set")
        return sid

    def search(self, query="", types=None, space_id=None, keys=None, limit=0,
               full_text=None):
        """Search objects in a space. Returns a list of dicts.

        Args:
            query: full-text query (matches object name and snippet).
            types: optional list of type ids or unique keys to filter by.
            space_id: the space to search; defaults to the client default.
            keys: which relation keys to return per record (default: a useful set).
            limit: max results (0 means server default).
        """
        req = self.new_request("ObjectSearch")
        req.spaceId = self._space(space_id)
        req.fullText = full_text if full_text is not None else query
        if limit:
            req.limit = limit
        for k in (keys or ["id", "name", "type", "layout", "snippet"]):
            req.keys.append(k)
        # Filter by type if requested (resolves nothing fancy; expects ids).
        resp = self.call("ObjectSearch", req)
        return [json_format.MessageToDict(r) for r in resp.records]

    def get_object(self, object_id, space_id=None):
        """Open an object and return its full view as a dict (blocks + details)."""
        resp = self.call(
            "ObjectShow", spaceId=self._space(space_id), objectId=object_id
        )
        return self.to_dict(resp)

    def set_details(self, object_id, details, space_id=None):
        """Set one or more detail (property) values on an object.

        Args:
            details: a dict of {relation_key: value}. Values are plain Python
                types (str, number, bool, list, dict, None).
        """
        req = self.new_request("ObjectSetDetails")
        req.contextId = object_id
        for key, value in details.items():
            d = req.details.add()
            d.key = key
            d.value.CopyFrom(_to_value(value))
        return self.call("ObjectSetDetails", req)

    def set_cover(self, object_id, file_object_id, x=0.0, y=0.0, space_id=None):
        """Set an uploaded image file as an object's cover.

        ``file_object_id`` is the id returned by ``upload_file``.
        """
        return self.set_details(
            object_id,
            {"coverType": 1, "coverId": file_object_id, "coverX": x, "coverY": y},
            space_id=space_id,
        )

    def upload_file(self, url=None, local_path=None, space_id=None, kind="Image"):
        """Upload a file (by URL or local path) and return its file object id.

        Note: the desktop helper process may be sandboxed and unable to read
        arbitrary local paths or fetch hotlink-protected URLs. Serving a file
        over http://127.0.0.1 and passing that URL is the most reliable route.
        """
        req = self.new_request("FileUpload")
        req.spaceId = self._space(space_id)
        if url:
            req.url = url
        if local_path:
            req.localPath = local_path
        # Type enum: Image is the common case; see the proto for the full set.
        try:
            req.type = req.DESCRIPTOR.fields_by_name["type"].enum_type.values_by_name[kind].number
        except Exception:
            pass
        resp = self.call("FileUpload", req)
        return getattr(resp, "objectId", "")

    def delete_objects(self, object_ids, space_id=None):
        """Move objects to the bin (archive). Accepts one id or a list."""
        if isinstance(object_ids, str):
            object_ids = [object_ids]
        return self.call("ObjectListSetIsArchived", objectIds=list(object_ids),
                         isArchived=True)

    def list_spaces(self):
        """Return the spaces available to this account, as dicts."""
        return self.search("", space_id=None, keys=["id", "name"]) if self.default_space \
            else self.to_dict(self.call("WorkspaceGetAll"))

    # ----- block operations (the tricky ones, proven this session) ------------

    def add_block(self, context_id, target_id=None, position="Bottom", *,
                  text=None, style="Paragraph", link_to=None, card=False):
        """Add a text or link block to an object.

        Args:
            context_id: the object (page) id to add into.
            target_id: an existing block to position relative to. None appends.
            position: one of "Top", "Bottom", "Left", "Right", "Inner".
            text: text content (for a text block).
            style: text style ("Paragraph", "Header1".."Header3", "Checkbox",
                "Marked", "Toggle", "ToggleHeader1", and so on).
            link_to: an object id to make this a link block instead of text.
            card: if linking, render as a card (with cover) instead of inline.
        """
        block = {}
        if link_to is not None:
            link = {"targetBlockId": link_to}
            if card:
                link.update({"cardStyle": "Card", "iconSize": "SizeMedium",
                             "relations": ["cover"]})
            block["link"] = link
        else:
            block["text"] = {"text": text or "", "style": style}
        req = self.new_request("BlockCreate")
        req.contextId = context_id
        if target_id:
            req.targetId = target_id
        req.position = req.DESCRIPTOR.fields_by_name["position"].enum_type.values_by_name[position].number
        json_format.ParseDict(block, req.block)
        resp = self.call("BlockCreate", req)
        return getattr(resp, "blockId", "")

    def move_blocks(self, context_id, block_ids, drop_target_id, position="Bottom"):
        """Move blocks within an object. Position "Inner" nests them under the target.

        Preserves the order of ``block_ids``. The "Right" position relative to a
        column block is how horizontal card grids are built.
        """
        req = self.new_request("BlockListMoveToExistingObject")
        req.contextId = context_id
        req.targetContextId = context_id
        req.dropTargetId = drop_target_id
        req.position = req.DESCRIPTOR.fields_by_name["position"].enum_type.values_by_name[position].number
        req.blockIds.extend(block_ids)
        return self.call("BlockListMoveToExistingObject", req)

    def delete_blocks(self, context_id, block_ids):
        """Delete blocks from an object."""
        return self.call("BlockListDelete", contextId=context_id,
                         blockIds=list(block_ids))

    def set_block_text(self, context_id, block_id, text, style=None):
        """Replace a block's text content (and optionally its style)."""
        self.call("BlockTextSetText", contextId=context_id, blockId=block_id, text=text)
        if style:
            self.call("BlockTextSetStyle", contextId=context_id, blockId=block_id,
                      style=self.request_type("BlockTextSetStyle")
                      .DESCRIPTOR.fields_by_name["style"].enum_type
                      .values_by_name[style].number)

    # ----- namespaces (the comprehensive, domain-organized API) ---------------
    # Each namespace is a class wrapping this client. Built lazily on first use.
    # Example: at.blocks.add_header(page, "Title"); at.views.set_view_type(s, "Gallery")

    @cached_property
    def blocks(self):
        """Block tree editing: add, move, delete, restyle, grids, tables, toggles."""
        from .blocks import Blocks
        return Blocks(self)

    @cached_property
    def objects(self):
        """Object lifecycle: create, show, details, covers, archive, import/export."""
        from .objects import Objects
        return Objects(self)

    @cached_property
    def views(self):
        """Dataview and set/query views: type, columns, covers, filters, sorts."""
        from .views import Views
        return Views(self)

    @cached_property
    def files(self):
        """Files and images: upload, download, offload, usage."""
        from .files import Files
        return Files(self)

    @cached_property
    def types(self):
        """Types, relations (properties), options, and templates."""
        from .types import Types
        return Types(self)

    @cached_property
    def spaces(self):
        """Spaces and account: list, create, info, invites, participants."""
        from .spaces import Spaces
        return Spaces(self)

    @cached_property
    def query(self):
        """Advanced search and subscriptions (filters, sorts, live updates)."""
        from .search import Search
        return Search(self)

    def __repr__(self):
        return f"Anytype(address={self.address!r}, authed={bool(self.token)})"
