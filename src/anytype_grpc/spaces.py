"""The spaces domain: spaces (workspaces), invites, membership, and account select.

This module wraps the Workspace and Space RPC families plus the account-select
basics. A "space" and a "workspace" are the same thing in Anytype: the desktop
app calls them spaces, the gRPC API calls them workspaces. The ``space_id`` you
pass to other domains is exactly the id these methods return.

Most methods here are read-leaning (list spaces, view an invite, list members).
The few that change state (create a space, set its name or homepage, generate or
join an invite, approve a join or request, export a space) are marked clearly in
their docstrings.

Typical use:

    import anytype_grpc
    from anytype_grpc.spaces import Spaces
    at = anytype_grpc.Anytype()
    sp = Spaces(at)
    for s in sp.list_spaces():
        print(s["id"], s.get("name"))
"""

from google.protobuf import json_format

# Layout number for a "participant" object (a member of a shared space). See
# models.proto ObjectType.Layout: participant = 19. Participants are regular
# objects, so they are listed with a normal object search filtered by layout.
_PARTICIPANT_LAYOUT = 19


def _enum_num(message, field_name, value_name):
    """Resolve an enum member name to its number for a field on a message.

    Args:
        message: a protobuf message instance that has the field.
        field_name: the field whose enum type to look in.
        value_name: the enum member name, for example "Writer".

    Returns the integer enum value. Raises KeyError if the name is unknown.
    """
    field = message.DESCRIPTOR.fields_by_name[field_name]
    return field.enum_type.values_by_name[value_name].number


class Spaces:
    """Spaces (workspaces), invites, membership, and account selection.

    Construct with a client:

        sp = Spaces(at)

    where ``at`` is an ``anytype_grpc.Anytype`` instance.
    """

    def __init__(self, client):
        self.c = client

    # ----- listing and basic info ---------------------------------------------

    def list_space_ids(self):
        """Return the list of space (workspace) ids for the logged-in account.

        Takes no arguments. Returns a list of strings, for example
        ``["bafy...space1", "bafy...space2"]``. This is the raw id list from
        WorkspaceGetAll; use ``list_spaces`` if you also want names.

        Example:
            ids = sp.list_space_ids()
            print(ids)
        """
        resp = self.c.call("WorkspaceGetAll")
        return list(resp.workspaceIds)

    def current_space_id(self):
        """Return the id of the currently active space (workspace), as a string.

        Takes no arguments. This reflects the space the app last selected. May be
        empty if nothing is active.

        Example:
            print(sp.current_space_id())
        """
        resp = self.c.call("WorkspaceGetCurrent")
        return resp.workspaceId

    def get_space_info(self, space_id):
        """Return details about one space as a dict (name, icon, and so on).

        This opens the space's "workspace" object and reads its details. The keys
        are relation keys such as "name", "iconImage", "spaceDashboardId".

        Args:
            space_id: the id of the space to inspect (from ``list_space_ids``).

        Returns a dict of the space object's details. Returns an empty dict if the
        space object cannot be found.

        Example:
            info = sp.get_space_info("bafy...space1")
            print(info.get("name"))
        """
        # The space's own descriptor object has id == space_id within that space.
        try:
            view = self.c.get_object(space_id, space_id=space_id)
        except Exception:
            return {}
        details = view.get("objectView", {}).get("details", [])
        for d in details:
            if d.get("id") == space_id:
                return d.get("details", {})
        # Fall back to the first details entry if the exact id is not present.
        if details:
            return details[0].get("details", {})
        return {}

    def list_spaces(self):
        """Return spaces as dicts with at least an "id", and "name" when known.

        Combines WorkspaceGetAll (the id list) with a per-space details read so
        each entry carries a human-readable name. Takes no arguments.

        Returns a list of dicts, for example
        ``[{"id": "bafy...", "name": "My space"}, ...]``. If a name cannot be
        resolved for a space, only its id is present.

        Example:
            for s in sp.list_spaces():
                print(s["id"], s.get("name", "(no name)"))
        """
        out = []
        for sid in self.list_space_ids():
            entry = {"id": sid}
            info = self.get_space_info(sid)
            name = info.get("name")
            if name:
                entry["name"] = name
            out.append(entry)
        return out

    # ----- creating and editing spaces ----------------------------------------

    def create_space(self, name, details=None, use_case=None):
        """Create a new space (workspace). CHANGES STATE: makes a new space.

        Args:
            name: the display name for the new space, for example "Work".
            details: optional dict of extra object details to set on the new
                space, for example {"iconOption": 3}. The "name" key is filled
                from the ``name`` argument and need not be repeated here.
            use_case: optional starter content template name. One of the
                Object.ImportUseCase use case names: "NONE", "GET_STARTED",
                "DATA_SPACE", "GUIDE_ONLY", "GET_STARTED_MOBILE", "CHAT_SPACE",
                "DATA_SPACE_MOBILE". Leave as None for the default.

        Returns a dict with keys "spaceId" (the new space's id) and
        "startingObjectId" (the object to open first, may be empty).

        Example:
            res = sp.create_space("Work")
            print(res["spaceId"])
        """
        req = self.c.new_request("WorkspaceCreate")
        merged = dict(details or {})
        merged["name"] = name
        json_format.ParseDict(merged, req.details)
        if use_case is not None:
            req.useCase = _enum_num(req, "useCase", use_case)
        resp = self.c.call("WorkspaceCreate", req)
        return {"spaceId": resp.spaceId, "startingObjectId": resp.startingObjectId}

    def set_space_info(self, space_id, details):
        """Set details on a space, for example its name or icon. CHANGES STATE.

        Args:
            space_id: the id of the space to edit.
            details: a dict of {relation_key: value} to set on the space object,
                for example {"name": "Renamed space"} or {"iconOption": 2}.
                Values are plain Python types (str, number, bool, list, dict).

        Returns the raw WorkspaceSetInfo response message.

        Example:
            sp.set_space_info("bafy...space1", {"name": "Renamed space"})
        """
        req = self.c.new_request("WorkspaceSetInfo")
        req.spaceId = space_id
        json_format.ParseDict(dict(details), req.details)
        return self.c.call("WorkspaceSetInfo", req)

    def rename_space(self, space_id, name):
        """Rename a space. CHANGES STATE. Convenience over ``set_space_info``.

        Args:
            space_id: the id of the space to rename.
            name: the new display name.

        Returns the raw WorkspaceSetInfo response message.

        Example:
            sp.rename_space("bafy...space1", "New name")
        """
        return self.set_space_info(space_id, {"name": name})

    def set_homepage(self, space_id, object_id):
        """Set a space's homepage (the object shown when the space opens).

        CHANGES STATE.

        Args:
            space_id: the id of the space.
            object_id: the id of the object to use as the homepage. Pass an empty
                string to clear the homepage.

        Returns the raw WorkspaceSetHomepage response message.

        Example:
            sp.set_homepage("bafy...space1", "bafy...page1")
        """
        req = self.c.new_request("WorkspaceSetHomepage")
        req.spaceId = space_id
        req.homepage = object_id
        return self.c.call("WorkspaceSetHomepage", req)

    def open_space(self, space_id):
        """Open (load) a space so its data is available. CHANGES STATE: loads it.

        Args:
            space_id: the id of the space to open.

        Returns a dict form of the WorkspaceOpen response, which includes an
        "info" block with account/space ids and any "corruptedBackupPaths".

        Example:
            info = sp.open_space("bafy...space1")
        """
        resp = self.c.call("WorkspaceOpen", spaceId=space_id)
        return self.c.to_dict(resp)

    def select_workspace(self, workspace_id):
        """Make a workspace the active one for the app. CHANGES STATE.

        Note: in current Anytype this is a legacy selector. Most flows use
        ``open_space`` for this. Provided for completeness.

        Args:
            workspace_id: the id of the workspace (space) to select.

        Returns the raw WorkspaceSelect response message.

        Example:
            sp.select_workspace("bafy...space1")
        """
        return self.c.call("WorkspaceSelect", workspaceId=workspace_id)

    def export_space(self, space_id, path):
        """Export a whole space to disk. CHANGES STATE: writes files to ``path``.

        Args:
            space_id: the id of the space (workspace) to export.
            path: a directory path on the machine running Anytype where the
                export files will be written.

        Returns the destination path string reported by the server.

        Example:
            out = sp.export_space("bafy...space1", "/home/me/anytype-export")
            print(out)
        """
        req = self.c.new_request("WorkspaceExport")
        req.workspaceId = space_id
        req.path = path
        resp = self.c.call("WorkspaceExport", req)
        return resp.path

    # ----- invites and membership ---------------------------------------------

    def generate_invite(self, space_id, permissions="Reader", invite_type="Member"):
        """Create a sharing invite for a space. CHANGES STATE: shares the space.

        This makes the space shareable (if it is not already) and returns the
        invite identifiers others need to join.

        Args:
            space_id: the id of the space to share.
            permissions: the permission level granted to people who join with
                this invite. One of "Reader", "Writer", "Owner", "Admin",
                "NoPermissions". Default "Reader".
            invite_type: the kind of invite. One of "Member" (normal, approval
                needed), "Guest" (guest access), "WithoutApprove" (joins without
                an approval step). Default "Member".

        Returns a dict with "inviteCid" and "inviteFileKey". Hand both to another
        account so they can call ``view_invite`` then ``join_space``.

        Example:
            inv = sp.generate_invite("bafy...space1", permissions="Writer")
            print(inv["inviteCid"], inv["inviteFileKey"])
        """
        req = self.c.new_request("SpaceInviteGenerate")
        req.spaceId = space_id
        req.permissions = _enum_num(req, "permissions", permissions)
        req.inviteType = _enum_num(req, "inviteType", invite_type)
        resp = self.c.call("SpaceInviteGenerate", req)
        return {"inviteCid": resp.inviteCid, "inviteFileKey": resp.inviteFileKey}

    def get_current_invite(self, space_id):
        """Return the active invite for a space, if any. Read-only.

        Args:
            space_id: the id of the space.

        Returns a dict with "inviteCid" and "inviteFileKey". Both are empty
        strings if the space has no active invite.

        Example:
            inv = sp.get_current_invite("bafy...space1")
            if inv["inviteCid"]:
                print("active invite present")
        """
        resp = self.c.call("SpaceInviteGetCurrent", spaceId=space_id)
        return {"inviteCid": resp.inviteCid, "inviteFileKey": resp.inviteFileKey}

    def view_invite(self, invite_cid, invite_file_key):
        """Preview an invite before joining. Read-only: does not join anything.

        Args:
            invite_cid: the invite content id from ``generate_invite``.
            invite_file_key: the invite file key from ``generate_invite``.

        Returns a dict describing the invite, with keys such as "spaceId",
        "spaceName", "creatorName", and "inviteType". Use the "spaceId" it
        returns when calling ``join_space``.

        Example:
            v = sp.view_invite(cid, key)
            print(v.get("spaceName"), v.get("spaceId"))
        """
        req = self.c.new_request("SpaceInviteView")
        req.inviteCid = invite_cid
        req.inviteFileKey = invite_file_key
        resp = self.c.call("SpaceInviteView", req)
        return self.c.to_dict(resp)

    def join_space(self, space_id, invite_cid, invite_file_key, network_id=""):
        """Request to join a shared space via an invite. CHANGES STATE.

        After this, the space owner usually needs to approve the request with
        ``approve_request`` unless the invite type was "WithoutApprove".

        Args:
            space_id: the id of the space to join (from ``view_invite``).
            invite_cid: the invite content id.
            invite_file_key: the invite file key.
            network_id: only needed for self-hosted networks; the network id the
                space lives on. Leave "" for the default Anytype network.

        Returns the raw SpaceJoin response message.

        Example:
            v = sp.view_invite(cid, key)
            sp.join_space(v["spaceId"], cid, key)
        """
        req = self.c.new_request("SpaceJoin")
        req.spaceId = space_id
        req.inviteCid = invite_cid
        req.inviteFileKey = invite_file_key
        if network_id:
            req.networkId = network_id
        return self.c.call("SpaceJoin", req)

    def approve_request(self, space_id, identity, permissions="Reader"):
        """Approve a pending join request from one identity. CHANGES STATE.

        Use this (the owner side) to admit someone who called ``join_space``.

        Args:
            space_id: the id of the shared space.
            identity: the identity (public key string) of the requester to admit.
            permissions: the permission level to grant. One of "Reader", "Writer",
                "Owner", "Admin", "NoPermissions". Default "Reader".

        Returns the raw SpaceRequestApprove response message.

        Example:
            sp.approve_request("bafy...space1", "A5k...identity", "Writer")
        """
        req = self.c.new_request("SpaceRequestApprove")
        req.spaceId = space_id
        req.identity = identity
        req.permissions = _enum_num(req, "permissions", permissions)
        return self.c.call("SpaceRequestApprove", req)

    def approve_leave(self, space_id, identities):
        """Approve members leaving a shared space. CHANGES STATE: removes them.

        Args:
            space_id: the id of the shared space.
            identities: one identity string, or a list of identity strings, that
                have asked to leave and should be removed.

        Returns the raw SpaceLeaveApprove response message.

        Example:
            sp.approve_leave("bafy...space1", "A5k...identity")
        """
        if isinstance(identities, str):
            identities = [identities]
        req = self.c.new_request("SpaceLeaveApprove")
        req.spaceId = space_id
        req.identities.extend(identities)
        return self.c.call("SpaceLeaveApprove", req)

    def list_participants(self, space_id):
        """List the members (participants) of a space. Read-only.

        Participants are regular objects with the "participant" layout, so this
        runs an object search filtered to that layout.

        Args:
            space_id: the id of the space whose members to list.

        Returns a list of dicts, one per participant, with keys including "id",
        "name", "identity", "participantPermissions", and "participantStatus"
        when those relations are set.

        Example:
            for p in sp.list_participants("bafy...space1"):
                print(p.get("name"), p.get("participantPermissions"))
        """
        req = self.c.new_request("ObjectSearch")
        req.spaceId = space_id
        for k in ("id", "name", "identity", "participantPermissions",
                  "participantStatus", "globalName"):
            req.keys.append(k)
        flt = req.filters.add()
        # The proto field is spelled "RelationKey" (capital R) on Filter.
        flt.RelationKey = "layout"
        flt.condition = _enum_num(flt, "condition", "Equal")
        flt.value.number_value = _PARTICIPANT_LAYOUT
        resp = self.c.call("ObjectSearch", req)
        return [json_format.MessageToDict(r) for r in resp.records]

    # ----- account ------------------------------------------------------------

    def select_account(self, account_id, root_path="", **options):
        """Launch (log into) an account by id. CHANGES STATE: starts the node.

        This is normally done by the desktop app at startup. You rarely need it
        from this library because you connect to an already-running app. It is
        wrapped here for completeness and for headless scenarios.

        Args:
            account_id: the id of the account to select.
            root_path: optional account data directory; set only on the first
                request after recovering a wallet. Leave "" otherwise.
            **options: optional extra flat fields on the AccountSelect request,
                for example disableLocalNetworkSync=True or
                jsonApiListenAddr="127.0.0.1:31009". Field names match the proto.

        Returns a dict form of the AccountSelect response, including the selected
        "account".

        Example:
            res = sp.select_account("A5k...account")
            print(res.get("account", {}).get("id"))
        """
        req = self.c.new_request("AccountSelect", **options)
        req.id = account_id
        if root_path:
            req.rootPath = root_path
        resp = self.c.call("AccountSelect", req)
        return self.c.to_dict(resp)
