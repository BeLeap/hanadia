# Hanadia Mono

## About

Hanadia Mono is a coding font combining the Latin, programming symbols, and
OpenType features of Cascadia Code with Korean glyphs derived from Pretendard.
It is an independent derivative project for terminal and coding use.

The generated static fonts are:

- `Hanadia Mono Light`
- `Hanadia Mono Regular`
- `Hanadia Mono SemiBold`
- `Hanadia Mono Bold`

## Screenshots / Examples

No screenshots are committed yet. Use the following sample after installing the
font:

```text
abcdefghijklmnopqrstuvwxyz
ABCDEFGHIJKLMNOPQRSTUVWXYZ
0123456789

Hello, 세계!
가나다라마바사아자차카타파하
한글 English 1234
ABC가나다DEF
가A나B다C

-> => != === !== >= <=
ffi fi fl

│ ─ ┌ ┐ └ ┘ ├ ┤ ┬ ┴ ┼
```

The following lines are an eight-column alignment test when the terminal uses
the font's horizontal advances:

```text
12345678
가나다라
AB가CD나
한글ABCD
```

Each ASCII character occupies one Cascadia Code cell. Each mapped Hangul
character occupies two of those cells.

## Building

Requirements: Nix with flakes enabled.

```sh
nix flake check
nix build
find -L result/share/fonts/truetype -type f -name '*.ttf' -print
```

`nix build` creates `result/share/fonts/truetype/HanadiaMono-*.ttf`. The build
fetches the pinned upstream archives inside the Nix sandbox; no upstream font
binary is stored in this repository.

## Installation

On Linux:

```sh
mkdir -p ~/.local/share/fonts/hanadia-mono
cp result/share/fonts/truetype/*.ttf ~/.local/share/fonts/hanadia-mono/
fc-cache -f ~/.local/share/fonts/hanadia-mono
```

On macOS, copy the generated TTF files to `~/Library/Fonts/` and select
`Hanadia Mono` in the terminal or editor.

## Nix / Home Manager

Add the flake input:

```nix
{
  inputs.hanadia-mono.url = "github:beleap/hanadia";

  # ...
  outputs = { self, nixpkgs, home-manager, hanadia-mono, ... }@inputs: {
    # ...
  };
}
```

Then add the package to Home Manager:

```nix
{ pkgs, inputs, ... }:
{
  home.packages = [
    inputs.hanadia-mono.packages.${pkgs.system}.default
  ];

  fonts.fontconfig.enable = true;
}
```

## Alacritty

```toml
[font.normal]
family = "Hanadia Mono"

[font.bold]
family = "Hanadia Mono"
style = "Bold"
```

## How It Is Built

The flake pins and fetches these official release archives:

| Upstream | Release/tag | Git commit | Archive SRI hash |
| --- | --- | --- | --- |
| Cascadia Code | `v2407.24` | `56bcca3f2c1e4cb19458954f0e2bb4635960df91` | `sha256-5npo7jOG22P0i5BUvRlup1K8ak67TfNa3OZzPaUMhHQ=` |
| Pretendard | `v1.3.9` | `5c41199ea0024a9e0b2cb31735265056e5472d76` | `sha256-BL41GnTWv31gxICjCH5R0YVIXTWlICMUKvHfGeuMQoo=` |

The base file is the matching static `CascadiaCode-<weight>.ttf`. The source
file is selected by the `pretendardWeightFor` mapping in `flake.nix` and
defaults to the matching `Pretendard-<weight>.ttf` from the release archive's
`public/static/alternative/` directory. Change only the `Regular` mapping to
`Medium` if a heavier Korean regular cut is desired. License files are also
fetched by fixed commit and compared byte-for-byte with the checked-in copies
during the build.

`scripts/merge-font.py` performs the merge as follows:

1. It reads both `head.unitsPerEm` values and scales Pretendard coordinates and
   horizontal metrics by `CascadiaCode.unitsPerEm / Pretendard.unitsPerEm` with
   exact rational rounding.
2. It selects Hangul Jamo, Compatibility Jamo, Extended-A, Hangul Syllables,
   and Extended-B cmap entries. Recursive composite dependencies are copied
   into a `hanadia.g#####` glyph namespace, with component references rewritten.
3. It adds centered two-cell wrapper glyphs in a `hanadia.w#####` namespace.
   Their advance is exactly twice the measured `A`/`M`/`0`/space cell width, and
   their visual bounding box is centered in that width.
4. Cascadia Code's glyphs, GSUB, GPOS, GDEF, and global vertical metrics remain
   the base. Only derived bounds, horizontal summary metrics, and Unicode
   ranges are recalculated. Source hinting programs are not copied because
   their CVT and instruction programs belong to Pretendard.
5. The generated names are `Hanadia Mono <weight>`, with matching
   `HanadiaMono-<weight>` PostScript names. Upstream attribution and license
   information are retained in the `name` table.

The build runs `scripts/verify-font.py` on every generated weight. It checks
that the TTF reopens, components are not dangling, ASCII is one cell, Hangul
is two cells, vertical outlines fit the base line box, required names and
license notices exist, and Cascadia Code's contextual `calt` feature remains.

## License

Hanadia Mono is a modified Font Software derivative of Cascadia Code and
Pretendard. The fixed upstream license files state that both upstream Font
Software distributions use the SIL Open Font License, Version 1.1. Hanadia
Mono is distributed under the SIL Open Font License, Version 1.1 as well.

The OFL permits use, study, copying, merging, embedding, modification,
redistribution, and sale of modified copies, subject to its conditions. In
particular, the Font Software may not be sold by itself, copies must retain
the applicable notices and license, and a Modified Version must not use a
Reserved Font Name as its primary font name.

The generated primary names are `Hanadia Mono`, `Hanadia Mono <weight>`, and
`HanadiaMono-<weight>`. They do not use the upstream primary names or the
reserved name `Cascadia Code` or `Pretendard`. Attribution fields may still
mention upstream projects and contributors. Pretendard's original metadata
also records attribution to Inter, Source/Source Han Sans, and M PLUS 1p;
those names are retained only as attribution, not as Hanadia Mono's primary
name.

The upstream copyright and license headers, including their Reserved Font
Name declarations, are preserved in `LICENSES/` and in the generated font's
metadata where appropriate. The exact upstream texts are:

- `LICENSES/Cascadia-Code-OFL.txt`
- `LICENSES/Pretendard-OFL.txt`

`LICENSE` contains the OFL 1.1 text applied to Hanadia Mono. A release archive
includes that file and both upstream notices so the TTF files are not
separated from their licensing information.

Hanadia Mono is an independent derivative project. It is not an official
release of, endorsed by, or officially supported by Microsoft, the Cascadia
Code project, the Pretendard project, or any upstream copyright holder.

## Upstream Projects

- [Microsoft Cascadia Code](https://github.com/microsoft/cascadia-code),
  release `v2407.24` at commit
  `56bcca3f2c1e4cb19458954f0e2bb4635960df91`.
- [orioncactus Pretendard](https://github.com/orioncactus/pretendard),
  release `v1.3.9` at commit
  `5c41199ea0024a9e0b2cb31735265056e5472d76`.

These links acknowledge source contributions only; they do not imply upstream
review, endorsement, or support for Hanadia Mono.

## Releases

A new binary release is built automatically whenever a commit is pushed to the
`master` branch. Pull requests do not run the release workflow.

Release artifacts are produced directly from `nix flake check` and `nix build`.
Each archive contains the generated TTF files, `LICENSE.txt`, both upstream
license notices, `README.txt`, and `BUILD-INFO.txt` with the release tag,
commit SHA, and pinned upstream revisions.

Tags use the format:

```text
vYYYY.MM.DD.<run-number>
```

The date is the UTC calendar date of the pushed commit and the final component
is `github.run_number`. Tags are never force-updated. If a rerun finds the
same completed release, it leaves that release unchanged; if a tag already
points at a different commit, the workflow fails rather than moving it.

The latest non-prerelease build is available from the GitHub Releases page.

## Known Limitations

- The current build creates Light, Regular, SemiBold, and Bold upright static
  TTFs only. Italic and variable fonts are outside this scope.
- Only the requested Hangul ranges are imported from Pretendard. Its Latin,
  punctuation, and layout features are not used to replace Cascadia Code.
- Imported Pretendard hinting programs are intentionally omitted; the base
  Cascadia Code instruction tables are retained.
- A terminal that hard-codes Unicode East Asian Width instead of using font
  advances may not honor the two-cell behavior. The generated `hmtx` table
  still enforces the requested widths.
- The upstream release archives are large because they contain multiple font
  formats and weights; Nix downloads them only when their fixed store paths
  are unavailable.
