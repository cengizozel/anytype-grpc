# anytype-grpc

Edit [Anytype](https://anytype.io) blocks, layouts, and views from Python or MCP, over its internal gRPC API.

## Why this exists

Every other Anytype library wraps the official **Local HTTP API**, which covers search, object creation, properties, and markdown. The block tree, layouts, set and query views, and covers live a layer deeper.

This library talks to that layer: the internal gRPC service (`anytype-heart`'s `ClientCommands`) that the Anytype desktop app uses for every action. It can do everything the desktop UI does, programmatically:

- create, move, delete, and restyle any block (text, headers, toggles, checkboxes, code, tables, links)
- build column and grid layouts
- create and edit sets and queries, switch view types (table, gallery, list, kanban, calendar), and choose which properties show and which relation provides the cover
- set object covers and icons, upload files and images
- create and edit types, relations, and templates
- search, and read the full block tree of any object

All 332 RPC methods are reachable. The common, fiddly ones have ergonomic helpers.

## How it works

The desktop app runs a local helper process that serves gRPC on a loopback port. This library auto-discovers that port, authenticates with a session token derived from your account, and speaks the same protocol the UI speaks. The real Anytype engine does all the work, and this library is a thin remote control over it.

## Install

This is not on PyPI yet, so install it from source.

Straight from GitHub:

```bash
pip install "anytype-grpc[mcp] @ git+https://github.com/cengizozel/anytype-grpc.git"
```

Or clone and install editable, which is handy for reading or changing the code:

```bash
git clone https://github.com/cengizozel/anytype-grpc.git
cd anytype-grpc
pip install -e ".[mcp]"
```

Drop the `[mcp]` extra if you only want the client without the MCP server. Requires the Anytype desktop app to be running on the same machine.

## Authenticate

The full gRPC surface needs a session token derived from your account. Mint one from your recovery phrase (the words you saved when you set up Anytype):

```bash
python -m anytype_grpc.auth
```

It reads the phrase from hidden input, never writes it to disk, and prints a token. Put that token in your environment:

```bash
export ANYTYPE_TOKEN="<the token>"
```

The token grants complete access to your local vault. Treat it like a password and never commit it.

## Quick start

```python
from anytype_grpc import Anytype

at = Anytype()                       # auto-discovers the port, reads ANYTYPE_TOKEN
print(at.app_version())              # works without a token

space = "your-space-id"
results = at.search("project", space_id=space)   # full-text search
page = results[0]["id"]

# read the whole object (blocks + details)
obj = at.objects.show(page)

# edit the block tree (namespaces group the full API by domain)
at.blocks.add_header(page, "A new heading", level=2)
at.blocks.add_text(page, "some body text")

# set a property
at.objects.set_details(page, {"description": "edited by anytype-grpc"})

# make a set, turn it into a gallery, choose its columns
new_set = at.objects.create_set([type_id], details={"name": "My gallery"})
at.views.set_view_type(new_set, "Gallery")
at.views.set_visible_columns(new_set, ["name", "status"])
```

## Two layers

**1. Ergonomic namespaces** group the full helper API by domain. Each is reached on the client:

- `at.blocks` blocks: text, headers, checkboxes, toggles, code, links, files, tables, grids
- `at.objects` objects: create, show, details, covers, icons, archive, import, export
- `at.views` set and query views: type, columns, covers, filters, sorts
- `at.files` files and images: upload, download, offload, usage
- `at.types` types, relations (properties), options, templates
- `at.spaces` spaces and account: list, create, info, invites, members
- `at.query` advanced search and live subscriptions

A few of the most common operations also have top-level shortcuts (`at.search`, `at.get_object`, `at.add_block`). See the [docs](docs/) for every method.

**2. Generic access to every method.** Anything the app can do is reachable, even if there is no hand-written helper:

```python
# call any of the 332 RPC methods by name
resp = at.call("BlockListSetAlign", context_id=page, blockIds=[bid], align=1)

# build a request to fill in by hand when a method needs nested messages
req = at.new_request("ObjectSearch")
req.spaceId = space
req.fullText = "notes"
resp = at.call("ObjectSearch", req)

# resolve the request type for any method
print(at.request_type("ObjectCreateSet").DESCRIPTOR.full_name)
```

## MCP server

This package also ships an MCP server, so AI assistants can drive Anytype through the same capabilities. It is a thin wrapper over the library. See [docs/mcp.md](docs/mcp.md) for setup and the full tool reference.

```bash
anytype-grpc-mcp
```

## Security

- Your recovery phrase and the session token grant full access to your local vault. Never commit them. Keep them in environment variables or a gitignored `.env`.
- The gRPC service listens only on loopback (`127.0.0.1`).
- Keep the desktop app updated.

## Versioning

The internal gRPC API is private and can change between Anytype versions. The vendored protos are pinned to a specific Anytype version (see `protos/`). If you upgrade the desktop app, regenerate the bindings with `scripts/gen_protos.sh` against the matching `anytype-heart` tag.

## License

MIT. The vendored protos are from [anyproto/anytype-heart](https://github.com/anyproto/anytype-heart) (MIT).
