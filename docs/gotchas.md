# gotchas: non-obvious behavior and limits of the internal gRPC API

This is a field guide to the traps in Anytype's internal gRPC API (the
`ClientCommands` service that the desktop app itself uses). The API is powerful
but it is not documented for outside use, and several operations behave in ways
you would not guess from the proto field names. Each item below states the trap,
why it happens, and the correct approach with a runnable snippet.

All snippets assume you have a client:

```python
import anytype_grpc
at = anytype_grpc.Anytype()      # auto-discovers the port, reads ANYTYPE_TOKEN
```

Everything here can be checked offline by building the request messages (no
running app required), which is how the field names and enum values in this
document were confirmed.

---

## 1. View columns: use the ViewRelation calls (ViewUpdate changes view meta only)

The trap: you want to change which relations show as columns in one view of a
set or collection, so you reach for `BlockDataviewViewUpdate` and set its
`view.relations`. Nothing changes.

Why: the `view` message you pass to `BlockDataviewViewUpdate` does carry a
`relations` field (the proto lets you set it), but the server ignores it on
update. `BlockDataviewViewUpdate` only applies view meta: `type`, `name`,
`cardSize`, `coverRelationKey`, `coverFit`, `hideIcon`, `groupRelationKey`,
`pageLimit`, `defaultTemplateId`, `defaultObjectTypeId`, and similar. Per-view
visible columns are a separate set of RPCs.

The correct approach: add, remove, and order columns with the dedicated calls.

- `BlockDataviewViewRelationAdd` adds one column. Its request has
  `contextId`, `blockId`, `viewId`, and a single nested `relation` message
  (note: the field is singular `relation`). The relation message has
  `key` and `isVisible` (plus `width`, `align`, and date-format fields).
- `BlockDataviewViewRelationSort` sets left-to-right order. It takes a
  repeated `relationKeys` (the full ordered list of keys).
- `BlockDataviewViewRelationRemove` removes columns. It also takes repeated
  `relationKeys`.

```python
# Add "tag" as a visible column to one view.
req = at.new_request("BlockDataviewViewRelationAdd")
req.contextId = "bafy_set_id"
req.blockId = "dataview"          # the dataview block id, usually this literal
req.viewId = "view_id_1"
req.relation.key = "tag"
req.relation.isVisible = True
at.call("BlockDataviewViewRelationAdd", req)

# Order the columns left to right.
sort = at.new_request("BlockDataviewViewRelationSort")
sort.contextId = "bafy_set_id"
sort.blockId = "dataview"
sort.viewId = "view_id_1"
sort.relationKeys.extend(["name", "tag", "createdDate"])
at.call("BlockDataviewViewRelationSort", sort)
```

The `Views` helper module wraps all of this: `add_view_relation`,
`remove_view_relation`, `sort_view_relations`, and the high-level
`set_visible_columns`. Prefer those.

---

## 2. Horizontal card grids: move each card Right of the previous COLUMN block

The trap: to lay cards out side by side you create the cards, then move card 2
to the "Right" of card 1, card 3 to the "Right" of card 2, and so on. After the
first move it stops behaving and the columns nest or stack wrong.

Why: when you move a block to the "Right" of another block, Anytype wraps the
pair in a horizontal Row layout, and each side becomes a Column layout block
(`Block.Content.Layout.Style` value `Column = 1`). The card you moved is now a
child inside a Column block. To add a third column you must position relative to
that Column block. Positioning relative to the card again puts the new block
inside the existing column.

The correct approach: move the second card to the "Right" of the first card
(this creates the row and two columns). For every later card, move it to the
"Right" of the PREVIOUS COLUMN block (the layout block whose style is `Column`,
which wraps the previous card). Read the object after each move (`at.get_object(page)`)
to find the new Column block ids, or track them from the move responses.

```python
def move_right(page, block_ids, drop_target_id):
    req = at.new_request("BlockListMoveToExistingObject")
    req.contextId = page
    req.targetContextId = page
    req.dropTargetId = drop_target_id     # for card 2: the first card;
                                          # for later cards: the previous Column
    req.position = req.DESCRIPTOR.fields_by_name["position"] \
        .enum_type.values_by_name["Right"].number
    req.blockIds.extend(block_ids)
    return at.call("BlockListMoveToExistingObject", req)
```

`Anytype.move_blocks(context_id, block_ids, drop_target_id, position="Right")`
wraps the call; the discipline of choosing the Column block as the drop target
is on you.

---

## 3. "Inner" position nests blocks under the target

The trap: you want blocks to become children of another block (for example, the
body of a toggle), but "Bottom" or "Top" just place them as siblings.

Why: child placement is a distinct position value. The `position` enum is
`None, Top, Bottom, Left, Right, Inner, Replace, InnerFirst`. "Inner" makes the
moved blocks children of the target, while "Bottom" and "Top" keep them siblings.
"Inner" appends them inside while preserving the order of `blockIds`. "InnerFirst"
inserts them as the first children.

The correct approach: move with position "Inner" and the toggle (or other
container) block as the drop target.

```python
at.move_blocks("bafy_page_id",
               ["child_block_a", "child_block_b"],
               drop_target_id="toggle_block_id",
               position="Inner")
```

---

## 4. Blocks are restricted on Type and Set objects

The trap: you open a Type object or a Set object and try to add a text or link
block with `BlockCreate`. The server returns an error like `restricted: Blocks`.

Why: Type and Set objects do not have a free-form block tree the way a Page
does. A Type defines a schema (its layout, relations, default template), and a
Set/Collection is backed by a dataview. Block editing is restricted on them by
design.

The correct approach: change them through their details (relation values) and,
for sets, through the dataview view RPCs. Do not try to write blocks.

```python
# Describe a Type by setting its details (the description relation holds the text).
at.set_details("bafy_type_id", {"description": "Projects we are tracking."})
```

If you genuinely need rich block content, put it on a normal Page object and
link to it.

---

## 5. Two different "covers": the object cover lives in details, the gallery cover in a relation

The trap: you set `coverRelationKey` hoping to give an object a banner image, or
you set `coverType`/`coverId` hoping to give a gallery its card images. Neither
does what you expected.

Why: there are two unrelated cover concepts.

- An object's own cover (the banner at the top of a Page) is stored in the
  object's details: `coverType` and `coverId`. For an uploaded image file, set
  `coverType = 1` and `coverId = <file object id from FileUpload>`. You can also
  set `coverX` and `coverY` for the focal point.
- A gallery view's card cover comes from a relation. Each card pulls its cover
  from a relation on the object it represents. You set the view's
  `coverRelationKey` (for example `"picture"` or `"cover"`) via
  `BlockDataviewViewUpdate`, and optionally `coverFit`. The actual image then
  comes from whatever each object has in that relation.

The correct approach: pick the right one.

```python
# Object banner cover from an uploaded file id.
file_id = at.upload_file(url="http://127.0.0.1:8000/banner.jpg")
at.set_cover("bafy_page_id", file_id)        # sets coverType=1, coverId=file_id

# Gallery card cover from a relation (a relation key supplies the image).
req = at.new_request("BlockDataviewViewUpdate")
req.contextId = "bafy_set_id"
req.blockId = "dataview"
req.viewId = "view_id_1"
req.view.id = "view_id_1"
req.view.coverRelationKey = "picture"
req.view.coverFit = True
at.call("BlockDataviewViewUpdate", req)      # or Views.set_gallery_cover(...)
```

---

## 6. FileUpload is sandboxed: serve over http://127.0.0.1

The trap: you call `FileUpload` with `localPath` pointing at a file in `/tmp`,
or with a `url` to a CDN image, and it fails: the local path is not readable, or
the URL returns 403.

Why: the desktop helper process that performs the upload runs sandboxed. It
cannot read arbitrary local paths (notably `/tmp`), and when it fetches a URL it
sends its own headers, so hotlink-protected or referer-checked CDNs reject it
with 403.

The correct approach: serve the file from a tiny local HTTP server on
`127.0.0.1` and pass that URL. The helper can always fetch loopback, and there
is no referer or hotlink check to fail.

```python
# Terminal: serve the directory holding your file.
#   cd /path/to/files && python -m http.server 8000
file_id = at.upload_file(url="http://127.0.0.1:8000/banner.jpg", kind="Image")
```

The `FileUpload` request fields are `spaceId`, `url`, `localPath`, `type`
(the kind enum: `Image`, `File`, `Video`, `Audio`, `PDF`, `None`), and a few
options. `Anytype.upload_file` sets these for you and returns the new file
object id.

---

## 7. Markdown import/patch flattens card layouts

The trap: you carefully built a page with side-by-side cards and column layouts,
then you run a markdown patch or re-import the page from markdown. The columns
collapse into a single vertical stack.

Why: markdown has no concept of Row/Column layout blocks or card link blocks.
When Anytype turns markdown back into blocks (via `ObjectImport` with
`markdownParams`, or any markdown-based update path), it produces a flat,
top-to-bottom block list. There is nothing in the markdown to reconstruct the
horizontal layout, so it is lost.

The correct approach: treat layout as something you build and maintain through
the block RPCs (`BlockCreate`, `BlockListMoveToExistingObject` with "Right" and
"Inner"). Use markdown import for plain prose, or for the initial text of a page
you will then arrange. A layout-heavy page keeps its layout when you maintain it
through the block RPCs, so round-tripping it through markdown drops the layout.

```python
# Fine: import prose to seed a page.
req = at.new_request("ObjectImport")
req.spaceId = at.default_space
# ... set req.markdownParams ...
at.call("ObjectImport", req)
# Then build any column/card layout afterward with the block RPCs.
```

---

## 8. Deleting a Type orphans its hidden templates

The trap: you delete an object Type to clean up a space. Later you notice
leftover template objects, or your object count does not drop as much as
expected.

Why: every Type can have one or more template objects, and templates are hidden
objects (they do not show up in normal searches unless you ask for hidden ones).
Deleting the Type does not cascade to its templates. They are separate objects
and stay behind, now orphaned (pointing at a Type that no longer exists). There
is no dedicated "delete type" RPC; a Type is just an object, removed with the
same calls as any object (`ObjectListDelete` to delete permanently, or
`ObjectListSetIsArchived` to send to the bin).

The correct approach: before deleting a Type, find and delete its templates
too. Templates carry a `targetObjectType` relation pointing at their Type and a
hidden layout; search with hidden objects included and filter by that relation.

```python
# 1. Find the type's templates (you must include hidden objects).
req = at.new_request("ObjectSearch")
req.spaceId = at.default_space
req.keys.extend(["id", "name", "targetObjectType"])
# Add a filter on targetObjectType == "<type_id>" and include hidden objects,
# then read resp.records.
resp = at.call("ObjectSearch", req)

# 2. Delete templates, then the type itself.
template_ids = [r["fields"]["id"] for r in []]   # from resp, filtered
at.call("ObjectListDelete", objectIds=template_ids + ["bafy_type_id"])
```

If you only archive (bin) the Type with `ObjectListSetIsArchived`, the same rule
applies: bin the templates in the same pass or they linger.

---

## 9. Port discovery: the gRPC port changes across restarts

The trap: you hardcode `127.0.0.1:31007` (or whatever you saw once), and after
the next app restart your client connects to a dead or wrong port.

Why: the desktop app starts a helper process (`anytypeHelper`) that opens
several loopback ports (JSON HTTP API, gRPC, gRPC-web). The gRPC port is chosen
at launch and changes across restarts. The port is allocated dynamically each run.

The correct approach: let the client discover it. By default `Anytype()` lists
the loopback ports the helper process holds (`ss -tlnp`) and probes each with an
unauthenticated `AppGetVersion` until one answers gRPC. You can override with
the `ANYTYPE_GRPC_ADDR` env var or the `address=` argument when you know the
port, and pass `auto_discover=False` to skip probing (useful in offline tests).

```python
at = anytype_grpc.Anytype()                       # auto-discovers the port
at = anytype_grpc.Anytype(address="127.0.0.1:31007")   # explicit
at = anytype_grpc.Anytype(auto_discover=False)    # offline, no probing
print(anytype_grpc.discovery.find_grpc_address()) # what discovery found, or None
```

If discovery returns nothing the app is probably not running, or `ss` is not
available; fall back to an explicit address.

---

## 10. Version pinning: the internal API changes between releases

The trap: you upgrade the Anytype desktop app and your client starts failing
with unknown fields, missing methods, or decode errors. Or you assume any
method name from these docs exists in your build.

Why: `ClientCommands` is an internal API of `anytype-heart`. It is private to the
desktop app and versions with it. Methods, fields, and enum values change between releases.
The bindings this library ships were generated from protos vendored at one
specific `anytype-heart` version (see `protos/`), and this build exposes 333 RPC
methods. A different app version can have a different surface.

The correct approach: keep the vendored protos matched to the desktop app you
run against. When you upgrade the app, regenerate the bindings from the matching
`anytype-heart` tag with `scripts/gen_protos.sh`, then re-run the offline checks.
Confirm the running app's version at any time (no token needed):

```python
print(at.app_version())          # the desktop app's version string
```

If a method or field referenced in these docs is absent in your build, it is a
version mismatch. Regenerate against your app's tag to resolve it.
