# AGENTS.md

Read this before changing anything. `README.md` explains what the tool does and how the ids are decoded. This file lists what agents must and must not do, and what to check when a Cursor update breaks the tool.

## What this repo is

A page on localhost that draws every Cursor icon id, using the icon font from the user's installed Cursor. The repo has two code files and no dependencies.

- `serve.py` finds the Cursor install, decodes the id catalog from the workbench bundle, and serves three routes.
- `index.html` is the whole page. It fetches `/api/icons` and draws the grid with the `cursor-icons` font.
- `README.md` is for users.
- `AGENTS.md` is for agents.

## Rules that hold for every Cursor version

- Never copy Cursor assets or data into this repo. That covers the font file, the packed id strings, and a decoded id list. The font and the catalog are read from the install at startup and passed straight to the browser. Do not vendor them, cache them to disk, or embed them in `index.html`. A handful of ids as examples in docs is fine.
- Use the standard library only. The system `python3` is 3.8, so the code must run there. No `X | Y` type unions, no `list[int]` generics, no `match`, no `str.removeprefix`.
- The server binds to `127.0.0.1` and serves a fixed route table: `/`, `/api/icons`, `/font/cursor-icons.woff2`. Do not add a route that maps a request path to a file.
- `index.html` stays one file with no CDN, framework, or build step. The browser gets the font only from `/font/cursor-icons.woff2`.
- Keep ids exactly as decoded. Ids are case sensitive and some are mixed case, such as `chatBubble` and `trafficCone`. Do not lowercase, deduplicate, or reorder them. The page lowercases only to match the search text. Order is Python's sort by id.
- The page lists every id Cursor accepts, including alternate names that draw the same glyph. The Edit Icon pane shows fewer, 672 in 3.24.9. The difference is expected.
- `serve.py` reads the install, the catalog, and `index.html` once at startup. Restart the server after editing `index.html` or after a Cursor update.
- Keep the code minimal. Do not extract a helper that has one caller, and do not add a util folder. Update `README.md` in the same change whenever the decode steps change.
- The owner edits these files by hand. Re-read a file before editing it and use targeted edits. A full rewrite from memory has already erased the owner's edits once.

## After a Cursor update

Run these first.

```bash
python3 serve.py --list | wc -l
python3 -c "import serve; n, p, *_ = serve.load_install(); print(len(n), hex(p[n.index('circles')]))"
```

Last known good: Cursor 3.24.9, commit `cd6d2a1f2e56e9841f0ed9c7c24542087b4e69b0`, 808 ids, `circles` at `0xea97`. The id count may change. The `circles` codepoint may change too, but it must match the CSS rule.

```bash
rg -o 'codicon-circles:before\{content:"[^"]*"' \
  /Applications/Cursor.app/Contents/Resources/app/out/vs/workbench/workbench.glass.main.css
```

Then run `python3 serve.py` and look at the page. Every cell must show an icon. A blank cell or a stray letter means the font or the codepoint pairing is wrong, even though the decode did not fail. If `circles` is gone, pick another `codicon-<id>` rule in the same CSS file that sets `font-family:cursor-icons`.

### When `serve.py` stops with an error

| Message | Likely cause | What to change |
|---|---|---|
| `Cursor was not found.` | Install moved, or the font file was renamed. The install check requires both `product.json` and the font. | Add the new location to `app_roots` in `load_install`. If the font was renamed, update `FONT_FILE_DIR`. The new name is in the `@font-face` rule for `cursor-icons` in `workbench.glass.main.css`. |
| `No workbench bundle under ...` | Both bundle files were renamed or moved. | List `out/vs/workbench/` and update the file names tried in `load_install`. |
| `cursor-icons.js was not found in the workbench bundle.` | The module was renamed or the bundle was restructured. | Search the bundle for the packed ids, for example `0account 1dd`, then read the module key just before that string. Update `MODULE_KEY`. Keep the quotes in it. |
| `Expected one packed id string, found 0.` | Ids are now escaped, the tokens changed shape, or the strings sit more than 100KB after the module key. | Inspect the strings after the key. Adjust the token regex, the 50 token minimum, the 10 hyphen minimum, or the 100KB window to match what the bundle now contains. |
| `Expected one packed id string, found N` with N above 1 | Another string now passes the name checks. | Tighten the name checks until exactly one string matches. Do not pick the first match. |
| `Expected one codepoint string, found 0.` | The codepoint string no longer has one token per id, or its token shape changed. | Compare its token count with the id count and adjust the codepoint regex. |
| `Expected one codepoint string, found N` with N above 1 | A second string has the same token count as the ids. | Tighten the checks. The filled variants string is shorter than the id list in 3.24.9, and the count check is what skips it. |
| `Packed id prefix is longer...`, `Decoded icon ids are not unique.`, or `Decoded codepoint is outside Unicode.` | The packing scheme itself changed. | Write a new decoder. Update `README.md` to match. |

Do not loosen the checks just to make a failing decode pass. Examples are accepting several matches, taking the first one, or skipping the uniqueness test. The checks make a changed bundle stop the tool instead of drawing wrong ids. Do not hardcode ids or codepoints as a fallback either.

## What the code assumes

If one of these stops being true, the decoder needs a change.

- The module key is the double-quoted string `"cursor-icons.js"`.
- Ids use only letters, digits, and hyphens.
- Ids are prefix compressed, one token per id, with the prefix length in the first character as one base-36 digit.
- Codepoints are a second string of base-36 deltas, one token per id, in the same order.
- Those codepoints select glyphs in the `cursor-icons` face, loaded from `cursor-icons-16.woff2`.
- The glass and desktop workbench bundles hold the same catalog string in 3.24.9. The code uses the glass bundle first and falls back to the desktop one.
- `CURSOR_APP` covers a different install location. It does not cover a different layout under `resources/app`.
