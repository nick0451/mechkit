"""Standard hardware as solids with their standard dimensions: screws and heat-set inserts.

The parts and their tables come from bd_warehouse (Apache-2.0, https://github.com/gumyr/bd_warehouse), the standard
parts library of build123d's author; MechKit uses it as an installed dependency. Each call returns the solid (a simple
stand-in without modelled threads, for fit checks and pictures) and its facts, every number tagged like any other
dimension: "stated", with the standard or the maker's table as its source. A value that matters for fit is still
worth a caliper check on the parts actually bought: then record it as "measured" in the part's interface.json.

    screw("M3-0.5", 10)                         ISO 4762 socket head cap screw
    screw("M3-0.5", 8, kind="pan_head")         ISO 14583 pan head
    insert("M3-0.5", length=4.0)                heat-set insert, by maker table (default "CNCKitchen")
    screw_sizes(), insert_sizes(maker)          what exists

Frames: axis along Z. A screw has its head's underside at z = 0 and its shank going to -Z; an insert stands on z = 0
and goes up by its length.
Bearings are not offered: bd_warehouse 0.4.0's bearings do not build with this kernel version.
"""

import warnings

SCREWS = {"socket_head": ("SocketHeadCapScrew", "iso4762", "ISO 4762"),
          "pan_head": ("PanHeadScrew", "iso14583", "ISO 14583"),
          "countersunk": ("CounterSunkScrew", "iso10642", "ISO 10642"),
          "button_head": ("ButtonHeadScrew", "iso7380_1", "ISO 7380-1")}


def _lib():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        import bd_warehouse.fastener as f
    return f


def _version():
    from importlib.metadata import version
    return version("bd_warehouse")


def _dim(value, source):
    return {"value": round(float(value), 4), "tag": "stated", "source": source}


def screw_sizes(kind="socket_head"):
    f = _lib()
    cls, ftype, _ = SCREWS[kind]
    return sorted(getattr(f, cls).sizes(ftype))


def screw(size, length, kind="socket_head"):
    """(solid, facts) of a metric screw. size like "M3-0.5"; length in mm (nominal: under the head, or overall for a
    countersunk screw). Raises ValueError for a size or kind the standard does not have."""
    f = _lib()
    if kind not in SCREWS:
        raise ValueError("unknown screw kind %r (have: %s)" % (kind, ", ".join(SCREWS)))
    cls, ftype, standard = SCREWS[kind]
    if size not in getattr(f, cls).sizes(ftype):
        raise ValueError("%s has no size %r" % (standard, size))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        s = getattr(f, cls)(size=size, length=float(length), fastener_type=ftype, simple=True)
    src = "%s (bd_warehouse %s)" % (standard, _version())
    facts = {"name": "%s %sx%g" % (standard, size.split("-")[0], length), "kind": "screw", "standard": standard, "size": size,
             "dims": {"thread_d": _dim(s.thread_diameter, src), "length": _dim(length, src),
                      "head_d": _dim(s.head_diameter, src), "head_h": _dim(s.head_height, src)},
             "clearance_hole_d": {k.lower(): _dim(v, src) for k, v in s.clearance_hole_diameters.items()},
             "tap_hole_d": {k.lower(): _dim(v, src) for k, v in s.tap_hole_diameters.items()}}
    return s, facts


def insert_sizes(maker="CNCKitchen"):
    return sorted(_lib().HeatSetNut.sizes(maker))


def insert(size, length=None, maker="CNCKitchen"):
    """(solid, facts) of a heat-set insert from a maker's table. size like "M3-0.5"; length picks the entry of that
    height (mm) when the maker has several. facts["hole_d"] is the maker's hole diameter for plastic; facts["sold_as"]
    is the maker's product link where the table has one (buying is the person's decision, gate G2)."""
    f = _lib()
    makers = sorted(f.HeatSetNut.types())
    if maker not in makers:
        raise ValueError("unknown insert maker %r (have: %s)" % (maker, ", ".join(makers)))
    names = [n for n in f.HeatSetNut.sizes(maker) if n == size or n.startswith(size + "-")]
    if not names:
        raise ValueError("%s has no %s insert" % (maker, size))
    built = []
    for n in names:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            built.append((n, f.HeatSetNut(size=n, fastener_type=maker, simple=True)))
    if length is not None:
        built = [b for b in built if abs(b[1].nut_thickness - float(length)) < 0.05]
        if not built:
            raise ValueError("%s has no %s insert %g mm long" % (maker, size, length))
    name, s = built[0]
    src = "%s table (bd_warehouse %s)" % (maker, _version())
    hole = s.nut_data.get("dc")                               # the maker's hole for the INSERT (not the thread's tap drill)
    facts = {"name": "Heat-set insert %s (%s)" % (name, maker), "kind": "insert", "maker": maker, "size": name,
             "dims": {"outer_d": _dim(s.nut_diameter, src), "length": _dim(s.nut_thickness, src)},
             "hole_d": _dim(hole, src) if hole else None, "sold_as": s.nut_data.get("part")}
    return s, facts
