# MCP server: drive Anytype from an AI client

`anytype_grpc.mcp_server` is an MCP (Model Context Protocol) server that exposes
Anytype over its internal gRPC API as a set of tools. Any MCP client (Claude
Desktop, an IDE plugin, a custom agent) can connect to it and then search, read,
create, and edit objects, blocks, details, covers, and set/collection views, or
call any of the 332 gRPC methods directly.

It uses the official Python `mcp` SDK (FastMCP) and speaks over the stdio
transport, which is what desktop MCP clients launch and talk to.

## What you need first

1. A running Anytype desktop app (the server talks to its local gRPC service).
2. A full-scope session token. Mint one with:

   ```
   python -m anytype_grpc.auth
   ```

   or, if installed, `anytype-mint-token`. Copy the printed token.
3. The id of the space you want to work in (your default space). You can get it
   by searching, or from the desktop app.

## Install

The MCP extra pulls in the `mcp` SDK:

```
pip install "anytype-grpc[mcp]"
```

From a checkout (editable):

```
pip install -e ".[mcp]"
```

This installs a console script named `anytype-grpc-mcp` that runs the server
over stdio. You can also run it as a module:

```
python -m anytype_grpc.mcp_server
```

## Configure: environment variables

The server builds one Anytype client from the environment on the first tool
call:

| Variable           | Required | Meaning                                                                                   | Example               |
| ------------------ | -------- | ----------------------------------------------------------------------------------------- | --------------------- |
| `ANYTYPE_TOKEN`    | yes      | Full-scope session token. Needed for almost every read and write. Mint with `auth`.       | `eyJ...` (long token) |
| `ANYTYPE_SPACE_ID` | usually  | Default space id used when a tool does not get an explicit `space_id`.                     | `bafyspace...`        |
| `ANYTYPE_GRPC_ADDR`| no       | gRPC address `host:port`. If unset, the server auto-discovers the running app's port.      | `127.0.0.1:31009`     |

## Configure: Claude Desktop

Claude Desktop reads a JSON config file:

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- Linux: `~/.config/Claude/claude_desktop_config.json`

Add an entry under `mcpServers`. Use the console script (if it is on PATH) or a
full path to the Python interpreter of the environment where you installed the
package.

Using the console script:

```json
{
  "mcpServers": {
    "anytype": {
      "command": "anytype-grpc-mcp",
      "env": {
        "ANYTYPE_TOKEN": "PASTE_YOUR_TOKEN_HERE",
        "ANYTYPE_SPACE_ID": "bafyspace...",
        "ANYTYPE_GRPC_ADDR": "127.0.0.1:31009"
      }
    }
  }
}
```

Using an explicit interpreter and the module form (more robust if PATH is not
set up for GUI apps):

```json
{
  "mcpServers": {
    "anytype": {
      "command": "/absolute/path/to/.venv/bin/python",
      "args": ["-m", "anytype_grpc.mcp_server"],
      "env": {
        "ANYTYPE_TOKEN": "PASTE_YOUR_TOKEN_HERE",
        "ANYTYPE_SPACE_ID": "bafyspace...",
        "ANYTYPE_GRPC_ADDR": "127.0.0.1:31009"
      }
    }
  }
}
```

After editing the config, restart Claude Desktop. The Anytype tools then appear
in the client.

## Configure: a generic MCP client

Any MCP client that launches a stdio server uses the same shape: a command, its
arguments, and an environment. The generic JSON is:

```json
{
  "mcpServers": {
    "anytype": {
      "command": "python",
      "args": ["-m", "anytype_grpc.mcp_server"],
      "env": {
        "ANYTYPE_TOKEN": "PASTE_YOUR_TOKEN_HERE",
        "ANYTYPE_SPACE_ID": "bafyspace...",
        "ANYTYPE_GRPC_ADDR": "127.0.0.1:31009"
      }
    }
  }
}
```

If your client launches MCP servers differently, the only requirements are: run
`python -m anytype_grpc.mcp_server` (or `anytype-grpc-mcp`), over stdio, with the
three environment variables set.

## How results come back

Every tool returns plain JSON (a dict, a list, or a string). Read tools
(`search`, `get_object`) return the data. Write tools return a small confirmation
like `{"ok": true}` or the new id, for example `{"object_id": "bafyrei..."}`.
Failures are returned as `{"error": "RpcError: ..."}` so the call stays alive and
the model gets a readable message.

Key concepts to pass correctly:

- An object id looks like `bafyrei...`. Get ids from `search`.
- An object type is identified by a unique key like `ot-page` or `ot-note`. This
  key is what a type is addressed by, which can differ from a type object id.
- A block id is found by reading an object with `get_object` (look in its
  blocks).
- You cannot add blocks to a Type or Set object; edit those with `set_details`.

## Tools

| Tool                  | Parameters                                                                                            | What it does                                                                  |
| --------------------- | ----------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| `search`              | `query` (str), `types` (list[str]?), `limit` (int), `keys` (list[str]?), `space_id` (str?)            | Full-text search; returns a list of matching objects as dicts.                |
| `get_object`          | `object_id` (str), `space_id` (str?)                                                                  | Open an object; returns its blocks and details as a dict.                      |
| `create_object`       | `type_unique_key` (str), `details` (dict?), `template_id` (str?), `space_id` (str?)                   | Create an object of a type; returns `{object_id}`.                            |
| `add_block`           | `object_id` (str), `text` (str?), `style` (str), `link_to` (str?), `card` (bool), `target_id` (str?), `position` (str) | Add a text or link block; returns `{block_id}`.            |
| `edit_block_text`     | `object_id` (str), `block_id` (str), `text` (str), `style` (str?)                                     | Replace a text block's content (and optionally its style).                    |
| `delete_block`        | `object_id` (str), `block_ids` (list[str])                                                            | Delete one or more blocks from an object.                                     |
| `set_details`         | `object_id` (str), `details` (dict)                                                                   | Set property/relation values (rename, mark done, edit Types/Sets).            |
| `set_cover`           | `object_id` (str), `file_object_id` (str), `x` (float), `y` (float)                                   | Set an uploaded image file as an object's cover.                              |
| `upload_image`        | `url_or_path` (str), `space_id` (str?)                                                                | Upload an image; returns `{file_object_id}`.                                  |
| `set_view_type`       | `set_id` (str), `view_type` (str), `view_id` (str?), `space_id` (str?)                                | Change a set/collection view type (Gallery, Table, List, Kanban, ...).        |
| `set_visible_columns` | `set_id` (str), `relation_keys` (list[str]), `view_id` (str?), `space_id` (str?)                      | Set which relations show as columns in a view, in order.                      |
| `call_rpc`            | `method` (str), `request` (dict?)                                                                     | Generic: call any of the 332 gRPC methods by name with a JSON request.        |

A `?` marks an optional parameter (it may be omitted or null).

### Example calls

These are the JSON arguments an MCP client sends for each tool. The exact
envelope depends on the client; the argument objects below are what matters.

`search`: find notes mentioning "budget".

```json
{ "query": "budget", "types": ["ot-note"], "limit": 10 }
```

`get_object`: read an object and its blocks.

```json
{ "object_id": "bafyrei..." }
```

`create_object`: make a new page named "Project plan".

```json
{ "type_unique_key": "ot-page", "details": { "name": "Project plan" } }
```

`add_block`: add a header to a page.

```json
{ "object_id": "bafyrei...", "text": "Overview", "style": "Header2" }
```

`add_block`: add a link card to another object.

```json
{ "object_id": "bafyrei...", "link_to": "bafyother...", "card": true }
```

`edit_block_text`: change a block's text and make it a quote.

```json
{ "object_id": "bafyrei...", "block_id": "66ab...", "text": "New text", "style": "Quote" }
```

`delete_block`: remove two blocks.

```json
{ "object_id": "bafyrei...", "block_ids": ["66ab...", "77cd..."] }
```

`set_details`: rename and mark a task done.

```json
{ "object_id": "bafyrei...", "details": { "name": "Renamed", "done": true } }
```

`upload_image`: upload from a local server, then set it as a cover.

```json
{ "url_or_path": "http://127.0.0.1:8000/cover.png" }
```

```json
{ "object_id": "bafyrei...", "file_object_id": "bafyfile..." }
```

`set_view_type`: switch the first view of a set to a Gallery.

```json
{ "set_id": "bafyset...", "view_type": "Gallery" }
```

`set_visible_columns`: choose the columns of a view.

```json
{ "set_id": "bafyset...", "relation_keys": ["name", "tag", "createdDate"] }
```

`call_rpc`: duplicate an object (no curated tool for this).

```json
{ "method": "ObjectDuplicate", "request": { "contextId": "bafyrei..." } }
```

`call_rpc`: run a raw search with the full request shape.

```json
{
  "method": "ObjectSearch",
  "request": {
    "spaceId": "bafyspace...",
    "fullText": "notes",
    "keys": ["id", "name"],
    "limit": 10
  }
}
```

## The escape hatch: call_rpc

`call_rpc` reaches every operation the curated tools do not wrap. Its `request`
keys are the protobuf request fields in camelCase (for example `contextId`,
`spaceId`, `objectId`), and enum fields usually accept their value name as a
string. The response comes back as a JSON dict. The full method list is the 332
methods of the `ClientCommands` gRPC service (the same calls the desktop app
makes). When you are unsure of the exact fields, prefer a curated tool.

## Troubleshooting

- "no space_id given and no default space set": set `ANYTYPE_SPACE_ID`, or pass
  `space_id` to the tool.
- Auth or permission errors on writes: your `ANYTYPE_TOKEN` is missing or
  expired. Mint a new one with `python -m anytype_grpc.auth`.
- Connection refused or no response: the Anytype desktop app is not running, or
  `ANYTYPE_GRPC_ADDR` points at the wrong port. Leave the address unset to let
  the server auto-discover the port, or set it to the app's actual gRPC port.
- "restricted: Blocks" when adding a block: the target is a Type or Set object.
  Use `set_details` for those (`add_block` works on Page objects).
- Image upload fails for a local path or a remote URL: the desktop helper is
  sandboxed (it may not read `/tmp`) and hotlinked URLs can return 403. Serve the
  file over `http://127.0.0.1` and pass that URL to `upload_image`.
```
