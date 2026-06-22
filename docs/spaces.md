# Spaces domain

The spaces domain wraps the Workspace and Space gRPC families plus the
account-select basics. In Anytype a "space" and a "workspace" are the same thing:
the desktop app says space, the gRPC API says workspace. The `space_id` returned
by these methods is exactly the id you pass to other domains (blocks, objects,
and so on).

Most methods here are read-leaning: list spaces, view an invite, list members.
A few change state and are clearly marked in their docstrings and below.

## Setup

```python
import anytype_grpc

at = anytype_grpc.Anytype()      # auto-discovers the port, reads ANYTYPE_TOKEN
sp = at.spaces
```

All methods are on the `Spaces` instance (`sp` above).

## Listing and info (read-only)

### list_space_ids()

Return the list of space ids for the logged-in account.

- Parameters: none.
- Returns: list of strings, for example `["bafy...space1", "bafy...space2"]`.

```python
ids = sp.list_space_ids()
print(ids)
```

### current_space_id()

Return the id of the currently active space.

- Parameters: none.
- Returns: a string id. May be empty if nothing is active.

```python
print(sp.current_space_id())
```

### get_space_info(space_id)

Return one space's details as a dict (name, icon, dashboard, and so on).

- Parameters:
  - `space_id` (str): the id of the space to inspect.
- Returns: a dict of the space object's details, keyed by relation key (for
  example `"name"`). Returns an empty dict if the space object is not found.

```python
info = sp.get_space_info("bafy...space1")
print(info.get("name"))
```

### list_spaces()

Return spaces as dicts, combining ids with names.

- Parameters: none.
- Returns: list of dicts, each with `"id"` and, when resolvable, `"name"`, for
  example `[{"id": "bafy...", "name": "My space"}]`.

```python
for s in sp.list_spaces():
    print(s["id"], s.get("name", "(no name)"))
```

## Creating and editing spaces

### create_space(name, details=None, use_case=None)

Create a new space. CHANGES STATE: makes a new space.

- Parameters:
  - `name` (str): the display name for the new space.
  - `details` (dict, optional): extra object details to set, for example
    `{"iconOption": 3}`. The name is taken from `name` and need not be repeated.
  - `use_case` (str, optional): starter content template. One of `"NONE"`,
    `"GET_STARTED"`, `"DATA_SPACE"`, `"GUIDE_ONLY"`, `"GET_STARTED_MOBILE"`,
    `"CHAT_SPACE"`, `"DATA_SPACE_MOBILE"`. None for the default.
- Returns: a dict `{"spaceId": <str>, "startingObjectId": <str>}`.

```python
res = sp.create_space("Work")
print(res["spaceId"])
```

### set_space_info(space_id, details)

Set details on a space (name, icon, and so on). CHANGES STATE.

- Parameters:
  - `space_id` (str): the space to edit.
  - `details` (dict): `{relation_key: value}` pairs to set, for example
    `{"name": "Renamed space"}`. Values are plain Python types.
- Returns: the raw WorkspaceSetInfo response message.

```python
sp.set_space_info("bafy...space1", {"name": "Renamed space"})
```

### rename_space(space_id, name)

Rename a space. CHANGES STATE. Convenience over `set_space_info`.

- Parameters:
  - `space_id` (str): the space to rename.
  - `name` (str): the new display name.
- Returns: the raw WorkspaceSetInfo response message.

```python
sp.rename_space("bafy...space1", "New name")
```

### set_homepage(space_id, object_id)

Set a space's homepage (the object shown when the space opens). CHANGES STATE.

- Parameters:
  - `space_id` (str): the space.
  - `object_id` (str): the object to use as the homepage. Empty string clears it.
- Returns: the raw WorkspaceSetHomepage response message.

```python
sp.set_homepage("bafy...space1", "bafy...page1")
```

### open_space(space_id)

Open (load) a space so its data is available. CHANGES STATE: loads it.

- Parameters:
  - `space_id` (str): the space to open.
- Returns: a dict form of the WorkspaceOpen response, including an `"info"` block
  and any `"corruptedBackupPaths"`.

```python
info = sp.open_space("bafy...space1")
```

### select_workspace(workspace_id)

Make a workspace the active one. CHANGES STATE. This is a legacy selector kept
for completeness. Most flows use `open_space`.

- Parameters:
  - `workspace_id` (str): the workspace (space) to select.
- Returns: the raw WorkspaceSelect response message.

```python
sp.select_workspace("bafy...space1")
```

### export_space(space_id, path)

Export a whole space to disk. CHANGES STATE: writes files to `path`.

- Parameters:
  - `space_id` (str): the space to export.
  - `path` (str): a directory on the machine running Anytype where the export
    files will be written.
- Returns: the destination path string reported by the server.

```python
out = sp.export_space("bafy...space1", "/home/me/anytype-export")
print(out)
```

## Invites and membership

### generate_invite(space_id, permissions="Reader", invite_type="Member")

Create a sharing invite for a space. CHANGES STATE: shares the space.

- Parameters:
  - `space_id` (str): the space to share.
  - `permissions` (str): level granted to joiners. One of `"Reader"`, `"Writer"`,
    `"Owner"`, `"Admin"`, `"NoPermissions"`. Default `"Reader"`.
  - `invite_type` (str): `"Member"` (approval needed), `"Guest"`, or
    `"WithoutApprove"` (joins without an approval step). Default `"Member"`.
- Returns: a dict `{"inviteCid": <str>, "inviteFileKey": <str>}`. Hand both to
  another account so they can `view_invite` then `join_space`.

```python
inv = sp.generate_invite("bafy...space1", permissions="Writer")
print(inv["inviteCid"], inv["inviteFileKey"])
```

### get_current_invite(space_id)

Return the active invite for a space, if any. Read-only.

- Parameters:
  - `space_id` (str): the space.
- Returns: a dict `{"inviteCid": <str>, "inviteFileKey": <str>}`. Both empty
  strings when there is no active invite.

```python
inv = sp.get_current_invite("bafy...space1")
if inv["inviteCid"]:
    print("active invite present")
```

### view_invite(invite_cid, invite_file_key)

Preview an invite before joining. Read-only: does not join anything.

- Parameters:
  - `invite_cid` (str): the invite content id.
  - `invite_file_key` (str): the invite file key.
- Returns: a dict describing the invite, with keys such as `"spaceId"`,
  `"spaceName"`, `"creatorName"`, `"inviteType"`. Use its `"spaceId"` for
  `join_space`.

```python
v = sp.view_invite(cid, key)
print(v.get("spaceName"), v.get("spaceId"))
```

### join_space(space_id, invite_cid, invite_file_key, network_id="")

Request to join a shared space via an invite. CHANGES STATE. After this the
owner usually approves with `approve_request`, unless the invite type was
`"WithoutApprove"`.

- Parameters:
  - `space_id` (str): the space to join (from `view_invite`).
  - `invite_cid` (str): the invite content id.
  - `invite_file_key` (str): the invite file key.
  - `network_id` (str): only for self-hosted networks; the network id the space
    lives on. Leave `""` for the default Anytype network.
- Returns: the raw SpaceJoin response message.

```python
v = sp.view_invite(cid, key)
sp.join_space(v["spaceId"], cid, key)
```

### approve_request(space_id, identity, permissions="Reader")

Approve a pending join request from one identity. CHANGES STATE. This is the
owner side: it admits someone who called `join_space`.

- Parameters:
  - `space_id` (str): the shared space.
  - `identity` (str): the identity (public key string) of the requester.
  - `permissions` (str): level to grant. One of `"Reader"`, `"Writer"`,
    `"Owner"`, `"Admin"`, `"NoPermissions"`. Default `"Reader"`.
- Returns: the raw SpaceRequestApprove response message.

```python
sp.approve_request("bafy...space1", "A5k...identity", "Writer")
```

### approve_leave(space_id, identities)

Approve members leaving a shared space. CHANGES STATE: removes them.

- Parameters:
  - `space_id` (str): the shared space.
  - `identities` (str or list of str): identities that asked to leave and should
    be removed. A single string is accepted and wrapped in a list.
- Returns: the raw SpaceLeaveApprove response message.

```python
sp.approve_leave("bafy...space1", "A5k...identity")
```

### list_participants(space_id)

List the members (participants) of a space. Read-only. Participants are regular
objects with the participant layout, so this runs an object search filtered to
that layout.

- Parameters:
  - `space_id` (str): the space whose members to list.
- Returns: a list of dicts, one per participant, with keys including `"id"`,
  `"name"`, `"identity"`, `"participantPermissions"`, `"participantStatus"` when
  set.

```python
for p in sp.list_participants("bafy...space1"):
    print(p.get("name"), p.get("participantPermissions"))
```

## Account

### select_account(account_id, root_path="", **options)

Launch (log into) an account by id. CHANGES STATE: starts the node. Normally the
desktop app does this at startup, so you rarely need it from this library, since
you connect to an already-running app. Wrapped for completeness and headless use.

- Parameters:
  - `account_id` (str): the account to select.
  - `root_path` (str): optional account data directory; set only on the first
    request after recovering a wallet. Leave `""` otherwise.
  - `**options`: extra flat fields on the AccountSelect request, for example
    `disableLocalNetworkSync=True` or `jsonApiListenAddr="127.0.0.1:31009"`.
    Names match the proto.
- Returns: a dict form of the AccountSelect response, including the selected
  `"account"`.

```python
res = sp.select_account("A5k...account")
print(res.get("account", {}).get("id"))
```

## Notes and quirks

- Workspace and Space are two RPC families for the same concept. There is no
  single "rename space" RPC: renaming goes through WorkspaceSetInfo with a
  `name` detail, wrapped here as `set_space_info` and `rename_space`.
- The ObjectSearch Filter message spells its relation key field `RelationKey`
  with a capital R, where the lowercase `relationKey` would be expected.
  `list_participants` accounts for this.
- Participants are objects with layout value 19 (participant). There is no
  dedicated "list participants" RPC, so this domain reaches them through search.
- The invite flow has two sides. Owner: `generate_invite`, then later
  `approve_request` (or `approve_leave`). Joiner: `view_invite`, then
  `join_space`. An invite type of `"WithoutApprove"` skips the approval step.
- `select_account`, `select_workspace`, and `open_space` are mainly for headless
  or multi-account setups. When you connect to a running desktop app, the active
  account and space are already loaded.
