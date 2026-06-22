"""The "views" domain: dataview and set/collection views.

A set or collection object holds a single "dataview" block (its id is almost
always the literal string "dataview"). That block has:

- a relation pool: the set of relations available to all views of the block
  (managed with BlockDataviewRelationAdd / BlockDataviewRelationDelete).
- one or more views: each view has a type (Table, List, Gallery, Kanban,
  Calendar, Graph), its own visible columns, filters, and sorts.

This module wraps every dataview RPC and adds a few high-level helpers
(set_view_type, set_visible_columns, set_gallery_cover) that handle the
fiddly parts for you.

Important gotchas baked into this module:

- The per-view visible columns are NOT set through BlockDataviewViewUpdate.
  That RPC only changes view meta (type, name, cardSize, coverRelationKey,
  coverFit, hideIcon). To change which relations show as columns, use
  add_view_relation / remove_view_relation / sort_view_relations (which wrap
  BlockDataviewViewRelationAdd / Remove / Sort).
- There are two relation lists. The block relation pool (add_relation /
  remove_relation) makes a relation available to the dataview at all. The
  per-view relation list (add_view_relation, isVisible) controls whether a
  relation shows as a column in that one view.
- Gallery covers come from a relation, a property that holds an image. Set the
  view's coverRelationKey (for example "picture" or "cover") with
  set_gallery_cover.

All ids you pass are object ids and view ids from the running space. This
module never makes a call on its own at import time; constructing a request
needs no running app.
"""

from google.protobuf import json_format


# View type names accepted by set_view_type and create_view, mapped to the
# enum value names in model.Block.Content.Dataview.View.Type.
_VIEW_TYPES = ("Table", "List", "Gallery", "Kanban", "Calendar", "Graph")
# Card size names accepted by set_view_type / update_view, mapped to
# model.Block.Content.Dataview.View.Size.
_CARD_SIZES = ("Small", "Medium", "Large")


class Views:
    """Create and edit the views of a set or collection (its dataview block).

    Construct with a client:

        import anytype_grpc
        from anytype_grpc.views import Views
        at = anytype_grpc.Anytype()
        views = Views(at)

    Every method takes the set/collection object id as ``set_id`` and, unless
    noted, the dataview block id as ``block_id`` (default "dataview"). View
    ids come from the object's blocks: open it with ``at.get_object(set_id)``
    and read the dataview block's ``views`` list, or use ``list_views``.
    """

    def __init__(self, client):
        self.c = client

    # ----- internal helpers ---------------------------------------------------

    @staticmethod
    def _enum_number(message, field_name, value_name):
        """Resolve an enum value name to its number on a field of ``message``.

        ``message`` is a protobuf message instance, ``field_name`` is one of its
        fields whose type is an enum, and ``value_name`` is the enum member
        name (for example "Gallery"). Returns the integer enum value.
        """
        field = message.DESCRIPTOR.fields_by_name[field_name]
        return field.enum_type.values_by_name[value_name].number

    @staticmethod
    def _view_type_number(view_msg, type_name):
        """Resolve a view type name ("Table".."Graph") to its enum number."""
        if type_name not in _VIEW_TYPES:
            raise ValueError(
                f"unknown view type {type_name!r}; expected one of {_VIEW_TYPES}"
            )
        return view_msg.DESCRIPTOR.fields_by_name["type"].enum_type.values_by_name[
            type_name
        ].number

    @staticmethod
    def _card_size_number(view_msg, size_name):
        """Resolve a card size name ("Small"/"Medium"/"Large") to its number."""
        if size_name not in _CARD_SIZES:
            raise ValueError(
                f"unknown card size {size_name!r}; expected one of {_CARD_SIZES}"
            )
        return view_msg.DESCRIPTOR.fields_by_name["cardSize"].enum_type.values_by_name[
            size_name
        ].number

    def list_views(self, set_id, block_id="dataview", space_id=None):
        """Return the views of a set/collection as a list of dicts.

        This is a convenience reader built on ObjectShow. Each item has at
        least an ``id``, a ``type``, and a ``name``. Use the ``id`` field as
        the ``view_id`` argument for the other methods.

        Args:
            set_id: the set/collection object id.
            block_id: the dataview block id (default "dataview").
            space_id: the space id; defaults to the client default space.

        Returns:
            A list of dicts, one per view. Returns an empty list if the block
            has no views or cannot be found.

        Example:
            for v in views.list_views("bafy_set_id"):
                print(v["id"], v.get("type"), v.get("name"))
        """
        obj = self.c.get_object(set_id, space_id=space_id)
        blocks = obj.get("objectView", {}).get("blocks", []) or obj.get("blocks", [])
        for block in blocks:
            if block.get("id") != block_id:
                continue
            dataview = block.get("dataview")
            if dataview:
                return dataview.get("views", []) or []
        return []

    # ----- views (create / update / delete / order / active) ------------------

    def create_view(self, set_id, view_type="Table", name="", *,
                    block_id="dataview", source=None):
        """Create a new view on the dataview block. Returns the new view id.

        Args:
            set_id: the set/collection object id (the request's contextId).
            view_type: one of "Table", "List", "Gallery", "Kanban",
                "Calendar", "Graph".
            name: the view name shown in the UI (may be empty).
            block_id: the dataview block id (default "dataview").
            source: optional list of type/relation ids to scope the view to.
                Most callers leave this None.

        Returns:
            The id (string) of the created view.

        Example:
            vid = views.create_view("bafy_set_id", "Gallery", "Cards")
        """
        req = self.c.new_request("BlockDataviewViewCreate")
        req.contextId = set_id
        req.blockId = block_id
        req.view.type = self._view_type_number(req.view, view_type)
        if name:
            req.view.name = name
        if source:
            req.source.extend(source)
        resp = self.c.call("BlockDataviewViewCreate", req)
        return getattr(resp, "viewId", "")

    def update_view(self, set_id, view_id, *, block_id="dataview",
                    view_type=None, name=None, card_size=None,
                    cover_relation_key=None, cover_fit=None, hide_icon=None):
        """Update a view's meta. Does NOT change visible columns, filters, or sorts.

        This wraps BlockDataviewViewUpdate, which only edits view meta. To
        change which relations are shown as columns use add_view_relation /
        remove_view_relation / sort_view_relations. To change filters or sorts
        use the filter/sort methods.

        Only the arguments you pass (non-None) are applied; the rest keep their
        current values.

        Args:
            set_id: the set/collection object id (contextId).
            view_id: the id of the view to update.
            block_id: the dataview block id (default "dataview").
            view_type: optional new type ("Table".."Graph").
            name: optional new view name.
            card_size: optional gallery card size ("Small"/"Medium"/"Large").
            cover_relation_key: optional relation key used for the gallery cover
                (for example "picture"). Set this to make a gallery show images.
            cover_fit: optional bool; if True the cover image fits the card.
            hide_icon: optional bool; if True the object icon is hidden in the view.

        Returns:
            The raw BlockDataviewViewUpdate response message.

        Example:
            views.update_view("bafy_set_id", "view_id_1",
                              name="Photos", card_size="Large",
                              cover_relation_key="picture", cover_fit=True)
        """
        req = self.c.new_request("BlockDataviewViewUpdate")
        req.contextId = set_id
        req.blockId = block_id
        req.viewId = view_id
        # The View message carries the new meta. Field 1 (id) is left empty.
        if view_type is not None:
            req.view.type = self._view_type_number(req.view, view_type)
        if name is not None:
            req.view.name = name
        if card_size is not None:
            req.view.cardSize = self._card_size_number(req.view, card_size)
        if cover_relation_key is not None:
            req.view.coverRelationKey = cover_relation_key
        if cover_fit is not None:
            req.view.coverFit = bool(cover_fit)
        if hide_icon is not None:
            req.view.hideIcon = bool(hide_icon)
        return self.c.call("BlockDataviewViewUpdate", req)

    def delete_view(self, set_id, view_id, block_id="dataview"):
        """Delete a view from the dataview block.

        Args:
            set_id: the set/collection object id (contextId).
            view_id: the id of the view to remove.
            block_id: the dataview block id (default "dataview").

        Returns:
            The raw BlockDataviewViewDelete response message.

        Example:
            views.delete_view("bafy_set_id", "view_id_1")
        """
        req = self.c.new_request("BlockDataviewViewDelete")
        req.contextId = set_id
        req.blockId = block_id
        req.viewId = view_id
        return self.c.call("BlockDataviewViewDelete", req)

    def set_active_view(self, set_id, view_id, block_id="dataview"):
        """Set the currently active (locally shown) view of the dataview block.

        Args:
            set_id: the set/collection object id (contextId).
            view_id: the id of the view to make active.
            block_id: the dataview block id (default "dataview").

        Returns:
            The raw BlockDataviewViewSetActive response message.

        Example:
            views.set_active_view("bafy_set_id", "view_id_2")
        """
        req = self.c.new_request("BlockDataviewViewSetActive")
        req.contextId = set_id
        req.blockId = block_id
        req.viewId = view_id
        return self.c.call("BlockDataviewViewSetActive", req)

    def set_view_position(self, set_id, view_id, position, block_id="dataview"):
        """Move a view to a new index in the view tab order.

        Args:
            set_id: the set/collection object id (contextId).
            view_id: the id of the view to move.
            position: zero-based target index (0 means first).
            block_id: the dataview block id (default "dataview").

        Returns:
            The raw BlockDataviewViewSetPosition response message.

        Example:
            views.set_view_position("bafy_set_id", "view_id_2", 0)
        """
        req = self.c.new_request("BlockDataviewViewSetPosition")
        req.contextId = set_id
        req.blockId = block_id
        req.viewId = view_id
        req.position = int(position)
        return self.c.call("BlockDataviewViewSetPosition", req)

    # ----- block relation pool (available relations) --------------------------

    def add_relation(self, set_id, relation_keys, block_id="dataview"):
        """Add relations to the dataview block's relation pool.

        This makes relations available to the dataview. It does not by itself
        show them as columns in a view; for that use add_view_relation.

        Args:
            set_id: the set/collection object id (contextId).
            relation_keys: a relation key string or a list of relation keys
                (for example "tag" or ["tag", "createdDate"]).
            block_id: the dataview block id (default "dataview").

        Returns:
            The raw BlockDataviewRelationAdd response message.

        Example:
            views.add_relation("bafy_set_id", ["tag", "priority"])
        """
        if isinstance(relation_keys, str):
            relation_keys = [relation_keys]
        req = self.c.new_request("BlockDataviewRelationAdd")
        req.contextId = set_id
        req.blockId = block_id
        req.relationKeys.extend(relation_keys)
        return self.c.call("BlockDataviewRelationAdd", req)

    def remove_relation(self, set_id, relation_keys, block_id="dataview"):
        """Remove relations from the dataview block's relation pool.

        Args:
            set_id: the set/collection object id (contextId).
            relation_keys: a relation key string or a list of relation keys.
            block_id: the dataview block id (default "dataview").

        Returns:
            The raw BlockDataviewRelationDelete response message.

        Example:
            views.remove_relation("bafy_set_id", "priority")
        """
        if isinstance(relation_keys, str):
            relation_keys = [relation_keys]
        req = self.c.new_request("BlockDataviewRelationDelete")
        req.contextId = set_id
        req.blockId = block_id
        req.relationKeys.extend(relation_keys)
        return self.c.call("BlockDataviewRelationDelete", req)

    # ----- per-view visible columns -------------------------------------------

    def add_view_relation(self, set_id, view_id, relation_key, *,
                          is_visible=True, block_id="dataview"):
        """Add a relation as a column to one view (and set its visibility).

        Use this method to control which relations show as columns in a
        specific view (update_view controls view meta). The relation should
        already be in the block's relation pool (add_relation); if it is not,
        add it first.

        Args:
            set_id: the set/collection object id (contextId).
            view_id: the id of the view to add the column to.
            relation_key: the relation key to show (for example "tag").
            is_visible: whether the column is visible (default True).
            block_id: the dataview block id (default "dataview").

        Returns:
            The raw BlockDataviewViewRelationAdd response message.

        Example:
            views.add_view_relation("bafy_set_id", "view_id_1", "tag")
        """
        req = self.c.new_request("BlockDataviewViewRelationAdd")
        req.contextId = set_id
        req.blockId = block_id
        req.viewId = view_id
        req.relation.key = relation_key
        req.relation.isVisible = bool(is_visible)
        return self.c.call("BlockDataviewViewRelationAdd", req)

    def remove_view_relation(self, set_id, view_id, relation_keys,
                            block_id="dataview"):
        """Remove one or more column relations from a single view.

        Args:
            set_id: the set/collection object id (contextId).
            view_id: the id of the view to remove columns from.
            relation_keys: a relation key string or a list of relation keys.
            block_id: the dataview block id (default "dataview").

        Returns:
            The raw BlockDataviewViewRelationRemove response message.

        Example:
            views.remove_view_relation("bafy_set_id", "view_id_1", "tag")
        """
        if isinstance(relation_keys, str):
            relation_keys = [relation_keys]
        req = self.c.new_request("BlockDataviewViewRelationRemove")
        req.contextId = set_id
        req.blockId = block_id
        req.viewId = view_id
        req.relationKeys.extend(relation_keys)
        return self.c.call("BlockDataviewViewRelationRemove", req)

    def sort_view_relations(self, set_id, view_id, relation_keys,
                           block_id="dataview"):
        """Set the left-to-right order of a view's column relations.

        Pass the full list of relation keys in the order you want them shown.

        Args:
            set_id: the set/collection object id (contextId).
            view_id: the id of the view to reorder.
            relation_keys: the ordered list of relation keys.
            block_id: the dataview block id (default "dataview").

        Returns:
            The raw BlockDataviewViewRelationSort response message.

        Example:
            views.sort_view_relations("bafy_set_id", "view_id_1",
                                     ["name", "tag", "createdDate"])
        """
        req = self.c.new_request("BlockDataviewViewRelationSort")
        req.contextId = set_id
        req.blockId = block_id
        req.viewId = view_id
        req.relationKeys.extend(relation_keys)
        return self.c.call("BlockDataviewViewRelationSort", req)

    # ----- filters ------------------------------------------------------------

    def add_filter(self, set_id, view_id, filter_dict, block_id="dataview"):
        """Add a filter to a view. Returns the new filter id.

        Args:
            set_id: the set/collection object id (contextId).
            view_id: the id of the view to filter.
            filter_dict: a dict describing the filter, parsed into a
                model.Block.Content.Dataview.Filter. Common keys (camelCase):
                "RelationKey" (the relation to filter on), "condition" (a
                Condition enum name like "Equal", "NotEqual", "Like",
                "In", "Empty", "NotEmpty"), and "value" (the comparison
                value). Example:
                {"RelationKey": "tag", "condition": "In", "value": ["work"]}.
            block_id: the dataview block id (default "dataview").

        Returns:
            The id (string) of the created filter.

        Example:
            fid = views.add_filter("bafy_set_id", "view_id_1",
                {"RelationKey": "done", "condition": "Equal", "value": True})
        """
        req = self.c.new_request("BlockDataviewFilterAdd")
        req.contextId = set_id
        req.blockId = block_id
        req.viewId = view_id
        json_format.ParseDict(filter_dict, req.filter)
        resp = self.c.call("BlockDataviewFilterAdd", req)
        return getattr(resp, "filterId", "")

    def remove_filter(self, set_id, view_id, filter_ids, block_id="dataview"):
        """Remove one or more filters from a view by id.

        Args:
            set_id: the set/collection object id (contextId).
            view_id: the id of the view.
            filter_ids: a filter id string or a list of filter ids (the ids
                returned by add_filter, or read from the view's filters list).
            block_id: the dataview block id (default "dataview").

        Returns:
            The raw BlockDataviewFilterRemove response message.

        Example:
            views.remove_filter("bafy_set_id", "view_id_1", fid)
        """
        if isinstance(filter_ids, str):
            filter_ids = [filter_ids]
        req = self.c.new_request("BlockDataviewFilterRemove")
        req.contextId = set_id
        req.blockId = block_id
        req.viewId = view_id
        req.ids.extend(filter_ids)
        return self.c.call("BlockDataviewFilterRemove", req)

    def replace_filter(self, set_id, view_id, filter_id, filter_dict,
                       block_id="dataview"):
        """Replace an existing filter (by id) with a new filter definition.

        Args:
            set_id: the set/collection object id (contextId).
            view_id: the id of the view.
            filter_id: the id of the filter to replace.
            filter_dict: the new filter as a dict (same shape as in add_filter).
            block_id: the dataview block id (default "dataview").

        Returns:
            The id (string) of the new filter.

        Example:
            views.replace_filter("bafy_set_id", "view_id_1", fid,
                {"RelationKey": "done", "condition": "Equal", "value": False})
        """
        req = self.c.new_request("BlockDataviewFilterReplace")
        req.contextId = set_id
        req.blockId = block_id
        req.viewId = view_id
        req.id = filter_id
        json_format.ParseDict(filter_dict, req.filter)
        resp = self.c.call("BlockDataviewFilterReplace", req)
        return getattr(resp, "filterId", "")

    def sort_filters(self, set_id, view_id, filter_ids, block_id="dataview"):
        """Set the order of a view's filters by passing their ids in order.

        This wraps BlockDataviewFilterSort (it reorders filters, it does not
        sort objects; for object sorting use add_sort).

        Args:
            set_id: the set/collection object id (contextId).
            view_id: the id of the view.
            filter_ids: the ordered list of filter ids.
            block_id: the dataview block id (default "dataview").

        Returns:
            The raw BlockDataviewFilterSort response message.

        Example:
            views.sort_filters("bafy_set_id", "view_id_1", [fid_a, fid_b])
        """
        req = self.c.new_request("BlockDataviewFilterSort")
        req.contextId = set_id
        req.blockId = block_id
        req.viewId = view_id
        req.ids.extend(filter_ids)
        return self.c.call("BlockDataviewFilterSort", req)

    # ----- sorts --------------------------------------------------------------

    def add_sort(self, set_id, view_id, sort_dict, block_id="dataview"):
        """Add a sort rule to a view.

        Args:
            set_id: the set/collection object id (contextId).
            view_id: the id of the view.
            sort_dict: a dict describing the sort, parsed into a
                model.Block.Content.Dataview.Sort. Common keys (camelCase):
                "RelationKey" (the relation to sort by) and "type" (a Sort.Type
                enum name: "Asc", "Desc", or "Custom"). Example:
                {"RelationKey": "createdDate", "type": "Desc"}.
            block_id: the dataview block id (default "dataview").

        Returns:
            The raw BlockDataviewSortAdd response message.

        Example:
            views.add_sort("bafy_set_id", "view_id_1",
                {"RelationKey": "name", "type": "Asc"})
        """
        req = self.c.new_request("BlockDataviewSortAdd")
        req.contextId = set_id
        req.blockId = block_id
        req.viewId = view_id
        json_format.ParseDict(sort_dict, req.sort)
        return self.c.call("BlockDataviewSortAdd", req)

    def remove_sort(self, set_id, view_id, sort_ids, block_id="dataview"):
        """Remove one or more sort rules from a view by id.

        Args:
            set_id: the set/collection object id (contextId).
            view_id: the id of the view.
            sort_ids: a sort id string or a list of sort ids (read the ids from
                the view's sorts list; a Sort's id is its "id" field).
            block_id: the dataview block id (default "dataview").

        Returns:
            The raw BlockDataviewSortRemove response message.

        Example:
            views.remove_sort("bafy_set_id", "view_id_1", "sort_id_1")
        """
        if isinstance(sort_ids, str):
            sort_ids = [sort_ids]
        req = self.c.new_request("BlockDataviewSortRemove")
        req.contextId = set_id
        req.blockId = block_id
        req.viewId = view_id
        req.ids.extend(sort_ids)
        return self.c.call("BlockDataviewSortRemove", req)

    def replace_sort(self, set_id, view_id, sort_id, sort_dict,
                     block_id="dataview"):
        """Replace an existing sort rule (by id) with a new sort definition.

        Args:
            set_id: the set/collection object id (contextId).
            view_id: the id of the view.
            sort_id: the id of the sort to replace.
            sort_dict: the new sort as a dict (same shape as in add_sort).
            block_id: the dataview block id (default "dataview").

        Returns:
            The raw BlockDataviewSortReplace response message.

        Example:
            views.replace_sort("bafy_set_id", "view_id_1", "sort_id_1",
                {"RelationKey": "name", "type": "Desc"})
        """
        req = self.c.new_request("BlockDataviewSortReplace")
        req.contextId = set_id
        req.blockId = block_id
        req.viewId = view_id
        req.id = sort_id
        json_format.ParseDict(sort_dict, req.sort)
        return self.c.call("BlockDataviewSortReplace", req)

    def sort_sorts(self, set_id, view_id, sort_ids, block_id="dataview"):
        """Set the precedence order of a view's sort rules by their ids.

        This wraps BlockDataviewSortSort, which reorders the existing sort
        rules (the first id has the highest precedence).

        Args:
            set_id: the set/collection object id (contextId).
            view_id: the id of the view.
            sort_ids: the ordered list of sort ids.
            block_id: the dataview block id (default "dataview").

        Returns:
            The raw BlockDataviewSortSort response message.

        Example:
            views.sort_sorts("bafy_set_id", "view_id_1", ["sort_b", "sort_a"])
        """
        req = self.c.new_request("BlockDataviewSortSort")
        req.contextId = set_id
        req.blockId = block_id
        req.viewId = view_id
        req.ids.extend(sort_ids)
        return self.c.call("BlockDataviewSortSort", req)

    # ----- source and detach --------------------------------------------------

    def set_source(self, set_id, source, block_id="dataview"):
        """Set the source of the dataview block (what a query set selects).

        For a query set, the source is the list of type ids (or relation ids)
        the set queries over. Changing it changes which objects the set shows.

        Args:
            set_id: the set object id (contextId).
            source: a source id string or a list of source ids (type/relation
                ids). Pass an empty list to clear the source.
            block_id: the dataview block id (default "dataview").

        Returns:
            The raw BlockDataviewSetSource response message.

        Example:
            views.set_source("bafy_set_id", ["ot_page_type_id"])
        """
        if isinstance(source, str):
            source = [source]
        req = self.c.new_request("BlockDataviewSetSource")
        req.contextId = set_id
        req.blockId = block_id
        req.source.extend(source)
        return self.c.call("BlockDataviewSetSource", req)

    def create_from_existing_object(self, context_id, target_object_id,
                                    block_id="dataview"):
        """Point an inline dataview block at an existing set/collection object.

        This wraps BlockDataviewCreateFromExistingObject: it makes the dataview
        block in ``context_id`` mirror the views of ``target_object_id``.

        Args:
            context_id: the object that contains the dataview block.
            target_object_id: the existing set/collection object whose views to
                use.
            block_id: the dataview block id in context_id (default "dataview").

        Returns:
            The BlockDataviewCreateFromExistingObject response as a dict, which
            includes the resulting blockId, targetObjectId, and the view list.

        Example:
            views.create_from_existing_object("bafy_page_id", "bafy_set_id")
        """
        req = self.c.new_request("BlockDataviewCreateFromExistingObject")
        req.contextId = context_id
        req.blockId = block_id
        req.targetObjectId = target_object_id
        return self.c.call_dict("BlockDataviewCreateFromExistingObject", req)

    # ----- high-level helpers -------------------------------------------------

    def set_view_type(self, set_id, view_type, view_id=None, *,
                      block_id="dataview", space_id=None):
        """Change a view's display type, by name.

        Args:
            set_id: the set/collection object id.
            view_type: one of "Gallery", "Table", "List", "Kanban",
                "Calendar", "Graph".
            view_id: the view to change. If None, the first view of the block
                is used (looked up with list_views).
            block_id: the dataview block id (default "dataview").
            space_id: the space id (only used when view_id is None, to look up
                the first view); defaults to the client default space.

        Returns:
            The raw BlockDataviewViewUpdate response message.

        Example:
            views.set_view_type("bafy_set_id", "Gallery")
        """
        if view_id is None:
            view_id = self._first_view_id(set_id, block_id, space_id)
        return self.update_view(set_id, view_id, block_id=block_id,
                                view_type=view_type)

    def set_visible_columns(self, set_id, relation_keys, view_id=None, *,
                           block_id="dataview", space_id=None):
        """Set exactly which relations show as columns in a view, in order.

        This adds each relation as a visible view column (BlockDataviewView
        RelationAdd) and then sets their left-to-right order (BlockDataview
        ViewRelationSort). It does not remove columns that are already present
        and not in your list; remove those with remove_view_relation if needed.
        Relations should also be in the block relation pool (add_relation).

        Args:
            set_id: the set/collection object id.
            relation_keys: the ordered list of relation keys to show as columns.
            view_id: the view to change. If None, the first view is used.
            block_id: the dataview block id (default "dataview").
            space_id: the space id (used when view_id is None); defaults to the
                client default space.

        Returns:
            The raw BlockDataviewViewRelationSort response message (the final
            ordering call).

        Example:
            views.set_visible_columns("bafy_set_id",
                ["name", "tag", "createdDate"])
        """
        if view_id is None:
            view_id = self._first_view_id(set_id, block_id, space_id)
        for key in relation_keys:
            self.add_view_relation(set_id, view_id, key, is_visible=True,
                                   block_id=block_id)
        return self.sort_view_relations(set_id, view_id, list(relation_keys),
                                        block_id=block_id)

    def set_gallery_cover(self, set_id, relation_key, view_id=None, *,
                         cover_fit=True, block_id="dataview", space_id=None):
        """Set the relation used as the gallery card cover (and fit).

        A gallery's cards take their cover image from a relation, a property
        that holds an image or file. This sets the view's coverRelationKey (and
        coverFit). Use a relation that holds an image or file, for example
        "picture" or "cover".

        Args:
            set_id: the set/collection object id.
            relation_key: the relation key to use for the cover (for example
                "picture").
            view_id: the gallery view to change. If None, the first view is used.
            cover_fit: if True the image fits the card (default True).
            block_id: the dataview block id (default "dataview").
            space_id: the space id (used when view_id is None); defaults to the
                client default space.

        Returns:
            The raw BlockDataviewViewUpdate response message.

        Example:
            views.set_gallery_cover("bafy_set_id", "picture")
        """
        if view_id is None:
            view_id = self._first_view_id(set_id, block_id, space_id)
        return self.update_view(set_id, view_id, block_id=block_id,
                                cover_relation_key=relation_key,
                                cover_fit=cover_fit)

    def _first_view_id(self, set_id, block_id, space_id):
        """Return the id of the first view of the block, or raise if none."""
        views = self.list_views(set_id, block_id=block_id, space_id=space_id)
        if not views:
            from .errors import AnytypeError
            raise AnytypeError(
                f"no views found on block {block_id!r} of object {set_id!r}; "
                "pass an explicit view_id"
            )
        return views[0].get("id", "")
