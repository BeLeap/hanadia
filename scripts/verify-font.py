#!/usr/bin/env python3
"""Verify the structural, naming, licensing, and width invariants of Hanadia Mono."""

from __future__ import annotations

import argparse
from pathlib import Path
from fontTools.ttLib import TTFont


HANGUL_RANGES = (
    (0x1100, 0x11FF),
    (0x3130, 0x318F),
    (0xA960, 0xA97F),
    (0xAC00, 0xD7A3),
    (0xD7B0, 0xD7FF),
)

PRIMARY_NAME_IDS = (1, 2, 3, 4, 5, 6, 16, 17, 18)
RESERVED_NAMES = (
    "Pretendard",
    "Cascadia Code",
    "Source",
    "Inter",
    "M PLUS 1",
)
REQUIRED_HANGUL = "가한글힣ㄱㅏ"
ALIGNMENT_CASES = {
    "12345678": 8,
    "가나다라": 8,
    "AB가CD나": 8,
    "한글ABCD": 8,
}


def in_hangul_range(codepoint: int) -> bool:
    return any(start <= codepoint <= end for start, end in HANGUL_RANGES)


def all_name_strings(font: TTFont) -> list[str]:
    values: list[str] = []
    for record in font["name"].names:
        try:
            value = record.toUnicode()
        except Exception as error:  # pragma: no cover - corrupt input path
            raise AssertionError(
                f"cannot decode name ID {record.nameID}"
            ) from error
        if value not in values:
            values.append(value)
    return values


def name_strings(font: TTFont, name_id: int) -> list[str]:
    return [
        record.toUnicode()
        for record in font["name"].names
        if record.nameID == name_id
    ]


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def lookup_type(lookup, subtable):
    """Return a concrete lookup type, unwrapping GSUB extensions."""

    if lookup.LookupType == 7:
        return subtable.ExtensionLookupType, subtable.ExtSubTable
    return lookup.LookupType, subtable


def has_contextual_substitution(font: TTFont, feature_tag: str) -> bool:
    table = font["GSUB"].table
    for feature_record in table.FeatureList.FeatureRecord:
        if feature_record.FeatureTag != feature_tag:
            continue
        for lookup_index in feature_record.Feature.LookupListIndex:
            lookup = table.LookupList.Lookup[lookup_index]
            for subtable in lookup.SubTable:
                concrete_type, _ = lookup_type(lookup, subtable)
                if concrete_type in (5, 6):
                    return True
    return False


def assert_no_dangling_components(font: TTFont) -> None:
    glyph_names = set(font.getGlyphOrder())
    glyf = font["glyf"]
    for glyph_name in font.getGlyphOrder():
        glyph = glyf[glyph_name]
        if not glyph.isComposite():
            continue
        for component in glyph.components:
            assert_true(
                component.glyphName in glyph_names,
                f"dangling component reference: {glyph_name} -> {component.glyphName}",
            )


def glyph_bounds(font: TTFont, glyph_name: str) -> tuple[int, int, int, int] | None:
    glyph = font["glyf"][glyph_name]
    coordinates, _, _ = glyph.getCoordinates(font["glyf"])
    if not coordinates:
        return None
    xs = [point[0] for point in coordinates]
    ys = [point[1] for point in coordinates]
    return min(xs), min(ys), max(xs), max(ys)


def verify_alignment(font: TTFont, cmap: dict[int, str], cell_width: int) -> None:
    for text, expected_cells in ALIGNMENT_CASES.items():
        total_width = 0
        for character in text:
            codepoint = ord(character)
            assert_true(
                codepoint in cmap,
                f"alignment sample character is missing: U+{codepoint:04X}",
            )
            total_width += font["hmtx"][cmap[codepoint]][0]
        expected_width = expected_cells * cell_width
        assert_true(
            total_width == expected_width,
            f"alignment sample {text!r}: width {total_width}, "
            f"expected {expected_width}",
        )


def verify(path: Path, expected_style: str) -> None:
    font = TTFont(path, lazy=False)
    try:
        required_tables = {
            "head",
            "hhea",
            "maxp",
            "OS/2",
            "hmtx",
            "cmap",
            "loca",
            "glyf",
            "name",
            "post",
        }
        missing_tables = sorted(required_tables.difference(font.keys()))
        assert_true(not missing_tables, f"missing required tables: {missing_tables}")

        glyph_order = font.getGlyphOrder()
        assert_true(
            len(glyph_order) == font["maxp"].numGlyphs,
            "maxp.numGlyphs does not match glyph order",
        )
        assert_true(font["post"].isFixedPitch == 1, "font is not marked monospace")
        assert_no_dangling_components(font)

        cmap = font.getBestCmap() or {}
        required_codepoints = [ord(character) for character in REQUIRED_HANGUL]
        for codepoint in required_codepoints:
            assert_true(
                codepoint in cmap,
                f"required Hangul character is missing: U+{codepoint:04X}",
            )

        ascii_widths = {}
        for character in ("A", "M", "0", " "):
            codepoint = ord(character)
            assert_true(codepoint in cmap, f"required ASCII character is missing: {character!r}")
            ascii_widths[character] = font["hmtx"][cmap[codepoint]][0]
        assert_true(
            len(set(ascii_widths.values())) == 1,
            f"ASCII cell widths differ: {ascii_widths}",
        )
        cell_width = next(iter(ascii_widths.values()))
        assert_true(cell_width > 0, "ASCII cell width is not positive")

        for codepoint in range(0x20, 0x7F):
            assert_true(
                codepoint in cmap,
                f"ASCII cmap entry is missing: U+{codepoint:04X}",
            )
            width = font["hmtx"][cmap[codepoint]][0]
            assert_true(
                width == cell_width,
                f"ASCII glyph U+{codepoint:04X} has width {width}, "
                f"expected {cell_width}",
            )

        hangul_count = 0
        maximum_side_bearing_imbalance = 0
        for codepoint, glyph_name in cmap.items():
            if not in_hangul_range(codepoint):
                continue
            hangul_count += 1
            width = font["hmtx"][glyph_name][0]
            assert_true(
                width == 2 * cell_width,
                f"Hangul U+{codepoint:04X} has width {width}, "
                f"expected {2 * cell_width}",
            )
            bounds = glyph_bounds(font, glyph_name)
            if bounds is not None:
                minimum_x, minimum_y, maximum_x, maximum_y = bounds
                right_side_bearing = width - font["hmtx"][glyph_name][1] - (
                    maximum_x - minimum_x
                )
                side_bearing_imbalance = abs(
                    font["hmtx"][glyph_name][1] - right_side_bearing
                )
                maximum_side_bearing_imbalance = max(
                    maximum_side_bearing_imbalance,
                    side_bearing_imbalance,
                )
                assert_true(
                    side_bearing_imbalance <= 1,
                    f"Hangul U+{codepoint:04X} is not centered: "
                    f"left/right imbalance {side_bearing_imbalance}",
                )
                assert_true(
                    minimum_y >= font["hhea"].descent,
                    f"Hangul U+{codepoint:04X} falls below hhea descent",
                )
                assert_true(
                    maximum_y <= font["hhea"].ascent,
                    f"Hangul U+{codepoint:04X} exceeds hhea ascent",
                )
        assert_true(hangul_count > 0, "no Hangul cmap entries found")
        verify_alignment(font, cmap, cell_width)

        expected_names = {
            1: "Hanadia Mono",
            2: expected_style,
            4: f"Hanadia Mono {expected_style}",
            6: f"HanadiaMono-{expected_style}",
            16: "Hanadia Mono",
            17: expected_style,
        }
        for name_id, expected in expected_names.items():
            values = name_strings(font, name_id)
            assert_true(values, f"name ID {name_id} is missing")
            assert_true(
                expected in values,
                f"name ID {name_id} does not contain {expected!r}: {values}",
            )

        primary_values = [
            value
            for name_id in PRIMARY_NAME_IDS
            for value in name_strings(font, name_id)
        ]
        for reserved_name in RESERVED_NAMES:
            assert_true(
                not any(reserved_name.casefold() in value.casefold() for value in primary_values),
                f"reserved upstream name appears in primary naming: {reserved_name!r}",
            )

        all_names = all_name_strings(font)
        metadata = "\n".join(all_names)
        for required_notice in (
            "SIL Open Font License",
            "Microsoft Corporation",
            "Kil Hyung-jin",
            "Reserved Font Name Cascadia Code",
            "Reserved Font Name Pretendard",
        ):
            assert_true(
                required_notice in metadata,
                f"license/copyright metadata is missing: {required_notice!r}",
            )

        assert_true("GSUB" in font, "GSUB table is missing")
        feature_tags = {
            record.FeatureTag
            for record in font["GSUB"].table.FeatureList.FeatureRecord
        }
        assert_true("calt" in feature_tags, "Cascadia Code calt feature is missing")
        assert_true(
            has_contextual_substitution(font, "calt"),
            "calt has no contextual substitution used by programming ligatures",
        )
        for sequence in ("->", "=>", "!=", "===", "!==", ">=", "<="):
            for character in sequence:
                assert_true(
                    ord(character) in cmap,
                    f"ligature input character is missing: {character!r}",
                )

        print(
            f"verified {path}: style={expected_style}, cellWidth={cell_width}, "
            f"hangulCodepoints={hangul_count}, glyphs={len(glyph_order)}, "
            f"maximumSideBearingImbalance={maximum_side_bearing_imbalance}, "
            "GSUB=calt/contextual, license metadata=present"
        )
    finally:
        font.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font", required=True, type=Path)
    parser.add_argument(
        "--style",
        required=True,
        choices=("Light", "Regular", "SemiBold", "Bold"),
    )
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    try:
        verify(arguments.font, arguments.style)
    except (AssertionError, KeyError, ValueError) as error:
        raise SystemExit(f"verification failed: {error}") from error
