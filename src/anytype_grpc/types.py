"""The "types" domain: object types, relations (properties), options, templates.

In Anytype a "type" (object type) is itself an object that describes a kind of
object: its name, its layout, and which relations (properties) it recommends.
A "relation" (called a property in the UI) is also an object: it has a name and
a data format (for example text, number, date, checkbox). A "relation option" is
a single choice value for a select or multi-select relation (a tag). Templates
are pre-filled objects of a type that the user can start from.

This module wraps the gRPC calls that create and configure all of those. It uses
the generic client (``self.c.call`` and ``self.c.new_request``) and the module
level helper ``_to_value`` for putting plain Python values into protobuf details.

Quick start:

    import anytype_grpc
    from anytype_grpc.types import Types
    at = anytype_grpc.Anytype()
    t = Types(at)
    type_id = t.create_type(at.default_space, "Recipe", layout="basic",
                            recommended_relation_keys=["description"])["objectId"]

Note on layouts and formats: layout names and format names are passed as strings
and resolved to the protobuf enum numbers for you. The valid names are listed in
``LAYOUTS`` and ``FORMATS`` below, and in the docstrings of the methods that use
them.
"""

from google.protobuf import json_format

from .client import _to_value
from .errors import AnytypeError


# Object type layout names, mapped to the model ObjectType.Layout enum numbers.
# These describe how an object of the type is shown. "basic" is a plain page,
# "note" is a body-only note, "todo" is a task with a checkbox, "set" and
# "collection" are query/list objects, "profile" is a person-like object.
LAYOUTS = {
    "basic": 0,
    "profile": 1,
    "todo": 2,
    "set": 3,
    "objectType": 4,
    "relation": 5,
    "file": 6,
    "dashboard": 7,
    "image": 8,
    "note": 9,
    "space": 10,
    "bookmark": 11,
    "collection": 14,
    "audio": 15,
    "video": 16,
    "date": 17,
    "participant": 19,
    "pdf": 20,
    "tag": 23,
}

# Relation (property) format names, mapped to the model RelationFormat enum
# numbers. The user-facing names on the left follow the Anytype UI vocabulary,
# so "select" is a single choice (the model calls it status) and "multiselect"
# is multiple choices (the model calls it tag). The proto names are also
# accepted as aliases so callers can use either.
FORMATS = {
    # user-facing name : enum number
    "longtext": 0,      # long text
    "shorttext": 1,     # short text (single line)
    "number": 2,
    "select": 3,        # single choice; proto name "status"
    "status": 3,
    "date": 4,
    "file": 5,
    "checkbox": 6,
    "url": 7,
    "email": 8,
    "phone": 9,
    "emoji": 10,
    "multiselect": 11,  # multiple choices; proto name "tag"
    "tag": 11,
    "object": 100,
    "relations": 101,
    "map": 102,
}


def _layout_number(layout):
    """Resolve a layout name (str) or an int to the layout enum number."""
    if isinstance(layout, int):
        return layout
    if layout in LAYOUTS:
        return LAYOUTS[layout]
    raise AnytypeError(
        f"unknown layout {layout!r}; valid names: {sorted(LAYOUTS)}"
    )


def _format_number(fmt):
    """Resolve a format name (str) or an int to the RelationFormat enum number."""
    if isinstance(fmt, int):
        return fmt
    if fmt in FORMATS:
        return FORMATS[fmt]
    raise AnytypeError(
        f"unknown relation format {fmt!r}; valid names: {sorted(FORMATS)}"
    )


class Types:
    """Create and configure object types, relations, options, and templates.

    Construct with a connected client:

        from anytype_grpc.types import Types
        t = Types(at)            # at is an anytype_grpc.Anytype
    """

    def __init__(self, client):
        self.c = client

    # ----- types ---------------------------------------------------------------

    def list_types(self, space_id=None, keys=None):
        """List the object types in a space.

        This searches for objects whose layout is "objectType" (the layout that
        type-describing objects have) and returns them as dicts.

        Args:
            space_id: the space to look in. Defaults to the client default space.
            keys: which relation keys to return per type. Defaults to a useful
                set: id, name, uniqueKey, recommendedRelations, iconEmoji.

        Returns:
            A list of dicts, one per type. The "id" is the type object id you
            pass to ``add_relations`` or ``set_recommended_relations``; the
            "uniqueKey" (for example "ot-note") is what some object-create calls
            expect as ``objectTypeUniqueKey``.

        Example:
            for ty in t.list_types(at.default_space):
                print(ty.get("name"), ty.get("id"))
        """
        sid = self.c._space(space_id)
        req = self.c.new_request("ObjectSearch")
        req.spaceId = sid
        for k in (keys or ["id", "name", "uniqueKey", "recommendedRelations",
                           "iconEmoji"]):
            req.keys.append(k)
        # Filter: layout == objectType (enum number 4).
        f = req.filters.add()
        f.RelationKey = "layout"
        f.condition = f.DESCRIPTOR.fields_by_name["condition"].enum_type \
            .values_by_name["Equal"].number
        f.value.CopyFrom(_to_value(LAYOUTS["objectType"]))
        resp = self.c.call("ObjectSearch", req)
        return [json_format.MessageToDict(r) for r in resp.records]

    def create_type(self, space_id=None, name="", layout="basic",
                    recommended_relation_keys=None, plural_name=None,
                    icon_emoji=None, description=None, extra_details=None):
        """Create a new object type.

        Args:
            space_id: the space to create the type in. Defaults to the client
                default space.
            name: the type name in singular form (for example "Recipe").
            layout: how objects of this type are shown. A name from ``LAYOUTS``
                (for example "basic", "note", "todo", "profile") or an int enum
                number. Defaults to "basic".
            recommended_relation_keys: a list of relation keys (for example
                ["description", "tag"]) that objects of this type should show.
                These are stored on the type as recommendedRelations. Pass keys
                of relations that already exist in the space. Optional.
            plural_name: the type name in plural form (for example "Recipes").
                Optional; if omitted the server may derive one.
            icon_emoji: a single emoji to use as the type icon. Optional.
            description: a short description of the type. Optional.
            extra_details: a dict of any other detail keys to set on the type
                object directly (advanced). Optional.

        Returns:
            A dict from the response with at least "objectId" (the new type's id)
            and "details" (the created type's details). Use the objectId for
            later configuration calls.

        Example:
            res = t.create_type(at.default_space, "Recipe", layout="basic",
                               recommended_relation_keys=["description"],
                               icon_emoji="R")
            type_id = res["objectId"]
        """
        details = {
            "name": name,
            "recommendedLayout": _layout_number(layout),
        }
        if recommended_relation_keys:
            details["recommendedRelations"] = list(recommended_relation_keys)
        if plural_name is not None:
            details["pluralName"] = plural_name
        if icon_emoji is not None:
            details["iconEmoji"] = icon_emoji
        if description is not None:
            details["description"] = description
        if extra_details:
            details.update(extra_details)

        req = self.c.new_request("ObjectCreateObjectType")
        req.spaceId = self.c._space(space_id)
        for k, v in details.items():
            req.details.fields[k].CopyFrom(_to_value(v))
        resp = self.c.call("ObjectCreateObjectType", req)
        return self.c.to_dict(resp)

    def add_relations(self, type_url, relation_keys):
        """Add one or more relations (properties) to a type.

        This adds the relations to the type's relation links so objects of the
        type can carry those properties. To control which relations are shown
        and in what order, use ``set_recommended_relations`` instead.

        Args:
            type_url: the type object id (also called objectTypeUrl). This is the
                "id" from ``list_types``.
            relation_keys: a list of relation keys to add (for example
                ["assignee", "dueDate"]).

        Returns:
            A dict from the response. Raises RpcError if the type is read-only.

        Example:
            t.add_relations(type_id, ["assignee", "dueDate"])
        """
        req = self.c.new_request("ObjectTypeRelationAdd")
        req.objectTypeUrl = type_url
        req.relationKeys.extend(relation_keys)
        return self.c.to_dict(self.c.call("ObjectTypeRelationAdd", req))

    def remove_relations(self, type_url, relation_keys):
        """Remove one or more relations (properties) from a type.

        Args:
            type_url: the type object id (also called objectTypeUrl), from
                ``list_types``.
            relation_keys: a list of relation keys to remove.

        Returns:
            A dict from the response. Raises RpcError if the type is read-only.

        Example:
            t.remove_relations(type_id, ["dueDate"])
        """
        req = self.c.new_request("ObjectTypeRelationRemove")
        req.objectTypeUrl = type_url
        req.relationKeys.extend(relation_keys)
        return self.c.to_dict(self.c.call("ObjectTypeRelationRemove", req))

    def set_recommended_relations(self, type_object_id, relation_object_ids):
        """Set the recommended relations of a type (the visible property list).

        This replaces the type's recommended relations with the given list, in
        order. Note the difference from ``add_relations``: this call takes
        relation OBJECT IDS (the "id" of each relation object), not relation
        keys. Get a relation's object id from its create response or by searching
        for relation objects.

        Args:
            type_object_id: the type object id (the "id" from ``list_types``).
            relation_object_ids: an ordered list of relation object ids to make
                the type's recommended (shown) relations.

        Returns:
            A dict from the response. Raises RpcError if the type is read-only.

        Example:
            rel_id = t.create_relation(at.default_space, "Spice level",
                                       "number")["objectId"]
            t.set_recommended_relations(type_id, [rel_id])
        """
        req = self.c.new_request("ObjectTypeRecommendedRelationsSet")
        req.typeObjectId = type_object_id
        req.relationObjectIds.extend(relation_object_ids)
        return self.c.to_dict(
            self.c.call("ObjectTypeRecommendedRelationsSet", req)
        )

    def list_conflicting_relations(self, type_object_id, space_id=None):
        """List relation ids that conflict for a type.

        A conflicting relation is one that appears on objects of the type but is
        not part of the type's recommended relations. This is useful for tidying
        a type's property list.

        Args:
            type_object_id: the type object id (the "id" from ``list_types``).
            space_id: the space the type lives in. Defaults to the client
                default space.

        Returns:
            A dict from the response with "relationIds": a list of relation ids.

        Example:
            t.list_conflicting_relations(type_id)
        """
        req = self.c.new_request("ObjectTypeListConflictingRelations")
        req.spaceId = self.c._space(space_id)
        req.typeObjectId = type_object_id
        return self.c.to_dict(
            self.c.call("ObjectTypeListConflictingRelations", req)
        )

    def set_type_details(self, type_object_id, details):
        """Set arbitrary detail values on one or more type objects.

        Types are configured through their details (you cannot add blocks to a
        type object; the server rejects that with "restricted: Blocks"). Use
        this to change a type's name, icon, plural name, description, and so on.

        Args:
            type_object_id: a single type object id, or a list of type object
                ids to apply the same details to.
            details: a dict of {relation_key: value} with plain Python values.
                Common keys: "name", "pluralName", "iconEmoji", "description",
                "recommendedLayout" (an int layout enum number).

        Returns:
            A dict from the response.

        Example:
            t.set_type_details(type_id, {"name": "Meal", "iconEmoji": "M"})
        """
        ids = [type_object_id] if isinstance(type_object_id, str) \
            else list(type_object_id)
        req = self.c.new_request("ObjectListSetDetails")
        req.objectIds.extend(ids)
        for k, v in details.items():
            d = req.details.add()
            d.key = k
            d.value.CopyFrom(_to_value(v))
        return self.c.to_dict(self.c.call("ObjectListSetDetails", req))

    # ----- relations (properties) ---------------------------------------------

    def create_relation(self, space_id=None, name="", format="shorttext",
                        object_types=None, max_count=None, extra_details=None):
        """Create a new relation (property).

        A relation defines a property objects can carry, with a fixed data
        format. After creating it you can attach it to a type with
        ``add_relations`` (by key) or ``set_recommended_relations`` (by object
        id), or set it on an object with the client's ``set_details``.

        Args:
            space_id: the space to create the relation in. Defaults to the
                client default space.
            name: the relation name (for example "Spice level").
            format: the data format. A name from ``FORMATS`` or an int enum
                number. The names are: "shorttext", "longtext", "number",
                "select" (single choice, also "status"), "multiselect" (multiple
                choices, also "tag"), "date", "checkbox", "url", "email",
                "phone", "object", "file", "emoji". Defaults to "shorttext".
            object_types: for the "object" format, a list of type object ids the
                relation may link to. Empty or omitted allows any object.
                Ignored for other formats. Optional.
            max_count: the maximum number of values (0 means no limit, 1 means a
                single value). Optional.
            extra_details: a dict of any other detail keys to set on the relation
                object directly (advanced). Optional.

        Returns:
            A dict from the response with "objectId" (the relation object id),
            "key" (the relation key you use in details and add_relations), and
            "details".

        Example:
            res = t.create_relation(at.default_space, "Spice level", "number")
            rel_key = res["key"]          # use with set_details / add_relations
            rel_id = res["objectId"]      # use with set_recommended_relations
        """
        details = {
            "name": name,
            "relationFormat": _format_number(format),
        }
        if object_types:
            details["relationFormatObjectTypes"] = list(object_types)
        if max_count is not None:
            details["relationMaxCount"] = max_count
        if extra_details:
            details.update(extra_details)

        req = self.c.new_request("ObjectCreateRelation")
        req.spaceId = self.c._space(space_id)
        for k, v in details.items():
            req.details.fields[k].CopyFrom(_to_value(v))
        return self.c.to_dict(self.c.call("ObjectCreateRelation", req))

    def relation_options(self, relation_key):
        """List the existing options (choices) of a select/multi-select relation.

        Args:
            relation_key: the relation key (for example "tag"), not the name.

        Returns:
            A dict from the response with "options" (a RelationOptions message as
            a dict, with an "options" list of {id, text, color, ...}).

        Example:
            t.relation_options("tag")
        """
        req = self.c.new_request("RelationOptions")
        req.relationKey = relation_key
        return self.c.to_dict(self.c.call("RelationOptions", req))

    def relation_list_with_value(self, value, space_id=None):
        """List relations that hold a given value, with how many objects use it.

        This finds which relations across the space currently reference the given
        value (for example a specific object id, or a tag option id), and counts
        the objects. Useful before deleting an option or object to see its use.

        Args:
            value: the value to search for. A plain Python value (most often a
                string id). It is converted to a protobuf Value for you.
            space_id: the space to search. Defaults to the client default space.

        Returns:
            A dict from the response with "list": a list of
            {relationKey, counter} items.

        Example:
            t.relation_list_with_value(option_id)
        """
        req = self.c.new_request("RelationListWithValue")
        req.spaceId = self.c._space(space_id)
        req.value.CopyFrom(_to_value(value))
        return self.c.to_dict(self.c.call("RelationListWithValue", req))

    # ----- options (tags / statuses) ------------------------------------------

    def create_option(self, space_id=None, relation_key="", text="", color=None,
                      extra_details=None):
        """Create a new option (choice) for a select or multi-select relation.

        Options are the individual values a "select" (single) or "multiselect"
        (tag) relation can take. Each option belongs to one relation, identified
        by its key.

        Args:
            space_id: the space to create the option in. Defaults to the client
                default space.
            relation_key: the key of the relation this option belongs to (for
                example "tag"). Required.
            text: the option label (for example "Spicy").
            color: an optional color name string (for example "red", "blue",
                "green", "yellow", "orange", "purple", "pink", "grey"). Optional.
            extra_details: a dict of any other detail keys to set on the option
                object directly (advanced). Optional.

        Returns:
            A dict from the response with "objectId": the option object id. Use
            that id as the value (or one of the values) of the relation on an
            object via the client's ``set_details``.

        Example:
            opt = t.create_option(at.default_space, "tag", "Spicy", color="red")
            at.set_details(my_object_id, {"tag": [opt["objectId"]]})
        """
        if not relation_key:
            raise AnytypeError("create_option requires a relation_key")
        details = {
            "relationKey": relation_key,
            "name": text,
        }
        if color is not None:
            details["relationOptionColor"] = color
        if extra_details:
            details.update(extra_details)

        req = self.c.new_request("ObjectCreateRelationOption")
        req.spaceId = self.c._space(space_id)
        for k, v in details.items():
            req.details.fields[k].CopyFrom(_to_value(v))
        return self.c.to_dict(self.c.call("ObjectCreateRelationOption", req))

    # ----- templates -----------------------------------------------------------

    def create_template_from_object(self, object_id):
        """Make a template out of an existing object.

        The object's type, details, and blocks become a reusable template that
        appears when creating new objects of that type.

        Args:
            object_id: the id of the object to turn into a template.

        Returns:
            A dict from the response with "id": the new template's id.

        Example:
            t.create_template_from_object(my_object_id)
        """
        req = self.c.new_request("TemplateCreateFromObject")
        req.contextId = object_id
        return self.c.to_dict(self.c.call("TemplateCreateFromObject", req))

    def clone_template(self, template_id, space_id=None):
        """Duplicate an existing template.

        Args:
            template_id: the id of the template to clone.
            space_id: the space the template lives in. Defaults to the client
                default space.

        Returns:
            A dict from the response with "id": the new (cloned) template's id.

        Example:
            t.clone_template(template_id)
        """
        req = self.c.new_request("TemplateClone")
        req.contextId = template_id
        req.spaceId = self.c._space(space_id)
        return self.c.to_dict(self.c.call("TemplateClone", req))
