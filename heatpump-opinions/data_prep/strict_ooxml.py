"""Read Strict OOXML (ISO 29500 strict) .xlsx files.

Nesta's heat pump suitability workbook is saved as Strict OOXML rather than the
near-universal Transitional flavour. The two differ mainly in their XML
namespace URIs (`purl.oclc.org/ooxml/...` instead of
`schemas.openxmlformats.org/...`), and most Python readers only handle
Transitional:

  - openpyxl reports the workbook as having ZERO sheets, with no error at all,
    so `pd.read_excel` hands back nothing and a careless pipeline silently
    produces an empty table.
  - python-calamine raises `CalamineError: Relationship not found`.

Rather than hand-roll a sheet parser, we rewrite the namespace URIs in the XML
parts and hand the result to openpyxl, which then reads it normally. Only
namespace strings are touched; cell data is copied through untouched.

This matters beyond one awkward file: Nesta are retiring the suitability map, so
the downloaded snapshot is the permanent artefact and this conversion is a
permanent part of reading it.
"""
from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

# Strict -> Transitional namespace substitutions. Order matters: the longer,
# more specific relationship URIs must be replaced before the shorter prefixes
# they share, or a partial match would corrupt them.
_NAMESPACE_SUBSTITUTIONS: tuple[tuple[bytes, bytes], ...] = (
    (
        b"http://purl.oclc.org/ooxml/officeDocument/relationships",
        b"http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    ),
    (
        b"http://purl.oclc.org/ooxml/officeDocument/extendedProperties",
        b"http://schemas.openxmlformats.org/officeDocument/2006/extended-properties",
    ),
    (
        b"http://purl.oclc.org/ooxml/officeDocument/docPropsVTypes",
        b"http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes",
    ),
    (
        b"http://purl.oclc.org/ooxml/spreadsheetml/main",
        b"http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    ),
    (
        b"http://purl.oclc.org/ooxml/drawingml/main",
        b"http://schemas.openxmlformats.org/drawingml/2006/main",
    ),
    # openpyxl refuses to load a workbook still declaring strict conformance.
    (b' conformance="strict"', b""),
)


def is_strict_ooxml(path: str | Path) -> bool:
    """True if `path` is an xlsx using the Strict OOXML namespaces."""
    with zipfile.ZipFile(path) as archive:
        if "xl/workbook.xml" not in archive.namelist():
            return False
        return b"purl.oclc.org/ooxml" in archive.read("xl/workbook.xml")


def to_transitional(source: str | Path, dest: str | Path) -> Path:
    """Rewrite a Strict OOXML workbook to Transitional at `dest`.

    Non-strict files are copied through unchanged, so this is safe to call
    unconditionally. Returns `dest`.
    """
    source, dest = Path(source), Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)

    if not is_strict_ooxml(source):
        shutil.copyfile(source, dest)
        return dest

    with zipfile.ZipFile(source) as archive_in:
        # ZIP_DEFLATED keeps the intermediate a sensible size; these sheets
        # expand to tens of MB of XML.
        with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as archive_out:
            for item in archive_in.infolist():
                payload = archive_in.read(item.filename)
                if item.filename.endswith((".xml", ".rels")):
                    for strict, transitional in _NAMESPACE_SUBSTITUTIONS:
                        payload = payload.replace(strict, transitional)
                archive_out.writestr(item.filename, payload)

    return dest
