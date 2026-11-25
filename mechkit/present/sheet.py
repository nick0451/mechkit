"""Picture sheets from a presentation manifest: each named view rendered off-screen; exploded views get trace lines,
numbered balloons and the parts table. No Fusion needed.

    from mechkit.present import manifest, sheet
    files = sheet.make(manifest.load(path), out_dir)        # -> [png paths] + parts_table.md
"""

from pathlib import Path

from . import layout

W3D, H = 1500, 1150          # the rendered picture
WTAB = 760                   # the parts table beside it (exploded sheets only)
KIND_MARK = {"printed": "printed", "bought": "bought", "hardware": "hardware"}


def _rgb(hexcolour):
    return tuple(int(hexcolour[i:i + 2], 16) for i in (1, 3, 5))


def _mesh(step_path, tolerance=0.05):
    import build123d as bd
    import numpy as np
    import pyvista as pv

    shape = bd.import_step(str(step_path))
    verts, tris = shape.tessellate(tolerance)
    pts = np.array([[v.X, v.Y, v.Z] for v in verts], dtype=float)
    faces = np.hstack([[3, a, b, c] for (a, b, c) in tris]).astype(np.int64)
    return pv.PolyData(pts, faces)


def _font(size, bold=False):
    from PIL import ImageFont

    for name in (("arialbd.ttf", "DejaVuSans-Bold.ttf") if bold else ("arial.ttf", "DejaVuSans.ttf")):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def _render(data, view, meshes, path):
    """Render one view; returns {key: (px, py)} of each shown item's centre in the picture (y down)."""
    import pyvista as pv
    import vtk

    exploded = view["group"] == "exploded"
    pl = pv.Plotter(off_screen=True, window_size=(W3D, H))
    pl.set_background("white")
    pl.enable_depth_peeling(8)                                  # so see-through reference parts really are see-through
    anchors, lines = {}, []
    for e in data["parts"]:
        if exploded and e["kind"] == "reference":
            continue
        d = e["explode"] if exploded else [0.0, 0.0, 0.0]
        m = meshes[e["key"]].translate(d, inplace=False)
        pl.add_mesh(m, color=e["colour"], opacity=e.get("opacity", 1.0), smooth_shading=True, split_sharp_edges=True)
        c = [e["centre"][i] + d[i] for i in range(3)]
        anchors[e["key"]] = c
        if exploded and any(d):
            lines += [e["centre"], c]
    if lines:
        import numpy as np
        pl.add_lines(np.array(lines, dtype=float), color="#8a8f98", width=1.5)
    pl.camera_position = [view["eye"], view["target"], view["up"]]
    pl.reset_camera()
    pl.camera.zoom(1.25 if not exploded else 1.1)
    pl.show(auto_close=False)
    pl.screenshot(str(path))
    out = {}
    coord = vtk.vtkCoordinate()
    coord.SetCoordinateSystemToWorld()
    for key, c in anchors.items():
        coord.SetValue(*c)
        x, y = coord.GetComputedDoubleDisplayValue(pl.renderer)
        out[key] = (x, H - y)
    pl.close()
    return out


def _place_balloons(points, r):
    """Balloon centres in picture pixels, kept inside the picture."""
    spots = layout.place_balloons(points, r, 150)
    return [(min(max(x, r + 4), W3D - r - 4), min(max(y, r + 4), H - r - 4)) for x, y in spots]


def _wrap(draw, text, font, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=font) <= width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _compose(data, view, png, anchors):
    from PIL import Image, ImageDraw

    exploded = view["group"] == "exploded"
    shot = Image.open(png).convert("RGB")
    sheet = Image.new("RGB", (W3D + (WTAB if exploded else 0), H), "white")
    sheet.paste(shot, (0, 0))
    dr = ImageDraw.Draw(sheet)
    ink, grey = (25, 27, 31), (110, 115, 124)
    dr.text((28, 22), data["project"], font=_font(34, True), fill=ink)
    dr.text((28, 64), "%s  |  view: %s" % (data["version"], view["name"]), font=_font(20), fill=grey)
    if exploded:
        r = 19
        shown = [e for e in data["parts"] if e["kind"] != "reference" and e["count"] > 0]
        spots = _place_balloons([anchors[e["key"]] for e in shown], r)
        for e, (bx, by) in zip(shown, spots):
            ax, ay = anchors[e["key"]]
            dr.line([(ax, ay), (bx, by)], fill=ink, width=2)
            dr.ellipse([ax - 3, ay - 3, ax + 3, ay + 3], fill=ink)
        f = _font(20, True)
        for e, (bx, by) in zip(shown, spots):
            dr.ellipse([bx - r, by - r, bx + r, by + r], fill="white", outline=ink, width=2)
            t = str(e["label"])
            dr.text((bx - dr.textlength(t, font=f) / 2, by - 12), t, font=f, fill=ink)
        # parts table
        x0, y = W3D + 10, 24
        dr.line([(W3D, 20), (W3D, H - 20)], fill=(200, 203, 208), width=2)
        dr.text((x0 + 8, y), "Parts", font=_font(28, True), fill=ink)
        y += 46
        fh, fb, fs = _font(18, True), _font(18), _font(15)
        for row in data["table"]:
            dr.ellipse([x0 + 8, y, x0 + 40, y + 32], outline=ink, width=2)
            t = str(row["label"])
            dr.text((x0 + 24 - dr.textlength(t, font=fh) / 2, y + 6), t, font=fh, fill=ink)
            dr.text((x0 + 52, y), "%s   x %d" % (row["part"], row["qty"]), font=fh, fill=ink)
            meta = ", ".join(v for v in (row["made"], row["material"], row["part_number"]) if v)
            dr.text((x0 + 52, y + 22), meta, font=fs, fill=grey)
            yy = y + 42
            for line in _wrap(dr, row["description"], fs, WTAB - 80):
                dr.text((x0 + 52, yy), line, font=fs, fill=ink)
                yy += 18
            y = yy + 12
        if y > H:
            raise ValueError("parts table does not fit on the sheet (%d px of %d): shorten descriptions or enlarge the sheet" % (y, H))
    sheet.save(png)


def table_markdown(data):
    out = ["| No. | Part | Qty | Made | Material | Part number | Description |", "|---|---|---|---|---|---|---|"]
    for r in data["table"]:
        out.append("| %d | %s | %d | %s | %s | %s | %s |" % (r["label"], r["part"], r["qty"], r["made"], r["material"], r["part_number"], r["description"]))
    return "\n".join(out) + "\n"


def make(data, out_dir):
    """Write one sheet per view + parts_table.md into out_dir. Returns the list of files written."""
    import pyvista as pv

    pv.OFF_SCREEN = True
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    folder = Path(data["folder"])
    meshes = {e["key"]: _mesh(folder / e["step"]) for e in data["parts"]}
    files = []
    for view in data["views"]:
        png = out_dir / ("%s_%s.png" % (data["version"], view["name"].lower().replace(" ", "_")))
        anchors = _render(data, view, meshes, png)
        _compose(data, view, png, anchors)
        files.append(png)
    md = out_dir / "parts_table.md"
    md.write_text("# %s %s: parts\n\n%s" % (data["project"], data["version"], table_markdown(data)), encoding="utf-8", newline="\n")
    files.append(md)
    return files
