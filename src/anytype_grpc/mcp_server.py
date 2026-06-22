"""An MCP (Model Context Protocol) server that exposes Anytype over its gRPC API.

This module turns the anytype-grpc client into a set of MCP tools that any MCP
client (Claude Desktop, an IDE plugin, a custom agent) can call. It uses the
official Python "mcp" SDK (FastMCP) and speaks over the stdio transport, which
is what desktop MCP clients launch and talk to.

What it exposes:

- A curated set of high-value tools (search, get_object, create_object,
  add_block, edit_block_text, delete_block, set_details, set_cover,
  upload_image, set_view_type, set_visible_columns), each with a verbose
  description and per-parameter documentation written so a small language model
  can call it without guessing.
- A generic escape hatch, call_rpc, that can invoke any one of the 332 gRPC
  ClientCommands methods by name with a JSON request body. Use it for anything
  the curated tools do not cover.

How it connects:

The server builds one Anytype client from environment variables, lazily on the
first tool call:

- ANYTYPE_TOKEN: the full-scope session token (mint one with
  ``python -m anytype_grpc.auth``). Required for almost every write and most
  reads.
- ANYTYPE_GRPC_ADDR: the gRPC address as "host:port" (for example
  "127.0.0.1:31009"). If unset, the client auto-discovers the running app's
  port.
- ANYTYPE_SPACE_ID: the default space id used when a tool does not get an
  explicit space_id. Most tools fall back to this.

Run it directly for stdio:

    python -m anytype_grpc.mcp_server

or, after installing the package, via the console entry if one is configured.
See docs/mcp.md for client configuration JSON and the full tool table.

Design notes:

- Tools return plain JSON-serializable Python (dicts, lists, strings). The MCP
  SDK wraps the return value as the tool result, so callers get structured data.
- Every tool description states what it does, documents every parameter with a
  type and an example, says what it returns, and lists common mistakes. The
  per-parameter help is attached with typing.Annotated and pydantic.Field so it
  shows up in the tool's input schema where the model can see it.
- Errors are surfaced as a JSON object {"error": "..."} the caller can read, so a
  calling model gets a readable message in place of a transport failure.
"""

import json
import os
from typing import Annotated, Any, Optional

from pydantic import Field

from mcp.server.fastmcp import FastMCP

from . import Anytype
from .blocks import Blocks
from .files import Files
from .objects import Objects
from .search import Search
from .views import Views


# The MCP server instance. Tools are registered on it with @mcp.tool(...).
mcp = FastMCP(
    "anytype-grpc",
    instructions=(
        "Full-control access to a running Anytype app over its internal gRPC "
        "API. Use 'search' to find object ids, 'get_object' to read an object's "
        "blocks and details, and the create/add/edit/set tools to change things. "
        "Object ids look like 'bafyrei...'. An object 'type' is identified by a "
        "unique key like 'ot-page' or 'ot-note'. This unique key is the type's "
        "own identifier, which differs from an object id. For any "
        "operation the curated tools do not cover, use 'call_rpc' with the gRPC "
        "method name and a JSON request. Set the space with the ANYTYPE_SPACE_ID "
        "environment variable, or pass space_id where a tool accepts it."
    ),
)


# ----- client and domain helpers (built lazily from the environment) ----------

# Cached singletons so we connect once and reuse the channel across tool calls.
_client: Optional[Anytype] = None
_blocks: Optional[Blocks] = None
_files: Optional[Files] = None
_objects: Optional[Objects] = None
_search: Optional[Search] = None
_views: Optional[Views] = None


def _get_client() -> Anytype:
    """Return the shared Anytype client, building it from the environment once.

    Reads ANYTYPE_TOKEN, ANYTYPE_GRPC_ADDR, and ANYTYPE_SPACE_ID. If
    ANYTYPE_GRPC_ADDR is unset, the client auto-discovers the running app's
    gRPC port. The connection is lazy and cached: the first tool call builds it,
    later calls reuse it.
    """
    global _client, _blocks, _files, _objects, _search, _views
    if _client is None:
        _client = Anytype(
            token=os.environ.get("ANYTYPE_TOKEN"),
            address=os.environ.get("ANYTYPE_GRPC_ADDR"),
            space_id=os.environ.get("ANYTYPE_SPACE_ID"),
        )
        _blocks = Blocks(_client)
        _files = Files(_client)
        _objects = Objects(_client)
        _search = Search(_client)
        _views = Views(_client)
    return _client


def _ok(value: Any) -> Any:
    """Return a JSON-serializable success value for a tool result."""
    return value


def _err(exc: Exception) -> dict:
    """Turn an exception into a readable error result for the calling model."""
    return {"error": f"{type(exc).__name__}: {exc}"}


def _parse_json_arg(value: Any, what: str) -> Any:
    """Accept either a parsed object or a JSON string for an argument.

    MCP clients sometimes send a JSON string where an object is expected. This
    accepts both: if ``value`` is a string it is parsed as JSON, otherwise it is
    returned as is. ``what`` names the argument for clearer error messages.
    """
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{what} must be valid JSON: {exc}") from exc
    return value


# ----- curated tools ----------------------------------------------------------


@mcp.tool(
    description=(
        "Search objects in an Anytype space by full text and return a list of "
        "matching objects as dicts. This is the primary way to discover object "
        "ids before reading or editing them. It matches the query against object "
        "names and snippets. Returns a JSON list; each item has the relation "
        "keys you asked for (default: id, name, type, layout, snippet). Common "
        "mistakes: passing a type's object id where a unique key is expected (use "
        "the 'types' filter with unique keys like 'ot-note'); expecting fuzzy "
        "matching on ids (query is full text over name and snippet, and ids are "
        "matched only by the 'types' filter)."
    )
)
def search(
    query: Annotated[
        str,
        Field(description=(
            "Full-text query string. Matches object name and snippet. Example: "
            "'meeting notes'. Pass an empty string '' to match all objects "
            "(useful with types or limit)."
        )),
    ] = "",
    types: Annotated[
        Optional[list[str]],
        Field(description=(
            "Optional list of object type unique keys or type object ids to "
            "filter by. Example: ['ot-note', 'ot-page']. Null or empty means no "
            "type filter."
        )),
    ] = None,
    limit: Annotated[
        int,
        Field(description=(
            "Maximum number of results to return. Example: 20. Use 0 for the "
            "server default (no explicit limit)."
        )),
    ] = 0,
    keys: Annotated[
        Optional[list[str]],
        Field(description=(
            "Optional list of relation keys to return per object. Example: "
            "['id', 'name', 'type']. Null returns a useful default set "
            "(id, name, type, layout, snippet)."
        )),
    ] = None,
    space_id: Annotated[
        Optional[str],
        Field(description=(
            "The space to search in. Example: 'bafyspace...'. Null uses the "
            "ANYTYPE_SPACE_ID default."
        )),
    ] = None,
) -> Any:
    """Search objects and return a list of dicts. See the tool description."""
    try:
        c = _get_client()
        return _ok(c.search(query=query, types=types, space_id=space_id,
                            keys=keys, limit=limit))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool(
    description=(
        "Open one object by id and return its full view as a dict: its blocks "
        "(the content tree) and its details (properties/relations). Use this "
        "after 'search' to read an object's contents, to find block ids before "
        "editing or deleting blocks, or to read property values. Returns a JSON "
        "dict with an 'objectView' holding 'blocks' and 'details'. Common "
        "mistake: passing a name where an id is required (use 'search' first to "
        "get the id)."
    )
)
def get_object(
    object_id: Annotated[
        str,
        Field(description=(
            "The object id to open. Example: 'bafyreih...'. Get it from 'search'."
        )),
    ],
    space_id: Annotated[
        Optional[str],
        Field(description=(
            "The object's space. Example: 'bafyspace...'. Null uses the "
            "ANYTYPE_SPACE_ID default. Only strictly needed for date objects."
        )),
    ] = None,
) -> Any:
    """Open an object and return blocks and details. See the tool description."""
    try:
        c = _get_client()
        return _ok(c.get_object(object_id, space_id=space_id))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool(
    description=(
        "Create a new object of a given type and return its new object id as a "
        "string. The type is given by its unique key (for example 'ot-page', "
        "'ot-note', 'ot-task'). This unique key is the type's own identifier, "
        "which differs from a type object id. You can set initial "
        "properties with the 'details' dict (for example {'name': 'My page'}). "
        "Returns a dict {'object_id': '<new id>'}. Common mistakes: passing a "
        "type object id where a unique key is required; trying to add blocks to a "
        "Type or Set object later (that is restricted, edit those via "
        "set_details)."
    )
)
def create_object(
    type_unique_key: Annotated[
        str,
        Field(description=(
            "The object type's unique key. Examples: 'ot-page', 'ot-note', "
            "'ot-bookmark', or a custom type key. This is the type's own "
            "identifier, which differs from a type object id."
        )),
    ],
    details: Annotated[
        Optional[dict],
        Field(description=(
            "Optional initial properties as a JSON object of {relation_key: "
            "value}. Example: {'name': 'Project plan', 'done': false}. Values are "
            "plain JSON types (string, number, boolean, list, null). Null means "
            "no initial details."
        )),
    ] = None,
    template_id: Annotated[
        Optional[str],
        Field(description=(
            "Optional id of a template object to apply on creation. Example: "
            "'bafytemplate...'. Null means no template."
        )),
    ] = None,
    space_id: Annotated[
        Optional[str],
        Field(description=(
            "The space to create the object in. Null uses the ANYTYPE_SPACE_ID "
            "default."
        )),
    ] = None,
) -> Any:
    """Create an object and return its id. See the tool description."""
    try:
        _get_client()
        details = _parse_json_arg(details, "details") if details else None
        new_id = _objects.create(type_unique_key, details=details,
                                 template_id=template_id, space_id=space_id)
        return _ok({"object_id": new_id})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool(
    description=(
        "Add a block to an object's content tree and return the new block id. "
        "This adds a text block (paragraph, header, checkbox, quote, code, "
        "toggle, list item, callout) or, if you pass 'link_to', a link block "
        "pointing at another object. Returns a dict {'block_id': '<new id>'}. "
        "Common mistakes: adding blocks to a Type or Set object (the server "
        "returns 'restricted: Blocks'; edit those via set_details instead); "
        "using an unknown style name; placing relative to a block that does not "
        "exist."
    )
)
def add_block(
    object_id: Annotated[
        str,
        Field(description=(
            "The object (page) id to add the block into. Example: 'bafyrei...'."
        )),
    ],
    text: Annotated[
        Optional[str],
        Field(description=(
            "The text content for a text block. Example: 'Hello world'. Leave "
            "null when creating a link block (pass link_to instead)."
        )),
    ] = None,
    style: Annotated[
        str,
        Field(description=(
            "The text style for a text block. One of: 'Paragraph', 'Header1', "
            "'Header2', 'Header3', 'Quote', 'Code', 'Checkbox', 'Marked' "
            "(bullet), 'Numbered', 'Toggle', 'Callout'. Default 'Paragraph'. "
            "Ignored for link blocks."
        )),
    ] = "Paragraph",
    link_to: Annotated[
        Optional[str],
        Field(description=(
            "If set, create a link block pointing at this object id (a text "
            "block is the default). Example: 'bafyrei...'. Null creates a text "
            "block."
        )),
    ] = None,
    card: Annotated[
        bool,
        Field(description=(
            "When link_to is set, render the link as a card with a cover (an "
            "inline link is the default). Default false. Ignored for text "
            "blocks."
        )),
    ] = False,
    target_id: Annotated[
        Optional[str],
        Field(description=(
            "An existing block id to position the new block relative to. Get "
            "block ids from get_object. Null appends to the end of the object."
        )),
    ] = None,
    position: Annotated[
        str,
        Field(description=(
            "Where to insert relative to target_id. One of 'Top', 'Bottom', "
            "'Left', 'Right', 'Inner' (nest under the target). Default 'Bottom'."
        )),
    ] = "Bottom",
) -> Any:
    """Add a text or link block and return its id. See the tool description."""
    try:
        _get_client()
        if link_to is not None:
            block_id = _blocks.add_link(object_id, link_to, card=card,
                                       target_id=target_id, position=position)
        else:
            block_id = _blocks.add_text(object_id, text or "", style=style,
                                       target_id=target_id, position=position)
        return _ok({"block_id": block_id})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool(
    description=(
        "Replace the text content of an existing text block, and optionally "
        "change its style. Use get_object first to find the block id. Returns "
        "{'ok': true} on success. Common mistakes: passing an object id where a "
        "block id is required; using this on a non-text block (only text blocks "
        "have editable text)."
    )
)
def edit_block_text(
    object_id: Annotated[
        str,
        Field(description=(
            "The object (page) id the block lives in. Example: 'bafyrei...'."
        )),
    ],
    block_id: Annotated[
        str,
        Field(description=(
            "The id of the text block to edit. Get it from get_object's blocks. "
            "Example: '66ab...' ."
        )),
    ],
    text: Annotated[
        str,
        Field(description=(
            "The new text content for the block. Example: 'Updated text'."
        )),
    ],
    style: Annotated[
        Optional[str],
        Field(description=(
            "Optional new text style to also apply. One of 'Paragraph', "
            "'Header1', 'Header2', 'Header3', 'Quote', 'Code', 'Checkbox', "
            "'Marked', 'Numbered', 'Toggle', 'Callout'. Null keeps the current "
            "style."
        )),
    ] = None,
) -> Any:
    """Set a block's text (and optionally style). See the tool description."""
    try:
        _get_client()
        _blocks.set_text(object_id, block_id, text)
        if style:
            _blocks.set_style(object_id, block_id, style)
        return _ok({"ok": True})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool(
    description=(
        "Delete one or more blocks from an object's content tree. Use get_object "
        "first to find the block ids. Returns {'ok': true} on success. Common "
        "mistakes: passing an object id where block ids are required; deleting a parent "
        "block expecting children to survive (deleting a block deletes its "
        "subtree)."
    )
)
def delete_block(
    object_id: Annotated[
        str,
        Field(description=(
            "The object (page) id the blocks live in. Example: 'bafyrei...'."
        )),
    ],
    block_ids: Annotated[
        list[str],
        Field(description=(
            "A list of block ids to delete. Example: ['66ab...', '77cd...']. "
            "Get ids from get_object."
        )),
    ],
) -> Any:
    """Delete blocks from an object. See the tool description."""
    try:
        _get_client()
        _blocks.delete(object_id, list(block_ids))
        return _ok({"ok": True})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool(
    description=(
        "Set one or more detail (property/relation) values on an object. This is "
        "how you rename an object, set its description, mark a task done, set a "
        "tag, and so on. It is also the way to edit Type and Set objects, which "
        "do not allow block edits. Returns {'ok': true} on success. Pass null as "
        "a value to clear that relation. Common mistakes: supplying a relation's "
        "display name where its key is required (use the key, for example 'done', "
        "which is the internal key and can differ from the display name 'Done'); "
        "expecting this to add blocks (it only sets properties)."
    )
)
def set_details(
    object_id: Annotated[
        str,
        Field(description=(
            "The object id to edit. Example: 'bafyrei...'."
        )),
    ],
    details: Annotated[
        dict,
        Field(description=(
            "A JSON object of {relation_key: value} to set. Example: "
            "{'name': 'Renamed', 'done': true, 'description': 'hi'}. Values are "
            "plain JSON types (string, number, boolean, list, null). Use null to "
            "clear a value."
        )),
    ],
) -> Any:
    """Set object detail values. See the tool description."""
    try:
        _get_client()
        details = _parse_json_arg(details, "details")
        _objects.set_details(object_id, details)
        return _ok({"ok": True})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool(
    description=(
        "Set an already-uploaded image file as an object's cover image. The "
        "'file_object_id' is the id returned by the upload_image tool. This sets "
        "the object's coverType=1 and coverId details. Returns {'ok': true} on "
        "success. Common mistakes: passing an image URL here (upload it first "
        "with upload_image to get a file object id); confusing this with a "
        "gallery cover (a set or collection gallery takes its cover from a "
        "relation via set_view's coverRelationKey, a property that holds an "
        "image)."
    )
)
def set_cover(
    object_id: Annotated[
        str,
        Field(description=(
            "The object (page) id to give the cover to. Example: 'bafyrei...'."
        )),
    ],
    file_object_id: Annotated[
        str,
        Field(description=(
            "The id of an uploaded image file object, as returned by "
            "upload_image. Example: 'bafyfile...'."
        )),
    ],
    x: Annotated[
        float,
        Field(description=(
            "Horizontal focus offset of the cover, a float. Default 0.0."
        )),
    ] = 0.0,
    y: Annotated[
        float,
        Field(description=(
            "Vertical focus offset of the cover, a float. Default 0.0."
        )),
    ] = 0.0,
) -> Any:
    """Set an object's cover from an uploaded file. See the tool description."""
    try:
        _get_client()
        _objects.set_cover(object_id, file_object_id, x=x, y=y)
        return _ok({"ok": True})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool(
    description=(
        "Upload an image (by URL or local path) and return its new file object "
        "id, which you can then pass to set_cover or use as a relation value or "
        "block target. Returns {'file_object_id': '<id>'}. Reliability note: the "
        "Anytype desktop helper is sandboxed and may be unable to read arbitrary "
        "local paths (for example anything under /tmp) and can get HTTP 403 from "
        "hotlink-protected remote URLs. The most reliable route is to serve the "
        "file yourself over a local http://127.0.0.1 URL and pass that. Common "
        "mistakes: passing a path the sandbox cannot read; passing a hotlinked "
        "remote URL that returns 403."
    )
)
def upload_image(
    url_or_path: Annotated[
        str,
        Field(description=(
            "An http(s) URL or an absolute local path to the image. Treated as a "
            "URL if it starts with 'http://' or 'https://', otherwise as a local "
            "path. Prefer a local URL you serve yourself, for example "
            "'http://127.0.0.1:8000/cover.png'."
        )),
    ],
    space_id: Annotated[
        Optional[str],
        Field(description=(
            "The space to upload into. Null uses the ANYTYPE_SPACE_ID default."
        )),
    ] = None,
) -> Any:
    """Upload an image and return its file object id. See the tool description."""
    try:
        _get_client()
        file_id = _files.upload_image(url_or_path, space_id=space_id)
        return _ok({"file_object_id": file_id})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool(
    description=(
        "Change the display type of a set or collection view (its dataview "
        "block). For example switch a view to a Gallery to show image cards, or "
        "to a Table for rows and columns. Returns {'ok': true} on success. If "
        "you do not pass a view_id, the first view of the block is used. Common "
        "mistakes: passing a regular page id (this only works on set/collection "
        "objects that have a dataview block); expecting this to change which "
        "columns show (use set_visible_columns for that)."
    )
)
def set_view_type(
    set_id: Annotated[
        str,
        Field(description=(
            "The set or collection object id. Example: 'bafyset...'."
        )),
    ],
    view_type: Annotated[
        str,
        Field(description=(
            "The new view display type. One of 'Table', 'List', 'Gallery', "
            "'Kanban', 'Calendar', 'Graph'. Example: 'Gallery'."
        )),
    ],
    view_id: Annotated[
        Optional[str],
        Field(description=(
            "The id of the view to change. Null uses the first view of the "
            "block. Get view ids from get_object (the dataview block's 'views')."
        )),
    ] = None,
    space_id: Annotated[
        Optional[str],
        Field(description=(
            "The space the set lives in, used only when view_id is null to look "
            "up the first view. Null uses the ANYTYPE_SPACE_ID default."
        )),
    ] = None,
) -> Any:
    """Set a set/collection view's display type. See the tool description."""
    try:
        _get_client()
        _views.set_view_type(set_id, view_type, view_id=view_id,
                            space_id=space_id)
        return _ok({"ok": True})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool(
    description=(
        "Set exactly which relations show as columns in a set or collection "
        "view, and in what left-to-right order. This adds each relation as a "
        "visible column and orders them. Note: per-view visible columns require "
        "the dedicated relation-add and relation-sort calls, which this tool "
        "issues for you. Returns {'ok': true} on success. "
        "Common mistakes: trying to set columns via set_view_type (wrong tool); "
        "passing relations that are not in the dataview's relation pool (they "
        "are added as view columns, but if they are not in the block pool you "
        "may also need to add them there first via call_rpc with "
        "BlockDataviewRelationAdd)."
    )
)
def set_visible_columns(
    set_id: Annotated[
        str,
        Field(description=(
            "The set or collection object id. Example: 'bafyset...'."
        )),
    ],
    relation_keys: Annotated[
        list[str],
        Field(description=(
            "The ordered list of relation keys to show as columns, left to "
            "right. Example: ['name', 'tag', 'createdDate']."
        )),
    ],
    view_id: Annotated[
        Optional[str],
        Field(description=(
            "The id of the view to change. Null uses the first view of the "
            "block. Get view ids from get_object."
        )),
    ] = None,
    space_id: Annotated[
        Optional[str],
        Field(description=(
            "The space the set lives in, used only when view_id is null. Null "
            "uses the ANYTYPE_SPACE_ID default."
        )),
    ] = None,
) -> Any:
    """Set a view's visible columns in order. See the tool description."""
    try:
        _get_client()
        _views.set_visible_columns(set_id, list(relation_keys), view_id=view_id,
                                  space_id=space_id)
        return _ok({"ok": True})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool(
    description=(
        "Generic escape hatch: call ANY of the 332 Anytype gRPC ClientCommands "
        "methods by name with a JSON request body, and get the response back as "
        "a dict. Use this for operations the curated tools do not cover (for "
        "example BlockDataviewViewCreate, ObjectListExport, RelationListWithValue, "
        "ObjectDuplicate). The 'request' object's keys are the protobuf request "
        "fields in camelCase (for example contextId, spaceId, objectId). Enum "
        "fields usually accept their value name as a string. Returns the response "
        "as a JSON dict, or {'error': '...'} on failure. Common mistakes: wrong "
        "method name (it is case-sensitive, so write 'ObjectSearch' with that "
        "exact capitalization); wrong field names (use camelCase proto field "
        "names); "
        "forgetting required ids like contextId or spaceId. If you are unsure of "
        "the exact fields, prefer a curated tool."
    )
)
def call_rpc(
    method: Annotated[
        str,
        Field(description=(
            "The exact gRPC method name, case-sensitive. Examples: "
            "'ObjectSearch', 'BlockCreate', 'ObjectDuplicate', "
            "'BlockDataviewViewCreate', 'ObjectListExport'."
        )),
    ],
    request: Annotated[
        Optional[dict],
        Field(description=(
            "The request body as a JSON object whose keys are the protobuf "
            "request fields in camelCase. Example for ObjectSearch: "
            "{'spaceId': 'bafyspace...', 'fullText': 'notes', "
            "'keys': ['id', 'name'], 'limit': 10}. Enum fields accept their value "
            "name as a string. Null or {} sends an empty request."
        )),
    ] = None,
) -> Any:
    """Call any gRPC method by name with a JSON request. See the description."""
    try:
        from google.protobuf import json_format

        c = _get_client()
        req = c.request_type(method)()
        body = _parse_json_arg(request, "request") if request else None
        if body:
            json_format.ParseDict(body, req, ignore_unknown_fields=False)
        resp = c.call(method, req)
        return _ok(c.to_dict(resp))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


# ----- entry point ------------------------------------------------------------


def main() -> None:
    """Run the MCP server over the stdio transport.

    This is what a desktop MCP client launches: it starts the process and
    communicates over standard input and output. Configure the client to run
    ``python -m anytype_grpc.mcp_server`` (or this module's console script) with
    the ANYTYPE_TOKEN, ANYTYPE_GRPC_ADDR, and ANYTYPE_SPACE_ID environment
    variables set. See docs/mcp.md.
    """
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
