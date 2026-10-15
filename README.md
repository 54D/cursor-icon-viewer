# Cursor icon viewer

A **local** page that lists the Cursor icon set from your existing Cursor installation.

## Run it

```bash
python3 serve.py
```

If Cursor is not in `/Applications/Cursor.app` or `~/Applications/Cursor.app`, set `CURSOR_APP` to the `.app` bundle or to the `resources/app` directory inside a Linux install:

```bash
CURSOR_APP="/Applications/Cursor.app" python3 serve.py
```

Alternatively you can simply ask to list the icon ids:

```bash
python3 serve.py --list
```

## Where the ids live

Cursor packs them into the workbench bundle. `serve.py` reads the first of these that exists:

- `Cursor.app/Contents/Resources/app/out/vs/workbench/workbench.glass.main.js`
- `Cursor.app/Contents/Resources/app/out/vs/workbench/workbench.desktop.main.js`

On a layout without the macOS bundle prefix, the same files hang off `resources/app/`.

Inside the bundle, search for `"cursor-icons.js"`, quotes included. That module holds two space-separated strings. The minified binding names change between builds. Match the strings by shape, not by those names.

The name string reuses a prefix of the previous id. The first character of each token is the prefix length, written as one base-36 digit. The rest of the token is appended:

```javascript
function decodeNames(packed) {
  const names = [];
  let prev = "";
  for (const token of packed.split(" ")) {
    const keep = Number.parseInt(token[0], 36);
    prev = prev.slice(0, keep) + token.slice(1);
    names.push(prev);
  }
  return names;
}
```

`0account` decodes to `account`. The next token `1dd` keeps `a` and appends `dd`, which is `add`. `5-circle` keeps five characters and appends `-circle`.

The codepoint string has one token per id, in the same order. Each token is a base-36 integer added to the running value. A leading minus is allowed:

```javascript
function decodeCodepoints(packed) {
  const points = [];
  let value = 0;
  for (const token of packed.split(" ")) {
    value += Number.parseInt(token, 36);
    points.push(value);
  }
  return points;
}
```

In Cursor 3.24.9 those codepoints run from U+EA60 through U+F5A8. A later catalog can use different values. The pairing by index is what matters.

The same module also has a shorter delta string for filled variants, and a spacer-free index string that points into it. Leave both alone. The page draws the outline set, which is what the Edit Icon pane shows.

To get the icon list:

1. Open the glass workbench file. Fall back to the desktop file if the glass file is absent.
2. Find the module key `"cursor-icons.js"`, quotes included, and take about 100KB after its closing quote. Searching without the quotes starts the scan inside the key, and every later string is then read off by one quote.
3. Split the window into double-quoted JavaScript strings, stepping over backslash escapes so an escaped quote does not end a string. Do not unescape. The 3.24.9 strings are plain text. An escaped character would fail the token checks below, so a build that starts escaping these strings stops the decode instead of producing wrong ids.
4. The name string has at least 50 tokens. Every token matches `[0-9a-z][0-9A-Za-z-]+`, and at least ten tokens have a hyphen after the first character (`5-circle`). Decode it with `decodeNames`. Expect exactly one such string.
5. The codepoint string has tokens that all match `-?[0-9a-z]+`, and its token count equals the name count. Decode it with `decodeCodepoints`. Expect exactly one such string. The shorter delta string in the module is the filled set, and the count check skips it.
6. Zip the two results by index. Sort by id for alphabetical order. The packed name string is already in that order.

`python3 serve.py --list` runs those steps and prints one id per line.

Reject the decode if either string is missing or ambiguous, a prefix length exceeds the previous id, any id repeats, or any codepoint falls outside 0..0x10FFFF.

## How a glyph is drawn

`workbench.glass.main.css` declares the face:

```css
@font-face {
  font-family: cursor-icons;
  src: url(../../media/cursor-icons-16.woff2) format("woff2");
}
```

The file on disk is:

`Cursor.app/Contents/Resources/app/out/media/cursor-icons-16.woff2`

`serve.py` reads that file at startup and answers `/font/cursor-icons.woff2` with it. The page sets `font-family: cursor-icons` and inserts the decoded character. A browser will not load the font from a `file://` page in another directory, which is why the viewer is a localhost server rather than a file you double-click.

## Check a decode

`workbench.glass.main.css` contains rules like:

```css
.codicon.codicon-circles:before {
  content: "\ea97";
  font-family: cursor-icons;
}
```

Decode the catalog and compare. For `circles` in 3.24.9 the codepoint is U+EA97 (decimal 60055). If a later release drops that rule, pick any other `codicon-<id>` rule that sets `font-family: cursor-icons` and compare that id. A mismatch means the two strings were paired wrong.

## What has to stay the same

A longer or shorter id list is fine. These have to keep holding:

- The module key is still the double-quoted string `"cursor-icons.js"`.
- Ids use only letters, digits, and hyphens.
- Ids stay prefix-compressed, one token per id, prefix length in the first character as a base-36 digit.
- Outline codepoints stay a parallel string of base-36 deltas.
- Those codepoints still select glyphs from the `cursor-icons` face in `cursor-icons-16.woff2`.

`CURSOR_APP` covers a different install location. It does not cover a different layout under `resources/app`. A new packing scheme or a move to another file needs a new decoder.
