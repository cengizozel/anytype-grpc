"""The objects domain: create, open, edit details, convert, import, and export objects.

This module wraps the Object.* RPCs of the Anytype gRPC service into one class,
``Objects``, built around a connected ``Anytype`` client. It covers the full
lifecycle of an object: creation (plain object, set, bookmark, from a URL),
opening and closing, editing details (properties), changing layout, type, and
source, duplicating, archiving, favoriting, deleting, converting to a set or a
collection, importing from external formats, exporting, and reading the object
graph. It also includes ``set_cover`` and ``set_icon`` helpers.

Construct it with a client:

    import anytype_grpc
    from anytype_grpc.objects import Objects
    at = anytype_grpc.Anytype()
    objects = Objects(at)
    new_id = objects.create("ot-page", details={"name": "My page"})

Notes that matter:

- Object "details" are the object's properties (relations). Plain Python values
  (str, number, bool, list, dict, None) are accepted and converted for you.
- An object type is identified by its "unique key" (for example "ot-page",
  "ot-note", "ot-bookmark"), not its object id. The type's unique key is what
  the create and set-type calls expect.
- You cannot add blocks to a Type or a Set object (the server replies
  "restricted: Blocks"). Edit those through details instead.
- The image cover of an object is set by two details: coverType=1 and
  coverId=<file object id>. Use ``set_cover`` for that. The icon is set by the
  ``iconImage`` detail (an uploaded file object id) or the ``iconEmoji`` detail
  (a single emoji string). Use ``set_icon`` for that.
"""

from google.protobuf import json_format

from .client import _to_value


# Object layout names accepted by set_layout, mapped for clarity in the docs.
# These are the names of the anytype.model.ObjectType.Layout enum.
_LAYOUT_NAMES = (
    "basic", "profile", "todo", "set", "objectType", "relation", "file",
    "dashboard", "image", "note", "space", "bookmark", "relationOptionsList",
    "relationOption", "collection", "audio", "video", "date", "spaceView",
    "participant", "pdf", "tag",
)

# Export format names accepted by list_export (anytype.model.Export.Format).
_EXPORT_FORMATS = ("Markdown", "Protobuf", "JSON", "DOT", "SVG", "GRAPH_JSON")


class Objects:
    """Object lifecycle and details for one Anytype space.

    Built around a connected ``Anytype`` client. Every method that needs a space
    falls back to the client's default space (``ANYTYPE_SPACE_ID``) when you do
    not pass ``space_id``. Methods raise ``RpcError`` on a non-zero server error
    unless you pass ``check=False`` through to the underlying call.
    """

    def __init__(self, client):
        """Store the client.

        Args:
            client: a connected ``anytype_grpc.Anytype`` instance.
        """
        self.c = client

    # ----- internal helpers ---------------------------------------------------

    def _space(self, space_id):
        """Resolve the space id, falling back to the client default."""
        return self.c._space(space_id)

    def _set_struct(self, req, details):
        """Fill a request's ``details`` Struct field from a Python dict.

        ``details`` may be None (leaves the field empty) or a dict of
        {relation_key: python_value}. Used by the create-family RPCs whose
        ``details`` field is a google.protobuf.Struct.
        """
        if details:
            for key, value in details.items():
                req.details.fields[key].CopyFrom(_to_value(value))

    def _fill_details_list(self, req, details):
        """Fill a request's repeated ``Detail`` field from a Python dict.

        Used by SetDetails and ListSetDetails whose ``details`` field is a
        repeated anytype.model.Detail (each has ``key`` and ``value``).
        """
        for key, value in details.items():
            d = req.details.add()
            d.key = key
            d.value.CopyFrom(_to_value(value))

    @staticmethod
    def _enum(req, field, name):
        """Resolve an enum value number by its name for a request field."""
        return req.DESCRIPTOR.fields_by_name[field].enum_type.values_by_name[name].number

    # ----- creation -----------------------------------------------------------

    def create(self, type_unique_key, details=None, template_id=None,
               space_id=None, with_chat=False):
        """Create a new object and return its new object id.

        Args:
            type_unique_key: the object type's unique key, for example "ot-page",
                "ot-note", or a custom type's key. This is not the type's object
                id.
            details: optional dict of {relation_key: value} to set on the new
                object, for example {"name": "My page"}. Values are plain Python
                types. None means no initial details.
            template_id: optional id of a template object to apply on creation.
                None means no template.
            space_id: the space to create in. Defaults to the client default.
            with_chat: if True, create the object with an attached chat.

        Returns:
            The new object's id as a string.

        Example:
            new_id = objects.create("ot-page", details={"name": "Notes"})
        """
        # Type unique keys have the form "ot-<name>" (for example "ot-page"). As a
        # convenience, a bare bundled name like "page" is normalized to "ot-page".
        key = type_unique_key
        if key and not key.startswith("ot-") and "-" not in key and len(key) <= 30:
            key = "ot-" + key
        req = self.c.new_request("ObjectCreate")
        req.spaceId = self._space(space_id)
        req.objectTypeUniqueKey = key
        if template_id:
            req.templateId = template_id
        if with_chat:
            req.withChat = True
        self._set_struct(req, details)
        return self.c.call("ObjectCreate", req).objectId

    def create_set(self, source, details=None, template_id=None, space_id=None,
                   with_chat=False):
        """Create a Set object that auto-collects objects of given types.

        A Set is a live query over a space: its "source" is a list of object type
        ids (or relation ids) that define which objects appear in it.

        Args:
            source: a list of object type ids (or relation ids) the set queries.
                Pass a single string and it will be wrapped in a list.
            details: optional dict of {relation_key: value}, for example
                {"name": "All tasks"}. None means the set is named after the type.
            template_id: optional template id to apply. None means no template.
            space_id: the space to create in. Defaults to the client default.
            with_chat: if True, create the set with an attached chat.

        Returns:
            The new set object's id as a string.

        Example:
            set_id = objects.create_set([task_type_id], details={"name": "Tasks"})
        """
        if isinstance(source, str):
            source = [source]
        req = self.c.new_request("ObjectCreateSet")
        req.spaceId = self._space(space_id)
        req.source.extend(source)
        if template_id:
            req.templateId = template_id
        if with_chat:
            req.withChat = True
        self._set_struct(req, details)
        return self.c.call("ObjectCreateSet", req).objectId

    def create_bookmark(self, url=None, details=None, template_id=None,
                        space_id=None, with_chat=False):
        """Create a Bookmark object, optionally seeded with a source URL.

        The bookmark's URL is carried in details under the "source" relation key.
        Pass ``url`` for convenience and it is merged into details as "source".

        Args:
            url: the web address to bookmark. Optional if you set "source" in
                details yourself. None means no URL is set here.
            details: optional dict of {relation_key: value}. Merged with ``url``.
            template_id: optional template id to apply. None means no template.
            space_id: the space to create in. Defaults to the client default.
            with_chat: if True, create the bookmark with an attached chat.

        Returns:
            The new bookmark object's id as a string.

        Example:
            bm_id = objects.create_bookmark(url="https://anytype.io")
        """
        merged = dict(details) if details else {}
        if url is not None:
            merged.setdefault("source", url)
        req = self.c.new_request("ObjectCreateBookmark")
        req.spaceId = self._space(space_id)
        if template_id:
            req.templateId = template_id
        if with_chat:
            req.withChat = True
        self._set_struct(req, merged)
        return self.c.call("ObjectCreateBookmark", req).objectId

    def create_from_url(self, url, type_unique_key, details=None,
                        add_page_content=False, template_id=None, space_id=None,
                        with_chat=False):
        """Create an object from a web URL (fetches and parses the page).

        Useful for turning an article URL into an object of a chosen type. With
        ``add_page_content`` the fetched page body is added as blocks.

        Args:
            url: the web address to fetch and create from.
            type_unique_key: the object type's unique key, for example "ot-page".
            details: optional dict of {relation_key: value} to set in addition.
            add_page_content: if True, add the fetched page content as blocks.
            template_id: optional template id to apply. None means no template.
            space_id: the space to create in. Defaults to the client default.
            with_chat: if True, create the object with an attached chat.

        Returns:
            The new object's id as a string.

        Example:
            oid = objects.create_from_url("https://example.com", "ot-page",
                                          add_page_content=True)
        """
        req = self.c.new_request("ObjectCreateFromUrl")
        req.spaceId = self._space(space_id)
        req.objectTypeUniqueKey = type_unique_key
        req.url = url
        if add_page_content:
            req.addPageContent = True
        if template_id:
            req.templateId = template_id
        if with_chat:
            req.withChat = True
        self._set_struct(req, details)
        return self.c.call("ObjectCreateFromUrl", req).objectId

    # ----- open / show / close ------------------------------------------------

    def show(self, object_id, space_id=None, trace_id=None):
        """Open an object and return its full view as a dict (blocks + details).

        ``show`` and ``open`` send the same data; ``show`` is the read-oriented
        name and is the usual way to fetch an object's blocks and properties.

        Args:
            object_id: the id of the object to view.
            space_id: the object's space. Defaults to the client default. Only
                strictly required for date objects.
            trace_id: optional client trace id for debugging. None to omit.

        Returns:
            A dict with the object view (keys like "objectView" holding "blocks"
            and "details").

        Example:
            view = objects.show(object_id)
        """
        req = self.c.new_request("ObjectShow")
        req.objectId = object_id
        if space_id or self.c.default_space:
            req.spaceId = self._space(space_id)
        if trace_id:
            req.traceId = trace_id
        return self.c.to_dict(self.c.call("ObjectShow", req))

    def open(self, object_id, space_id=None, trace_id=None):
        """Open an object for editing and return its view as a dict.

        Same payload as ``show``. Open establishes the editing session the
        desktop app uses; for plain reads ``show`` is enough.

        Args:
            object_id: the id of the object to open.
            space_id: the object's space. Defaults to the client default. Only
                strictly required for date objects.
            trace_id: optional client trace id for debugging. None to omit.

        Returns:
            A dict with the object view.

        Example:
            view = objects.open(object_id)
        """
        req = self.c.new_request("ObjectOpen")
        req.objectId = object_id
        if space_id or self.c.default_space:
            req.spaceId = self._space(space_id)
        if trace_id:
            req.traceId = trace_id
        return self.c.to_dict(self.c.call("ObjectOpen", req))

    def close(self, object_id, space_id=None):
        """Close an object that was opened (releases the editing session).

        Args:
            object_id: the id of the object to close.
            space_id: the object's space. Defaults to the client default. Only
                strictly required for date objects.

        Returns:
            The raw close response message.

        Example:
            objects.close(object_id)
        """
        req = self.c.new_request("ObjectClose")
        req.objectId = object_id
        if space_id or self.c.default_space:
            req.spaceId = self._space(space_id)
        return self.c.call("ObjectClose", req)

    # ----- details ------------------------------------------------------------

    def set_details(self, object_id, details):
        """Set one or more detail (property) values on a single object.

        Args:
            object_id: the id of the object to edit.
            details: a dict of {relation_key: value}. Values are plain Python
                types (str, number, bool, list, dict, None). To clear a value,
                pass None for that key.

        Returns:
            The raw set-details response message.

        Example:
            objects.set_details(oid, {"name": "Renamed", "done": True})
        """
        req = self.c.new_request("ObjectSetDetails")
        req.contextId = object_id
        self._fill_details_list(req, details)
        return self.c.call("ObjectSetDetails", req)

    def list_set_details(self, object_ids, details):
        """Set the same detail values on many objects at once.

        Args:
            object_ids: a list of object ids to edit. A single string is wrapped
                in a list.
            details: a dict of {relation_key: value} applied to every object.
                Values are plain Python types.

        Returns:
            The raw response message.

        Example:
            objects.list_set_details([a, b, c], {"done": True})
        """
        if isinstance(object_ids, str):
            object_ids = [object_ids]
        req = self.c.new_request("ObjectListSetDetails")
        req.objectIds.extend(object_ids)
        self._fill_details_list(req, details)
        return self.c.call("ObjectListSetDetails", req)

    def set_cover(self, object_id, file_object_id, x=0.0, y=0.0):
        """Set an uploaded image file as an object's cover.

        This sets the two details that make up an image cover: coverType=1 and
        coverId=<file object id>. The file object id is what ``upload_file``
        returns on the client.

        Args:
            object_id: the id of the object to edit.
            file_object_id: the id of an uploaded image file object.
            x: horizontal focus offset of the cover, a float (default 0.0).
            y: vertical focus offset of the cover, a float (default 0.0).

        Returns:
            The raw set-details response message.

        Example:
            fid = at.upload_file(url="http://127.0.0.1:8000/cover.jpg")
            objects.set_cover(oid, fid)
        """
        return self.set_details(
            object_id,
            {"coverType": 1, "coverId": file_object_id, "coverX": x, "coverY": y},
        )

    def set_icon(self, object_id, emoji=None, file_object_id=None):
        """Set an object's icon to an emoji or to an uploaded image file.

        Pass exactly one of ``emoji`` or ``file_object_id``. Setting one clears
        the other so the chosen icon shows.

        Args:
            object_id: the id of the object to edit.
            emoji: a single emoji string, for example "star". None to skip.
            file_object_id: the id of an uploaded image file object to use as the
                icon. None to skip.

        Returns:
            The raw set-details response message.

        Example:
            objects.set_icon(oid, emoji="rocket")
            objects.set_icon(oid, file_object_id=fid)
        """
        if (emoji is None) == (file_object_id is None):
            raise ValueError("pass exactly one of emoji or file_object_id")
        if emoji is not None:
            details = {"iconEmoji": emoji, "iconImage": ""}
        else:
            details = {"iconImage": file_object_id, "iconEmoji": ""}
        return self.set_details(object_id, details)

    # ----- layout / type / source ---------------------------------------------

    def set_layout(self, object_id, layout):
        """Set an object's layout (its visual presentation).

        Args:
            object_id: the id of the object to edit.
            layout: the layout name (a string) or its enum number. Common names:
                "basic", "profile", "todo", "note", "set", "collection",
                "bookmark", "image", "file", "audio", "video", "date", "tag".
                See the module's full list for all values.

        Returns:
            The raw set-layout response message.

        Example:
            objects.set_layout(oid, "note")
        """
        req = self.c.new_request("ObjectSetLayout")
        req.contextId = object_id
        if isinstance(layout, str):
            layout = self._enum(req, "layout", layout)
        req.layout = layout
        return self.c.call("ObjectSetLayout", req)

    def set_object_type(self, object_id, type_unique_key):
        """Change a single object's type.

        Args:
            object_id: the id of the object to edit.
            type_unique_key: the new object type's unique key, for example
                "ot-note" (not the type's object id).

        Returns:
            The raw response message.

        Example:
            objects.set_object_type(oid, "ot-note")
        """
        req = self.c.new_request("ObjectSetObjectType")
        req.contextId = object_id
        req.objectTypeUniqueKey = type_unique_key
        return self.c.call("ObjectSetObjectType", req)

    def set_source(self, object_id, source):
        """Set the source query of a Set object (which types/relations it shows).

        Args:
            object_id: the id of the Set object to edit.
            source: a list of object type ids (or relation ids). A single string
                is wrapped in a list.

        Returns:
            The raw response message.

        Example:
            objects.set_source(set_id, [task_type_id])
        """
        if isinstance(source, str):
            source = [source]
        req = self.c.new_request("ObjectSetSource")
        req.contextId = object_id
        req.source.extend(source)
        return self.c.call("ObjectSetSource", req)

    # ----- duplicate / archive / favorite / delete ----------------------------

    def duplicate(self, object_id):
        """Duplicate an object and return the new object's id.

        Args:
            object_id: the id of the object to duplicate.

        Returns:
            The new (duplicated) object's id as a string.

        Example:
            copy_id = objects.duplicate(oid)
        """
        return self.c.call("ObjectDuplicate", contextId=object_id).id

    def list_delete(self, object_ids):
        """Permanently delete objects (not the bin; this removes them).

        This deletes the objects from the local store and unsubscribes from
        remote changes. To move objects to the bin instead, use
        ``set_archived(ids, True)``.

        Args:
            object_ids: a list of object ids to delete. A single string is
                wrapped in a list.

        Returns:
            The raw response message.

        Example:
            objects.list_delete([oid1, oid2])
        """
        if isinstance(object_ids, str):
            object_ids = [object_ids]
        req = self.c.new_request("ObjectListDelete")
        req.objectIds.extend(object_ids)
        return self.c.call("ObjectListDelete", req)

    def set_archived(self, object_ids, archived=True):
        """Move objects to the bin (archive) or restore them.

        Args:
            object_ids: a list of object ids. A single string is wrapped in a
                list.
            archived: True to move to the bin (default), False to restore.

        Returns:
            The raw response message.

        Example:
            objects.set_archived([oid], True)   # to bin
            objects.set_archived([oid], False)  # restore
        """
        if isinstance(object_ids, str):
            object_ids = [object_ids]
        req = self.c.new_request("ObjectListSetIsArchived")
        req.objectIds.extend(object_ids)
        req.isArchived = archived
        return self.c.call("ObjectListSetIsArchived", req)

    def set_favorite(self, object_ids, favorite=True):
        """Add objects to favorites or remove them.

        Args:
            object_ids: a list of object ids. A single string is wrapped in a
                list.
            favorite: True to favorite (default), False to unfavorite.

        Returns:
            The raw response message.

        Example:
            objects.set_favorite([oid], True)
        """
        if isinstance(object_ids, str):
            object_ids = [object_ids]
        req = self.c.new_request("ObjectListSetIsFavorite")
        req.objectIds.extend(object_ids)
        req.isFavorite = favorite
        return self.c.call("ObjectListSetIsFavorite", req)

    # ----- convert ------------------------------------------------------------

    def to_set(self, object_id, source):
        """Convert an existing object into a Set with the given source.

        Args:
            object_id: the id of the object to convert.
            source: a list of object type ids (or relation ids) the set queries.
                A single string is wrapped in a list.

        Returns:
            The raw response message.

        Example:
            objects.to_set(oid, [task_type_id])
        """
        if isinstance(source, str):
            source = [source]
        req = self.c.new_request("ObjectToSet")
        req.contextId = object_id
        req.source.extend(source)
        return self.c.call("ObjectToSet", req)

    def to_collection(self, object_id):
        """Convert an existing object into a Collection.

        A Collection is a manually curated list of objects (unlike a Set, which
        is a live query).

        Args:
            object_id: the id of the object to convert.

        Returns:
            The raw response message.

        Example:
            objects.to_collection(oid)
        """
        return self.c.call("ObjectToCollection", contextId=object_id)

    # ----- import / export / graph --------------------------------------------

    def import_markdown(self, paths, space_id=None, no_collection=False,
                        create_directory_pages=False,
                        include_properties_as_block=False,
                        update_existing=False, no_progress=True):
        """Import one or more Markdown files or folders into the space.

        This wraps ObjectImport with markdown params. For other formats (Notion,
        HTML, CSV, and so on) build the request directly with
        ``at.new_request("ObjectImport")`` and set the matching oneof params.

        Args:
            paths: a list of filesystem paths to Markdown files or folders. A
                single string is wrapped in a list.
            space_id: the space to import into. Defaults to the client default.
            no_collection: if True, do not wrap imported files in a collection.
            create_directory_pages: if True, create a page per source directory.
            include_properties_as_block: if True, render frontmatter properties
                as a block instead of object relations.
            update_existing: if True, update objects that already exist instead
                of creating duplicates.
            no_progress: if True (default), suppress progress events.

        Returns:
            The raw import response message.

        Example:
            objects.import_markdown(["/home/me/notes"])
        """
        if isinstance(paths, str):
            paths = [paths]
        req = self.c.new_request("ObjectImport")
        req.spaceId = self._space(space_id)
        req.markdownParams.path.extend(paths)
        if create_directory_pages:
            req.markdownParams.createDirectoryPages = True
        if include_properties_as_block:
            req.markdownParams.includePropertiesAsBlock = True
        if no_collection:
            req.markdownParams.noCollection = True
        # anytype.model.Import.Type: Markdown = 1.
        req.type = req.DESCRIPTOR.fields_by_name["type"].enum_type.values_by_name["Markdown"].number
        if update_existing:
            req.updateExistingObjects = True
        if no_progress:
            req.noProgress = True
        return self.c.call("ObjectImport", req)

    def list_export(self, path, object_ids=None, format="Markdown", zip=False,
                    include_nested=True, include_files=True,
                    include_archived=False, space_id=None, no_progress=True):
        """Export objects to a folder on disk and return the export response.

        Args:
            path: the destination directory where files are written.
            object_ids: optional list of object ids to export. Empty or None
                means export all available objects. A single string is wrapped
                in a list.
            format: the export format name. One of "Markdown" (default),
                "Protobuf", "JSON", "DOT", "SVG", "GRAPH_JSON".
            zip: if True, write a single zip file instead of loose files.
            include_nested: if True (default), include linked/nested objects.
            include_files: if True (default), include attached files.
            include_archived: if True, also export archived objects.
            space_id: the space to export from. Defaults to the client default.
            no_progress: if True (default), suppress progress events.

        Returns:
            The raw export response message (its ``path`` is the output path and
            ``succeed`` is the number of exported objects).

        Example:
            resp = objects.list_export("/home/me/out", format="Markdown")
            print(resp.path, resp.succeed)
        """
        req = self.c.new_request("ObjectListExport")
        req.spaceId = self._space(space_id)
        req.path = path
        if object_ids:
            if isinstance(object_ids, str):
                object_ids = [object_ids]
            req.objectIds.extend(object_ids)
        req.format = req.DESCRIPTOR.fields_by_name["format"].enum_type.values_by_name[format].number
        if zip:
            req.zip = True
        if include_nested:
            req.includeNested = True
        if include_files:
            req.includeFiles = True
        if include_archived:
            req.includeArchived = True
        if no_progress:
            req.noProgress = True
        return self.c.call("ObjectListExport", req)

    def graph(self, space_id=None, keys=None, limit=0, collection_id=None,
              include_type_edges=False):
        """Return the object graph (nodes and edges) of a space as a dict.

        The graph is the set of objects (nodes) and the links and relations
        between them (edges). Useful for analysis and visualization.

        Args:
            space_id: the space to read. Defaults to the client default.
            keys: optional list of relation keys to include per node. None
                returns the server default set.
            limit: max number of nodes (0 means no limit).
            collection_id: optional collection id to scope the graph to.
            include_type_edges: if True, include edges from objects to their
                types.

        Returns:
            A dict with "nodes" (a list of object detail structs) and "edges" (a
            list of {source, target, name, type, ...}).

        Example:
            g = objects.graph()
            print(len(g.get("nodes", [])), len(g.get("edges", [])))
        """
        req = self.c.new_request("ObjectGraph")
        req.spaceId = self._space(space_id)
        if keys:
            req.keys.extend(keys)
        if limit:
            req.limit = limit
        if collection_id:
            req.collectionId = collection_id
        if include_type_edges:
            req.includeTypeEdges = True
        return self.c.to_dict(self.c.call("ObjectGraph", req))
