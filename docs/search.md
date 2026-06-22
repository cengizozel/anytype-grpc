# Search domain

The search domain finds and queries objects in an Anytype space. It wraps the
gRPC search and subscription methods of the internal ClientCommands service.

You use it through one class, `Search`, constructed with a client:

```python
import anytype_grpc

at = anytype_grpc.Anytype()        # auto-discovers the port, reads ANYTYPE_TOKEN
s = at.query
space = at.default_space           # from ANYTYPE_SPACE_ID, or pass space_id=...
```

Most methods take a `space_id`. If you leave it as `None`, the client default
space is used (set via `ANYTYPE_SPACE_ID` or the `space_id=` constructor arg).

## What it does

- One-shot search: ask for the objects matching some filters, get a list back.
- Live subscriptions: ask the running app to keep a result set up to date and
  push changes as events. This library returns the initial result; consuming the
  event stream afterward is left to the caller.
- Grouping: get the distinct values of a relation (used to build kanban columns).
- Reverse lookup: find which relations hold a given value (backlinks).

## Filters and sorts

You build filters and sorts with helper methods that return protobuf messages.
You then pass a list of them into the search and subscribe methods. The helpers
handle the protobuf for you.

### Condition enum

Used by a filter's condition. Pass the name as a string.

| Name           | Meaning                                                        |
|----------------|----------------------------------------------------------------|
| None           | No condition (matches everything).                             |
| Equal          | Relation value equals the given value.                        |
| NotEqual       | Relation value is not equal to the given value.               |
| Greater        | Value is greater than the given value (numbers, dates).       |
| Less           | Value is less than the given value.                           |
| GreaterOrEqual | Value is greater than or equal to the given value.            |
| LessOrEqual    | Value is less than or equal to the given value.               |
| Like           | Text contains the given substring (case-insensitive).         |
| NotLike        | Text does not contain the given substring.                    |
| In             | At least one of the object's values is in the given list.     |
| NotIn          | None of the object's values are in the given list.            |
| Empty          | Relation has no value.                                         |
| NotEmpty       | Relation has any value.                                       |
| AllIn          | All of the given values are present on the object.            |
| NotAllIn       | Not all of the given values are present.                      |
| ExactIn        | The object's list equals the given list exactly.             |
| NotExactIn     | The object's list does not equal the given list exactly.     |
| Exists         | The relation exists on the object.                            |

### Sort type enum

Used by a sort's direction. Pass the name as a string.

| Name   | Meaning      |
|--------|--------------|
| Asc    | Ascending.   |
| Desc   | Descending.  |
| Custom | Custom order (provide customOrder values on the proto directly). |

### `filter(relation_key, condition="Equal", value=None)`

Build one filter.

- `relation_key`: the relation (property) key to test, for example "name",
  "type", "tag", "createdDate", "done".
- `condition`: a Condition name from the table above. Defaults to "Equal".
- `value`: the plain Python value to compare against (str, number, bool, list,
  or None). For "In", "NotIn", "AllIn", "ExactIn" pass a list. For "Empty",
  "NotEmpty", "Exists" the value is ignored, pass None.

Returns a protobuf Filter message to drop into a `filters` list.

```python
s.filter("type", "Equal", "ot-note")
s.filter("name", "Like", "report")
s.filter("tag", "In", ["id_red", "id_green"])
s.filter("done", "Equal", True)
s.filter("description", "NotEmpty")
```

### `sort(relation_key, direction="Asc", include_time=False)`

Build one sort rule.

- `relation_key`: the relation to sort by, for example "name", "createdDate",
  "lastModifiedDate".
- `direction`: "Asc", "Desc", or "Custom". Defaults to "Asc".
- `include_time`: for date relations, whether to consider the time part as well
  as the day. Defaults to False.

Returns a protobuf Sort message to drop into a `sorts` list.

```python
s.sort("lastModifiedDate", "Desc")
s.sort("name", "Asc")
```

## One-shot search

### `search(space_id=None, query="", types=None, filters=None, sorts=None, keys=None, limit=0)`

The friendly form. Returns a list of plain dicts, one per matching object.

- `space_id`: the space to search. Defaults to the client default space.
- `query`: full-text query (matches name and snippet). Empty matches all.
- `types`: a list of type ids or unique keys to filter by (added as a "type" In
  filter). Optional.
- `filters`: a list of Filter messages from `s.filter`. Optional. All match (AND).
- `sorts`: a list of Sort messages from `s.sort`. Optional.
- `keys`: relation keys to return per record. Defaults to id, name, type,
  layout, snippet.
- `limit`: max results (0 means server default, no limit).

Returns a list of dicts. Keys are the relation keys you asked for, in camelCase.

```python
rows = s.search(
    at.default_space,
    query="report",
    types=["ot-note"],
    sorts=[s.sort("lastModifiedDate", "Desc")],
    keys=["id", "name"],
    limit=10,
)
for r in rows:
    print(r.get("name"), r.get("id"))
```

### `object_search(space_id=None, *, query="", filters=None, sorts=None, keys=None, limit=0, offset=0, object_types=None, need_total=False)`

The full, low-level wrapper. Returns the raw ObjectSearch response message
(use this when you need `total` or paging with `offset`).

- `space_id`: the space to search. Defaults to the client default space.
- `query`: full-text query. Empty matches all.
- `filters`: a list of Filter messages, or None.
- `sorts`: a list of Sort messages, or None.
- `keys`: relation keys to return per record. Empty or None returns all keys.
- `limit`: max records (0 means no limit).
- `offset`: number of leading records to skip (for paging).
- `object_types`: a list of type ids or unique keys (adds a "type" In filter).
- `need_total`: if True, the response `total` field holds the count of all
  matches ignoring limit and offset.

Returns the ObjectSearch response message. Its `records` field is a list of
protobuf Struct messages; convert one with `at.to_dict(record)`.

```python
resp = s.object_search(
    at.default_space,
    filters=[s.filter("type", "Equal", "ot-note")],
    sorts=[s.sort("name")],
    keys=["id", "name"],
    limit=50,
    offset=0,
    need_total=True,
)
print("total matches:", resp.total)
for rec in resp.records:
    print(at.to_dict(rec))
```

## Subscriptions

A subscription asks the running app to keep a result set current and push
changes as gRPC events under a subscription id. These methods return only the
initial response. The id you pass (or the one the app generates and returns as
`subId`) is what you later cancel with `search_unsubscribe`.

### `search_subscribe(space_id=None, *, sub_id="", query=None, filters=None, sorts=None, keys=None, limit=0, offset=0, source=None, collection_id="", no_dep_subscription=False)`

Start a live search subscription.

- `space_id`: the space to subscribe in. Defaults to the client default.
- `sub_id`: a subscription id you choose. If empty, the app generates one and
  returns it as `subId`. Reusing an existing id replaces that subscription.
- `query`: accepted for symmetry with `search`, and ignored on send. The
  subscribe RPC has no full-text field, so for text matching build a "Like"
  filter.
- `filters`: a list of Filter messages from `s.filter`. Optional.
- `sorts`: a list of Sort messages from `s.sort`. Optional.
- `keys`: relation keys to return per record. Defaults to id and name.
- `limit`: max records in the result set (0 means no limit).
- `offset`: number of leading records to skip.
- `source`: a list of source object ids (for set-style sources). Optional.
- `collection_id`: a collection object id to scope to. Optional.
- `no_dep_subscription`: if True, do not also subscribe to dependent objects
  referenced by relation values.

Returns the ObjectSearchSubscribe response, with `records` (current matches),
`dependencies`, `subId` (the resolved id), and `counters`.

```python
resp = s.search_subscribe(
    at.default_space,
    sub_id="notes",
    filters=[s.filter("type", "Equal", "ot-note")],
    keys=["id", "name"],
)
print(resp.subId, len(resp.records))
```

### `search_unsubscribe(sub_ids)`

Stop one or more search subscriptions.

- `sub_ids`: a single subscription id (str) or a list of ids to cancel.

Returns the ObjectSearchUnsubscribe response message.

```python
s.search_unsubscribe("notes")
s.search_unsubscribe(["notes", "tasks"])
```

### `subscribe_ids(space_id=None, *, ids, sub_id="", keys=None, no_dep_subscription=False)`

Subscribe to a fixed set of object ids. Use this when you already know the ids
and want their current details (and live updates) without a query.

- `space_id`: the space the ids live in. Defaults to the client default.
- `ids`: a list of object ids to subscribe to (required).
- `sub_id`: a subscription id you choose. If empty, the app generates one.
- `keys`: relation keys to return per record. Defaults to id and name.
- `no_dep_subscription`: if True, do not subscribe to dependent objects.

Returns the ObjectSubscribeIds response, with `records`, `dependencies`, and
`subId`.

```python
resp = s.subscribe_ids(
    at.default_space,
    ids=["bafy_obj1", "bafy_obj2"],
    keys=["id", "name", "type"],
)
for r in resp.records:
    print(at.to_dict(r))
```

### `groups_subscribe(space_id=None, *, relation_key, sub_id="", filters=None, source=None, collection_id="")`

Subscribe to the groups of a relation: the distinct values in use, for example
all Status or Tag values among the matching objects. This is what a kanban view
uses to lay out its columns.

- `space_id`: the space to look in. Defaults to the client default.
- `relation_key`: the relation to group by, for example "status" or "tag"
  (required).
- `sub_id`: a subscription id you choose. If empty, the app generates one.
- `filters`: a list of Filter messages from `s.filter` to limit the objects
  considered. Optional.
- `source`: a list of source object ids. Optional.
- `collection_id`: a collection object id to scope to. Optional.

Returns the ObjectGroupsSubscribe response, with `groups` (each a Dataview Group
holding a status, tag, checkbox, or date value) and `subId`.

```python
resp = s.groups_subscribe(at.default_space, relation_key="status")
print(resp.subId, len(resp.groups))
```

## Reverse lookup

### `relation_list_with_value(value, space_id=None)`

List the relations whose value matches the given value. Given a value (commonly
an object id), returns each relation key that holds that value somewhere in the
space, with a count. Useful for finding where an object is referenced.

- `value`: the plain Python value to look for (most often an object id string,
  but any value works: number, bool, list).
- `space_id`: the space to search. Defaults to the client default.

Returns a list of dicts, one per relation, each with `relationKey` and
`counter` (how many objects hold this value in that relation).

```python
hits = s.relation_list_with_value("bafy_target_object", at.default_space)
for h in hits:
    print(h["relationKey"], h.get("counter"))
```

## Notes and gotchas

- The protobuf field for a filter's relation key is `RelationKey` (capital R),
  and the same for a sort. The helpers handle this for you; you only ever pass
  `relation_key`.
- ObjectSearchSubscribe has no full-text field. To match text in a subscription,
  add a filter with condition "Like" on "name" or "snippet" (a query string has
  no effect here).
- A search `record` and a subscription `record` are protobuf Struct messages.
  Convert one to a dict with `at.to_dict(record)`. The `search` method already
  returns dicts for you.
- Filters combine with logical AND. For OR logic, use the filter `operator`
  field and `nestedFilters` on the proto directly (these helpers leave that to
  you).
