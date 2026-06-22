# views: dataview and set/collection views

The `Views` class edits the views of a set or collection object. A set or
collection holds one "dataview" block (its id is almost always the literal
string `"dataview"`). That block has:

- a relation pool: relations made available to the whole dataview block.
- one or more views: each view has a type (Table, List, Gallery, Kanban,
  Calendar, Graph), its own visible columns, filters, and sorts.

This module wraps every dataview RPC and adds three high-level helpers:
`set_view_type`, `set_visible_columns`, and `set_gallery_cover`.

## Two things to remember

1. There are two relation lists.
   - The block relation pool (`add_relation` / `remove_relation`) makes a
     relation available to the dataview at all.
   - The per-view relation list (`add_view_relation`, `remove_view_relation`,
     `sort_view_relations`) controls which relations show as columns in one
     view, and in what order. `update_view` does NOT change view columns.

2. Gallery covers come from a relation, not a file id. Set the view's
   `coverRelationKey` (for example `"picture"` or `"cover"`) with
   `set_gallery_cover`. Setting an object cover from a file id is a different
   operation (`Anytype.set_cover`), unrelated to galleries.

## Setup

```python
import anytype_grpc

at = anytype_grpc.Anytype()      # auto-discovers the port, reads ANYTYPE_TOKEN
views = at.views
```

Every method takes the set/collection object id as `set_id` and, unless noted,
the dataview block id as `block_id` (default `"dataview"`). View ids, filter
ids, and sort ids come from the object's blocks: open it with
`at.get_object(set_id)` and read the dataview block, or use `list_views`.

## Enum values

- View type (for `create_view`, `update_view`, `set_view_type`):
  `"Table"`, `"List"`, `"Gallery"`, `"Kanban"`, `"Calendar"`, `"Graph"`.
- Card size (for `update_view`): `"Small"`, `"Medium"`, `"Large"`.
- Filter condition (string in a filter dict, common ones): `"Equal"`,
  `"NotEqual"`, `"Like"`, `"NotLike"`, `"In"`, `"NotIn"`, `"Empty"`,
  `"NotEmpty"`, `"Greater"`, `"Less"`.
- Sort type (string in a sort dict): `"Asc"`, `"Desc"`, `"Custom"`.

## Methods

### list_views(set_id, block_id="dataview", space_id=None)

Reader. Returns the views of a set/collection as a list of dicts, each with at
least `id`, `type`, and `name`. Use the `id` as the `view_id` argument
elsewhere. Returns an empty list if the block has no views.

```python
for v in views.list_views("bafy_set_id"):
    print(v["id"], v.get("type"), v.get("name"))
```

### create_view(set_id, view_type="Table", name="", *, block_id="dataview", source=None)

Create a new view. Returns the new view id (string).

- `view_type`: one of the view type names above.
- `name`: view name shown in the UI (may be empty).
- `source`: optional list of type/relation ids to scope the view. Usually None.

```python
vid = views.create_view("bafy_set_id", "Gallery", "Cards")
```

### update_view(set_id, view_id, *, block_id="dataview", view_type=None, name=None, card_size=None, cover_relation_key=None, cover_fit=None, hide_icon=None)

Update a view's meta only. Does NOT change visible columns, filters, or sorts.
Only the non-None arguments are applied. Returns the raw response message.

- `view_type`: optional new type.
- `name`: optional new name.
- `card_size`: optional gallery card size.
- `cover_relation_key`: optional relation key for the gallery cover.
- `cover_fit`: optional bool, image fits the card.
- `hide_icon`: optional bool, hide the object icon in the view.

```python
views.update_view("bafy_set_id", "view_id_1",
                  name="Photos", card_size="Large",
                  cover_relation_key="picture", cover_fit=True)
```

### delete_view(set_id, view_id, block_id="dataview")

Delete a view from the dataview block. Returns the raw response message.

```python
views.delete_view("bafy_set_id", "view_id_1")
```

### set_active_view(set_id, view_id, block_id="dataview")

Make a view the currently active (locally shown) view. Returns the raw response.

```python
views.set_active_view("bafy_set_id", "view_id_2")
```

### set_view_position(set_id, view_id, position, block_id="dataview")

Move a view to a new zero-based index in the view tab order (0 means first).
Returns the raw response message.

```python
views.set_view_position("bafy_set_id", "view_id_2", 0)
```

### add_relation(set_id, relation_keys, block_id="dataview")

Add relations to the block's relation pool (makes them available to the
dataview). Accepts one key or a list. This does not by itself show them as
columns; use `add_view_relation` for that. Returns the raw response.

```python
views.add_relation("bafy_set_id", ["tag", "priority"])
```

### remove_relation(set_id, relation_keys, block_id="dataview")

Remove relations from the block's relation pool. Accepts one key or a list.
Returns the raw response.

```python
views.remove_relation("bafy_set_id", "priority")
```

### add_view_relation(set_id, view_id, relation_key, *, is_visible=True, block_id="dataview")

Add a relation as a column to one view and set its visibility. Use this, not
`update_view`, to control a view's columns. The relation should already be in
the block relation pool (`add_relation`). Returns the raw response.

```python
views.add_view_relation("bafy_set_id", "view_id_1", "tag")
```

### remove_view_relation(set_id, view_id, relation_keys, block_id="dataview")

Remove one or more column relations from a single view. Accepts one key or a
list. Returns the raw response.

```python
views.remove_view_relation("bafy_set_id", "view_id_1", "tag")
```

### sort_view_relations(set_id, view_id, relation_keys, block_id="dataview")

Set the left-to-right order of a view's column relations. Pass the full list of
relation keys in the order you want. Returns the raw response.

```python
views.sort_view_relations("bafy_set_id", "view_id_1",
                          ["name", "tag", "createdDate"])
```

### add_filter(set_id, view_id, filter_dict, block_id="dataview")

Add a filter to a view. Returns the new filter id (string).

`filter_dict` is parsed into a Dataview.Filter. Common keys (camelCase):
`RelationKey` (the relation to filter on), `condition` (a condition name like
`"Equal"`, `"In"`, `"Empty"`), and `value` (the comparison value).

```python
fid = views.add_filter("bafy_set_id", "view_id_1",
    {"RelationKey": "done", "condition": "Equal", "value": True})
```

### remove_filter(set_id, view_id, filter_ids, block_id="dataview")

Remove one or more filters by id. Accepts one id or a list. Returns the raw
response.

```python
views.remove_filter("bafy_set_id", "view_id_1", fid)
```

### replace_filter(set_id, view_id, filter_id, filter_dict, block_id="dataview")

Replace an existing filter (by id) with a new filter definition. Returns the
new filter id (string).

```python
views.replace_filter("bafy_set_id", "view_id_1", fid,
    {"RelationKey": "done", "condition": "Equal", "value": False})
```

### sort_filters(set_id, view_id, filter_ids, block_id="dataview")

Reorder a view's filters by passing their ids in the order you want. This
reorders filters; it does not sort objects. Returns the raw response.

```python
views.sort_filters("bafy_set_id", "view_id_1", [fid_a, fid_b])
```

### add_sort(set_id, view_id, sort_dict, block_id="dataview")

Add a sort rule to a view. Returns the raw response.

`sort_dict` is parsed into a Dataview.Sort. Common keys: `RelationKey` (the
relation to sort by) and `type` (`"Asc"`, `"Desc"`, or `"Custom"`).

```python
views.add_sort("bafy_set_id", "view_id_1",
    {"RelationKey": "createdDate", "type": "Desc"})
```

### remove_sort(set_id, view_id, sort_ids, block_id="dataview")

Remove one or more sort rules by id. Accepts one id or a list. Read a sort's id
from the view's `sorts` list (`id` field). Returns the raw response.

```python
views.remove_sort("bafy_set_id", "view_id_1", "sort_id_1")
```

### replace_sort(set_id, view_id, sort_id, sort_dict, block_id="dataview")

Replace an existing sort rule (by id) with a new sort definition. Returns the
raw response.

```python
views.replace_sort("bafy_set_id", "view_id_1", "sort_id_1",
    {"RelationKey": "name", "type": "Desc"})
```

### sort_sorts(set_id, view_id, sort_ids, block_id="dataview")

Set the precedence order of a view's sort rules by their ids (the first id has
the highest precedence). Returns the raw response.

```python
views.sort_sorts("bafy_set_id", "view_id_1", ["sort_b", "sort_a"])
```

### set_source(set_id, source, block_id="dataview")

Set the source of the dataview block (what a query set selects over). Accepts
one id or a list of type/relation ids. Pass an empty list to clear it. Returns
the raw response.

```python
views.set_source("bafy_set_id", ["ot_page_type_id"])
```

### create_from_existing_object(context_id, target_object_id, block_id="dataview")

Point an inline dataview block (in `context_id`) at an existing set/collection
object, so it mirrors that object's views. Returns the response as a dict,
including `blockId`, `targetObjectId`, and the view list.

```python
views.create_from_existing_object("bafy_page_id", "bafy_set_id")
```

## High-level helpers

### set_view_type(set_id, view_type, view_id=None, *, block_id="dataview", space_id=None)

Change a view's display type by name. If `view_id` is None, the first view of
the block is used (looked up with `list_views`). Returns the raw
`update_view` response.

```python
views.set_view_type("bafy_set_id", "Gallery")
```

### set_visible_columns(set_id, relation_keys, view_id=None, *, block_id="dataview", space_id=None)

Set which relations show as columns in a view, in order. Adds each relation as
a visible column, then sorts the columns. It does not remove columns already
present that are not in your list (remove those with `remove_view_relation`).
Relations should also be in the block relation pool (`add_relation`). If
`view_id` is None, the first view is used. Returns the final ordering response.

```python
views.set_visible_columns("bafy_set_id", ["name", "tag", "createdDate"])
```

### set_gallery_cover(set_id, relation_key, view_id=None, *, cover_fit=True, block_id="dataview", space_id=None)

Set the relation used for a gallery card cover (and whether the image fits the
card). Use a relation that holds an image or file, for example `"picture"`.
If `view_id` is None, the first view is used. Returns the raw `update_view`
response.

```python
views.set_gallery_cover("bafy_set_id", "picture")
```

## End-to-end example: make a set a gallery of cards

```python
import anytype_grpc

at = anytype_grpc.Anytype()
views = at.views
set_id = "bafy_set_id"

# 1. Switch the first view to a gallery.
views.set_view_type(set_id, "Gallery")

# 2. Make sure the cover relation is in the pool, then use it as the cover.
views.add_relation(set_id, "picture")
views.set_gallery_cover(set_id, "picture")

# 3. Show a couple of relations as card fields.
views.add_relation(set_id, ["tag"])
views.set_visible_columns(set_id, ["name", "tag"])
```
