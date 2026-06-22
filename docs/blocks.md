# Blocks domain

The blocks domain edits the content tree of a single Anytype object: the
paragraphs, headers, checkboxes, toggles, code blocks, dividers, list items,
file blocks, bookmarks, latex/embed blocks, tables, and the way they are
arranged (nesting, alignment, color, horizontal grids).

It is one class, `Blocks`, built around a connected `Anytype` client. Most
methods return the new block id string, or a list of ids; the edit methods
return the raw response message. Methods raise `RpcError` on a non-zero server
error.

## Setup

```python
import anytype_grpc

at = anytype_grpc.Anytype()          # auto-discovers the port, reads ANYTYPE_TOKEN
blocks = at.blocks
page = "bafy...someObjectId"          # the object whose blocks you edit
```

All methods take the object id as `context_id`. That object must be a normal
editable object (a page, note, task, and so on).

## Key concepts

- A block is one node in the object's content tree. Every create method returns
  the new block's id, which you reuse to position later blocks or to edit it.
- Position: when you insert or move a block you give a target block and a
  position relative to it. The names are `Top`, `Bottom`, `Left`, `Right`,
  `Inner`, `Replace`, `InnerFirst`, `None`. `Bottom` is the common append.
  `Inner` nests the block under the target (used for toggles and columns).
- Text style: text blocks share one style enum. The names are `Paragraph`,
  `Header1`, `Header2`, `Header3`, `Quote`, `Code`, `Title`, `Checkbox`,
  `Marked` (bullet list), `Numbered`, `Toggle`, `Description`, `Callout`,
  `ToggleHeader1`, `ToggleHeader2`, `ToggleHeader3`.

## Things to remember

- You cannot add blocks to a Type object or a Set object. The server replies
  "restricted: Blocks". Edit those through object details instead (see the
  objects domain).
- Per-view dataview columns are not handled here; they live in the views domain.
- A horizontal grid is not one call. You create the cards as a vertical stack,
  then move them so they wrap into columns. Use `grid()`; it does the moves.
- `Inner` nesting preserves the order of the moved blocks. `make_toggle()` uses
  this to place children inside a toggle.

## Creating blocks

Every create method shares three optional keyword arguments:

- `target_id`: an existing block to insert relative to. `None` appends to the
  object root.
- `position`: where to insert, a position name (default `"Bottom"`).

### add_text(context_id, text="", style="Paragraph", \*, target_id=None, position="Bottom", color=None, background_color=None)

Create a text block (paragraph, header, quote, callout, list item, and so on).

- `context_id` (str): the object to insert into.
- `text` (str): the block text.
- `style` (str): a text style name (see Key concepts). Default `"Paragraph"`.
- `color` (str, optional): text color name, for example `"red"`.
- `background_color` (str, optional): block background color name.
- Returns: the new block id (str).

```python
bid = blocks.add_text(page, "A heading", style="Header2")
note = blocks.add_text(page, "important", color="red", background_color="yellow")
```

### add_header(context_id, text, level=1, \*, target_id=None, position="Bottom")

Create a header at level 1, 2, or 3.

- `level` (int): 1, 2, or 3. Maps to `Header1`, `Header2`, `Header3`.
- Returns: the new block id (str).

```python
bid = blocks.add_header(page, "Section", level=2)
```

### add_checkbox(context_id, text="", checked=False, \*, target_id=None, position="Bottom")

Create a checkbox (to do) block.

- `checked` (bool): whether it starts checked.
- Returns: the new block id (str).

```python
bid = blocks.add_checkbox(page, "Buy milk", checked=False)
```

### add_toggle(context_id, text="", \*, target_id=None, position="Bottom")

Create an empty toggle block. To put children inside it, use `make_toggle()` or
create the children and then `move(..., position="Inner")` them under it.

- Returns: the new toggle block id (str).

```python
tid = blocks.add_toggle(page, "Details")
```

### add_code(context_id, text="", \*, target_id=None, position="Bottom")

Create a code block.

- Returns: the new block id (str).

```python
bid = blocks.add_code(page, "print('hi')")
```

### add_marked(context_id, text="", numbered=False, \*, target_id=None, position="Bottom")

Create a list item: a bullet (default) or a numbered item.

- `numbered` (bool): True for a numbered item, False for a bullet.
- Returns: the new block id (str).

```python
bid = blocks.add_marked(page, "First point")
num = blocks.add_marked(page, "Step one", numbered=True)
```

### add_divider(context_id, dots=False, \*, target_id=None, position="Bottom")

Create a divider: a thin horizontal line, or a row of dots.

- `dots` (bool): True for the dotted style, False for a line.
- Returns: the new block id (str).

```python
bid = blocks.add_divider(page)
```

### add_link(context_id, target_object_id, \*, card=False, target_id=None, position="Bottom")

Create a link block pointing at another object.

- `target_object_id` (str): the object id this link points to.
- `card` (bool): True renders a card with a cover, False renders inline text.
- Returns: the new block id (str).

```python
bid = blocks.add_link(page, other_object_id, card=True)
```

### add_file(context_id, file_object_id, kind="File", \*, embed=False, target_id=None, position="Bottom")

Create a file block referencing an already uploaded file object. Upload the file
first with the client's `upload_file` helper, then pass the returned id here.

- `file_object_id` (str): the file object id from `upload_file`.
- `kind` (str): file type name, one of `"File"`, `"Image"`, `"Video"`,
  `"Audio"`, `"PDF"`. Picks how Anytype renders it.
- `embed` (bool): True renders embedded, False renders as a link.
- Returns: the new block id (str).

```python
fid = at.upload_file(url="http://127.0.0.1:8000/pic.png")
bid = blocks.add_file(page, fid, kind="Image", embed=True)
```

### add_bookmark(context_id, url, \*, target_id=None, position="Bottom")

Create a bookmark block for a web URL. The block starts empty and Anytype
fetches the title and preview asynchronously.

- `url` (str): the web URL.
- Returns: the new block id (str).

```python
bid = blocks.add_bookmark(page, "https://anytype.io")
```

### add_latex(context_id, text="", processor="Latex", \*, target_id=None, position="Bottom")

Create a latex or embed block. For math use processor `"Latex"`. For an embedded
site use the matching processor name and put the URL in `text`. Processor names
include `Latex`, `Mermaid`, `Chart`, `Youtube`, `Vimeo`, `Soundcloud`,
`GoogleMaps`, `Miro`, `Figma`, `Twitter`, `OpenStreetMap`, `Reddit`, `Facebook`,
`Instagram`, `Telegram`, `GithubGist`, `Codepen`, `Bilibili`, `Excalidraw`,
`Kroki`, `Graphviz`, `Sketchfab`, `Image`, `Drawio`, `Spotify`.

- Returns: the new block id (str).

```python
bid = blocks.add_latex(page, "E = mc^2", processor="Latex")
diagram = blocks.add_latex(page, "graph TD; A-->B", processor="Mermaid")
```

### create_raw(context_id, block_dict, \*, target_id=None, position="Bottom")

Create a block from a raw `anytype.model.Block` dict, for content kinds this
module does not wrap directly (for example a table of contents).

- `block_dict` (dict): a dict matching the Block message. Enum fields may be
  given by their proto name strings.
- Returns: the new block id (str).

```python
bid = blocks.create_raw(page, {"tableOfContents": {}})
```

## Deleting, moving, duplicating, copy/paste

### delete(context_id, block_ids)

Delete one or more blocks.

- `block_ids` (str or list of str): one id, or a list of ids.
- Returns: the response message.

```python
blocks.delete(page, [bid1, bid2])
```

### move(context_id, block_ids, drop_target_id, position="Bottom", \*, target_context_id=None)

Move blocks within an object, or into another object. Order is preserved.

- `block_ids` (str or list of str): the blocks to move.
- `drop_target_id` (str): the block to drop relative to.
- `position` (str): a position name. `"Inner"` nests under the target.
- `target_context_id` (str, optional): destination object id. Defaults to
  `context_id` (move within the same object).
- Returns: the response message.

```python
blocks.move(page, [bid], header_id, position="Inner")
```

### duplicate(context_id, block_ids, target_id, position="Bottom", \*, target_context_id=None)

Duplicate blocks and insert the copies relative to a target.

- `block_ids` (str or list of str): the source blocks to copy.
- `target_id` (str): the block to insert the copies relative to.
- `target_context_id` (str, optional): destination object id. Defaults to
  `context_id`.
- Returns: a list of the new block ids (list of str).

```python
new_ids = blocks.duplicate(page, [bid], bid, position="Bottom")
```

### copy(context_id, blocks, \*, range_from=None, range_to=None)

Copy blocks to the internal clipboard slots and return them. The returned dict
feeds `paste()`.

- `blocks` (list of dict): raw Block dicts to copy, each needs at least an id,
  for example `[{"id": bid}]`.
- `range_from`, `range_to` (int, optional): offsets for a partial text copy.
- Returns: a dict with keys `textSlot` (str), `htmlSlot` (str), `anySlot`
  (list of Block messages).

```python
slots = blocks.copy(page, [{"id": bid}])
blocks.paste(other_page, focused_block_id=target, **slots)
```

### paste(context_id, \*, focused_block_id="", textSlot="", htmlSlot="", anySlot=None, url="", selected_block_ids=None)

Paste clipboard slot content into an object. Supply slots from `copy()`, or a
plain text/html string, or a url. At least one slot must be non empty.

- `focused_block_id` (str): the block the caret is in. Empty appends.
- `textSlot` (str): plain text to paste.
- `htmlSlot` (str): html to paste.
- `anySlot` (list): Block messages or raw Block dicts, usually from `copy()`.
- `url` (str): a url to paste (becomes a bookmark or link).
- `selected_block_ids` (list of str): blocks the paste should replace.
- Returns: a list of the new block ids (list of str).

```python
ids = blocks.paste(page, textSlot="hello")
```

### split(context_id, block_id, at_offset, \*, style=None, mode="BOTTOM")

Split a text block in two at a character offset.

- `at_offset` (int): the character index to split at.
- `style` (str, optional): text style name for the new block. Defaults to the
  original block's style on the server side.
- `mode` (str): where the new block goes, one of `"BOTTOM"`, `"TOP"`,
  `"INNER"`, `"TITLE"`. Default `"BOTTOM"`.
- Returns: the new block id (str).

```python
new_id = blocks.split(page, bid, 5)
```

### merge(context_id, first_block_id, second_block_id)

Merge the second text block into the first.

- `first_block_id` (str): the block that keeps existing and receives content.
- `second_block_id` (str): the block whose content is appended then removed.
- Returns: the response message.

```python
blocks.merge(page, top_id, bottom_id)
```

## Editing text and style

### set_text(context_id, block_id, text)

Replace a text block's text content.

- Returns: the response message.

```python
blocks.set_text(page, bid, "new content")
```

### set_style(context_id, block_id, style)

Change a text block's style.

- `style` (str): a text style name (see Key concepts).
- Returns: the response message.

```python
blocks.set_style(page, bid, "Quote")
```

### set_color(context_id, block_id, color)

Set the text color of a text block.

- `color` (str): a color name, for example `"red"`, `"blue"`, `"grey"`.
- Returns: the response message.

```python
blocks.set_color(page, bid, "red")
```

### set_checked(context_id, block_id, checked)

Check or uncheck a checkbox block.

- `checked` (bool): True to check, False to uncheck.
- Returns: the response message.

```python
blocks.set_checked(page, bid, True)
```

### set_mark(context_id, block_ids, mark_type, range_from, range_to, param="")

Apply an inline text mark to a character range. The mark covers characters from
`range_from` (inclusive) up to `range_to` (exclusive) in each listed block.

- `block_ids` (str or list of str): the blocks to mark.
- `mark_type` (str): one of `Strikethrough`, `Keyboard`, `Italic`, `Bold`,
  `Underscored`, `Link`, `TextColor`, `BackgroundColor`, `Mention`, `Emoji`,
  `Object`.
- `range_from` (int), `range_to` (int): the character range.
- `param` (str): extra data for marks that need it. `Link` needs the url,
  `TextColor` and `BackgroundColor` need a color name, `Object` and `Mention`
  need the target object id, `Emoji` needs the emoji.
- Returns: the response message.

```python
blocks.set_mark(page, bid, "Bold", 0, 5)
blocks.set_mark(page, bid, "Link", 0, 5, param="https://x.com")
```

### turn_into(context_id, block_ids, style)

Convert one or more blocks into a different text style. This is the list-level
"turn into" the app uses; it handles structural conversions cleanly.

- `block_ids` (str or list of str): the blocks to convert.
- `style` (str): a target text style name.
- Returns: the response message.

```python
blocks.turn_into(page, [bid], "Header2")
```

### set_align(context_id, block_ids, align)

Set the horizontal alignment of one or more blocks.

- `block_ids` (str or list of str): the blocks. An empty list applies the
  alignment to the object layout itself.
- `align` (str): one of `"AlignLeft"`, `"AlignCenter"`, `"AlignRight"`,
  `"AlignJustify"`.
- Returns: the response message.

```python
blocks.set_align(page, [bid], "AlignCenter")
```

### set_background_color(context_id, block_ids, color)

Set the background color of one or more blocks.

- `block_ids` (str or list of str): the blocks.
- `color` (str): a color name, for example `"yellow"`, `"grey"`.
- Returns: the response message.

```python
blocks.set_background_color(page, [bid], "yellow")
```

## High-level helpers

### make_toggle(context_id, title, child_block_ids, \*, target_id=None, position="Bottom")

Create a toggle and nest existing blocks inside it. Creates a Toggle block with
the given title, then moves each block in `child_block_ids` Inner (under the
toggle), preserving order.

- `title` (str): the toggle's visible title text.
- `child_block_ids` (list of str): existing block ids to put inside, in order.
- Returns: the new toggle block id (str).

```python
a = blocks.add_text(page, "inside one")
b = blocks.add_text(page, "inside two")
tid = blocks.make_toggle(page, "Click me", [a, b])
```

### grid(context_id, card_block_ids, per_row)

Arrange existing blocks into a horizontal grid of rows. Anytype has no single
grid call; this helper performs the moves that wrap blocks into columns.

Technique applied for you: for each row, the second card is moved to the Right
of the first card, which makes Anytype wrap them in a Row layout with two Column
layout blocks. Each later card in the row is moved Right of the previous card,
which the server resolves into a new column in that row. If you need pixel-exact
control, do the moves yourself with `move()`.

- `card_block_ids` (list of str): a flat list of existing block ids, in order.
  Typically link cards made with `add_link(card=True)`.
- `per_row` (int): how many cards per row (the column count). Must be >= 1.
- Returns: a list of rows, where each row is the list of block ids in it.

```python
ids = [blocks.add_link(page, oid, card=True) for oid in objs]
rows = blocks.grid(page, ids, per_row=3)
```

## Tables

### create_table(context_id, rows, columns, \*, with_header_row=False, target_id=None, position="Bottom")

Create a table block with a given number of rows and columns.

- `rows` (int): number of rows.
- `columns` (int): number of columns.
- `with_header_row` (bool): if True, mark the first row as a header row.
- Returns: the new table block id (str).

```python
tid = blocks.create_table(page, rows=3, columns=2, with_header_row=True)
```

### add_table_row(context_id, target_row_id, position="Bottom")

Add a row to a table, relative to an existing row.

- `target_row_id` (str): an existing row block to position by.
- `position` (str): usually `"Bottom"` or `"Top"`.
- Returns: the response message.

```python
blocks.add_table_row(page, existing_row_id, position="Bottom")
```

### add_table_column(context_id, target_column_id, position="Right")

Add a column to a table, relative to an existing column.

- `target_column_id` (str): an existing column block to position by.
- `position` (str): usually `"Right"` or `"Left"`.
- Returns: the response message.

```python
blocks.add_table_column(page, existing_column_id, position="Right")
```

### fill_table_rows(context_id, row_ids)

Fill empty cells in the given table rows so every column has a cell. New rows can
be missing cells for some columns; this populates them so the rows are complete
and editable.

- `row_ids` (str or list of str): the row ids to fill.
- Returns: the response message.

```python
blocks.fill_table_rows(page, [row1_id, row2_id])
```
