# Quickstart

This guide gets you from nothing to working code: install the package, mint a
session token, connect, and run ten worked examples. Each example is a complete,
runnable snippet. For the details of authentication, read [auth.md](auth.md)
first. For each domain in depth, see the domain guides linked from
[index.md](index.md).

## Requirements

- The Anytype desktop app installed and running on the same machine. The library
  talks to the app's local gRPC service, so the app must be open.
- Python 3.9 or newer.

## Install

```bash
pip install anytype-grpc          # the core client
pip install "anytype-grpc[mcp]"   # also install the bundled MCP server
```

This installs the `anytype_grpc` package and the `anytype-mint-token` command.

## Mint a token

The restricted Local API key is not enough for the full gRPC surface. You need a
session token derived from your account. Mint one from your recovery phrase (the
words you saved when you first set up Anytype):

```bash
python -m anytype_grpc.auth
```

It reads the phrase from hidden input, never writes it to disk, and prints a
token to stdout. Copy that token and put it in your environment:

```bash
export ANYTYPE_TOKEN="<the token you got>"
```

You can also set a default space so you do not pass `space_id` everywhere:

```bash
export ANYTYPE_SPACE_ID="<your space id>"
```

The token grants full control of your local vault. Treat it like a password and
never commit it. See [auth.md](auth.md) for why this token is needed and the
security implications.

## Connect

```python
import anytype_grpc

# Reads ANYTYPE_TOKEN and ANYTYPE_SPACE_ID from the environment, and
# auto-discovers the running app's gRPC port.
at = anytype_grpc.Anytype()

print(at.app_version())            # works even without a token
print(at.default_space)            # the space id from ANYTYPE_SPACE_ID
```

You can also pass everything explicitly instead of using the environment:

```python
at = anytype_grpc.Anytype(
    token="your-session-token",
    space_id="your-space-id",
    address="127.0.0.1:31007",     # optional; auto-discovered if omitted
)
```

If a call fails, the client raises `anytype_grpc.RpcError` with the method name,
the numeric error code, and the server's description. Catch it like any
exception:

```python
from anytype_grpc import RpcError
try:
    at.get_object("does-not-exist")
except RpcError as exc:
    print(exc.method, exc.code, exc.description)
```

In the examples below, `space` is your space id. If you set `ANYTYPE_SPACE_ID`,
you can leave `space_id` off and the helpers use the default.

```python
space = at.default_space            # or "your-space-id"
```

## Example 1: search

Find objects by full text. Returns a list of plain dicts.

```python
results = at.search("project notes", space_id=space, limit=10)
for r in results:
    print(r.get("name"), r.get("id"))
```

For filters and sorts, use the `Search` class:

```python
s = at.query

rows = s.search(
    space,
    types=["ot-note"],                         # only notes
    filters=[s.filter("name", "Like", "report")],
    sorts=[s.sort("lastModifiedDate", "Desc")],
    keys=["id", "name"],
    limit=20,
)
for r in rows:
    print(r.get("name"), r.get("id"))
```

## Example 2: read an object

Open an object and read its blocks and details as a dict.

```python
results = at.search("", space_id=space, limit=1)
object_id = results[0]["id"]

obj = at.get_object(object_id, space_id=space)
# The view holds the details (properties) and the block tree.
view = obj.get("objectView", {})
print("details:", view.get("details"))
print("block count:", len(view.get("blocks", [])))
```

## Example 3: create an object

Create a new page with a name. The first argument is the type's unique key (a
string like `ot-page` or `ot-note`), not a type object id.

```python
objects = at.objects

page_id = objects.create("ot-page", details={"name": "My new page"})
print("created:", page_id)

# Set or change properties later:
objects.set_details(page_id, {"description": "made by anytype-grpc"})
```

## Example 4: edit blocks

Add to and edit an object's content tree with the `Blocks` class.

```python
blocks = at.blocks

# Add a header, then a paragraph under it.
h = blocks.add_header(page_id, "Section one", level=2)
p = blocks.add_text(page_id, "Some body text.", target_id=h, position="Bottom")

# Restyle and re-text an existing block.
blocks.set_style(page_id, p, "Quote")
blocks.set_text(page_id, p, "An edited quote.")

# A checkbox and a bullet list item.
blocks.add_checkbox(page_id, "Buy milk", checked=False)
blocks.add_marked(page_id, "First bullet")

# Make a bold range on the paragraph (characters 0..3).
blocks.set_mark(page_id, p, "Bold", 0, 3)
```

Note: you cannot add blocks to a Type object or a Set object. The server replies
"restricted: Blocks". Edit those through details instead (Example 6 onward).

## Example 5: build a horizontal grid

Anytype has no single grid call. You create cards as a vertical stack, then move
them into columns. The `grid` helper does the moves for you. Cards are usually
link blocks rendered as cards.

```python
# Suppose you have some object ids to show as cards.
targets = [r["id"] for r in at.search("", space_id=space, limit=6)]

card_ids = [blocks.add_link(page_id, oid, card=True) for oid in targets]
rows = blocks.grid(page_id, card_ids, per_row=3)
print("laid out rows:", rows)
```

How it works under the hood: for each row, the second card is moved to the
"Right" of the first card, which makes Anytype wrap them in a Row layout with two
Column blocks. Each later card is moved Right of the previous card, and the
server resolves that to the enclosing column. You do not have to manage the
column blocks yourself.

## Example 6: create a set

A Set is a live query over a space. Its source is a list of object type ids (not
unique keys, the actual type object ids) that decide which objects appear in it.

```python
types = at.types

# Find the object id of the type you want the set to collect (for example notes).
type_rows = types.list_types(space)        # returns dicts with id and uniqueKey
note_type_id = next(t["id"] for t in type_rows
                    if t.get("uniqueKey") == "ot-note")

# Create a set that auto-collects all notes.
set_id = objects.create_set([note_type_id], details={"name": "All notes"})
print("set:", set_id)
```

## Example 7: switch a set to a gallery with chosen columns and a cover

A set or collection holds one dataview block (its id is almost always the literal
string `"dataview"`). Use the `Views` class to change the view's type, choose
which relations show, and set the gallery cover. Important: a gallery cover comes
from a relation (a property that holds an image), not from a file id directly.

```python
views = at.views

# 1. Switch the first view to a gallery.
views.set_view_type(set_id, "Gallery")

# 2. Choose which relations show as card fields, in order.
views.add_relation(set_id, ["tag", "picture"])     # add to the block pool first
views.set_visible_columns(set_id, ["name", "tag"]) # then show these columns

# 3. Use a relation that holds an image as the card cover.
views.set_gallery_cover(set_id, "picture")
```

`set_visible_columns` adds and orders the columns you list; it does not remove
columns already present. The relations you show should also be in the block
relation pool, which `add_relation` handles.

## Example 8: upload an image and set it as an object cover

An object's image cover is two details: `coverType=1` and `coverId=<file object
id>`. The `Files` class can upload an image and set the cover in one call. The
reliable upload route is to serve the file over `http://127.0.0.1` and pass that
URL, because the desktop helper is sandboxed and may not read local paths like
`/tmp` or fetch hotlink-protected remote URLs.

```python
files = at.files

# Serve the image yourself first, in a separate terminal:
#   python -m http.server 8000 --directory /path/to/images --bind 127.0.0.1
# Then upload it and set it as the page cover, in one call:
file_id = files.upload_cover(page_id, "http://127.0.0.1:8000/banner.jpg")
print("cover file object:", file_id)
```

If you only want the uploaded file id (to use as a relation value, a block
target, or to set the cover yourself later):

```python
file_id = files.upload(url="http://127.0.0.1:8000/photo.jpg", kind="Image")
objects.set_cover(page_id, file_id)         # the explicit two-step form
```

## Example 9: set an emoji or image icon

The icon is a separate detail from the cover. Use the `Objects` helper.

```python
objects.set_icon(page_id, emoji="rocket")           # an emoji icon
# or, with an uploaded image file object:
objects.set_icon(page_id, file_object_id=file_id)   # an image icon
```

## Example 10: the generic call()

Every one of the 332 RPC methods is reachable by name, even ones with no
hand-written helper. This is the escape hatch when a helper does not exist yet.

```python
# Simple flat-field call: pass fields as keywords.
resp = at.call("AppGetVersion")
print(resp.version)

# Build a request when a method needs nested messages you set by hand.
req = at.new_request("ObjectSearch")
req.spaceId = space
req.fullText = "notes"
req.keys.append("id")
req.keys.append("name")
resp = at.call("ObjectSearch", req)
for rec in resp.records:
    print(at.to_dict(rec))

# Get a response straight back as a dict.
d = at.call_dict("AppGetVersion")
print(d)

# Inspect a request type to learn its fields and nested message paths.
rt = at.request_type("BlockCreate")
print(rt.DESCRIPTOR.full_name)              # anytype.Rpc.Block.Create.Request

# Set an enum field by name (the by-number pattern the helpers use):
req = at.new_request("BlockCreate")
req.position = (req.DESCRIPTOR.fields_by_name["position"]
                .enum_type.values_by_name["Inner"].number)
```

By default `call()` raises `RpcError` on a non-zero server error code. Pass
`check=False` to get the raw response back even on error, and inspect
`resp.error.code` and `resp.error.description` yourself.

## Where to go next

- [auth.md](auth.md): tokens, scope, and security in depth.
- [index.md](index.md): the full table of contents.
- The domain guides (objects, blocks, views, search, types, spaces, files) for
  the complete method reference of each area.
