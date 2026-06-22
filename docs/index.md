# anytype-grpc documentation

`anytype-grpc` is a full-control Python client for Anytype, built on the same
internal gRPC API (`anytype-heart`'s `ClientCommands`) that the Anytype desktop
app uses. It can do everything the desktop UI can do: edit the block tree, build
layouts, create and reshape sets and views, set covers and icons, upload files,
and create types, relations, and templates. All 332 RPC methods are reachable,
and the common, fiddly ones have ergonomic helpers.

If you are new, read the guides in this order: auth, then quickstart, then the
domain guide for whatever you are working on.

## Table of contents

### Getting started

- [quickstart.md](quickstart.md): install the package, mint a token, connect,
  and ten worked examples (search, read, create, edit blocks, build a grid,
  make a set, switch it to a gallery, upload an image cover, and the generic
  `call()`). Start here once you have a token.
- [auth.md](auth.md): the difference between the restricted Local API key and a
  full session token, why the full token is needed, how to mint one safely,
  where to put it, and the security implications. Read this before quickstart.

### Domain guides

Each guide documents one domain. Every domain is a namespace on a connected
`Anytype` client, so you call its snake_case methods directly, for example
`at.blocks.add_header(...)` or `at.views.set_view_type(...)`. Every method has an
example. The namespaces are: `at.blocks`, `at.objects`, `at.views`, `at.files`,
`at.types`, `at.spaces`, and `at.query` (advanced search).

- [objects.md](objects.md): the `Objects` class. The object lifecycle: create
  (plain object, set, bookmark, from a URL), open and close, edit details
  (properties), change layout, type, and source, duplicate, archive, favorite,
  delete, convert to a set or collection, import, export, the object graph, and
  the cover and icon helpers.
- [blocks.md](blocks.md): the `Blocks` class. Build and edit an object's content
  tree: text, headers, checkboxes, toggles, code, lists, dividers, links, files,
  bookmarks, latex and embeds, and tables. Move, duplicate, copy, paste, split,
  and merge blocks. High-level helpers for a toggle with children and a
  horizontal card grid.
- [views.md](views.md): the `Views` class. Edit the views of a set or
  collection: create and delete views, switch a view's type (table, list,
  gallery, kanban, calendar, graph), choose which relations show as columns and
  in what order, add filters and sorts, and set a gallery cover relation.
- [search.md](search.md): the `Search` class. One-shot search with filters and
  sorts, live subscriptions, relation grouping (for kanban columns), and reverse
  lookup of where a value is referenced.
- [types.md](types.md): the `Types` class. Create and configure object types,
  relations (properties), options (tags and statuses), and templates.
- [spaces.md](spaces.md): the `Spaces` class. List spaces, read and rename space
  info, set a homepage, create spaces, generate and accept invites, manage
  members, and export a whole space.
- [files.md](files.md): the `Files` class. Upload files and images (by URL or
  local path), upload an image and set it as a cover in one call, download,
  offload to free local disk, and read storage usage.

### Reference

- [capabilities.md](capabilities.md): the complete catalog of all 332 RPC methods,
  grouped by domain, marking which have an ergonomic helper. Proof that the whole
  Anytype surface is reachable, and a map for finding the right method to call.
- [gotchas.md](gotchas.md): the non-obvious behaviors and limits of the internal
  gRPC API (view columns, the grid technique, blocks restricted on types and sets,
  cover handling, the sandboxed file upload, and more), each with the correct
  approach. Read this when something does not behave as expected.

### Other

- [mcp.md](mcp.md): the bundled MCP server, which exposes these capabilities to
  AI assistants as tools. Setup and the full tool reference.

## How the two layers fit together

Every domain class is a thin wrapper over the generic client. Anything a guide
does with a helper, you can also do by hand with the generic API:

```python
import anytype_grpc
at = anytype_grpc.Anytype()        # auto-discovers the port, reads ANYTYPE_TOKEN

# call any of the 332 RPC methods by name
resp = at.call("AppGetVersion")

# build a request to fill in for methods with no helper
req = at.new_request("ObjectSearch")
req.spaceId = at.default_space
resp = at.call("ObjectSearch", req)
```

See [quickstart.md](quickstart.md) for the generic `call()` in context.
