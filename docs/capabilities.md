# Capability catalog

This is the complete list of what anytype-grpc can do. It mirrors the internal
gRPC service that the Anytype desktop app uses, `anytype.ClientCommands`, which
exposes 333 RPC methods. Every one of them is reachable from this library.

## How to call anything

Any method in this catalog is callable by name through the generic client, even
when there is no hand-written helper for it:

    from anytype_grpc import Anytype
    at = Anytype()

    # Call by method name. Pass top-level request fields as keyword arguments.
    resp = at.call("AppGetVersion")
    print(resp.version)

    # For deeply nested requests, build the request object, fill it, then call.
    req = at.new_request("ObjectSearch", spaceId="bafyrei...space")
    req.limit = 50
    resp = at.call("ObjectSearch", request=req)

    # Get the request class directly if you want full control.
    cls = at.request_type("BlockCreate")   # anytype.Rpc.Block.Create.Request

    # Get the response straight back as a plain dict.
    d = at.call_dict("WorkspaceGetAll")

So coverage is total: the helpers below are conveniences, not gates. Anything the
Anytype app itself can do over gRPC, you can do here with `at.call("MethodName", ...)`.

## Legend

- The "Helper" column names the ergonomic wrapper, if one exists in this library.
- A blank Helper cell means "call it by name with `at.call`": still fully supported,
  just without a tailored signature or extra convenience logic.
- Helper locations:
  - `at.<name>` is a method on the `Anytype` client (`client.py`).
  - `Objects.*`, `Blocks.*`, `Views.*`, `Spaces.*`, `Types.*`, `Search.*`, `Files.*`
    are methods on the domain classes in the matching module
    (`objects.py`, `blocks.py`, `views.py`, `spaces.py`, `types.py`, `search.py`, `files.py`).
    Construct each with the client, for example `at.objects`.
  - `auth.mint_token` is the module-level helper in `auth.py`.

---

## App

Process lifecycle and version of the running anytype-heart node.

| Method | Helper | Notes |
| --- | --- | --- |
| AppGetVersion | `at.app_version()` | Works without a token. Returns the version string. |
| AppSetDeviceState | | Tell the node the app is foreground or background. |
| AppShutdown | | Gracefully stop the node. |

## Wallet

Create or recover the local key wallet and open a session. A session is what
produces the bearer token the rest of the API needs.

| Method | Helper | Notes |
| --- | --- | --- |
| WalletCreate | | Create a new wallet from a fresh mnemonic. |
| WalletRecover | | Recover a wallet from an existing mnemonic. |
| WalletConvert | | Convert between mnemonic and entropy forms. |
| WalletCreateSession | `auth.mint_token()` | Mints a session token from a mnemonic. |
| WalletCloseSession | | Invalidate a session token. |

## Account

Create, select, recover, migrate, move, and delete the local account. Also the
local-link app-token pairing flow used to authorize external clients.

| Method | Helper | Notes |
| --- | --- | --- |
| AccountRecover | | Find recoverable accounts on this device. |
| AccountMigrate | | Migrate account data to a new storage format. |
| AccountMigrateCancel | | Cancel an in-progress migration. |
| AccountCreate | | Create a new account. |
| AccountDelete | | Schedule account deletion. |
| AccountRevertDeletion | | Undo a pending account deletion. |
| AccountSelect | `Spaces.*` uses it on open | Select and start an account by id. |
| AccountEnableLocalNetworkSync | | Toggle LAN peer sync. |
| AccountChangeJsonApiAddr | | Change the local JSON API bind address. |
| AccountStop | | Stop the running account. |
| AccountMove | | Move account data to another directory. |
| AccountConfigUpdate | | Update account-level config flags. |
| AccountRecoverFromLegacyExport | | Import from a legacy export bundle. |
| AccountChangeNetworkConfigAndRestart | | Switch network mode (local, self-host, anytype) and restart. |
| AccountLocalLinkNewChallenge | | Start the pairing challenge for an external app. |
| AccountLocalLinkSolveChallenge | | Answer the pairing challenge with the displayed code. |
| AccountLocalLinkCreateApp | | Register an external app and get its token. |
| AccountLocalLinkListApps | | List paired external apps. |
| AccountLocalLinkRevokeApp | | Revoke a paired app token. |

## Workspace and Space

A workspace is the local handle to a space. These cover creating spaces, opening
and selecting them, setting info and homepage, exporting, and the full sharing,
invite, membership, and ownership lifecycle for multiplayer spaces.

| Method | Helper | Notes |
| --- | --- | --- |
| WorkspaceCreate | `Spaces.create()` | Create a new space. |
| WorkspaceOpen | `Spaces.open()` | Open a space and get its info. |
| WorkspaceSelect | `Spaces.select()` | Set the active space. |
| WorkspaceGetCurrent | `Spaces.current()` | Id of the active space. |
| WorkspaceGetAll | `Spaces.list()` / `at.list_spaces()` | All spaces. |
| WorkspaceSetInfo | `Spaces.set_info()` | Set name, description, icon. |
| WorkspaceSetHomepage | `Spaces.set_homepage()` | Set the dashboard or a specific object as home. |
| WorkspaceExport | `Spaces.export()` | Export the whole space. |
| WorkspaceObjectAdd | | Add an existing object to the space index. |
| WorkspaceObjectListAdd | | Add many objects to the space index. |
| WorkspaceObjectListRemove | | Remove objects from the space index. |
| SpaceDelete | | Delete a space. |
| SpaceInviteGenerate | `Spaces.invite_generate()` | Create a share invite link. |
| SpaceInviteChange | | Rotate or change an existing invite. |
| SpaceInviteGetCurrent | `Spaces.invite_current()` | Current invite for a space. |
| SpaceInviteGetGuest | | Get a guest-mode invite. |
| SpaceInviteRevoke | | Revoke an invite. |
| SpaceInviteView | `Spaces.invite_view()` | Preview an invite link without joining. |
| SpaceJoin | `Spaces.join()` | Join a shared space via invite. |
| SpaceJoinCancel | | Cancel a pending join request. |
| SpaceStopSharing | | Stop sharing a space. |
| SpaceRequestApprove | `Spaces.request_approve()` | Approve a join request. |
| SpaceRequestDecline | | Decline a join request. |
| SpaceLeaveApprove | `Spaces.leave_approve()` | Approve a member leaving. |
| SpaceMakeShareable | | Mark a space as shareable. |
| SpaceParticipantRemove | | Remove a member. |
| SpaceParticipantPermissionsChange | | Change a member's permissions. |
| SpaceParticipantsAddList | | Add multiple participants directly. |
| SpaceSetOrder | | Set the space ordering. |
| SpaceUnsetOrder | | Clear custom space ordering. |
| SpaceChangeOwnership | | Transfer ownership to another member. |
| SpaceDeleteCorruptedBackup | | Remove a corrupted local backup of a space. |

## Publishing

Publish objects to the web and manage published pages.

| Method | Helper | Notes |
| --- | --- | --- |
| PublishingCreate | | Publish an object to a public URL. |
| PublishingRemove | | Unpublish. |
| PublishingList | | List published objects. |
| PublishingResolveUri | | Resolve a public URI to an object. |
| PublishingGetStatus | | Get publish status for an object. |

## Object

The core of the API: open, show, create, search, subscribe, duplicate, set
details, set type and layout, favorite and archive, undo and redo, import and
export, and the relation-on-object operations. Search subscriptions stream live
updates of matching objects.

| Method | Helper | Notes |
| --- | --- | --- |
| ObjectOpen | `Objects.open()` / `at.get_object()` | Open an object and stream its blocks. |
| ObjectShow | `Objects.show()` | Show an object snapshot without subscribing. |
| ObjectRefresh | | Re-pull an object from source. |
| ObjectClose | `Objects.close()` | Close an opened object. |
| ObjectCreate | `Objects.create()` / `at.add` flows | Create an object with details and type. |
| ObjectCreateBookmark | `Objects.create_bookmark()` | Create a bookmark object from a URL. |
| ObjectCreateFromUrl | `Objects.create_from_url()` | Create an object by fetching a URL. |
| ObjectCreateSet | `Objects.create_set()` | Create a set (query view) object. |
| ObjectCreateRelation | `Types.create_relation()` | Create a relation (property). |
| ObjectCreateRelationOption | `Types.create_relation_option()` | Create a select or tag option. |
| ObjectCreateObjectType | `Types.create_type()` | Create a new object type. |
| ObjectGraph | `Objects.graph()` | Node and edge graph of the space. |
| ObjectSearch | `Search.search()` / `at.search()` | One-shot search. |
| ObjectSearchWithMeta | | Search returning highlight metadata. |
| ObjectSearchSubscribe | `Search.subscribe()` | Live subscription to a query. |
| ObjectSearchUnsubscribe | `Search.unsubscribe()` | Stop a subscription. |
| ObjectCrossSpaceSearchSubscribe | | Live subscription across all spaces. |
| ObjectCrossSpaceSearchUnsubscribe | | Stop a cross-space subscription. |
| ObjectSubscribeIds | `Search.subscribe_ids()` | Subscribe to a fixed set of ids. |
| ObjectGroupsSubscribe | `Search.groups_subscribe()` | Subscribe to grouped (kanban) results. |
| ObjectSetDetails | `Objects.set_details()` / `at.set_details()` | Set fields on an object. |
| ObjectDuplicate | `Objects.duplicate()` | Copy an object. |
| ObjectSetObjectType | `Objects.set_type()` | Change an object's type. |
| ObjectSetLayout | `Objects.set_layout()` | Change layout (basic, profile, todo, note, etc). |
| ObjectSetInternalFlags | | Set creation-time UI flags. |
| ObjectSetIsFavorite | `Objects.set_favorite` via list helper | Favorite or unfavorite. |
| ObjectSetIsArchived | `Objects.set_archived` via list helper | Archive or unarchive. |
| ObjectSetSource | `Objects.set_source()` | Set the source of a set or query. |
| ObjectListDuplicate | | Duplicate many objects. |
| ObjectListDelete | `Objects.delete()` / `at.delete_objects()` | Permanently delete objects. |
| ObjectListSetIsArchived | `Objects.set_archived()` | Archive many objects. |
| ObjectListSetIsFavorite | `Objects.set_favorite()` | Favorite many objects. |
| ObjectListSetObjectType | | Set type on many objects. |
| ObjectListSetDetails | `Objects.set_details_many()` | Set details on many objects. |
| ObjectListModifyDetailValues | | Append or remove values in list fields. |
| ObjectApplyTemplate | | Apply a template to an existing object. |
| ObjectToSet | `Objects.to_set()` | Convert an object into a set. |
| ObjectToCollection | `Objects.to_collection()` | Convert an object into a collection. |
| ObjectShareByLink | | Get a shareable link to an object. |
| ObjectUndo | | Undo the last change. |
| ObjectRedo | | Redo. |
| ObjectListExport | `Objects.export()` | Export selected objects. |
| ObjectExport | | Export a single object. |
| ObjectImport | `Objects.import_data()` | Import from Notion, markdown, HTML, etc. |
| ObjectImportList | | List importable formats. |
| ObjectImportNotionValidateToken | | Validate a Notion integration token. |
| ObjectImportUseCase | | Import a built-in use-case bundle. |
| ObjectImportExperience | | Import a gallery experience. |
| ObjectBookmarkFetch | | Refetch bookmark metadata. |
| ObjectDateByTimestamp | | Get or create the date object for a timestamp. |
| ObjectCollectionAdd | | Add objects to a collection. |
| ObjectCollectionRemove | | Remove objects from a collection. |
| ObjectCollectionSort | | Reorder a collection. |
| ObjectRelationAdd | | Add a relation to an object. |
| ObjectRelationDelete | | Remove a relation from an object. |
| ObjectRelationAddFeatured | | Feature a relation in the header. |
| ObjectRelationRemoveFeatured | | Unfeature a relation. |
| ObjectRelationListAvailable | | List relations that can be added. |
| ObjectChatAdd | | Attach a chat to an object. |
| ObjectAddDiscussion | | Add a discussion thread to an object. |

## Relation and option

Relations are the typed properties. Options are the choices for select and tag
relations. These manage options and look up where a relation value is used.

| Method | Helper | Notes |
| --- | --- | --- |
| ObjectCreateRelation | `Types.create_relation()` | Listed under Object; included here for context. |
| ObjectCreateRelationOption | `Types.create_relation_option()` | Create a select or tag option. |
| RelationOptions | `Types.relation_options()` | List options for a relation. |
| RelationOptionSetOrder | | Reorder options. |
| RelationListRemoveOption | | Delete options. |
| RelationListWithValue | `Search.relation_with_value()` / `Types.relation_with_value()` | Find objects that use a value. |

## ObjectType

Create types and manage their recommended and featured relations, plus
conflicting-relation resolution and ordering.

| Method | Helper | Notes |
| --- | --- | --- |
| ObjectCreateObjectType | `Types.create_type()` | Create a type. |
| ObjectTypeRelationAdd | `Types.add_relation()` | Add a relation to a type. |
| ObjectTypeRelationRemove | `Types.remove_relation()` | Remove a relation from a type. |
| ObjectTypeRecommendedRelationsSet | `Types.set_recommended_relations()` | Set the recommended relation set. |
| ObjectTypeRecommendedFeaturedRelationsSet | | Set the featured relation set. |
| ObjectTypeListConflictingRelations | `Types.conflicting_relations()` | List relations that conflict with the type. |
| ObjectTypeResolveLayoutConflicts | | Resolve layout conflicts on a type. |
| ObjectTypeSetOrder | | Set the ordering of types. |

## Template

Create templates from objects, clone them, set placeholders, and export.

| Method | Helper | Notes |
| --- | --- | --- |
| TemplateCreateFromObject | `Types.template_from_object()` | Make a template out of an object. |
| TemplateClone | `Types.template_clone()` | Clone a template. |
| TemplateExportAll | | Export all templates. |
| TemplateSetPlaceholders | | Set placeholder values. |
| TemplateGetPlaceholders | | Read placeholder values. |
| TemplateDeletePlaceholders | | Remove placeholders. |

## Block

Generic block-tree editing: create, replace, split, merge, move, duplicate,
copy, cut, paste, set fields and alignment, turn-into, and export. This is the
heart of full layout control that the public HTTP API lacks.

| Method | Helper | Notes |
| --- | --- | --- |
| BlockCreate | `Blocks.create()` / `at.add_block()` | Create a block. |
| BlockReplace | | Replace a block in place. |
| BlockSplit | `Blocks.split()` | Split a text block at a cursor position. |
| BlockMerge | `Blocks.merge()` | Merge two blocks. |
| BlockCopy | `Blocks.copy()` | Copy blocks to clipboard form. |
| BlockCut | | Cut blocks. |
| BlockPaste | `Blocks.paste()` | Paste clipboard content. |
| BlockUpload | | Upload content into a file or media block. |
| BlockSetFields | | Set arbitrary block fields. |
| BlockSetCarriage | | Set the text cursor or carriage position. |
| BlockPreview | | Render a preview of pasted content. |
| BlockExport | | Export blocks. |
| BlockListDelete | `Blocks.delete()` / `at.delete_blocks()` | Delete blocks. |
| BlockListMoveToExistingObject | `Blocks.move()` / `at.move_blocks()` | Move blocks within or into an object. |
| BlockListMoveToNewObject | | Move blocks into a freshly created object. |
| BlockListConvertToObjects | | Turn blocks into standalone objects. |
| BlockListSetFields | | Set fields on many blocks. |
| BlockListDuplicate | `Blocks.duplicate()` | Duplicate blocks. |
| BlockListSetBackgroundColor | `Blocks.set_background_color()` | Set background color. |
| BlockListSetAlign | `Blocks.set_align()` | Set horizontal alignment. |
| BlockListSetVerticalAlign | | Set vertical alignment. |
| BlockListTurnInto | `Blocks.turn_into()` | Turn blocks into another style. |

## BlockText

Text-specific operations: set text and style, color, checked state, icon, and
inline marks (bold, italic, links, mentions).

| Method | Helper | Notes |
| --- | --- | --- |
| BlockTextSetText | `Blocks.set_text()` / `at.set_block_text()` | Set the text of a block. |
| BlockTextSetStyle | `Blocks.set_style()` | Set paragraph or heading style. |
| BlockTextSetColor | `Blocks.set_color()` | Set text color. |
| BlockTextSetChecked | `Blocks.set_checked()` | Check or uncheck a todo. |
| BlockTextSetIcon | | Set a callout or text icon. |
| BlockTextListSetColor | | Set color on many text blocks. |
| BlockTextListSetMark | `Blocks.set_mark()` | Apply an inline mark across a range. |
| BlockTextListSetStyle | | Set style on many text blocks. |
| BlockTextListClearStyle | | Clear style. |
| BlockTextListClearContent | | Clear content. |

## BlockFile, image, video, latex, div, relation, link, bookmark, widget

Media and special block kinds, plus link and bookmark blocks, latex, dividers,
relation blocks, and dashboard widgets.

| Method | Helper | Notes |
| --- | --- | --- |
| BlockFileSetName | | Set a file block name. |
| BlockFileSetTargetObjectId | | Point a file block at a file object. |
| BlockFileCreateAndUpload | | Create a file block and upload at once. |
| BlockFileListSetStyle | | Set file block display style. |
| BlockImageSetName | | Set an image block name. |
| BlockVideoSetName | | Set a video block name. |
| BlockLatexSetText | | Set latex equation text. |
| BlockDivListSetStyle | | Set divider style. |
| BlockRelationSetKey | | Bind a relation block to a relation key. |
| BlockRelationAdd | | Add a relation block. |
| BlockLinkCreateWithObject | | Create a link block and a new linked object. |
| BlockLinkListSetAppearance | | Set link block appearance (card, text, icon). |
| BlockBookmarkFetch | | Fetch bookmark metadata for a block. |
| BlockBookmarkCreateAndFetch | | Create a bookmark block and fetch it. |
| BlockCreateWidget | | Add a widget to the dashboard. |
| BlockWidgetSetTargetId | | Point a widget at an object. |
| BlockWidgetSetLayout | | Set widget layout (list, tree, link, compact). |
| BlockWidgetSetLimit | | Set widget item limit. |
| BlockWidgetSetViewId | | Set which dataview view a widget shows. |

## BlockDataview

Set and collection views: create and update views, set the source, manage
relations, filters, sorts, grouping, and object ordering. See the gotchas below.

| Method | Helper | Notes |
| --- | --- | --- |
| BlockDataviewViewCreate | `Views.create_view()` | Create a view (grid, gallery, kanban, etc). |
| BlockDataviewViewDelete | `Views.delete_view()` | Delete a view. |
| BlockDataviewViewUpdate | `Views.update_view()` | Update view meta only. See gotcha on columns. |
| BlockDataviewViewSetActive | `Views.set_active_view()` | Set the active view. |
| BlockDataviewViewSetPosition | `Views.set_view_position()` | Reorder views. |
| BlockDataviewSetSource | `Views.set_source()` | Set the query source of a dataview. |
| BlockDataviewCreateFromExistingObject | `Views.create_from_object()` | Embed an existing set as a dataview. |
| BlockDataviewRelationSet | | Replace the dataview relation set. |
| BlockDataviewRelationAdd | `Views.relation_add()` | Add a relation to the dataview. |
| BlockDataviewRelationDelete | `Views.relation_delete()` | Remove a relation from the dataview. |
| BlockDataviewViewRelationAdd | `Views.view_relation_add()` | Add or show a relation column in a view. |
| BlockDataviewViewRelationRemove | `Views.view_relation_remove()` | Hide or remove a column in a view. |
| BlockDataviewViewRelationReplace | | Replace a view relation entry. |
| BlockDataviewViewRelationSort | `Views.view_relation_sort()` | Reorder the visible columns of a view. |
| BlockDataviewFilterAdd | `Views.filter_add()` | Add a filter. |
| BlockDataviewFilterRemove | `Views.filter_remove()` | Remove a filter. |
| BlockDataviewFilterReplace | `Views.filter_replace()` | Replace a filter. |
| BlockDataviewFilterSort | `Views.filter_sort()` | Reorder filters. |
| BlockDataviewSortAdd | `Views.sort_add()` | Add a sort rule. |
| BlockDataviewSortRemove | `Views.sort_remove()` | Remove a sort rule. |
| BlockDataviewSortReplace | `Views.sort_replace()` | Replace a sort rule. |
| BlockDataviewSortSort | `Views.sort_sort()` | Reorder sort rules. |
| BlockDataviewGroupOrderUpdate | | Set the order of kanban groups. |
| BlockDataviewObjectOrderUpdate | | Set manual object order in a view. |
| BlockDataviewObjectOrderMove | | Move an object within manual order. |

## BlockTable

Full table editing: create tables, add and remove rows and columns, move and
duplicate columns, set headers, fill and clean, and sort.

| Method | Helper | Notes |
| --- | --- | --- |
| BlockTableCreate | `Blocks.table_create()` | Create a table block. |
| BlockTableExpand | | Grow a table by rows and columns. |
| BlockTableRowCreate | `Blocks.table_row_create()` | Add a row. |
| BlockTableRowDelete | | Delete a row. |
| BlockTableRowDuplicate | | Duplicate a row. |
| BlockTableRowSetHeader | | Mark a row as a header row. |
| BlockTableRowListFill | `Blocks.table_row_fill()` | Fill rows with empty cells. |
| BlockTableRowListClean | | Clear cell contents in rows. |
| BlockTableColumnCreate | `Blocks.table_column_create()` | Add a column. |
| BlockTableColumnMove | | Move a column. |
| BlockTableColumnDelete | | Delete a column. |
| BlockTableColumnDuplicate | | Duplicate a column. |
| BlockTableColumnListFill | | Fill columns with empty cells. |
| BlockTableSort | | Sort rows by a column. |

## File

Upload, download, drop, offload, and usage accounting for files and the file
node. See the FileUpload gotcha below.

| Method | Helper | Notes |
| --- | --- | --- |
| FileUpload | `Files.upload()` / `at.upload_file()` | Upload a file by url or local path. |
| FileDownload | `Files.download()` | Download a file object to disk. |
| FileDrop | | Drop a file into a block. |
| FileDiscardPreload | | Discard a preloaded file. |
| FileSpaceOffload | `Files.space_offload()` | Offload all files in a space. |
| FileListOffload | `Files.list_offload()` | Offload specific files. |
| FileReconcile | | Reconcile file state with the node. |
| FileSpaceUsage | `Files.space_usage()` | Storage used by a space. |
| FileNodeUsage | `Files.node_usage()` | Storage used on the file node. |
| FileSetAutoDownload | | Toggle auto-download for a file. |
| FileCacheDownload | | Cache a file locally. |
| FileCacheCancelDownload | | Cancel a cache download. |
| FileAutoDownloadSetLimit | | Set the auto-download size limit. |

## History

Version history: list versions, show and diff them, and roll back.

| Method | Helper | Notes |
| --- | --- | --- |
| HistoryGetVersions | | List versions of an object. |
| HistoryShowVersion | | Show a specific version. |
| HistorySetVersion | | Restore a version. |
| HistoryDiffVersions | | Diff two versions. |

## Navigation

Browse objects and their inbound and outbound links.

| Method | Helper | Notes |
| --- | --- | --- |
| NavigationListObjects | | List navigable objects. |
| NavigationGetObjectInfoWithLinks | | Object info plus links in and out. |

## Link preview, Unsplash, Gallery

External content helpers for link previews, stock photos, and gallery manifests.

| Method | Helper | Notes |
| --- | --- | --- |
| LinkPreview | | Fetch link preview metadata. |
| UnsplashSearch | | Search Unsplash photos. |
| UnsplashDownload | | Download an Unsplash photo into the space. |
| GalleryDownloadManifest | | Fetch a gallery experience manifest. |
| GalleryDownloadIndex | | Fetch the gallery index. |

## Process and events

Long-running task control and event streams.

| Method | Helper | Notes |
| --- | --- | --- |
| ProcessCancel | | Cancel a running process (import, export, etc). |
| ProcessSubscribe | | Subscribe to process progress. |
| ProcessUnsubscribe | | Stop process subscription. |
| ListenSessionEvents | | Stream all session events. |
| BroadcastPayloadEvent | | Broadcast a custom payload event. |
| InitialSetParameters | | Set initial client parameters on startup. |
| LogSend | | Send a client log line to the node. |

## Notification

In-app notifications.

| Method | Helper | Notes |
| --- | --- | --- |
| NotificationList | | List notifications. |
| NotificationReply | | Reply to or act on a notification. |
| NotificationTest | | Emit a test notification. |

## Device

Manage the devices linked to the account.

| Method | Helper | Notes |
| --- | --- | --- |
| DeviceSetName | | Rename a device. |
| DeviceList | | List linked devices. |
| DeviceNetworkStateSet | | Report device network state. |

## Push notification

Register and configure push tokens for mobile notifications.

| Method | Helper | Notes |
| --- | --- | --- |
| PushNotificationRegisterToken | | Register a push token. |
| PushNotificationSetSpaceMode | | Set per-space push mode. |
| PushNotificationSetForceModeIds | | Force push mode for specific ids. |
| PushNotificationResetIds | | Reset forced ids. |

## Membership

Anytype Network paid membership: status, tiers, payment, email verification,
codes, and the v2 cart and product flows.

| Method | Helper | Notes |
| --- | --- | --- |
| MembershipGetStatus | | Current membership status. |
| MembershipIsNameValid | | Check if a chosen any-name is valid. |
| MembershipRegisterPaymentRequest | | Start a payment. |
| MembershipGetPortalLinkUrl | | Get the billing portal link. |
| MembershipGetVerificationEmailStatus | | Email verification status. |
| MembershipGetVerificationEmail | | Request a verification email. |
| MembershipVerifyEmailCode | | Verify the email code. |
| MembershipFinalize | | Finalize membership setup. |
| MembershipGetTiers | | List membership tiers. |
| MembershipVerifyAppStoreReceipt | | Verify an App Store receipt. |
| MembershipCodeGetInfo | | Look up a redeem code. |
| MembershipCodeRedeem | | Redeem a code. |
| MembershipV2GetProducts | | List v2 products. |
| MembershipV2GetStatus | | v2 membership status. |
| MembershipV2GetPortalLink | | v2 billing portal link. |
| MembershipV2AnyNameIsValid | | Validate an any-name (v2). |
| MembershipV2AnyNameAllocate | | Allocate an any-name (v2). |
| MembershipV2CartGet | | Get the checkout cart. |
| MembershipV2CartUpdate | | Update the cart. |
| MembershipV2SubscribeToUpdates | | Subscribe to membership updates. |

## Name service

Resolve any-names and any-ids on the naming network.

| Method | Helper | Notes |
| --- | --- | --- |
| NameServiceUserAccountGet | | Get the name-service account. |
| NameServiceResolveName | | Resolve a name to an any-id. |
| NameServiceResolveAnyId | | Resolve an any-id to a name. |

## Chat

Space chat and object discussions: post, edit, delete, react, read, search,
pin, and subscribe to messages and previews.

| Method | Helper | Notes |
| --- | --- | --- |
| ChatAddMessage | | Post a message. |
| ChatEditMessageContent | | Edit a message. |
| ChatDeleteMessage | | Delete a message. |
| ChatToggleMessageReaction | | Add or remove a reaction. |
| ChatGetMessages | | Page through messages. |
| ChatGetMessagesByIds | | Fetch messages by id. |
| ChatSubscribeLastMessages | | Subscribe to the latest messages. |
| ChatUnsubscribe | | Stop a chat subscription. |
| ChatReadMessages | | Mark messages read. |
| ChatUnreadMessages | | Mark messages unread. |
| ChatReadAll | | Mark everything read. |
| ChatReadReactions | | Mark reactions read. |
| ChatSubscribeToMessagePreviews | | Subscribe to chat previews. |
| ChatUnsubscribeFromMessagePreviews | | Stop preview subscription. |
| ChatSearch | | Search chat messages. |
| ChatSetPinnedMessages | | Set the pinned message list. |
| ChatGetPinnedMessages | | Get pinned messages. |
| ChatAddNotificationSubscriber | | Subscribe a notification target. |
| ChatRemoveNotificationSubscriber | | Unsubscribe a notification target. |
| ObjectChatAdd | | Attach a chat to an object (also under Object). |
| ObjectAddDiscussion | | Add a discussion to an object (also under Object). |

## AI

Built-in AI helpers exposed by the node.

| Method | Helper | Notes |
| --- | --- | --- |
| AIWritingTools | | Run a writing tool on text (rewrite, summarize, etc). |
| AIAutofill | | Autofill relations or fields. |
| AIListSummary | | Summarize a list of objects. |
| AIObjectCreateFromUrl | | Create an object from a URL using AI extraction. |

## Debug

Diagnostics and profiling: tree dumps, space summaries, goroutine dumps,
localstore export, ping, subscriptions, profiler, net check, and reports.

| Method | Helper | Notes |
| --- | --- | --- |
| DebugStat | | Node statistics. |
| DebugTree | | Dump an object's change tree. |
| DebugTreeHeads | | Dump tree heads. |
| DebugSpaceSummary | | Summary of a space's storage and objects. |
| DebugStackGoroutines | | Dump goroutine stacks. |
| DebugExportLocalstore | | Export the local object store. |
| DebugPing | | Ping the node. |
| DebugSubscriptions | | List active subscriptions. |
| DebugOpenedObjects | | List opened objects. |
| DebugRunProfiler | | Run a CPU or memory profiler. |
| DebugAccountSelectTrace | | Trace an account-select run. |
| DebugAnystoreObjectChanges | | Dump anystore object changes. |
| DebugNetCheck | | Run a network connectivity check. |
| DebugExportReport | | Export a full diagnostic report. |
| DebugCleanupReport | | Clean up generated reports. |

---

## Hard-won gotchas these helpers encode

These are behaviors that are easy to get wrong with raw calls. The helpers above
handle them, and they are documented here so raw callers do not get stuck.

- View columns: the per-view visible relations are not settable through
  `BlockDataviewViewUpdate`. That call only changes view meta (type, cardSize,
  coverRelationKey, coverFit). To control columns use
  `BlockDataviewViewRelationAdd` with `{relation:{key, isVisible:true}}`,
  `BlockDataviewViewRelationSort` to order them, and
  `BlockDataviewViewRelationRemove` to drop them.
- Horizontal grids of blocks: create the cards first, then move the second card
  to position "Right" of the first card, and move each later card to "Right" of
  the previous column block (the layout block whose style is "Column"), not of
  the card itself.
- The "Inner" position nests moved blocks under the target. This is how toggles
  get their children. Order is preserved.
- You cannot add blocks to a Type object or a Set object. The server returns
  "restricted: Blocks". Change those through details instead.
- Image cover on an object: set details `coverType=1` and `coverId=<file object id>`.
  For a set or collection gallery the cover comes from a relation, so set the
  view `coverRelationKey` (for example "picture") instead.
- FileUpload: the desktop helper is sandboxed and cannot read `/tmp`, and fetching
  hotlink-protected URLs can return 403. The reliable route is to serve the file
  over `http://127.0.0.1` and pass that url.

## Bottom line

Every capability of the Anytype desktop app that goes through gRPC is in this
catalog, and every one is callable today with `at.call("MethodName", ...)`. The
named helpers add ergonomics and encode the gotchas above, but they are never a
limit on what you can reach.
