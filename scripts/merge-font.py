#!/usr/bin/env python3
"""Merge Hangul glyphs into a Cascadia Code TrueType font.

The base font is intentionally kept intact except for:

* Hangul cmap entries and namespaced Pretendard glyphs;
* metrics/bounds tables that must describe the added glyphs;
* final Hanadia Mono naming and license metadata; and
* removal of the upstream DSIG, whose signature cannot survive a merge.

Imported glyphs retain their TrueType composite structure.  Their component
names are rewritten into a private namespace, and source hinting programs are
not copied because their CVT/program indexes belong to Pretendard rather than
the Cascadia Code instruction environment.
"""

from __future__ import annotations

import argparse
import copy
from fractions import Fraction
from pathlib import Path
from typing import Iterable

from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._g_l_y_f import (
    ARGS_ARE_XY_VALUES,
    Glyph,
    GlyphComponent,
    GlyphCoordinates,
)
from fontTools.ttLib.tables.ttProgram import Program


HANGUL_RANGES = (
    (0x1100, 0x11FF),  # Hangul Jamo
    (0x3130, 0x318F),  # Hangul Compatibility Jamo
    (0xA960, 0xA97F),  # Hangul Jamo Extended-A
    (0xAC00, 0xD7A3),  # Hangul Syllables
    (0xD7B0, 0xD7FF),  # Hangul Jamo Extended-B
)

NAME_PLATFORMS = (
    (1, 0, 0),  # Macintosh, Roman, English
    (3, 1, 0x0409),  # Windows, Unicode BMP, English (US)
)


def round_ot(value: Fraction | int) -> int:
    """Round exactly as OpenType's otRound: ties go toward +infinity."""

    fraction = value if isinstance(value, Fraction) else Fraction(value)
    return (2 * fraction.numerator + fraction.denominator) // (
        2 * fraction.denominator
    )


def scaled_int(value: int, numerator: int, denominator: int) -> int:
    """Scale a font-unit integer without introducing binary-float error."""

    return round_ot(Fraction(value * numerator, denominator))


def in_hangul_range(codepoint: int) -> bool:
    return any(start <= codepoint <= end for start, end in HANGUL_RANGES)


def unique_strings(values: Iterable[str | None]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def name_values(font: TTFont, name_id: int) -> list[str]:
    values: list[str] = []
    for record in font["name"].names:
        if record.nameID != name_id:
            continue
        try:
            value = record.toUnicode()
        except Exception as error:  # pragma: no cover - corrupt input path
            raise ValueError(
                f"cannot decode name ID {name_id} in {font.reader.file.name}"
            ) from error
        if value not in values:
            values.append(value)
    return values


def read_license_header(path: Path | None) -> str | None:
    if path is None:
        return None
    text = path.read_text(encoding="utf-8")
    paragraphs = text.strip().split("\n\n", 1)
    if not paragraphs or not paragraphs[0].strip():
        raise ValueError(f"license file has no copyright header: {path}")
    return paragraphs[0].strip()


def set_name_records(
    name_table,
    name_id: int,
    value: str,
    *,
    mac_value: str | None = None,
) -> None:
    name_table.removeNames(nameID=name_id)
    for platform_id, encoding_id, language_id in NAME_PLATFORMS:
        selected_value = (
            mac_value if platform_id == 1 and mac_value is not None else value
        )
        name_table.setName(
            selected_value,
            name_id,
            platform_id,
            encoding_id,
            language_id,
        )


def bounds(font: TTFont, glyph_name: str) -> tuple[int, int, int, int] | None:
    glyph = font["glyf"][glyph_name]
    coordinates, _, _ = glyph.getCoordinates(font["glyf"])
    if not coordinates:
        return None
    xs = [point[0] for point in coordinates]
    ys = [point[1] for point in coordinates]
    return min(xs), min(ys), max(xs), max(ys)


def calculate_vertical_shift(
    vertical_bounds: list[tuple[int, int, int, int]],
    ascent: int,
    descent: int,
) -> int:
    """Return the smallest shift that keeps imported outlines in the line box.

    TrueType has no separate baseline coordinate in a glyph.  Both pinned
    source fonts use y=0 as the baseline, so the normal result is zero.  The
    safety adjustment handles a future source whose outlines exceed the base
    line box without changing the base font's global metrics.
    """

    if not vertical_bounds:
        return 0

    minimum_y = min(item[1] for item in vertical_bounds)
    maximum_y = max(item[3] for item in vertical_bounds)
    allowed_minimum = descent
    allowed_maximum = ascent

    lower_shift = allowed_minimum - minimum_y
    upper_shift = allowed_maximum - maximum_y
    if lower_shift > upper_shift:
        raise ValueError(
            "scaled Hangul outlines do not fit Cascadia Code's vertical line box: "
            f"outline y={minimum_y}..{maximum_y}, "
            f"line box={allowed_minimum}..{allowed_maximum}"
        )
    if lower_shift > 0:
        return lower_shift
    if upper_shift < 0:
        return upper_shift
    return 0


def ensure_required_base_glyphs(base: TTFont) -> int:
    cmap = base.getBestCmap() or {}
    required = {"A": ord("A"), "M": ord("M"), "0": ord("0"), " ": ord(" ")}
    missing = [character for character, codepoint in required.items() if codepoint not in cmap]
    if missing:
        raise ValueError(f"base font is missing required ASCII glyphs: {missing}")

    widths = {base["hmtx"][cmap[codepoint]][0] for codepoint in required.values()}
    if len(widths) != 1:
        raise ValueError(f"base ASCII cell widths are not uniform: {sorted(widths)}")
    cell_width = next(iter(widths))
    if cell_width <= 0:
        raise ValueError(f"base ASCII cell width is not positive: {cell_width}")
    return cell_width


def selected_source_glyphs(source: TTFont) -> list[tuple[int, str]]:
    cmap = source.getBestCmap() or {}
    selected = [
        (codepoint, glyph_name)
        for codepoint, glyph_name in cmap.items()
        if in_hangul_range(codepoint)
    ]
    if not selected:
        raise ValueError("source font contains no glyphs in the requested Hangul ranges")
    return sorted(selected)


def dependency_closure(source: TTFont, roots: Iterable[str]) -> set[str]:
    source_glyf = source["glyf"]
    needed: set[str] = set()
    pending = list(roots)
    while pending:
        glyph_name = pending.pop()
        if glyph_name in needed:
            continue
        if glyph_name not in source_glyf.glyphs:
            raise ValueError(
                f"source composite references missing glyph {glyph_name!r}"
            )
        needed.add(glyph_name)
        glyph = source_glyf[glyph_name]
        if glyph.isComposite():
            pending.extend(component.glyphName for component in glyph.components)
    return needed


def validate_components(font: TTFont) -> None:
    glyph_names = set(font.getGlyphOrder())
    for glyph_name in font.getGlyphOrder():
        glyph = font["glyf"][glyph_name]
        if not glyph.isComposite():
            continue
        for component in glyph.components:
            if component.glyphName not in glyph_names:
                raise ValueError(
                    f"dangling component reference: {glyph_name} -> "
                    f"{component.glyphName}"
                )


def merge(args: argparse.Namespace) -> None:
    base = TTFont(args.base, lazy=False)
    source = TTFont(args.source, lazy=False)
    base.recalcTimestamp = False

    try:
        if "glyf" not in base or "glyf" not in source:
            raise ValueError("both input fonts must contain TrueType glyf outlines")
        if "hmtx" not in base or "hmtx" not in source:
            raise ValueError("both input fonts must contain horizontal metrics")

        cell_width = ensure_required_base_glyphs(base)
        base_upem = base["head"].unitsPerEm
        source_upem = source["head"].unitsPerEm
        if base_upem <= 0 or source_upem <= 0:
            raise ValueError("unitsPerEm must be positive in both fonts")

        selected = selected_source_glyphs(source)
        roots = unique_strings(glyph_name for _, glyph_name in selected)
        needed = dependency_closure(source, roots)
        source_order = source.getGlyphOrder()
        source_order_index = {name: index for index, name in enumerate(source_order)}
        ordered_needed = sorted(needed, key=source_order_index.__getitem__)

        base_order = base.getGlyphOrder()
        existing_names = set(base_order)
        aliases = {
            old_name: f"hanadia.g{source_order_index[old_name]:05d}"
            for old_name in ordered_needed
        }
        wrappers = {
            old_name: f"hanadia.w{source_order_index[old_name]:05d}"
            for old_name in roots
        }
        added_names = list(aliases.values()) + list(wrappers.values())
        collisions = existing_names.intersection(added_names)
        if collisions:
            raise ValueError(f"generated glyph name collides with base font: {collisions}")

        glyf = base["glyf"]
        hmtx = base["hmtx"]
        source_glyf = source["glyf"]

        for old_name in ordered_needed:
            new_name = aliases[old_name]
            glyph = copy.deepcopy(source_glyf[old_name])
            if glyph.isComposite():
                for component in glyph.components:
                    component.glyphName = aliases[component.glyphName]
                    # The component matrix is dimensionless.  Its translation
                    # is in source font units and must be scaled; point-number
                    # attachment has no explicit translation to scale.
                    if hasattr(component, "x"):
                        component.x = scaled_int(component.x, base_upem, source_upem)
                    if hasattr(component, "y"):
                        component.y = scaled_int(component.y, base_upem, source_upem)
            elif glyph.numberOfContours > 0:
                glyph.coordinates = GlyphCoordinates(
                    [
                        (
                            scaled_int(x, base_upem, source_upem),
                            scaled_int(y, base_upem, source_upem),
                        )
                        for x, y in glyph.coordinates
                    ]
                )

            # Pretendard's instruction stream refers to its own CVT and
            # fpgm/prep tables.  An empty program is safer than dangling
            # instruction semantics in the Cascadia Code instruction set.
            glyph.program = Program()
            glyf.glyphs[new_name] = glyph

            source_advance, source_lsb = source["hmtx"][old_name]
            hmtx.metrics[new_name] = (
                scaled_int(source_advance, base_upem, source_upem),
                scaled_int(source_lsb, base_upem, source_upem),
            )

        # All source aliases are present before composite bounds are resolved.
        for new_name in aliases.values():
            glyf[new_name].recalcBounds(glyf)

        source_bounds = [
            item
            for old_name in roots
            if (item := bounds(base, aliases[old_name])) is not None
        ]
        vertical_shift = calculate_vertical_shift(
            source_bounds,
            ascent=base["hhea"].ascent,
            descent=base["hhea"].descent,
        )

        wrapper_order: list[str] = []
        wrapper_offsets: dict[str, int] = {}
        for old_name in roots:
            root_alias = aliases[old_name]
            wrapper_name = wrappers[old_name]
            root_bounds = bounds(base, root_alias)
            if root_bounds is None:
                horizontal_offset = 0
            else:
                root_min_x, _, root_max_x, _ = root_bounds
                target_center = Fraction(2 * cell_width, 2)
                source_center = Fraction(root_min_x + root_max_x, 2)
                horizontal_offset = round_ot(target_center - source_center)

            wrapper = Glyph()
            wrapper.numberOfContours = -1
            component = GlyphComponent()
            component.glyphName = root_alias
            component.flags = ARGS_ARE_XY_VALUES
            component.x = horizontal_offset
            component.y = vertical_shift
            wrapper.components = [component]
            glyf.glyphs[wrapper_name] = wrapper
            wrapper.recalcBounds(glyf)
            hmtx.metrics[wrapper_name] = (
                2 * cell_width,
                wrapper.xMin if hasattr(wrapper, "xMin") else 0,
            )
            wrapper_order.append(wrapper_name)
            wrapper_offsets[old_name] = horizontal_offset

        final_order = base_order + list(aliases.values()) + wrapper_order
        base.setGlyphOrder(final_order)

        additions = {codepoint: wrappers[glyph_name] for codepoint, glyph_name in selected}
        for cmap_table in base["cmap"].tables:
            if cmap_table.isUnicode():
                cmap_table.cmap.update(additions)

        # Keep Cascadia Code's global line metrics and layout tables.  Rebuild
        # only derived metrics/ranges that must account for the new glyphs.
        base["maxp"].recalc(base)
        base["hhea"].recalc(base)
        base["OS/2"].recalcAvgCharWidth(base)
        base["OS/2"].recalcUnicodeRanges(base)
        base["post"].isFixedPitch = 1
        base["OS/2"].achVendID = "HNDI"
        validate_components(base)

        if "DSIG" in base:
            del base["DSIG"]

        style = args.weight
        family = "Hanadia Mono"
        full_name = f"{family} {style}"
        postscript_name = f"HanadiaMono-{style}"
        unique_id = f"{full_name}; Version 1.000; Hanadia Mono"
        name_table = base["name"]

        all_copyright_values = unique_strings(
            [
                read_license_header(args.cascadia_license),
                read_license_header(args.pretendard_license),
                *name_values(base, 0),
                *name_values(source, 0),
            ]
        )
        copyright_value = "\n".join(all_copyright_values)
        mac_copyright = "\n".join(
            value
            for value in all_copyright_values
            if _mac_roman_encodable(value)
        )

        set_name_records(name_table, 0, copyright_value, mac_value=mac_copyright)
        set_name_records(name_table, 1, family)
        set_name_records(name_table, 2, style)
        set_name_records(name_table, 3, unique_id)
        set_name_records(name_table, 4, full_name)
        set_name_records(name_table, 5, "Version 1.000")
        set_name_records(name_table, 6, postscript_name)
        set_name_records(name_table, 10, "Independent modified font for coding and terminal use.")
        set_name_records(
            name_table,
            13,
            "This Font Software is licensed under the SIL Open Font License, Version 1.1. "
            "See LICENSE and the LICENSES directory for the upstream notices.",
        )
        set_name_records(name_table, 14, "https://scripts.sil.org/OFL")
        set_name_records(name_table, 16, family)
        set_name_records(name_table, 17, style)
        set_name_records(name_table, 18, full_name)

        # Keep upstream attribution fields, while making both contributors
        # visible instead of silently replacing one with the other.
        for name_id in (7, 8, 9, 11, 12):
            values = unique_strings([*name_values(base, name_id), *name_values(source, name_id)])
            if values:
                combined = "\n".join(values)
                mac_combined = "\n".join(
                    value for value in values if _mac_roman_encodable(value)
                )
                set_name_records(
                    name_table,
                    name_id,
                    combined,
                    mac_value=mac_combined,
                )

        base["head"].fontRevision = 1.0
        # 0x7C259DC0 is fontTools' OpenType timestamp boundary.  Using this
        # fixed value avoids build-time timestamps and avoids its low-time
        # compatibility warning when the font is reopened.
        base["head"].created = 0x7C259DC0
        base["head"].modified = 0x7C259DC0

        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        base.save(output, reorderTables=False)

        print(
            f"merged {args.weight}: base UPM={base_upem}, source UPM={source_upem}, "
            f"scale={base_upem}/{source_upem}, cellWidth={cell_width}, "
            f"selectedCodepoints={len(selected)}, dependencyGlyphs={len(needed)}, "
            f"verticalShift={vertical_shift}, output={output}"
        )
        if wrapper_offsets:
            offsets = list(wrapper_offsets.values())
            print(
                f"centered {len(offsets)} Hangul roots; "
                f"horizontalOffsetRange={min(offsets)}..{max(offsets)}"
            )
    finally:
        source.close()
        base.close()


def _mac_roman_encodable(value: str) -> bool:
    try:
        value.encode("mac_roman")
    except UnicodeEncodeError:
        return False
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--weight",
        required=True,
        choices=("Light", "Regular", "SemiBold", "Bold"),
    )
    parser.add_argument("--cascadia-license", type=Path)
    parser.add_argument("--pretendard-license", type=Path)
    return parser.parse_args()


if __name__ == "__main__":
    merge(parse_args())
