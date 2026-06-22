"""The files domain: upload, download, offload, and disk-usage of file objects.

In Anytype every uploaded file or image becomes its own object (a "file object")
with an id. Blocks, covers, and relations then point at that id. This module wraps
the file-level RPCs so you can:

- upload a file or image (by URL or local path) and get back its file object id,
- upload an image and set it as another object's cover in one call,
- download a file object back to a local path,
- free local disk by offloading file content (it stays in the network),
- read how much storage a space or the whole node is using.

Two hard-won gotchas about uploading, encoded here and worth repeating:

1. The desktop helper process that performs the upload is sandboxed. It often
   cannot read arbitrary local paths (for example anything under /tmp), so a
   localPath upload can silently fail or be denied.
2. Fetching a hotlink-protected remote URL from the helper can return HTTP 403.

The reliable route for both cases is to serve the bytes yourself over
http://127.0.0.1 (a tiny local web server) and pass that URL as ``url``. See
``serving_workaround`` at the bottom of this docstring and the example in
``upload``.
"""


class Files:
    """Files and images: upload, download, offload, and usage stats.

    Construct with a connected client:

        from anytype_grpc import Anytype
        from anytype_grpc.files import Files
        at = Anytype()
        files = Files(at)

    Every method that needs a space falls back to the client default space
    (``ANYTYPE_SPACE_ID`` or the ``space_id`` you passed to ``Anytype``) when you
    do not pass ``space_id``.
    """

    # File content type enum, from anytype.model.Block.Content.File.Type.
    # Pass one of these strings as ``kind`` to ``upload``.
    KINDS = ("None", "File", "Image", "Video", "Audio", "PDF")

    def __init__(self, client):
        self.c = client

    # ----- internal helpers ---------------------------------------------------

    def _space(self, space_id):
        """Resolve a space id, falling back to the client default. Internal."""
        return self.c._space(space_id)

    @staticmethod
    def _set_enum(req, field_name, value_name):
        """Set an enum field on ``req`` by its symbolic name. Internal."""
        field = req.DESCRIPTOR.fields_by_name[field_name]
        number = field.enum_type.values_by_name[value_name].number
        setattr(req, field_name, number)

    # ----- upload -------------------------------------------------------------

    def upload(self, url=None, local_path=None, kind="Image", space_id=None,
               details=None):
        """Upload a file or image and return its file object id (a string).

        Provide exactly one source: ``url`` or ``local_path``.

        Args:
            url: a URL to fetch the bytes from. Prefer a local
                http://127.0.0.1 URL you serve yourself (see the module
                docstring); remote hotlink-protected URLs can return HTTP 403.
            local_path: an absolute path on disk. Note the desktop helper is
                sandboxed and may be unable to read paths like /tmp; if a
                local_path upload fails, serve the file over http://127.0.0.1
                and pass it as ``url`` instead.
            kind: the file content type, one of "None", "File", "Image",
                "Video", "Audio", "PDF". Default "Image". Use "File" for a
                generic attachment.
            space_id: the space to upload into; defaults to the client default.
            details: optional dict of extra object details to set on the new
                file object, for example {"name": "My picture"}. Values are
                plain Python types.

        Returns:
            The file object id as a string. Use it as a cover id, a relation
            value, or a block target.

        Example:
            # Reliable route: serve the file locally, then upload by URL.
            #   python -m http.server 8000 --directory /path/to/dir --bind 127.0.0.1
            files = Files(at)
            file_id = files.upload(url="http://127.0.0.1:8000/photo.jpg",
                                   kind="Image")
            print(file_id)
        """
        if bool(url) == bool(local_path):
            from .errors import AnytypeError
            raise AnytypeError("upload needs exactly one of url or local_path")
        req = self.c.new_request("FileUpload")
        req.spaceId = self._space(space_id)
        if url:
            req.url = url
        if local_path:
            req.localPath = local_path
        if kind:
            self._set_enum(req, "type", kind)
        if details:
            from .client import _to_value
            for key, value in details.items():
                req.details.fields[key].CopyFrom(_to_value(value))
        resp = self.c.call("FileUpload", req)
        return getattr(resp, "objectId", "")

    def upload_image(self, url_or_path, space_id=None, details=None):
        """Upload an image and return its file object id (a string).

        A thin convenience over ``upload`` with kind="Image". The single
        argument is treated as a URL if it looks like one (starts with
        "http://" or "https://"), otherwise as a local path.

        Args:
            url_or_path: an http(s) URL or an absolute local path to the image.
                Prefer a http://127.0.0.1 URL you serve yourself; see ``upload``.
            space_id: the space to upload into; defaults to the client default.
            details: optional dict of extra details to set, for example
                {"name": "Cover"}.

        Returns:
            The image file object id as a string.

        Example:
            file_id = Files(at).upload_image("http://127.0.0.1:8000/cover.png")
        """
        is_url = isinstance(url_or_path, str) and url_or_path.startswith(
            ("http://", "https://"))
        return self.upload(
            url=url_or_path if is_url else None,
            local_path=None if is_url else url_or_path,
            kind="Image", space_id=space_id, details=details)

    def upload_cover(self, object_id, url_or_path, x=0.0, y=0.0, space_id=None):
        """Upload an image and set it as ``object_id``'s cover, in one call.

        This uploads the image as a file object, then sets the target object's
        details coverType=1 and coverId=<file object id> (the proven way to put
        an image cover on a page or object).

        Args:
            object_id: the object (page) to give the cover to.
            url_or_path: an http(s) URL or an absolute local path to the image.
                Prefer a http://127.0.0.1 URL you serve yourself; see ``upload``.
            x: horizontal cover offset as a float, default 0.0.
            y: vertical cover offset as a float, default 0.0.
            space_id: the space; defaults to the client default. Note the image
                is uploaded into this space and the cover is set on object_id.

        Returns:
            The file object id of the uploaded image (a string).

        Example:
            file_id = Files(at).upload_cover(page_id,
                "http://127.0.0.1:8000/banner.jpg")
        """
        file_id = self.upload_image(url_or_path, space_id=space_id)
        self.c.set_cover(object_id, file_id, x=x, y=y, space_id=space_id)
        return file_id

    # ----- download -----------------------------------------------------------

    def download(self, object_id, path=""):
        """Download a file object to local disk and return the saved path.

        Args:
            object_id: the file object id (as returned by ``upload``).
            path: absolute local path to save to. If empty, the app saves to a
                temp directory and returns that path. Note the sandbox caveats:
                the helper may not be able to write to every location.

        Returns:
            The local path the file was written to, as a string.

        Example:
            saved = Files(at).download(file_id, "/home/me/out.jpg")
            print(saved)
        """
        resp = self.c.call("FileDownload", objectId=object_id, path=path)
        return getattr(resp, "localPath", "")

    # ----- offload (free local disk) ------------------------------------------

    def offload(self, object_ids, include_not_pinned=False):
        """Offload specific file objects: drop their local copies to free disk.

        The file content stays in the Anytype network and is re-fetched on
        demand. This wraps FileListOffload restricted to the ids you pass.

        Args:
            object_ids: one file object id (string) or a list of them.
            include_not_pinned: if True, also offload files that are not yet
                pinned (fully synced). Default False, the safe choice.

        Returns:
            A dict {"filesOffloaded": int, "bytesOffloaded": int} describing how
            much was freed.

        Example:
            result = Files(at).offload([file_id])
            print(result["bytesOffloaded"])
        """
        if isinstance(object_ids, str):
            object_ids = [object_ids]
        req = self.c.new_request("FileListOffload")
        req.onlyIds.extend(object_ids)
        req.includeNotPinned = include_not_pinned
        resp = self.c.call("FileListOffload", req)
        return {"filesOffloaded": getattr(resp, "filesOffloaded", 0),
                "bytesOffloaded": getattr(resp, "bytesOffloaded", 0)}

    def offload_all(self, include_not_pinned=False):
        """Offload all file objects across all spaces to free local disk.

        Same as ``offload`` but with an empty id list, which the server treats
        as "all files".

        Args:
            include_not_pinned: if True, also offload not-yet-pinned files.
                Default False.

        Returns:
            A dict {"filesOffloaded": int, "bytesOffloaded": int}.

        Example:
            print(Files(at).offload_all())
        """
        req = self.c.new_request("FileListOffload")
        req.includeNotPinned = include_not_pinned
        resp = self.c.call("FileListOffload", req)
        return {"filesOffloaded": getattr(resp, "filesOffloaded", 0),
                "bytesOffloaded": getattr(resp, "bytesOffloaded", 0)}

    def offload_space(self, space_id=None):
        """Offload every file in a single space to free local disk.

        Wraps FileSpaceOffload. The content stays in the network.

        Args:
            space_id: the space to offload; defaults to the client default.

        Returns:
            A dict {"filesOffloaded": int, "bytesOffloaded": int}.

        Example:
            print(Files(at).offload_space())
        """
        req = self.c.new_request("FileSpaceOffload")
        req.spaceId = self._space(space_id)
        resp = self.c.call("FileSpaceOffload", req)
        return {"filesOffloaded": getattr(resp, "filesOffloaded", 0),
                "bytesOffloaded": getattr(resp, "bytesOffloaded", 0)}

    # ----- usage stats --------------------------------------------------------

    def space_usage(self, space_id=None):
        """Return file storage usage for one space, as a dict.

        Wraps FileSpaceUsage.

        Args:
            space_id: the space to query; defaults to the client default.

        Returns:
            A dict with these integer fields (all byte counts are bytes):
            filesCount, cidsCount, bytesUsage, bytesLeft, bytesLimit,
            localBytesUsage. localBytesUsage is what offloading can free;
            bytesUsage is the total stored in the network for this space.

        Example:
            u = Files(at).space_usage()
            print(u["localBytesUsage"], "bytes stored locally")
        """
        req = self.c.new_request("FileSpaceUsage")
        req.spaceId = self._space(space_id)
        resp = self.c.call("FileSpaceUsage", req)
        return self.c.to_dict(resp.usage)

    def node_usage(self):
        """Return file storage usage for the whole node, as a dict.

        Wraps FileNodeUsage. Takes no arguments (it reports across all spaces).

        Returns:
            A dict with two keys:
            - "usage": a dict with filesCount, cidsCount, bytesUsage, bytesLeft,
              bytesLimit, localBytesUsage (same fields as ``space_usage``), which
              are the totals for the node.
            - "spaces": a list of per-space dicts, each with spaceId, filesCount,
              cidsCount, bytesUsage.

        Example:
            n = Files(at).node_usage()
            print(n["usage"]["bytesLimit"])
            for s in n["spaces"]:
                print(s["spaceId"], s["bytesUsage"])
        """
        resp = self.c.call("FileNodeUsage")
        return {"usage": self.c.to_dict(resp.usage),
                "spaces": [self.c.to_dict(s) for s in resp.spaces]}
