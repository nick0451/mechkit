"""Presentation layer: turn a kit-built design into something to look at.

    manifest.py   the list of parts to show (names, descriptions, colours, labels, explode moves, views) + their STEP files
    sheet.py      pictures with numbered labels and a parts table, drawn by the kit itself (no Fusion needed)
    fusion.py     sends the manifest to Fusion: one `<Project>_Presentation` document, rebuilt from scratch each time

The design itself stays in the kit. Nothing here is read back into a build.
"""
