"""The blocks domain: create, edit, move, and structure blocks inside an object.

A block is one node in an object's content tree: a paragraph, a header, a
checkbox, a toggle, a code block, a divider, a file, a bookmark, a table, and
so on. This module wraps the fiddly gRPC calls that build and edit that tree
and adds a few high level helpers (a toggle with children, a horizontal card
grid, and a filled table).

Construct it with a client:

    import anytype_grpc
    from anytype_grpc.blocks import Blocks
    at = anytype_grpc.Anytype()
    blocks = Blocks(at)
    bid = blocks.add_text(page_id, "Hello world", style="Header1")

Every method returns plain values (usually a new block id string or a list of
ids) so you can chain calls.

Important gotchas, encoded here so you do not have to rediscover them:

- You cannot add blocks to a Type object or a Set object. The server replies
  "restricted: Blocks". Edit those through object details instead.
- Per view visible relations (dataview columns) are not handled here. They live
  in the dataview domain.
- Building a horizontal grid is not a single call. You create the cards as a
  vertical stack, then move the second card to the Right of the first card, and
  each later card to the Right of the previous column layout block (not the
  card). The grid() helper does this for you.
- Position "Inner" nests moved blocks under the target and preserves their
  order. make_toggle() uses this to put children inside a toggle.
"""

from google.protobuf import json_format


# Text block styles, by their proto enum name. Pass any of these as the
# ``style`` argument to add_text, turn_into, set_style, and so on.
TEXT_STYLES = (
    "Paragraph", "Header1", "Header2", "Header3", "Quote", "Code", "Title",
    "Checkbox", "Marked", "Numbered", "Toggle", "Description", "Callout",
    "ToggleHeader1", "ToggleHeader2", "ToggleHeader3",
)

# Block insert positions, by their proto enum name.
POSITIONS = (
    "None", "Top", "Bottom", "Left", "Right", "Inner", "Replace", "InnerFirst",
)

# Text mark types, by their proto enum name. Used by set_mark.
MARK_TYPES = (
    "Strikethrough", "Keyboard", "Italic", "Bold", "Underscored", "Link",
    "TextColor", "BackgroundColor", "Mention", "Emoji", "Object",
)

# Latex / embed processors, by their proto enum name. Used by add_latex.
LATEX_PROCESSORS = (
    "Latex", "Mermaid", "Chart", "Youtube", "Vimeo", "Soundcloud", "GoogleMaps",
    "Miro", "Figma", "Twitter", "OpenStreetMap", "Reddit", "Facebook",
    "Instagram", "Telegram", "GithubGist", "Codepen", "Bilibili", "Excalidraw",
    "Kroki", "Graphviz", "Sketchfab", "Image", "Drawio", "Spotify",
)


class Blocks:
    """Block tree editing for a single Anytype object."""

    def __init__(self, client):
        self.c = client

    # ----- internal helpers ---------------------------------------------------

    def _enum(self, method, field, name):
        """Resolve an enum value number on a request field by its proto name.

        Args:
            method: the RPC method name, for example "BlockCreate".
            field: the request field name holding the enum, for example "position".
            name: the proto enum value name, for example "Inner".

        Returns:
            The integer enum value to assign to the field.
        """
        rt = self.c.request_type(method)
        return rt.DESCRIPTOR.fields_by_name[field].enum_type.values_by_name[name].number

    def _create(self, context_id, block_dict, target_id=None, position="Bottom"):
        """Create one block from a plain dict describing its content.

        Args:
            context_id: id of the object to insert into.
            block_dict: a dict matching anytype.model.Block (for example
                {"text": {"text": "hi", "style": "Paragraph"}}). Enum values
                inside it may be given by their proto name strings; protobuf
                json parsing accepts them.
            target_id: an existing block to position relative to. None appends
                to the object root.
            position: one of POSITIONS, for example "Bottom" or "Inner".

        Returns:
            The new block id string.
        """
        req = self.c.new_request("BlockCreate")
        req.contextId = context_id
        if target_id:
            req.targetId = target_id
        req.position = self._enum("BlockCreate", "position", position)
        json_format.ParseDict(block_dict, req.block)
        resp = self.c.call("BlockCreate", req)
        return getattr(resp, "blockId", "")

    # ----- create blocks ------------------------------------------------------

    def add_text(self, context_id, text="", style="Paragraph", *,
                 target_id=None, position="Bottom", color=None,
                 background_color=None):
        """Create a text block (paragraph, header, quote, callout, and so on).

        Args:
            context_id: id of the object to insert into.
            text: the block's text content.
            style: a text style name from TEXT_STYLES, for example "Header1",
                "Quote", "Callout", "Numbered". Defaults to "Paragraph".
            target_id: an existing block to insert relative to. None appends.
            position: where to insert, one of POSITIONS. Defaults to "Bottom".
            color: optional text color name, for example "red" or "blue".
            background_color: optional background color name.

        Returns:
            The new block id string.

        Example:
            bid = blocks.add_text(page, "A heading", style="Header2")
        """
        content = {"text": text, "style": style}
        if color:
            content["color"] = color
        block = {"text": content}
        if background_color:
            block["backgroundColor"] = background_color
        return self._create(context_id, block, target_id, position)

    def add_header(self, context_id, text, level=1, *, target_id=None,
                   position="Bottom"):
        """Create a header block at level 1, 2, or 3.

        Args:
            context_id: id of the object to insert into.
            text: the header text.
            level: 1, 2, or 3. Maps to styles Header1, Header2, Header3.
            target_id: an existing block to insert relative to. None appends.
            position: where to insert, one of POSITIONS.

        Returns:
            The new block id string.

        Example:
            bid = blocks.add_header(page, "Section", level=2)
        """
        if level not in (1, 2, 3):
            raise ValueError("header level must be 1, 2, or 3")
        return self.add_text(context_id, text, style=f"Header{level}",
                             target_id=target_id, position=position)

    def add_checkbox(self, context_id, text="", checked=False, *,
                     target_id=None, position="Bottom"):
        """Create a checkbox (to do) block.

        Args:
            context_id: id of the object to insert into.
            text: the checkbox label text.
            checked: whether it starts checked.
            target_id: an existing block to insert relative to. None appends.
            position: where to insert, one of POSITIONS.

        Returns:
            The new block id string.

        Example:
            bid = blocks.add_checkbox(page, "Buy milk", checked=False)
        """
        block = {"text": {"text": text, "style": "Checkbox", "checked": checked}}
        return self._create(context_id, block, target_id, position)

    def add_toggle(self, context_id, text="", *, target_id=None,
                   position="Bottom"):
        """Create an empty toggle block. To put children inside it, use
        make_toggle() or create the children then move them Inner.

        Args:
            context_id: id of the object to insert into.
            text: the toggle's visible title text.
            target_id: an existing block to insert relative to. None appends.
            position: where to insert, one of POSITIONS.

        Returns:
            The new toggle block id string.

        Example:
            tid = blocks.add_toggle(page, "Details")
        """
        block = {"text": {"text": text, "style": "Toggle"}}
        return self._create(context_id, block, target_id, position)

    def add_code(self, context_id, text="", *, target_id=None,
                 position="Bottom"):
        """Create a code block.

        Args:
            context_id: id of the object to insert into.
            text: the code text.
            target_id: an existing block to insert relative to. None appends.
            position: where to insert, one of POSITIONS.

        Returns:
            The new block id string.

        Example:
            bid = blocks.add_code(page, "print('hi')")
        """
        block = {"text": {"text": text, "style": "Code"}}
        return self._create(context_id, block, target_id, position)

    def add_marked(self, context_id, text="", numbered=False, *,
                   target_id=None, position="Bottom"):
        """Create a list item: a bulleted (Marked) or numbered list block.

        Args:
            context_id: id of the object to insert into.
            text: the list item text.
            numbered: if True, create a numbered item, else a bullet.
            target_id: an existing block to insert relative to. None appends.
            position: where to insert, one of POSITIONS.

        Returns:
            The new block id string.

        Example:
            bid = blocks.add_marked(page, "First point")
        """
        style = "Numbered" if numbered else "Marked"
        block = {"text": {"text": text, "style": style}}
        return self._create(context_id, block, target_id, position)

    def add_divider(self, context_id, dots=False, *, target_id=None,
                    position="Bottom"):
        """Create a divider block: a horizontal line, or a row of dots.

        Args:
            context_id: id of the object to insert into.
            dots: if True, use the dotted divider style, else a thin line.
            target_id: an existing block to insert relative to. None appends.
            position: where to insert, one of POSITIONS.

        Returns:
            The new block id string.

        Example:
            bid = blocks.add_divider(page)
        """
        block = {"div": {"style": "Dots" if dots else "Line"}}
        return self._create(context_id, block, target_id, position)

    def add_link(self, context_id, target_object_id, *, card=False,
                 target_id=None, position="Bottom"):
        """Create a link block pointing at another object.

        Args:
            context_id: id of the object to insert into.
            target_object_id: the object id this link points to.
            card: if True, render as a card with a cover, else inline text.
            target_id: an existing block to insert relative to. None appends.
            position: where to insert, one of POSITIONS.

        Returns:
            The new block id string.

        Example:
            bid = blocks.add_link(page, other_object_id, card=True)
        """
        link = {"targetBlockId": target_object_id}
        if card:
            link.update({"cardStyle": "Card", "iconSize": "SizeMedium",
                         "relations": ["cover"]})
        return self._create(context_id, {"link": link}, target_id, position)

    def add_file(self, context_id, file_object_id, kind="File", *,
                 embed=False, target_id=None, position="Bottom"):
        """Create a file block that references an already uploaded file object.

        Upload the file first with the client's upload_file helper, then pass
        the returned file object id here as ``file_object_id``.

        Args:
            context_id: id of the object to insert into.
            file_object_id: the file object id returned by upload_file.
            kind: file type name, one of "File", "Image", "Video", "Audio",
                "PDF". Picks how Anytype renders it.
            embed: if True, render embedded (style Embed) instead of a link.
            target_id: an existing block to insert relative to. None appends.
            position: where to insert, one of POSITIONS.

        Returns:
            The new block id string.

        Example:
            fid = at.upload_file(url="http://127.0.0.1:8000/pic.png")
            bid = blocks.add_file(page, fid, kind="Image", embed=True)
        """
        file_content = {
            "targetObjectId": file_object_id,
            "type": kind,
            "state": "Done",
            "style": "Embed" if embed else "Auto",
        }
        return self._create(context_id, {"file": file_content}, target_id, position)

    def add_bookmark(self, context_id, url, *, target_id=None, position="Bottom"):
        """Create a bookmark block for a web URL.

        The block starts empty and Anytype fetches the page title and preview
        asynchronously. To force a fetch with full control, see the bookmark
        RPCs; this helper just creates the block with the URL set.

        Args:
            context_id: id of the object to insert into.
            url: the web URL to bookmark.
            target_id: an existing block to insert relative to. None appends.
            position: where to insert, one of POSITIONS.

        Returns:
            The new block id string.

        Example:
            bid = blocks.add_bookmark(page, "https://anytype.io")
        """
        block = {"bookmark": {"url": url, "state": "Empty"}}
        return self._create(context_id, block, target_id, position)

    def add_latex(self, context_id, text="", processor="Latex", *,
                  target_id=None, position="Bottom"):
        """Create a latex or embed block (math, mermaid, youtube, and so on).

        The block content holds the source text and a processor that decides how
        it renders. For plain math use processor "Latex". For an embedded site
        use the matching processor name and put the URL in ``text``.

        Args:
            context_id: id of the object to insert into.
            text: the latex source, or the embed URL for an embed processor.
            processor: a name from LATEX_PROCESSORS, for example "Latex",
                "Mermaid", "Youtube".
            target_id: an existing block to insert relative to. None appends.
            position: where to insert, one of POSITIONS.

        Returns:
            The new block id string.

        Example:
            bid = blocks.add_latex(page, "E = mc^2", processor="Latex")
        """
        block = {"latex": {"text": text, "processor": processor}}
        return self._create(context_id, block, target_id, position)

    def create_raw(self, context_id, block_dict, *, target_id=None,
                   position="Bottom"):
        """Create a block from a raw anytype.model.Block dict, for content
        kinds this module does not wrap directly.

        Args:
            context_id: id of the object to insert into.
            block_dict: a dict matching the Block message, for example
                {"text": {"text": "hi", "style": "Paragraph"}}. Enum fields may
                be given by their proto name strings.
            target_id: an existing block to insert relative to. None appends.
            position: where to insert, one of POSITIONS.

        Returns:
            The new block id string.

        Example:
            bid = blocks.create_raw(page, {"tableOfContents": {}})
        """
        return self._create(context_id, block_dict, target_id, position)

    # ----- delete, move, duplicate, copy, paste -------------------------------

    def delete(self, context_id, block_ids):
        """Delete one or more blocks from an object.

        Args:
            context_id: id of the object the blocks live in.
            block_ids: a single block id string, or a list of ids.

        Returns:
            The BlockListDelete response message.

        Example:
            blocks.delete(page, [bid1, bid2])
        """
        if isinstance(block_ids, str):
            block_ids = [block_ids]
        return self.c.call("BlockListDelete", contextId=context_id,
                           blockIds=list(block_ids))

    def move(self, context_id, block_ids, drop_target_id, position="Bottom", *,
             target_context_id=None):
        """Move blocks within an object (or into another object).

        Order of ``block_ids`` is preserved. Position "Inner" nests them under
        the target. Position "Right" relative to a column layout block is how
        horizontal grids are built (see grid()).

        Args:
            context_id: id of the object the blocks currently live in.
            block_ids: a single block id string, or a list of ids, to move.
            drop_target_id: the block to drop relative to.
            position: one of POSITIONS, for example "Bottom", "Inner", "Right".
            target_context_id: id of the destination object. Defaults to
                context_id (move within the same object).

        Returns:
            The BlockListMoveToExistingObject response message.

        Example:
            blocks.move(page, [bid], header_id, position="Inner")
        """
        if isinstance(block_ids, str):
            block_ids = [block_ids]
        req = self.c.new_request("BlockListMoveToExistingObject")
        req.contextId = context_id
        req.targetContextId = target_context_id or context_id
        req.dropTargetId = drop_target_id
        req.position = self._enum("BlockListMoveToExistingObject", "position", position)
        req.blockIds.extend(block_ids)
        return self.c.call("BlockListMoveToExistingObject", req)

    def duplicate(self, context_id, block_ids, target_id, position="Bottom", *,
                  target_context_id=None):
        """Duplicate blocks and insert the copies relative to a target.

        Args:
            context_id: id of the object the source blocks live in.
            block_ids: a single block id string, or a list of ids, to copy.
            target_id: the block to insert the copies relative to.
            position: one of POSITIONS, for example "Bottom".
            target_context_id: destination object id. Defaults to context_id.

        Returns:
            A list of the new block id strings.

        Example:
            new_ids = blocks.duplicate(page, [bid], bid, position="Bottom")
        """
        if isinstance(block_ids, str):
            block_ids = [block_ids]
        req = self.c.new_request("BlockListDuplicate")
        req.contextId = context_id
        req.targetId = target_id
        req.position = self._enum("BlockListDuplicate", "position", position)
        req.blockIds.extend(block_ids)
        if target_context_id:
            req.targetContextId = target_context_id
        resp = self.c.call("BlockListDuplicate", req)
        return list(getattr(resp, "blockIds", []))

    def copy(self, context_id, blocks, *, range_from=None, range_to=None):
        """Copy blocks to the internal clipboard slots and return them.

        This returns the text, html, and "any" slots that paste() consumes.
        Pass the blocks to copy as raw Block dicts (each needs at least an id).

        Args:
            context_id: id of the object the blocks live in.
            blocks: a list of raw Block dicts to copy, for example
                [{"id": bid}].
            range_from: optional start offset for a partial text copy.
            range_to: optional end offset for a partial text copy.

        Returns:
            A dict with keys textSlot, htmlSlot, anySlot from the response.

        Example:
            slots = blocks.copy(page, [{"id": bid}])
            blocks.paste(other_page, focused_block_id=target, **slots)
        """
        req = self.c.new_request("BlockCopy")
        req.contextId = context_id
        json_format.ParseDict({"blocks": blocks}, req)
        if range_from is not None or range_to is not None:
            # The Range "from" field is a Python keyword; set it with setattr.
            setattr(req.selectedTextRange, "from", range_from or 0)
            req.selectedTextRange.to = range_to or 0
        resp = self.c.call("BlockCopy", req)
        return {
            "textSlot": getattr(resp, "textSlot", ""),
            "htmlSlot": getattr(resp, "htmlSlot", ""),
            "anySlot": list(getattr(resp, "anySlot", [])),
        }

    def paste(self, context_id, *, focused_block_id="", textSlot="",
              htmlSlot="", anySlot=None, url="", selected_block_ids=None):
        """Paste clipboard slot content into an object.

        Supply slots from a previous copy(), or just a plain text or html
        string, or a url. At least one slot must be non empty.

        Args:
            context_id: id of the object to paste into.
            focused_block_id: id of the block the caret is in. Empty appends.
            textSlot: plain text to paste.
            htmlSlot: html to paste.
            anySlot: a list of raw Block dicts (or Block messages) to paste,
                usually taken from copy()'s anySlot.
            url: a url to paste (Anytype turns it into a bookmark or link).
            selected_block_ids: ids of blocks the paste should replace.

        Returns:
            A list of the new block id strings.

        Example:
            ids = blocks.paste(page, textSlot="hello")
        """
        req = self.c.new_request("BlockPaste")
        req.contextId = context_id
        if focused_block_id:
            req.focusedBlockId = focused_block_id
        if textSlot:
            req.textSlot = textSlot
        if htmlSlot:
            req.htmlSlot = htmlSlot
        if url:
            req.url = url
        if selected_block_ids:
            req.selectedBlockIds.extend(selected_block_ids)
        if anySlot:
            # anySlot items may be Block messages (from copy) or plain dicts.
            for item in anySlot:
                blk = req.anySlot.add()
                if isinstance(item, dict):
                    json_format.ParseDict(item, blk)
                else:
                    blk.CopyFrom(item)
        resp = self.c.call("BlockPaste", req)
        return list(getattr(resp, "blockIds", []))

    def split(self, context_id, block_id, at_offset, *, style=None,
              mode="BOTTOM"):
        """Split a text block in two at a character offset.

        Args:
            context_id: id of the object the block lives in.
            block_id: id of the text block to split.
            at_offset: the character index to split at. The split uses a range
                from this offset to this offset.
            style: optional text style name for the new block, from TEXT_STYLES.
                Defaults to the original block's style on the server side.
            mode: where the new block goes relative to the original, one of
                "BOTTOM", "TOP", "INNER", "TITLE". Defaults to "BOTTOM".

        Returns:
            The new block id string.

        Example:
            new_id = blocks.split(page, bid, 5)
        """
        req = self.c.new_request("BlockSplit")
        req.contextId = context_id
        req.blockId = block_id
        # The Range field is literally named "from" (a Python keyword), so it
        # must be set with setattr rather than attribute access.
        setattr(req.range, "from", at_offset)
        req.range.to = at_offset
        if style is not None:
            req.style = self._enum("BlockSplit", "style", style)
        req.mode = req.DESCRIPTOR.fields_by_name["mode"].enum_type.values_by_name[mode].number
        resp = self.c.call("BlockSplit", req)
        return getattr(resp, "blockId", "")

    def merge(self, context_id, first_block_id, second_block_id):
        """Merge the second text block into the first.

        Args:
            context_id: id of the object the blocks live in.
            first_block_id: the block that keeps existing and receives content.
            second_block_id: the block whose content is appended then removed.

        Returns:
            The BlockMerge response message.

        Example:
            blocks.merge(page, top_id, bottom_id)
        """
        return self.c.call("BlockMerge", contextId=context_id,
                           firstBlockId=first_block_id,
                           secondBlockId=second_block_id)

    # ----- edit text and style ------------------------------------------------

    def set_text(self, context_id, block_id, text):
        """Replace a text block's text content.

        Args:
            context_id: id of the object the block lives in.
            block_id: id of the text block.
            text: the new text content.

        Returns:
            The BlockTextSetText response message.

        Example:
            blocks.set_text(page, bid, "new content")
        """
        return self.c.call("BlockTextSetText", contextId=context_id,
                           blockId=block_id, text=text)

    def set_style(self, context_id, block_id, style):
        """Change a text block's style (paragraph, header, checkbox, and so on).

        Args:
            context_id: id of the object the block lives in.
            block_id: id of the text block.
            style: a style name from TEXT_STYLES, for example "Header1".

        Returns:
            The BlockTextSetStyle response message.

        Example:
            blocks.set_style(page, bid, "Quote")
        """
        req = self.c.new_request("BlockTextSetStyle")
        req.contextId = context_id
        req.blockId = block_id
        req.style = self._enum("BlockTextSetStyle", "style", style)
        return self.c.call("BlockTextSetStyle", req)

    def set_color(self, context_id, block_id, color):
        """Set the text color of a text block.

        Args:
            context_id: id of the object the block lives in.
            block_id: id of the text block.
            color: a color name string, for example "red", "blue", "grey".

        Returns:
            The BlockTextSetColor response message.

        Example:
            blocks.set_color(page, bid, "red")
        """
        return self.c.call("BlockTextSetColor", contextId=context_id,
                           blockId=block_id, color=color)

    def set_checked(self, context_id, block_id, checked):
        """Check or uncheck a checkbox block.

        Args:
            context_id: id of the object the block lives in.
            block_id: id of the checkbox block.
            checked: True to check, False to uncheck.

        Returns:
            The BlockTextSetChecked response message.

        Example:
            blocks.set_checked(page, bid, True)
        """
        return self.c.call("BlockTextSetChecked", contextId=context_id,
                           blockId=block_id, checked=checked)

    def set_mark(self, context_id, block_ids, mark_type, range_from, range_to,
                 param=""):
        """Apply an inline text mark (bold, italic, link, color) to a range.

        The mark covers characters from ``range_from`` up to ``range_to`` in
        each listed block. Some marks need ``param``: Link needs the url,
        TextColor and BackgroundColor need a color name, Object and Mention need
        the target object id, Emoji needs the emoji.

        Args:
            context_id: id of the object the blocks live in.
            block_ids: a single block id string, or a list of ids, to mark.
            mark_type: a mark name from MARK_TYPES, for example "Bold", "Link".
            range_from: start character offset (inclusive).
            range_to: end character offset (exclusive).
            param: extra data for marks that need it (url, color, id, emoji).

        Returns:
            The BlockTextListSetMark response message.

        Example:
            blocks.set_mark(page, bid, "Bold", 0, 5)
            blocks.set_mark(page, bid, "Link", 0, 5, param="https://x.com")
        """
        if isinstance(block_ids, str):
            block_ids = [block_ids]
        req = self.c.new_request("BlockTextListSetMark")
        req.contextId = context_id
        req.blockIds.extend(block_ids)
        # The Range "from" field is a Python keyword; set it with setattr.
        setattr(req.mark.range, "from", range_from)
        req.mark.range.to = range_to
        mark_field = req.mark.DESCRIPTOR.fields_by_name["type"]
        req.mark.type = mark_field.enum_type.values_by_name[mark_type].number
        if param:
            req.mark.param = param
        return self.c.call("BlockTextListSetMark", req)

    def turn_into(self, context_id, block_ids, style):
        """Convert one or more blocks into a different text style.

        Unlike set_style, this is the list level "turn into" operation the app
        uses, which also handles structural conversions cleanly.

        Args:
            context_id: id of the object the blocks live in.
            block_ids: a single block id string, or a list of ids.
            style: a target style name from TEXT_STYLES, for example "Toggle".

        Returns:
            The BlockListTurnInto response message.

        Example:
            blocks.turn_into(page, [bid], "Header2")
        """
        if isinstance(block_ids, str):
            block_ids = [block_ids]
        req = self.c.new_request("BlockListTurnInto")
        req.contextId = context_id
        req.blockIds.extend(block_ids)
        req.style = self._enum("BlockListTurnInto", "style", style)
        return self.c.call("BlockListTurnInto", req)

    def set_align(self, context_id, block_ids, align):
        """Set the horizontal alignment of one or more blocks.

        Args:
            context_id: id of the object the blocks live in.
            block_ids: a single block id string, or a list of ids. An empty list
                applies the alignment to the object layout itself.
            align: one of "AlignLeft", "AlignCenter", "AlignRight",
                "AlignJustify".

        Returns:
            The BlockListSetAlign response message.

        Example:
            blocks.set_align(page, [bid], "AlignCenter")
        """
        if isinstance(block_ids, str):
            block_ids = [block_ids]
        req = self.c.new_request("BlockListSetAlign")
        req.contextId = context_id
        req.blockIds.extend(block_ids)
        req.align = self._enum("BlockListSetAlign", "align", align)
        return self.c.call("BlockListSetAlign", req)

    def set_background_color(self, context_id, block_ids, color):
        """Set the background color of one or more blocks.

        Args:
            context_id: id of the object the blocks live in.
            block_ids: a single block id string, or a list of ids.
            color: a color name string, for example "yellow", "grey".

        Returns:
            The BlockListSetBackgroundColor response message.

        Example:
            blocks.set_background_color(page, [bid], "yellow")
        """
        if isinstance(block_ids, str):
            block_ids = [block_ids]
        return self.c.call("BlockListSetBackgroundColor", contextId=context_id,
                           blockIds=list(block_ids), color=color)

    # ----- high level helpers -------------------------------------------------

    def make_toggle(self, context_id, title, child_block_ids, *, target_id=None,
                    position="Bottom"):
        """Create a toggle and nest existing blocks inside it.

        This creates a Toggle block with the given title, then moves each block
        in ``child_block_ids`` Inner (under the toggle), preserving their order.

        Args:
            context_id: id of the object to build in.
            title: the toggle's visible title text.
            child_block_ids: a list of existing block ids to put inside the
                toggle, in the order they should appear.
            target_id: where to place the toggle, relative to an existing block.
                None appends to the object root.
            position: where to insert the toggle, one of POSITIONS.

        Returns:
            The new toggle block id string.

        Example:
            a = blocks.add_text(page, "inside one")
            b = blocks.add_text(page, "inside two")
            tid = blocks.make_toggle(page, "Click me", [a, b])
        """
        toggle_id = self.add_toggle(context_id, title, target_id=target_id,
                                    position=position)
        if child_block_ids:
            self.move(context_id, list(child_block_ids), toggle_id,
                      position="Inner")
        return toggle_id

    def grid(self, context_id, card_block_ids, per_row):
        """Arrange existing blocks into a horizontal grid of rows.

        Anytype has no single grid call. You build one by moving blocks into
        columns. This helper takes a flat list of blocks (typically link cards
        made with add_link(card=True)) and lays them out ``per_row`` across.

        Technique, applied here so you do not have to: for each row, move the
        second card to the Right of the first card. Moving Right of a normal
        block makes Anytype wrap both in a Row layout with two Column layout
        blocks. Each later card in the row is then moved to the Right of the
        PREVIOUS card's parent Column block, not the card itself, so it lands as
        a new column rather than nesting. Because we cannot read back the new
        column ids offline, this helper moves each later card Right of the
        previous card; the server resolves that to the enclosing column. If you
        need pixel exact control, do the moves yourself with move().

        Args:
            context_id: id of the object the cards live in.
            card_block_ids: a flat list of existing block ids, in order.
            per_row: how many cards to place in each row (the column count).

        Returns:
            A list of rows, where each row is the list of block ids in it.
            This mirrors the layout that was built.

        Example:
            ids = [blocks.add_link(page, oid, card=True) for oid in objs]
            rows = blocks.grid(page, ids, per_row=3)
        """
        if per_row < 1:
            raise ValueError("per_row must be at least 1")
        rows = [card_block_ids[i:i + per_row]
                for i in range(0, len(card_block_ids), per_row)]
        for row in rows:
            first = row[0]
            prev = first
            for card in row[1:]:
                # Move each later card to the Right of the previous card. The
                # first Right move on a plain block creates the Row/Column
                # layout; subsequent moves land as new columns in that row.
                self.move(context_id, [card], prev, position="Right")
                prev = card
        return rows

    # ----- tables -------------------------------------------------------------

    def create_table(self, context_id, rows, columns, *, with_header_row=False,
                     target_id=None, position="Bottom"):
        """Create a table block with a given number of rows and columns.

        Args:
            context_id: id of the object to insert into.
            rows: number of rows to create.
            columns: number of columns to create.
            with_header_row: if True, mark the first row as a header row.
            target_id: an existing block to insert relative to. None appends.
            position: where to insert, one of POSITIONS.

        Returns:
            The new table block id string.

        Example:
            tid = blocks.create_table(page, rows=3, columns=2,
                                      with_header_row=True)
        """
        req = self.c.new_request("BlockTableCreate")
        req.contextId = context_id
        if target_id:
            req.targetId = target_id
        req.position = self._enum("BlockTableCreate", "position", position)
        req.rows = rows
        req.columns = columns
        req.withHeaderRow = with_header_row
        resp = self.c.call("BlockTableCreate", req)
        return getattr(resp, "blockId", "")

    def add_table_row(self, context_id, target_row_id, position="Bottom"):
        """Add a row to a table, relative to an existing row.

        Args:
            context_id: id of the object the table lives in.
            target_row_id: id of an existing row block to position relative to.
            position: where to add the row, one of POSITIONS, usually "Bottom"
                or "Top".

        Returns:
            The BlockTableRowCreate response message.

        Example:
            blocks.add_table_row(page, existing_row_id, position="Bottom")
        """
        req = self.c.new_request("BlockTableRowCreate")
        req.contextId = context_id
        req.targetId = target_row_id
        req.position = self._enum("BlockTableRowCreate", "position", position)
        return self.c.call("BlockTableRowCreate", req)

    def add_table_column(self, context_id, target_column_id, position="Right"):
        """Add a column to a table, relative to an existing column.

        Args:
            context_id: id of the object the table lives in.
            target_column_id: id of an existing column block to position by.
            position: where to add the column, one of POSITIONS, usually "Right"
                or "Left".

        Returns:
            The BlockTableColumnCreate response message.

        Example:
            blocks.add_table_column(page, existing_column_id, position="Right")
        """
        req = self.c.new_request("BlockTableColumnCreate")
        req.contextId = context_id
        req.targetId = target_column_id
        req.position = self._enum("BlockTableColumnCreate", "position", position)
        return self.c.call("BlockTableColumnCreate", req)

    def fill_table_rows(self, context_id, row_ids):
        """Fill empty cells in the given table rows so every column has a cell.

        New table rows can be missing cells for some columns. This populates
        the empty cells so the rows are complete and editable.

        Args:
            context_id: id of the object the table lives in.
            row_ids: a single row id string, or a list of row ids to fill.

        Returns:
            The BlockTableRowListFill response message.

        Example:
            blocks.fill_table_rows(page, [row1_id, row2_id])
        """
        if isinstance(row_ids, str):
            row_ids = [row_ids]
        return self.c.call("BlockTableRowListFill", contextId=context_id,
                           blockIds=list(row_ids))
