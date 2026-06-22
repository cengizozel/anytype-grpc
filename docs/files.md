# Files domain

The files domain wraps Anytype's file-level RPCs: uploading files and images,
downloading them back to disk, offloading local copies to free disk space, and
reading storage usage. In Anytype every uploaded file or image becomes its own
object (a "file object") with an id. Covers, relations, and blocks point at that
id.

Construct the helper with a connected client:

```python
from anytype_grpc import Anytype

at = Anytype()          # auto-discovers the port, reads ANYTYPE_TOKEN
files = at.files
```

Methods that need a space fall back to the client default space
(`ANYTYPE_SPACE_ID`, or the `space_id` you passed to `Anytype`) when you do not
pass `space_id`.

## The upload workaround (read this before uploading)

Two things make uploads fail in practice:

1. The desktop helper process that performs the upload is sandboxed. It often
   cannot read arbitrary local paths (for example anything under `/tmp`), so a
   `local_path` upload can be denied or silently fail.
2. Fetching a hotlink-protected remote URL from the helper can return HTTP 403.

The reliable route for both is to serve the bytes yourself over
`http://127.0.0.1` and pass that URL. A one-line static server works:

```bash
python -m http.server 8000 --directory /path/to/folder --bind 127.0.0.1
```

Then upload by URL:

```python
file_id = files.upload(url="http://127.0.0.1:8000/photo.jpg", kind="Image")
```

## File kinds

`upload` takes a `kind` (the file content type). Valid values, as strings:

- `"None"`
- `"File"`  (generic attachment)
- `"Image"`
- `"Video"`
- `"Audio"`
- `"PDF"`

These are also available as `Files.KINDS`.

## Methods

### upload(url=None, local_path=None, kind="Image", space_id=None, details=None)

Upload a file or image and return its file object id (a string). Provide exactly
one source: `url` or `local_path`. Passing both, or neither, raises
`AnytypeError`.

Parameters:

- `url`: URL to fetch bytes from. Prefer a `http://127.0.0.1` URL you serve
  yourself; remote hotlink-protected URLs can return HTTP 403.
- `local_path`: absolute path on disk. The helper sandbox may not be able to
  read it; if it fails, serve over `http://127.0.0.1` and pass as `url`.
- `kind`: one of the file kinds above. Default `"Image"`.
- `space_id`: space to upload into; defaults to the client default.
- `details`: optional dict of extra details to set on the new file object, for
  example `{"name": "My picture"}`. Values are plain Python types.

Returns: the file object id (string).

Example:

```python
file_id = files.upload(url="http://127.0.0.1:8000/photo.jpg", kind="Image")
print(file_id)
```

### upload_image(url_or_path, space_id=None, details=None)

Upload an image and return its file object id (a string). Convenience over
`upload` with `kind="Image"`. The single argument is treated as a URL when it
starts with `http://` or `https://`, otherwise as a local path.

Parameters:

- `url_or_path`: an http(s) URL or an absolute local path to the image.
- `space_id`: space to upload into; defaults to the client default.
- `details`: optional dict of extra details, for example `{"name": "Cover"}`.

Returns: the image file object id (string).

Example:

```python
file_id = files.upload_image("http://127.0.0.1:8000/cover.png")
```

### upload_cover(object_id, url_or_path, x=0.0, y=0.0, space_id=None)

Upload an image and set it as `object_id`'s cover, in one call. Uploads the
image as a file object, then sets the target object's details `coverType=1` and
`coverId=<file object id>`.

Parameters:

- `object_id`: the object (page) to give the cover to.
- `url_or_path`: an http(s) URL or an absolute local path to the image.
- `x`: horizontal cover offset (float), default `0.0`.
- `y`: vertical cover offset (float), default `0.0`.
- `space_id`: space the image uploads into; defaults to the client default.

Returns: the file object id of the uploaded image (string).

Example:

```python
file_id = files.upload_cover(page_id, "http://127.0.0.1:8000/banner.jpg")
```

### download(object_id, path="")

Download a file object to local disk and return the saved path.

Parameters:

- `object_id`: the file object id (as returned by `upload`).
- `path`: absolute local path to save to. If empty, the app uses a temp
  directory and returns that path. The helper may not be able to write to every
  location.

Returns: the local path the file was written to (string).

Example:

```python
saved = files.download(file_id, "/home/me/out.jpg")
print(saved)
```

### offload(object_ids, include_not_pinned=False)

Offload specific file objects: drop their local copies to free disk. The content
stays in the Anytype network and is re-fetched on demand.

Parameters:

- `object_ids`: one file object id (string) or a list of ids.
- `include_not_pinned`: if True, also offload files not yet fully synced.
  Default False (the safe choice).

Returns: a dict `{"filesOffloaded": int, "bytesOffloaded": int}`.

Example:

```python
result = files.offload([file_id])
print(result["bytesOffloaded"])
```

### offload_all(include_not_pinned=False)

Offload all file objects across all spaces to free local disk.

Parameters:

- `include_not_pinned`: if True, also offload not-yet-pinned files. Default
  False.

Returns: a dict `{"filesOffloaded": int, "bytesOffloaded": int}`.

Example:

```python
print(files.offload_all())
```

### offload_space(space_id=None)

Offload every file in a single space to free local disk.

Parameters:

- `space_id`: the space to offload; defaults to the client default.

Returns: a dict `{"filesOffloaded": int, "bytesOffloaded": int}`.

Example:

```python
print(files.offload_space())
```

### space_usage(space_id=None)

Return file storage usage for one space, as a dict.

Parameters:

- `space_id`: the space to query; defaults to the client default.

Returns: a dict with integer fields (byte counts are in bytes):

- `filesCount`: number of file objects.
- `cidsCount`: number of content ids.
- `bytesUsage`: total stored in the network for this space.
- `bytesLeft`: remaining quota.
- `bytesLimit`: quota limit.
- `localBytesUsage`: how much is stored locally (this is what offloading frees).

Note: protobuf omits fields equal to zero, so a key may be absent when its value
is 0. Use `.get(key, 0)` if you need a default.

Example:

```python
u = files.space_usage()
print(u.get("localBytesUsage", 0), "bytes stored locally")
```

### node_usage()

Return file storage usage for the whole node (all spaces). Takes no arguments.

Returns: a dict with two keys:

- `"usage"`: a dict with the same fields as `space_usage` (`filesCount`,
  `cidsCount`, `bytesUsage`, `bytesLeft`, `bytesLimit`, `localBytesUsage`),
  reporting node totals.
- `"spaces"`: a list of per-space dicts, each with `spaceId`, `filesCount`,
  `cidsCount`, `bytesUsage`.

Example:

```python
n = files.node_usage()
print(n["usage"].get("bytesLimit", 0))
for s in n["spaces"]:
    print(s.get("spaceId"), s.get("bytesUsage", 0))
```

## Notes and quirks

- There is no single-file offload RPC registered in the service. `offload` uses
  `FileListOffload` restricted to the ids you pass, which is the supported way
  to offload one or more specific files.
- `space_usage` and `node_usage` return camelCase keys (the client's
  `to_dict` default). Byte counts are absent when zero because protobuf does not
  serialize zero-valued scalars.
