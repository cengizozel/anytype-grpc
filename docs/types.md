# Types domain

The types domain creates and configures the building blocks of an Anytype space:

- Object types: a "type" describes a kind of object (its name, layout, and the
  relations it recommends). A type is itself an object.
- Relations (properties): a relation defines a property objects can carry, with
  a fixed data format (text, number, date, checkbox, and so on). A relation is
  also an object.
- Options (tags / statuses): an option is a single choice value for a select or
  multi-select relation.
- Templates: a template is a pre-filled object of a type that users can start
  from when creating new objects.

All methods live on the `Types` class. Construct it with a connected client:

```python
import anytype_grpc

at = anytype_grpc.Anytype()      # auto-discovers the app, reads ANYTYPE_TOKEN
t = at.types
space = at.default_space          # or pass space_id=... to each method
```

Most methods return a plain dict (the gRPC response converted with
`at.to_dict`). They raise `anytype_grpc.RpcError` if the server returns a
non-zero error code (for example trying to edit a read-only system type), and
`anytype_grpc.AnytypeError` for bad arguments (for example an unknown format
name, or no space id given and no default set).

## Layout names

When creating a type you pass a `layout` name. The valid names (with their model
enum numbers) are:

| name | meaning |
| --- | --- |
| basic | a plain page |
| profile | a person-like object |
| todo | a task with a checkbox |
| set | a query object over a type |
| collection | a manual list of objects |
| note | a body-only note |
| bookmark | a saved link |
| file, image, audio, video, pdf | media objects |
| date | a date object |
| tag | a tag object |

The full map is `anytype_grpc.types.LAYOUTS`. You may also pass the raw int enum
number directly.

## Format names

When creating a relation you pass a `format` name. The names follow the Anytype
UI vocabulary; the proto names are accepted as aliases:

| name | meaning |
| --- | --- |
| shorttext | single line text |
| longtext | multi-line text |
| number | a number |
| select (alias: status) | a single choice from options |
| multiselect (alias: tag) | multiple choices from options |
| date | a date |
| checkbox | a boolean |
| url | a URL |
| email | an email address |
| phone | a phone number |
| object | a link to other objects |
| file | a file, image, audio, or video |
| emoji | a single emoji |

The full map is `anytype_grpc.types.FORMATS`. You may also pass the raw int enum
number.

## Methods

### list_types(space_id=None, keys=None)

List the object types in a space. Searches for objects whose layout is
"objectType" and returns them as dicts.

- `space_id`: the space to look in. Defaults to the client default space.
- `keys`: which relation keys to return per type. Defaults to
  `["id", "name", "uniqueKey", "recommendedRelations", "iconEmoji"]`.

Returns a list of dicts, one per type. The `id` is the type object id used by
`add_relations` and `set_recommended_relations`. The `uniqueKey` (for example
`ot-note`) is what object-create calls expect as `objectTypeUniqueKey`.

```python
for ty in t.list_types(space):
    print(ty.get("name"), ty.get("id"))
```

### create_type(space_id=None, name="", layout="basic", recommended_relation_keys=None, plural_name=None, icon_emoji=None, description=None, extra_details=None)

Create a new object type.

- `space_id`: the space to create in. Defaults to the client default space.
- `name`: the singular type name, for example "Recipe".
- `layout`: a name from `LAYOUTS` (for example "basic", "note", "todo") or an
  int. Defaults to "basic".
- `recommended_relation_keys`: a list of relation keys (for example
  `["description", "tag"]`) the type should show. Pass keys of relations that
  already exist in the space. Optional.
- `plural_name`: the plural type name, for example "Recipes". Optional.
- `icon_emoji`: a single emoji for the type icon. Optional.
- `description`: a short description. Optional.
- `extra_details`: a dict of any other detail keys to set on the type object
  (advanced). Optional.

Returns a dict with at least `objectId` (the new type id) and `details`.

```python
res = t.create_type(space, "Recipe", layout="basic",
                    recommended_relation_keys=["description"])
type_id = res["objectId"]
```

### add_relations(type_url, relation_keys)

Add one or more relations (properties) to a type by key. This adds the relations
to the type's relation links. To control which relations are shown and in what
order, use `set_recommended_relations`.

- `type_url`: the type object id (also called objectTypeUrl), from `list_types`.
- `relation_keys`: a list of relation keys to add.

Returns a dict from the response. Raises `RpcError` if the type is read-only.

```python
t.add_relations(type_id, ["assignee", "dueDate"])
```

### remove_relations(type_url, relation_keys)

Remove one or more relations from a type by key.

- `type_url`: the type object id, from `list_types`.
- `relation_keys`: a list of relation keys to remove.

Returns a dict from the response. Raises `RpcError` if the type is read-only.

```python
t.remove_relations(type_id, ["dueDate"])
```

### set_recommended_relations(type_object_id, relation_object_ids)

Set the type's recommended relations (the visible property list), in order. This
replaces the existing list.

Important: this takes relation OBJECT IDS (the `id` of each relation object). Get
a relation's object id from its create response (`objectId`) or by searching for
relation objects. `add_relations` takes relation keys, which are a separate
identifier on the same relation object.

- `type_object_id`: the type object id, from `list_types`.
- `relation_object_ids`: an ordered list of relation object ids.

Returns a dict from the response. Raises `RpcError` if the type is read-only.

```python
rel_id = t.create_relation(space, "Spice level", "number")["objectId"]
t.set_recommended_relations(type_id, [rel_id])
```

### list_conflicting_relations(type_object_id, space_id=None)

List relation ids that conflict for a type. A conflicting relation appears on
objects of the type but is not part of the type's recommended relations. Useful
for tidying a type's property list.

- `type_object_id`: the type object id, from `list_types`.
- `space_id`: the space the type lives in. Defaults to the client default space.

Returns a dict with `relationIds`: a list of relation ids.

```python
t.list_conflicting_relations(type_id)
```

### set_type_details(type_object_id, details)

Set arbitrary detail values on one or more type objects. Types are configured
through their details: you cannot add blocks to a type object (the server
rejects that with "restricted: Blocks"). Use this to change a type's name, icon,
plural name, description, recommended layout, and so on.

- `type_object_id`: a single type object id, or a list of them to apply the same
  details to all.
- `details`: a dict of `{relation_key: value}` with plain Python values. Common
  keys: `name`, `pluralName`, `iconEmoji`, `description`, `recommendedLayout`
  (an int layout enum number).

Returns a dict from the response.

```python
t.set_type_details(type_id, {"name": "Meal", "iconEmoji": "X"})
```

### create_relation(space_id=None, name="", format="shorttext", object_types=None, max_count=None, extra_details=None)

Create a new relation (property). After creating it, attach it to a type with
`add_relations` (by key) or `set_recommended_relations` (by object id), or set
it on an object with the client's `set_details`.

- `space_id`: the space to create in. Defaults to the client default space.
- `name`: the relation name, for example "Spice level".
- `format`: a name from `FORMATS` or an int. Defaults to "shorttext".
- `object_types`: for the "object" format, a list of type object ids the
  relation may link to. Empty or omitted allows any object. Ignored for other
  formats. Optional.
- `max_count`: max number of values (0 means no limit, 1 means a single value).
  Optional.
- `extra_details`: a dict of any other detail keys to set on the relation object
  (advanced). Optional.

Returns a dict with `objectId` (the relation object id), `key` (the relation key
you use in details and `add_relations`), and `details`.

```python
res = t.create_relation(space, "Spice level", "number")
rel_key = res["key"]        # use with set_details / add_relations
rel_id = res["objectId"]    # use with set_recommended_relations
```

### relation_options(relation_key)

List the existing options (choices) of a select or multi-select relation.

- `relation_key`: the relation key, for example "tag". This is the internal key,
  which can differ from the display name.

Returns a dict with `options`: a RelationOptions message as a dict, whose inner
`options` list holds `{id, text, color, ...}` entries.

```python
t.relation_options("tag")
```

### relation_list_with_value(value, space_id=None)

List relations that hold a given value, with how many objects use it. Useful
before deleting an option or object to see where it is referenced.

- `value`: the value to search for, a plain Python value (most often a string
  id). It is converted to a protobuf Value for you.
- `space_id`: the space to search. Defaults to the client default space.

Returns a dict with `list`: a list of `{relationKey, counter}` items.

```python
t.relation_list_with_value(option_id)
```

### create_option(space_id=None, relation_key="", text="", color=None, extra_details=None)

Create a new option (choice) for a select or multi-select relation. Each option
belongs to one relation, identified by its key.

- `space_id`: the space to create in. Defaults to the client default space.
- `relation_key`: the key of the relation this option belongs to (for example
  "tag"). Required; an `AnytypeError` is raised if missing.
- `text`: the option label, for example "Spicy".
- `color`: an optional color name string (for example "red", "blue", "green",
  "yellow", "orange", "purple", "pink", "grey"). Optional.
- `extra_details`: a dict of any other detail keys to set on the option object
  (advanced). Optional.

Returns a dict with `objectId`: the option object id. Use that id as the value
(or one of the values) of the relation on an object via the client's
`set_details`.

```python
opt = t.create_option(space, "tag", "Spicy", color="red")
at.set_details(my_object_id, {"tag": [opt["objectId"]]})
```

### create_template_from_object(object_id)

Make a template out of an existing object. The object's type, details, and
blocks become a reusable template shown when creating new objects of that type.

- `object_id`: the id of the object to turn into a template.

Returns a dict with `id`: the new template's id.

```python
t.create_template_from_object(my_object_id)
```

### clone_template(template_id, space_id=None)

Duplicate an existing template.

- `template_id`: the id of the template to clone.
- `space_id`: the space the template lives in. Defaults to the client default
  space.

Returns a dict with `id`: the new (cloned) template's id.

```python
t.clone_template(template_id)
```

## Quirks and notes

- Read-only system types reject `add_relations`, `remove_relations`, and
  `set_recommended_relations` with `RpcError` (READONLY_OBJECT_TYPE). Only your
  own custom types can be reconfigured.
- You cannot add blocks to a type object. Configure types through their details
  with `set_type_details` (and through the recommended-relations calls).
- `add_relations` takes relation KEYS. `set_recommended_relations` takes relation
  OBJECT IDS. These are different identifiers from the same relation object: the
  `key` and the `objectId` fields of the `create_relation` response.
- "select" is a single choice (the proto calls it `status`); "multiselect" is
  multiple choices (the proto calls it `tag`). Both names and both proto aliases
  are accepted by `create_relation`.
