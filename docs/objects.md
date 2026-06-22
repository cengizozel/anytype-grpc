# Objects domain

The objects domain covers the full lifecycle of an Anytype object: creating it,
opening and closing it, editing its details (properties), changing its layout,
type, and source, duplicating it, archiving, favoriting, deleting, converting it
to a set or a collection, importing from external formats, exporting, and
reading the space's object graph. It also includes helpers for the object cover
and icon.

It is one class, `Objects`, built around a connected `Anytype` client. Every
method that needs a space falls back to the client's default space
(`ANYTYPE_SPACE_ID`) when you do not pass `space_id`. Methods raise `RpcError`
on a non-zero server error.

## Setup

```python
import anytype_grpc

at = anytype_grpc.Anytype()          # auto-discovers the port, reads ANYTYPE_TOKEN
objects = at.objects
```

## Key concepts

- Details are an object's properties (relations). You pass plain Python values
  (str, number, bool, list, dict, None) and they are converted for you. Pass
  None for a key to clear that value.
- An object type is identified by its unique key, a string like `ot-page`,
  `ot-note`, or `ot-bookmark`, not by its object id. The create and set-type
  calls expect this unique key.
- A Set is a live query: its source is a list of object type ids (or relation
  ids) that decide which objects appear. A Collection is a manually curated list.
- The image cover is two details, `coverType=1` and `coverId=<file object id>`.
  Use `set_cover`. The icon is the `iconImage` detail (a file object id) or the
  `iconEmoji` detail (one emoji string). Use `set_icon`.
- You cannot add blocks to a Type or a Set object (the server replies
  "restricted: Blocks"). Edit those through details.

## Methods

### create(type_unique_key, details=None, template_id=None, space_id=None, with_chat=False)

Create a new object. Returns the new object's id (string).

- `type_unique_key`: object type unique key, for example `ot-page`.
- `details`: optional dict of {relation_key: value}, for example {"name": "Notes"}.
- `template_id`: optional template object id to apply, or None.
- `space_id`: target space, or None for the client default.
- `with_chat`: if True, attach a chat to the new object.

```python
new_id = objects.create("ot-page", details={"name": "Notes"})
```

### create_set(source, details=None, template_id=None, space_id=None, with_chat=False)

Create a Set that auto-collects objects of the given types. Returns the new set
object's id (string).

- `source`: list of object type ids (or relation ids); a single string is wrapped.
- `details`: optional dict of {relation_key: value}, for example {"name": "Tasks"}.
- `template_id`: optional template id, or None.
- `space_id`: target space, or None for the client default.
- `with_chat`: if True, attach a chat.

```python
set_id = objects.create_set([task_type_id], details={"name": "Tasks"})
```

### create_bookmark(url=None, details=None, template_id=None, space_id=None, with_chat=False)

Create a Bookmark object. Returns the new bookmark object's id (string). The URL
is stored under the `source` detail; passing `url` merges it in for you.

- `url`: the web address to bookmark, or None if you set `source` in details.
- `details`: optional dict of {relation_key: value}.
- `template_id`: optional template id, or None.
- `space_id`: target space, or None for the client default.
- `with_chat`: if True, attach a chat.

```python
bm_id = objects.create_bookmark(url="https://anytype.io")
```

### create_from_url(url, type_unique_key, details=None, add_page_content=False, template_id=None, space_id=None, with_chat=False)

Create an object from a web URL (the page is fetched and parsed). Returns the new
object's id (string).

- `url`: the web address to fetch and create from.
- `type_unique_key`: object type unique key, for example `ot-page`.
- `details`: optional dict of {relation_key: value}.
- `add_page_content`: if True, add the fetched page body as blocks.
- `template_id`: optional template id, or None.
- `space_id`: target space, or None for the client default.
- `with_chat`: if True, attach a chat.

```python
oid = objects.create_from_url("https://example.com", "ot-page", add_page_content=True)
```

### show(object_id, space_id=None, trace_id=None)

Open an object and return its full view as a dict (blocks plus details). This is
the usual read path.

- `object_id`: id of the object to view.
- `space_id`: object's space, or None for the client default. Only strictly
  required for date objects.
- `trace_id`: optional client trace id, or None.

Returns a dict with the object view (keys like `objectView` holding `blocks` and
`details`).

```python
view = objects.show(object_id)
```

### open(object_id, space_id=None, trace_id=None)

Open an object for editing and return its view as a dict. Same payload as
`show`. For plain reads, `show` is enough.

- `object_id`: id of the object to open.
- `space_id`: object's space, or None for the client default.
- `trace_id`: optional client trace id, or None.

Returns a dict with the object view.

```python
view = objects.open(object_id)
```

### close(object_id, space_id=None)

Close an object that was opened, releasing the editing session. Returns the raw
close response message.

- `object_id`: id of the object to close.
- `space_id`: object's space, or None for the client default.

```python
objects.close(object_id)
```

### set_details(object_id, details)

Set one or more detail (property) values on a single object. Returns the raw
response message.

- `object_id`: id of the object to edit.
- `details`: dict of {relation_key: value}. Pass None for a key to clear it.

```python
objects.set_details(oid, {"name": "Renamed", "done": True})
```

### list_set_details(object_ids, details)

Set the same detail values on many objects at once. Returns the raw response
message.

- `object_ids`: list of object ids; a single string is wrapped.
- `details`: dict of {relation_key: value} applied to every object.

```python
objects.list_set_details([a, b, c], {"done": True})
```

### set_cover(object_id, file_object_id, x=0.0, y=0.0)

Set an uploaded image file as the object's cover. This sets `coverType=1` and
`coverId=<file object id>`. The file object id is what the client's
`upload_file` returns. Returns the raw response message.

- `object_id`: id of the object to edit.
- `file_object_id`: id of an uploaded image file object.
- `x`, `y`: cover focus offsets as floats (default 0.0).

```python
fid = at.upload_file(url="http://127.0.0.1:8000/cover.jpg")
objects.set_cover(oid, fid)
```

### set_icon(object_id, emoji=None, file_object_id=None)

Set the object's icon to an emoji or an uploaded image file. Pass exactly one of
`emoji` or `file_object_id`; setting one clears the other. Returns the raw
response message. Raises ValueError if you pass both or neither.

- `object_id`: id of the object to edit.
- `emoji`: a single emoji string, or None.
- `file_object_id`: id of an uploaded image file object, or None.

```python
objects.set_icon(oid, emoji="rocket")
objects.set_icon(oid, file_object_id=fid)
```

### set_layout(object_id, layout)

Set an object's layout. Returns the raw response message.

- `object_id`: id of the object to edit.
- `layout`: a layout name (string) or its enum number. Names include `basic`,
  `profile`, `todo`, `note`, `set`, `collection`, `bookmark`, `image`, `file`,
  `audio`, `video`, `date`, `tag`.

```python
objects.set_layout(oid, "note")
```

### set_object_type(object_id, type_unique_key)

Change a single object's type. Returns the raw response message.

- `object_id`: id of the object to edit.
- `type_unique_key`: new type's unique key, for example `ot-note`.

```python
objects.set_object_type(oid, "ot-note")
```

### set_source(object_id, source)

Set the source query of a Set object. Returns the raw response message.

- `object_id`: id of the Set object to edit.
- `source`: list of object type ids (or relation ids); a single string is wrapped.

```python
objects.set_source(set_id, [task_type_id])
```

### duplicate(object_id)

Duplicate an object. Returns the new (duplicated) object's id (string).

- `object_id`: id of the object to duplicate.

```python
copy_id = objects.duplicate(oid)
```

### list_delete(object_ids)

Permanently delete objects (this removes them, it is not the bin). Returns the
raw response message. To move to the bin instead, use `set_archived(ids, True)`.

- `object_ids`: list of object ids; a single string is wrapped.

```python
objects.list_delete([oid1, oid2])
```

### set_archived(object_ids, archived=True)

Move objects to the bin (archive) or restore them. Returns the raw response
message.

- `object_ids`: list of object ids; a single string is wrapped.
- `archived`: True to move to the bin (default), False to restore.

```python
objects.set_archived([oid], True)    # to bin
objects.set_archived([oid], False)   # restore
```

### set_favorite(object_ids, favorite=True)

Add objects to favorites or remove them. Returns the raw response message.

- `object_ids`: list of object ids; a single string is wrapped.
- `favorite`: True to favorite (default), False to unfavorite.

```python
objects.set_favorite([oid], True)
```

### to_set(object_id, source)

Convert an existing object into a Set with the given source. Returns the raw
response message.

- `object_id`: id of the object to convert.
- `source`: list of object type ids (or relation ids); a single string is wrapped.

```python
objects.to_set(oid, [task_type_id])
```

### to_collection(object_id)

Convert an existing object into a Collection (a manually curated list). Returns
the raw response message.

- `object_id`: id of the object to convert.

```python
objects.to_collection(oid)
```

### import_markdown(paths, space_id=None, no_collection=False, create_directory_pages=False, include_properties_as_block=False, update_existing=False, no_progress=True)

Import one or more Markdown files or folders into the space. Returns the raw
import response message. For other formats (Notion, HTML, CSV, and so on) build
the request directly with `at.new_request("ObjectImport")` and set the matching
oneof params.

- `paths`: list of paths to Markdown files or folders; a single string is wrapped.
- `space_id`: target space, or None for the client default.
- `no_collection`: if True, do not wrap imported files in a collection.
- `create_directory_pages`: if True, create a page per source directory.
- `include_properties_as_block`: if True, render frontmatter properties as a
  block instead of object relations.
- `update_existing`: if True, update existing objects instead of duplicating.
- `no_progress`: if True (default), suppress progress events.

```python
objects.import_markdown(["/home/me/notes"])
```

### list_export(path, object_ids=None, format="Markdown", zip=False, include_nested=True, include_files=True, include_archived=False, space_id=None, no_progress=True)

Export objects to a folder on disk. Returns the raw export response message,
whose `path` is the output path and `succeed` is the number of exported objects.

- `path`: destination directory.
- `object_ids`: optional list of object ids; empty or None exports all. A single
  string is wrapped.
- `format`: one of `Markdown` (default), `Protobuf`, `JSON`, `DOT`, `SVG`,
  `GRAPH_JSON`.
- `zip`: if True, write a single zip file.
- `include_nested`: if True (default), include linked/nested objects.
- `include_files`: if True (default), include attached files.
- `include_archived`: if True, also export archived objects.
- `space_id`: source space, or None for the client default.
- `no_progress`: if True (default), suppress progress events.

```python
resp = objects.list_export("/home/me/out", format="Markdown")
print(resp.path, resp.succeed)
```

### graph(space_id=None, keys=None, limit=0, collection_id=None, include_type_edges=False)

Return the object graph of a space as a dict with `nodes` (object detail structs)
and `edges` ({source, target, name, type, ...}).

- `space_id`: source space, or None for the client default.
- `keys`: optional list of relation keys to include per node, or None for the
  server default.
- `limit`: max nodes (0 means no limit).
- `collection_id`: optional collection id to scope to.
- `include_type_edges`: if True, include object-to-type edges.

```python
g = objects.graph()
print(len(g.get("nodes", [])), len(g.get("edges", [])))
```

## Quirks

- The create-family RPCs (`create`, `create_set`, `create_bookmark`,
  `create_from_url`) carry details as a `google.protobuf.Struct`. The
  detail-editing RPCs (`set_details`, `list_set_details`) carry details as a
  repeated `Detail` list. Both accept the same plain Python dict here; the module
  handles the difference.
- A bookmark's URL lives in the `source` detail, not a dedicated field.
- `list_delete` is a hard delete. Use `set_archived(ids, True)` to send objects
  to the bin instead.
- `set_object_type` and `create` want the type unique key (for example
  `ot-note`), not the type's object id.
- `set_icon` requires exactly one of `emoji` or `file_object_id` and raises
  ValueError otherwise.
