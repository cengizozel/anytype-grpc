"""The search domain: find and query objects in a space.

This module wraps the gRPC search and subscription methods of ClientCommands:

- ObjectSearch: a one-shot query with filters, sorts, returned keys, full text,
  limit and offset. This is the workhorse for "give me the objects matching X".
- ObjectSearchSubscribe / ObjectSearchUnsubscribe: a live subscription. The
  initial response holds the current matches; further changes arrive as gRPC
  events (this library returns the initial response only).
- ObjectSubscribeIds: subscribe to a fixed set of object ids by id.
- ObjectGroupsSubscribe: get the groups (for a kanban-style grouping) for a
  relation, for example the set of Status or Tag values in use.
- RelationListWithValue: list which relations on objects hold a given value,
  with a count per relation. Useful for "where is this object referenced".

Filters and sorts are built from plain dicts with the Filter and Sort helpers,
so callers never touch protobuf directly.

Condition enum (used by Filter.condition), by name:

    None           no condition (matches everything)
    Equal          relation value equals the given value
    NotEqual       relation value is not equal to the given value
    Greater        value is greater than the given value (numbers, dates)
    Less           value is less than the given value
    GreaterOrEqual value is greater than or equal to the given value
    LessOrEqual    value is less than or equal to the given value
    Like           text contains the given substring (case-insensitive)
    NotLike        text does not contain the given substring
    In             at least one of the object's values is in the given list
    NotIn          none of the object's values are in the given list
    Empty          relation has no value (empty)
    NotEmpty       relation has any value
    AllIn          all of the given values are present on the object
    NotAllIn       not all of the given values are present
    ExactIn        the object's list equals the given list exactly
    NotExactIn     the object's list does not equal the given list exactly
    Exists         the relation exists on the object

Sort type enum (used by Sort.type), by name:

    Asc     ascending
    Desc    descending
    Custom  custom order (provide customOrder values via the proto directly)
"""

from google.protobuf import json_format

from .client import _to_value


# The fully qualified protobuf names of the shared Dataview Filter and Sort
# messages. Both ObjectSearch and the subscribe calls reuse them.
_FILTER_FULL_NAME = "anytype.model.Block.Content.Dataview.Filter"
_SORT_FULL_NAME = "anytype.model.Block.Content.Dataview.Sort"


class Search:
    """Find and query objects in a space.

    Construct with a client:

        import anytype_grpc
        from anytype_grpc.search import Search
        at = anytype_grpc.Anytype()
        s = Search(at)
        rows = s.search(at.default_space, query="meeting", limit=20)
    """

    def __init__(self, client):
        self.c = client

    # ----- builders -----------------------------------------------------------

    def filter(self, relation_key, condition="Equal", value=None):
        """Build one search filter as a protobuf Filter message.

        Pass the result (or several) to ``search`` or ``search_subscribe`` in a
        list. The filter matches objects whose ``relation_key`` value satisfies
        ``condition`` against ``value``.

        Args:
            relation_key: the relation (property) key to test, for example
                "name", "type", "tag", "createdDate", "done".
            condition: the comparison, by name. One of the Condition enum names
                documented in this module (Equal, NotEqual, Like, In, Empty,
                NotEmpty, Greater, Less, GreaterOrEqual, LessOrEqual, NotLike,
                NotIn, AllIn, NotAllIn, ExactIn, NotExactIn, Exists, None).
                Defaults to "Equal".
            value: the plain Python value to compare against (str, number, bool,
                list, or None). For "In"/"NotIn"/"AllIn"/"ExactIn" pass a list.
                For "Empty"/"NotEmpty"/"Exists" the value is ignored, pass None.

        Returns:
            A protobuf Filter message ready to drop into a filters list.

        Example:
            s.filter("type", "Equal", "ot-note")
            s.filter("name", "Like", "report")
            s.filter("tag", "In", ["id_red", "id_green"])
            s.filter("done", "Equal", True)
            s.filter("description", "NotEmpty")
        """
        f = self.c.request_type("ObjectSearch")().filters.add()
        f.Clear()
        f.RelationKey = relation_key
        f.condition = f.DESCRIPTOR.fields_by_name["condition"].enum_type.values_by_name[condition].number
        if value is not None:
            f.value.CopyFrom(_to_value(value))
        return f

    def sort(self, relation_key, direction="Asc", include_time=False):
        """Build one sort rule as a protobuf Sort message.

        Args:
            relation_key: the relation (property) key to sort by, for example
                "name", "createdDate", "lastModifiedDate".
            direction: "Asc" (ascending), "Desc" (descending), or "Custom".
                Defaults to "Asc".
            include_time: for date relations, whether to consider the time part
                as well as the day. Defaults to False.

        Returns:
            A protobuf Sort message ready to drop into a sorts list.

        Example:
            s.sort("lastModifiedDate", "Desc")
            s.sort("name", "Asc")
        """
        srt = self.c.request_type("ObjectSearch")().sorts.add()
        srt.Clear()
        srt.RelationKey = relation_key
        srt.type = srt.DESCRIPTOR.fields_by_name["type"].enum_type.values_by_name[direction].number
        if include_time:
            srt.includeTime = True
        return srt

    # ----- one-shot search ----------------------------------------------------

    def object_search(self, space_id=None, *, query="", filters=None, sorts=None,
                      keys=None, limit=0, offset=0, object_types=None,
                      need_total=False):
        """Call ObjectSearch and return the raw response message.

        This is the full, low-level wrapper. For a list of dicts use ``search``.

        Args:
            space_id: the space to search. Defaults to the client default space.
            query: full-text query (matches name and snippet). Empty matches all.
            filters: a list of Filter messages (build them with ``self.filter``)
                or None. All filters must match (logical AND).
            sorts: a list of Sort messages (build them with ``self.sort``) or
                None.
            keys: a list of relation keys to return per record. Empty or None
                returns all keys.
            limit: max number of records (0 means no limit, server default).
            offset: number of leading records to skip (for paging).
            object_types: a list of type ids or unique keys to filter by. This is
                a convenience that adds a "type" filter with condition "In".
            need_total: if True, the response ``total`` field is filled with the
                count of all matches ignoring limit and offset.

        Returns:
            The ObjectSearch response message. Its ``records`` field is a list of
            protobuf Struct messages, and ``total`` holds the count when
            ``need_total`` is True.

        Example:
            resp = s.object_search(at.default_space,
                                   filters=[s.filter("type", "Equal", "ot-note")],
                                   sorts=[s.sort("name")],
                                   keys=["id", "name"], limit=50)
            print(resp.total)
        """
        req = self.c.new_request("ObjectSearch")
        req.spaceId = self.c._space(space_id)
        if query:
            req.fullText = query
        if filters:
            req.filters.extend(filters)
        if object_types:
            req.filters.append(self.filter("type", "In", list(object_types)))
        if sorts:
            req.sorts.extend(sorts)
        for k in (keys or []):
            req.keys.append(k)
        if limit:
            req.limit = limit
        if offset:
            req.offset = offset
        if need_total:
            req.needTotal = True
        return self.c.call("ObjectSearch", req)

    def search(self, space_id=None, query="", types=None, filters=None,
               sorts=None, keys=None, limit=0):
        """Search objects and return a list of plain dicts.

        This is the friendly form: pass filters and sorts you built with
        ``self.filter`` and ``self.sort``, get back a list of dicts (one per
        matching object, with the requested relation keys).

        Args:
            space_id: the space to search. Defaults to the client default space.
            query: full-text query (matches name and snippet). Empty matches all.
            types: a list of type ids or unique keys to filter by (added as a
                "type" In filter). Optional.
            filters: a list of Filter messages from ``self.filter``. Optional.
            sorts: a list of Sort messages from ``self.sort``. Optional.
            keys: relation keys to return per record. Defaults to a useful set:
                id, name, type, layout, snippet.
            limit: max results (0 means server default, no limit).

        Returns:
            A list of dicts, one per matching object. Keys are the relation keys
            you asked for, in camelCase.

        Example:
            rows = s.search(at.default_space, query="report",
                            types=["ot-note"],
                            sorts=[s.sort("lastModifiedDate", "Desc")],
                            keys=["id", "name"], limit=10)
            for r in rows:
                print(r.get("name"), r.get("id"))
        """
        resp = self.object_search(
            space_id, query=query, filters=filters, sorts=sorts,
            object_types=types, limit=limit,
            keys=keys or ["id", "name", "type", "layout", "snippet"],
        )
        return [json_format.MessageToDict(r) for r in resp.records]

    # ----- subscriptions ------------------------------------------------------

    def search_subscribe(self, space_id=None, *, sub_id="", query=None,
                         filters=None, sorts=None, keys=None, limit=0, offset=0,
                         source=None, collection_id="", no_dep_subscription=False):
        """Start a live search subscription (ObjectSearchSubscribe).

        The response holds the current matching records. After this, the running
        app pushes changes as gRPC events under the same ``sub_id``. This library
        returns only the initial response; consuming the event stream is up to
        the caller. Note: ObjectSearchSubscribe takes no fullText; ``query`` here
        is accepted only as a synonym and ignored if empty (use ``filters`` with
        a "name"/"snippet" "Like" condition for text matching).

        Args:
            space_id: the space to subscribe in. Defaults to the client default.
            sub_id: a subscription id you choose. If empty, the app generates one
                and returns it as ``subId`` on the response. Reusing an existing
                id replaces that subscription.
            query: accepted for symmetry with ``search``; not sent (the subscribe
                RPC has no full-text field). Build a "Like" filter instead.
            filters: a list of Filter messages from ``self.filter``. Optional.
            sorts: a list of Sort messages from ``self.sort``. Optional.
            keys: relation keys to return per record. Defaults to id and name.
            limit: max records in the result set (0 means no limit).
            offset: number of leading records to skip.
            source: a list of source object ids (for set-style sources). Optional.
            collection_id: a collection object id to scope to. Optional.
            no_dep_subscription: if True, do not also subscribe to dependent
                objects referenced by relation values.

        Returns:
            The ObjectSearchSubscribe response message, with ``records`` (current
            matches), ``dependencies``, ``subId`` (the resolved id), and
            ``counters``.

        Example:
            resp = s.search_subscribe(at.default_space, sub_id="notes",
                                      filters=[s.filter("type", "Equal", "ot-note")],
                                      keys=["id", "name"])
            print(resp.subId, len(resp.records))
        """
        req = self.c.new_request("ObjectSearchSubscribe")
        req.spaceId = self.c._space(space_id)
        if sub_id:
            req.subId = sub_id
        if filters:
            req.filters.extend(filters)
        if sorts:
            req.sorts.extend(sorts)
        for k in (keys or ["id", "name"]):
            req.keys.append(k)
        if limit:
            req.limit = limit
        if offset:
            req.offset = offset
        for src in (source or []):
            req.source.append(src)
        if collection_id:
            req.collectionId = collection_id
        if no_dep_subscription:
            req.noDepSubscription = True
        return self.c.call("ObjectSearchSubscribe", req)

    def search_unsubscribe(self, sub_ids):
        """Stop one or more search subscriptions (ObjectSearchUnsubscribe).

        Args:
            sub_ids: a single subscription id (str) or a list of ids to cancel.

        Returns:
            The ObjectSearchUnsubscribe response message.

        Example:
            s.search_unsubscribe("notes")
            s.search_unsubscribe(["notes", "tasks"])
        """
        if isinstance(sub_ids, str):
            sub_ids = [sub_ids]
        return self.c.call("ObjectSearchUnsubscribe", subIds=list(sub_ids))

    def subscribe_ids(self, space_id=None, *, ids, sub_id="", keys=None,
                      no_dep_subscription=False):
        """Subscribe to a fixed set of object ids (ObjectSubscribeIds).

        Use this when you already know the object ids and want their current
        details (and live updates) without a query.

        Args:
            space_id: the space the ids live in. Defaults to the client default.
            ids: a list of object ids to subscribe to (required).
            sub_id: a subscription id you choose. If empty, the app generates one
                and returns it as ``subId``.
            keys: relation keys to return per record. Defaults to id and name.
            no_dep_subscription: if True, do not subscribe to dependent objects.

        Returns:
            The ObjectSubscribeIds response message, with ``records``,
            ``dependencies``, and ``subId``.

        Example:
            resp = s.subscribe_ids(at.default_space,
                                   ids=["bafy_obj1", "bafy_obj2"],
                                   keys=["id", "name", "type"])
            for r in resp.records:
                print(at.to_dict(r))
        """
        req = self.c.new_request("ObjectSubscribeIds")
        req.spaceId = self.c._space(space_id)
        for i in ids:
            req.ids.append(i)
        if sub_id:
            req.subId = sub_id
        for k in (keys or ["id", "name"]):
            req.keys.append(k)
        if no_dep_subscription:
            req.noDepSubscription = True
        return self.c.call("ObjectSubscribeIds", req)

    def groups_subscribe(self, space_id=None, *, relation_key, sub_id="",
                         filters=None, source=None, collection_id=""):
        """Subscribe to the groups of a relation (ObjectGroupsSubscribe).

        Returns the distinct groups (the set of values in use) for a relation,
        for example all Status or Tag values among the matching objects. This is
        what a kanban view uses to lay out its columns.

        Args:
            space_id: the space to look in. Defaults to the client default.
            relation_key: the relation to group by, for example "status" or
                "tag" (required).
            sub_id: a subscription id you choose. If empty, the app generates one.
            filters: a list of Filter messages from ``self.filter`` to limit the
                objects considered. Optional.
            source: a list of source object ids. Optional.
            collection_id: a collection object id to scope to. Optional.

        Returns:
            The ObjectGroupsSubscribe response message, with ``groups`` (each a
            Dataview Group, holding a status, tag, checkbox, or date value) and
            ``subId``.

        Example:
            resp = s.groups_subscribe(at.default_space, relation_key="status")
            print(resp.subId, len(resp.groups))
        """
        req = self.c.new_request("ObjectGroupsSubscribe")
        req.spaceId = self.c._space(space_id)
        req.relationKey = relation_key
        if sub_id:
            req.subId = sub_id
        if filters:
            req.filters.extend(filters)
        for src in (source or []):
            req.source.append(src)
        if collection_id:
            req.collectionId = collection_id
        return self.c.call("ObjectGroupsSubscribe", req)

    def relation_list_with_value(self, value, space_id=None):
        """List relations whose value matches the given value (RelationListWithValue).

        Given a value (commonly an object id), returns each relation key that
        holds that value somewhere in the space, with a count. Useful for finding
        where an object is referenced (backlinks across relations).

        Args:
            value: the plain Python value to look for (most often an object id
                string, but any value works: number, bool, list).
            space_id: the space to search. Defaults to the client default.

        Returns:
            A list of dicts, one per relation, each with "relationKey" and
            "counter" (how many objects hold this value in that relation).

        Example:
            hits = s.relation_list_with_value("bafy_target_object", at.default_space)
            for h in hits:
                print(h["relationKey"], h.get("counter"))
        """
        req = self.c.new_request("RelationListWithValue")
        req.spaceId = self.c._space(space_id)
        req.value.CopyFrom(_to_value(value))
        resp = self.c.call("RelationListWithValue", req)
        return [json_format.MessageToDict(item) for item in resp.list]
