"""Monitor weather display: the printed parts (detailed design v0.9, thin pod + bezel + board cap + M4 screw clamp), built headless with build123d.

    uv run python examples/monitor-weather-display/parts/custom/build.py        (from the kit's folder)

Writes exports/v0p9/*.stl + *.step (each part in its print orientation), renders/v0p9_*.png and logs/build_v0p9.json.

v0.9 (2026-11-24): the monitor is 21.5 mm thick where the clamp sits (MEASURED by the user), not the 23.4 first stated.
That is why the old M3 clamp (range 22.4-26.4) ran out of travel. The saddle is now sized for 21.5: only the Clamp changed.

v0.8 (2026-11-24, user: the M3 x 10 clamp bolt ran out of travel; they have M4 x 30 screws and M4 inserts): a proper
screw clamp. An M4 x 30 runs through an M4 insert in the centre of the back wall (the insert is set from the INSIDE of
the saddle, so clamping pushes it against a shoulder instead of pulling it out), turned by a printed KNOB, pressing a
44 mm wide JAW against the monitor's back. 24 mm of travel. The back wall now extends to the right, behind the monitor,
to carry the C3 board and its cap beside the screw. Clamp changed; Jaw and Knob are new; Shoe is gone; Board_Cap is the
same shape. Pod, Bezel, Cover unchanged.

v0.7 (2026-11-24, user: tape will lose to unplugging forces): the C3 board is now held MECHANICALLY. Its lower edge
tucks into a lipped ledge on the clamp's back wall; a printed BOARD CAP closes over it, hooks round the wall's right end
and is bolted on the left with a 4th insert + M3 x 10. The cap's top wall sits over the board's top edge (it takes the
pull when the cable is unplugged) with a slot for the USB socket. Clamp changed (clamp bolt moved to x -16, cap insert,
new ledge, wall 25.4 tall); new part Board_Cap. Pod, Bezel, Cover, Shoe unchanged from v0.6.

v0.9 cleanup (2026-11-25): text-to-cad's printing check found three slivers 0.01-0.05 mm thick in the Pod, where the
flex-ribbon relief cut 0.01 mm into the front lip and stopped 0.04 mm short of the pin channel. The relief now starts at
the lip and runs into the channel. Geometry moves by 0.04 mm at most; nothing a printer can make changes.

v0.6 (2026-11-24, the v0.5 Pod "fits much better"): a separate decorative BEZEL in the style of an earlier build (locating pins on
its back into blind holes in the pod face, a dab of glue) with a turbo-gauge look: deep chamfered bore and a tick scale.
The Pod gained the 5 pin holes; nothing else changed. The pod still works without the bezel.

v0.5 (2026-11-24, second Pod test print: fits better, but the soldered wire ends on the 7 pads stand proud of the
board's front face and tilt the display): a channel under the pad row lets them sink in. Only the Pod changed.

v0.4 (2026-11-24): the gap behind the monitor grew from 3.0 to 4.5 mm so the clamp still closes with 1 mm of padding on
the front lip AND on the shoe (v0.3 only had room for one of them). Only the Clamp changed.

v0.3 (2026-11-24, after the first Pod test print: "almost a perfect fit"): the screen pocket gained a relief for the
display's flex ribbon, which folds over about 2 mm past the screen toward the pins, about 14 mm wide. Only the Pod changed.

Layout (user, 2026-11-24): the pod holds ONLY the display and is about 10 mm deep; the ESP32-C3 SuperMini sits flat
on the clamp's back wall, hidden behind the monitor, USB pointing up; 7 soldered wires run from the display's tab
through a slot in the cover and hanger, under the saddle and up to the board.

Parts
    Clamp      saddle over the monitor's bottom edge + a hanger plate leaning back by the tilt angle + a locating
               corner for the C3 board on the back wall. Prints lying on its side (the -X end on the bed), no supports.
    Pod        U-shaped shell (flat top, round bottom) holding the display behind a window. Prints face down.
    Cover      flat back plate with four pads that hold the display's board in its pocket. Prints flat, pads up.
    Jaw        the clamp screw's pressure plate (stick rubber or felt on its flat face). Prints flat.
    Knob       presses onto the M4 screw's head. Board_Cap: covers and retains the C3 board. Bezel: decorative ring.
Hardware: 3 brass inserts M3 (2 in the pod, 1 in the clamp's back wall), 3 socket-head M3 x 10, foam tape for the board.

Frames (mm). World: X along the monitor edge, +Y toward the user, +Z up; monitor front face Y = 0, underside Z = 0.
Pod frame (x, v, z): origin = display centre on the pod's FRONT face; x = world X; v = up along the tilted face;
z = depth into the pod (0 = front face, positive = toward the back).
Dimension tags: display = STATED (seller drawing, 7-pin board with a tab; the user confirmed that description);
insert length 5.1 and socket-head M3 x 10 = STATED by the user; insert outer diameter and the C3 board size = ASSUMED;
monitor 23.4 thick, 24 chin, flat back and underside = STATED by the user.
"""

import json
import math
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]


def _kit_root():
    """The kit's folder: this project may sit beside it (../mechkit) or inside its examples folder."""
    for base in (PROJECT, *PROJECT.parents):
        for cand in (base, base / "mechkit"):
            if (cand / "mechkit" / "kernel" / "b3d.py").is_file():
                return cand
    raise SystemExit("cannot find the mechkit folder above %s" % PROJECT)


sys.path.insert(0, str(_kit_root()))

import build123d as bd  # noqa: E402

from mechkit.kernel import b3d  # noqa: E402

VERSION = "v0p9"


def iface(part):
    d = json.loads((PROJECT / "parts" / "purchased" / part / "interface.json").read_text(encoding="utf-8"))
    return {k: v[0] for k, v in d["dims"].items()}


TFT, MCU = iface("gc9a01_1p28"), iface("esp32c3_supermini")

P = {
    # monitor (stated by the user)
    "mon_thick": 21.5, "mon_chin": 24.0,     # thickness MEASURED by the user at the clamp position (2026-11-24); chin stated
    # look
    "tilt_deg": 10.0, "face_y": 3.0,            # display centre on the front face sits this far in front of the bezel plane
    # clamp
    "plate_t": 4.0, "lip_t": 3.0, "lip_h": 12.0, "back_gap": 4.5, "pad_t": 1.0, "back_t": 6.0, "back_h": 25.4, "bolt_z": 12.0, "bolt_x_clamp": 0.0, "wall_x1": 41.5,
    "root_fillet": 2.5,                         # gusset in the gap behind the monitor, at the root of the back wall
    "hanger_t": 4.0, "hanger_low_v": 6.0, "pod_gap": 1.0,
    # board corner on the back wall
    "board_x0": 20.2, "board_z0": 1.5,
    # lipped ledge under the board + the bolted cap over it
    "ledge_t": 1.6, "ledge_slot": 1.5, "ledge_lip_t": 1.2, "ledge_lip_h": 1.0,
    "cap_cavity": 5.0, "cap_skin": 1.6, "cap_play": 0.3, "cap_top_t": 1.2, "cap_bolt_x": 14.5, "cap_bolt_z": 13.0, "cap_ear_x0": 10.5,
    "cap_seat_t": 3.0, "cap_cb_d": 6.2, "cap_hook_z": (6.0, 20.0), "cap_hook_t": 1.4, "cap_lip": 1.2,
    # pod
    "pod_w": 48.0, "pod_top_v": 30.0, "pod_depth": 8.0, "lip_front": 1.2, "window_d": 33.0, "fit": 0.4,
    "bolt_x": 18.5, "bolt_v": 14.5, "fpc_clear": 0.6, "pin_channel_clear": 0.4, "pin_channel_h": 3.2,
    # bezel (same pin fit as an earlier build's bezels, which fitted first time: pin 1.8 in a 2.1 hole, 1.4 long in 1.6 deep)
    "bezel_od": 48.0, "bezel_h": 3.0, "bezel_bore_front": 38.0, "bezel_pin_d": 1.8, "bezel_pin_l": 1.4, "bezel_hole_d": 2.1, "bezel_hole_depth": 1.6,
    "bezel_pin_r": 21.7, "bezel_pin_angles": (50, 130, 210, 270, 330), "tick_w": 0.8, "tick_depth": 0.5,
    # cover
    "cover_t": 2.0, "pad_play": 0.2, "wire_slot": (16.0, 6.0), "wire_slot_v": 24.0,
    # hardware
    "insert_hole_d": 4.0,                       # confirmed by fit on the first test print (2026-11-24)
    "insert_l": 5.1,                            # stated
    "m3_clear": 3.4, "bolt_l": 10.0, "head_d": 5.5, "head_h": 3.0,
    # clamp: M4 x 30 socket-head screw (stated by the user) through an M4 heat-set insert (size ASSUMED: L4 x OD5, hole 4.5)
    "m4_len": 30.0, "m4_insert_hole_d": 4.5, "m4_insert_l": 4.0, "m4_clear": 4.4, "m4_head_d": 7.0, "m4_head_h": 4.0,
    "jaw_w": 44.0, "jaw_h": 18.0, "jaw_t": 3.0, "jaw_socket": 1.2, "jaw_z0": 1.5, "knob_d": 18.0, "knob_h": 9.0,
}


# ------------------------------------------------------------------------------------------------ frames
def pod_origin(p):
    """World (Y, Z) of the pod-frame origin: the pod's top-front corner sits pod_gap under the saddle."""
    t = math.radians(p["tilt_deg"])
    return p["face_y"], -p["plate_t"] - p["pod_gap"] - p["pod_top_v"] * math.cos(t)


def pod_to_world(p):
    """Location that maps pod-frame solids (x, v, z_back) into the world."""
    t = math.radians(p["tilt_deg"])
    oy, oz = pod_origin(p)
    n = bd.Vector(0, math.cos(t), math.sin(t))                 # out of the screen
    return bd.Location(bd.Plane(origin=(0, oy, oz), x_dir=(1, 0, 0), z_dir=-n))


def yz(p, v, z):
    """World (Y, Z) of a pod-frame point on the centre line."""
    t = math.radians(p["tilt_deg"])
    oy, oz = pod_origin(p)
    return oy - v * math.sin(t) - z * math.cos(t), oz + v * math.cos(t) - z * math.sin(t)


# ------------------------------------------------------------------------------------------------ 2D outlines (pod frame)
def u_outline(w, top_v):
    """Flat top, round bottom: a w-wide rectangle from v = 0 up to top_v joined to a half disc below."""
    return bd.Pos(0, top_v / 2) * bd.Rectangle(w, top_v) + bd.Circle(w / 2)


def pcb_outline(grow):
    """The display board seen from the front: round part + header tab (tab toward +v), grown by `grow`."""
    r, tab_w, tab_end = TFT["pcb_d"] / 2 + grow, TFT["tab_w"] + 2 * grow, TFT["pcb_len"] - TFT["pcb_d"] / 2 + grow
    return bd.Circle(r) + bd.Pos(0, tab_end / 2) * bd.Rectangle(tab_w, tab_end)


def slab(sketch, z0, z1):
    """Extrude a sketch drawn in (x, v) so that it fills z0..z1 (placed from its real box: a sketch can extrude either way)."""
    s = bd.extrude(sketch, amount=z1 - z0)
    return bd.Pos(0, 0, z0 - s.bounding_box().min.Z) * s


# ------------------------------------------------------------------------------------------------ parts (pod frame)
def pod(p):
    d = p["pod_depth"]
    shell = slab(u_outline(p["pod_w"], p["pod_top_v"]), 0, d)
    window = slab(bd.Circle(p["window_d"] / 2), -0.01, p["lip_front"] + 0.01)
    extra = TFT["bl_h"] - TFT["bl_w"]                                                 # the screen is a little longer toward the tab
    r_bl = TFT["bl_w"] / 2 + p["fit"] / 2
    z_pcb = p["lip_front"] + TFT["tft_t"] + 0.1                                      # where the board's front face lands
    screen_pocket = slab(bd.Circle(r_bl) + bd.Pos(0, extra) * bd.Circle(r_bl) + bd.Pos(0, extra / 2) * bd.Rectangle(2 * r_bl, extra),
                         p["lip_front"], z_pcb + 0.01)
    cavity = slab(pcb_outline(p["fit"]), z_pcb, d + 0.01)
    # relief for the flex ribbon: it folds over the screen's edge on the tab side, as thick as the screen itself
    top = extra + r_bl                                                               # pocket edge toward the tab
    v0, v1 = top - 4.0, top + TFT["fpc_past_screen"] + p["fpc_clear"]
    # channel in front of the 7 solder pads, so wire ends and solder on the board's front face do not lift it off its seat
    pin_v = TFT["pcb_len"] - TFT["pcb_d"] / 2 - TFT["pin_row_from_tab_end"]
    ch_v0 = pin_v - p["pin_channel_h"] / 2
    if 0 < ch_v0 - v1 < 0.2:                         # v0.9 cleanup: run on into the channel instead of leaving a 0.04 mm wall
        v1 = ch_v0
    # the relief starts AT the lip, not 0.01 into it: that overcut left a 0.01 mm step and a wedge against the window
    ribbon = bd.Pos(0, (v0 + v1) / 2, (p["lip_front"] + z_pcb + 0.01) / 2) * bd.Box(TFT["fpc_w"] + 2 * p["fpc_clear"], v1 - v0, z_pcb - p["lip_front"] + 0.01)
    ch_w = 6 * TFT["pin_pitch"] + 5.0                                              # the pad row + 2.5 mm each side
    ch_d = TFT["solder_leg_front"] + p["pin_channel_clear"]
    if z_pcb - ch_d < 0.8:
        raise ValueError("pin channel would leave under 0.8 mm of front wall")
    channel = bd.Pos(0, pin_v, z_pcb - ch_d / 2 + 0.01) * bd.Box(ch_w, p["pin_channel_h"], ch_d + 0.02)
    body = shell - window - screen_pocket - cavity - ribbon - channel
    for a in p["bezel_pin_angles"]:                                                  # blind holes in the front face for the bezel's pins
        x, v = p["bezel_pin_r"] * math.cos(math.radians(a)), p["bezel_pin_r"] * math.sin(math.radians(a))
        body -= bd.Pos(x, v, p["bezel_hole_depth"] / 2 - 0.01) * bd.Cylinder(p["bezel_hole_d"] / 2, p["bezel_hole_depth"] + 0.02)
    hole = p["insert_l"] + 0.5
    for sx in (-1, 1):                                                               # blind holes for the brass inserts, from the back
        body -= bd.Pos(sx * p["bolt_x"], p["bolt_v"], d - hole / 2 + 0.01) * bd.Cylinder(p["insert_hole_d"] / 2, hole)
    return body, z_pcb


def bezel(p):
    """Decorative ring glued to the pod's front: a deep chamfered bore like a gauge, and a tick scale sweeping over the top.

    Pod frame: the ring sits in FRONT of the face (z from -bezel_h to 0); its pins reach into the pod (z 0..pin_l).
    """
    h = p["bezel_h"]
    ring = bd.Pos(0, 0, -h / 2) * bd.Cylinder(p["bezel_od"] / 2, h)
    # bore: the window's diameter at the pod face, opening out toward the viewer
    ring -= bd.Pos(0, 0, -h / 2) * bd.Cone(p["bezel_bore_front"] / 2, p["window_d"] / 2, h + 0.02)
    # outer edge broken toward the viewer
    ring = ring & (bd.Pos(0, 0, -h / 2) * bd.Cone(p["bezel_od"] / 2 - 1.0, p["bezel_od"] / 2 + h - 1.0, h))
    # tick scale: 13 marks over 270 degrees with the gap at the bottom, every third one longer
    r_out = p["bezel_od"] / 2 - 1.6
    for i in range(13):
        a = 225.0 - i * 22.5
        length = 2.6 if i % 3 == 0 else 1.5
        tick = bd.Pos(r_out - length / 2, 0, -h + p["tick_depth"] / 2 - 0.01) * bd.Box(length, p["tick_w"], p["tick_depth"] + 0.02)
        ring -= bd.Rot(Z=a) * tick
    for a in p["bezel_pin_angles"]:
        x, v = p["bezel_pin_r"] * math.cos(math.radians(a)), p["bezel_pin_r"] * math.sin(math.radians(a))
        ring += bd.Pos(x, v, p["bezel_pin_l"] / 2 - 0.01) * bd.Cylinder(p["bezel_pin_d"] / 2, p["bezel_pin_l"] + 0.02)
    return ring


PAD_ANGLES = (200, 250, 290, 340)          # degrees round the display centre (0 = +x, 90 = toward the tab): on the board's rim


def cover(p, z_pcb):
    d, ct = p["pod_depth"], p["cover_t"]
    plate = slab(u_outline(p["pod_w"], p["pod_top_v"]), d, d + ct)
    for sx in (-1, 1):
        plate -= bd.Pos(sx * p["bolt_x"], p["bolt_v"], d + ct / 2) * bd.Cylinder(p["m3_clear"] / 2, ct + 0.1)
    sw, sh = p["wire_slot"]
    plate -= bd.Pos(0, p["wire_slot_v"], d + ct / 2) * bd.Box(sw, sh, ct + 0.1)
    # pads that reach forward to the back of the display board's rim (clear of the components in the middle)
    z_touch = z_pcb + TFT["pcb_t"] + p["pad_play"]
    r = TFT["pcb_d"] / 2 - 1.6
    part = plate
    for a in PAD_ANGLES:
        x, v = r * math.cos(math.radians(a)), r * math.sin(math.radians(a))
        part += bd.Pos(x, v, (z_touch + d) / 2) * bd.Cylinder(1.4, d - z_touch)
    return part, z_touch


def jaw(p):
    """Pressure plate for the clamp screw: wide, so the grip is spread and the unit cannot twist. Socket for the screw tip on top."""
    sock_dy = p["bolt_z"] - (p["jaw_z0"] + p["jaw_h"] / 2)
    plate = bd.Box(p["jaw_w"], p["jaw_h"], p["jaw_t"])
    return plate - bd.Pos(0, sock_dy, p["jaw_t"] / 2 - p["jaw_socket"] / 2 + 0.01) * bd.Cylinder(p["m4_clear"] / 2 + 0.2, p["jaw_socket"] + 0.02)


def knob(p):
    """Thumb knob: the M4 socket head presses into the pocket (a drop of glue keeps it); 12 finger flutes."""
    h = p["knob_h"]
    k = bd.Cylinder(p["knob_d"] / 2, h) - bd.Cylinder(p["m4_clear"] / 2, h + 0.1)
    k -= bd.Pos(0, 0, h / 2 - (p["m4_head_h"] + 0.3) / 2 + 0.01) * bd.Cylinder(p["m4_head_d"] / 2 + 0.1, p["m4_head_h"] + 0.3)
    for i in range(12):
        k -= bd.Rot(Z=i * 30) * (bd.Pos(p["knob_d"] / 2 + 0.6, 0, 0) * bd.Cylinder(1.6, h + 0.1))
    return k


def board_pose(p):
    """C3 board on the back wall's rear face: (x0, x1, z0, z1, y_face) with the USB end up."""
    y_face = -(p["mon_thick"] + p["back_gap"]) - p["back_t"]
    x0 = p["board_x0"] + p["fit"] / 2
    return x0, x0 + MCU["w"], p["board_z0"], p["board_z0"] + MCU["l"], y_face


def dummies(p, z_pcb):
    """Stand-ins for the bought parts, for the fit checks and the pictures (display in the pod frame, board in the world)."""
    extra = TFT["bl_h"] - TFT["bl_w"]
    pcb = slab(pcb_outline(0.0), z_pcb, z_pcb + TFT["pcb_t"])
    screen = slab(bd.Circle(TFT["bl_w"] / 2) + bd.Pos(0, extra) * bd.Circle(TFT["bl_w"] / 2), z_pcb - TFT["tft_t"], z_pcb)
    edge = extra + TFT["bl_w"] / 2
    screen += bd.Pos(0, edge + TFT["fpc_past_screen"] / 2 - 1.0, z_pcb - TFT["tft_t"] / 2) * bd.Box(TFT["fpc_w"], TFT["fpc_past_screen"] + 2.0, TFT["tft_t"])   # ribbon fold
    x0, x1, z0, z1, yf = board_pose(p)
    board = bd.Pos((x0 + x1) / 2, yf - MCU["pcb_t"] / 2, (z0 + z1) / 2) * bd.Box(MCU["w"], MCU["pcb_t"], MCU["l"])
    usb = bd.Pos((x0 + x1) / 2, yf - MCU["pcb_t"] - MCU["usb_h"] / 2, z1 - 3.5 + MCU["usb_overhang"]) * bd.Box(MCU["usb_w"], MCU["usb_h"], 7.0)
    pin_v = TFT["pcb_len"] - TFT["pcb_d"] / 2 - TFT["pin_row_from_tab_end"]              # soldered wire ends on the front of the pad row
    legs = bd.Pos(0, pin_v, z_pcb - TFT["solder_leg_front"] / 2) * bd.Box(6 * TFT["pin_pitch"] + 2.0, 2.0, TFT["solder_leg_front"])
    return {"display_pcb": pcb + legs, "display_screen": screen}, {"board": board + usb}


# ------------------------------------------------------------------------------------------------ clamp (world frame)
def clamp(p):
    w = p["pod_w"]
    x0 = -w / 2
    y_back_in = -(p["mon_thick"] + p["back_gap"])
    y_back_out = y_back_in - p["back_t"]
    z0, z1 = p["pod_depth"] + p["cover_t"], p["pod_depth"] + p["cover_t"] + p["hanger_t"]     # hanger plate sits behind the cover
    t = math.radians(p["tilt_deg"])
    oy, oz = pod_origin(p)
    v_top = (-0.5 - oz + z0 * math.sin(t)) / math.cos(t)       # the hanger's front-top corner ends 0.5 mm below the saddle's top face
    y_rear = min(yz(p, v_top, z1)[0] - 0.5, y_back_out)
    plate = b3d.prism_x([(p["lip_t"], -p["plate_t"]), (p["lip_t"], 0), (y_rear, 0), (y_rear, -p["plate_t"])], x0, w)
    lip = b3d.prism_x([(0, 0), (p["lip_t"], 0), (p["lip_t"], p["lip_h"]), (0, p["lip_h"])], x0, w)
    # the back wall runs on to the right, behind the monitor, to carry the board beside the clamp screw
    back = b3d.prism_x([(y_back_out, 0), (y_back_in, 0), (y_back_in, p["back_h"]), (y_back_out, p["back_h"])], x0, p["wall_x1"] - x0)
    f = p["root_fillet"]
    gusset = b3d.prism_x([(y_back_in, 0), (y_back_in + f, 0), (y_back_in, f)], x0, w)        # fills the corner of the gap behind the monitor
    hanger = b3d.prism_x([yz(p, p["hanger_low_v"], z0), yz(p, v_top, z0), yz(p, v_top, z1), yz(p, p["hanger_low_v"], z1)], x0, w)
    part = plate + lip + back + gusset + hanger
    # clamp bolt: brass insert through the back wall, to one side so the board has the other side
    # clamp screw: clearance through the wall, and a pocket for the M4 insert opening on the INNER face, so the clamping
    # force seats the insert against the pocket's floor
    part -= bd.Pos(p["bolt_x_clamp"], (y_back_in + y_back_out) / 2, p["bolt_z"]) * bd.Rot(X=90) * bd.Cylinder(p["m4_clear"] / 2, p["back_t"] + 0.1)
    pocket = p["m4_insert_l"] + 0.2
    part -= bd.Pos(p["bolt_x_clamp"], y_back_in - pocket / 2 + 0.01, p["bolt_z"]) * bd.Rot(X=90) * bd.Cylinder(p["m4_insert_hole_d"] / 2, pocket + 0.02)
    loc = pod_to_world(p)
    for sx in (-1, 1):                                          # clearance holes for the pod bolts, square to the hanger
        part -= loc * (bd.Pos(sx * p["bolt_x"], p["bolt_v"], (z0 + z1) / 2) * bd.Cylinder(p["m3_clear"] / 2, p["hanger_t"] + 0.2))
    sw, sh = p["wire_slot"]                                     # wire slot, in line with the cover's
    part -= loc * (bd.Pos(0, p["wire_slot_v"], (z0 + z1) / 2) * bd.Box(sw, sh, p["hanger_t"] + 0.2))
    # insert for the board cap's bolt
    part -= bd.Pos(p["cap_bolt_x"], (y_back_in + y_back_out) / 2, p["cap_bolt_z"]) * bd.Rot(X=90) * bd.Cylinder(p["insert_hole_d"] / 2, p["back_t"] + 0.1)
    # lipped ledge on the back wall's rear face: the board's lower edge tucks in behind the lip (an L profile running along
    # X, so it prints as a plain vertical extrusion with the clamp on its -X end)
    bx0, bx1, bz0, bz1, yf = board_pose(p)
    lt, slot, lipt, liph = p["ledge_t"], p["ledge_slot"], p["ledge_lip_t"], p["ledge_lip_h"]
    lx0, lx1 = bx0 + 0.2, bx1 - 0.2
    z_top = bz0 - 0.2                                           # the board rests 0.2 above the ledge
    part += box(lx0, lx1, yf - slot - lipt, yf, z_top - lt, z_top)
    part += box(lx0, lx1, yf - slot - lipt, yf - slot, z_top, z_top + liph)
    return part


def box(x0, x1, y0, y1, z0, z1):
    return bd.Pos((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2) * bd.Box(abs(x1 - x0), abs(y1 - y0), abs(z1 - z0))


def board_cap(p):
    """Cap over the C3 board (world frame). Hooks round the back wall's +X end, bolts on at the left."""
    bx0, bx1, bz0, bz1, yf = board_pose(p)
    y_back_in = -(p["mon_thick"] + p["back_gap"])
    cav, skin, play = p["cap_cavity"], p["cap_skin"], p["cap_play"]
    y_out = yf - cav - skin
    z0, z1 = -0.5, p["back_h"]
    wall_end = p["wall_x1"]
    x_left, x_right = bx0 - play - skin, wall_end + 0.2 + p["cap_hook_t"]
    body = box(x_left, x_right, y_out, yf, z0, z1)
    body -= box(bx0 - play, bx1 + play, yf - cav, yf + 0.01, z0 - 0.01, bz1 + 0.2)          # room for the board, parts and wires; open below for the wires
    # slot in the top wall for the USB socket (the wall on both sides of it sits over the board's top edge)
    cx = (bx0 + bx1) / 2
    body -= box(cx - MCU["usb_w"] / 2 - 0.4, cx + MCU["usb_w"] / 2 + 0.4, yf - MCU["pcb_t"] - MCU["usb_h"] - 0.4, yf - MCU["pcb_t"] + 0.2, bz1, z1 + 0.01)
    # bolt ear on the left, with the head sunk into it
    ez0, ez1 = p["cap_bolt_z"] - 6.0, p["cap_bolt_z"] + 6.0
    ear = box(p["cap_ear_x0"], x_left, y_out, yf, ez0, ez1)
    ymid = (y_out + yf) / 2
    ear -= bd.Pos(p["cap_bolt_x"], ymid, p["cap_bolt_z"]) * bd.Rot(X=90) * bd.Cylinder(p["m3_clear"] / 2, yf - y_out + 0.1)
    head_room = (yf - p["cap_seat_t"]) - y_out
    ear -= bd.Pos(p["cap_bolt_x"], y_out + head_room / 2 - 0.01, p["cap_bolt_z"]) * bd.Rot(X=90) * bd.Cylinder(p["cap_cb_d"] / 2, head_room + 0.02)
    # hook round the wall's +X end, with a lip on the wall's inner face (inside the gap behind the monitor)
    hz0, hz1 = p["cap_hook_z"]
    arm = box(wall_end + 0.2, x_right, yf, y_back_in + 0.2 + p["cap_lip"], hz0, hz1)
    lip = box(wall_end - 1.2, wall_end + 0.2, y_back_in + 0.2, y_back_in + 0.2 + p["cap_lip"], hz0, hz1)
    return body + ear + arm + lip


def hardware_items(p):
    """Each screw as its own solid, in place (world frame): name -> solid."""
    y_back_in = -(p["mon_thick"] + p["back_gap"])
    bx = p["bolt_x_clamp"]
    head_y = y_back_in - p["back_t"]
    tip_y = -p["mon_thick"] - (p["jaw_t"] - p["jaw_socket"])    # the M4 screw, shown clamped on the nominal monitor
    items = {}
    items["Screw_M4x30"] = (bd.Pos(bx, tip_y - p["m4_len"] / 2, p["bolt_z"]) * bd.Rot(X=90) * bd.Cylinder(2.0, p["m4_len"])
                            + bd.Pos(bx, tip_y - p["m4_len"] - p["m4_head_h"] / 2, p["bolt_z"]) * bd.Rot(X=90) * bd.Cylinder(p["m4_head_d"] / 2, p["m4_head_h"]))
    seat_y = head_y - p["cap_seat_t"]                           # the cap bolt's head sits on the ear's seat
    items["Bolt_M3x10_cap"] = (bd.Pos(p["cap_bolt_x"], seat_y + p["bolt_l"] / 2, p["cap_bolt_z"]) * bd.Rot(X=90) * bd.Cylinder(1.5, p["bolt_l"])
                               + bd.Pos(p["cap_bolt_x"], seat_y - p["head_h"] / 2, p["cap_bolt_z"]) * bd.Rot(X=90) * bd.Cylinder(p["head_d"] / 2, p["head_h"]))
    loc = pod_to_world(p)
    z_head = p["pod_depth"] + p["cover_t"] + p["hanger_t"]
    for sx, side in ((-1, "L"), (1, "R")):
        items["Bolt_M3x10_pod_%s" % side] = loc * (bd.Pos(sx * p["bolt_x"], p["bolt_v"], z_head - p["bolt_l"] / 2) * bd.Cylinder(1.5, p["bolt_l"])
                                                    + bd.Pos(sx * p["bolt_x"], p["bolt_v"], z_head + p["head_h"] / 2) * bd.Cylinder(p["head_d"] / 2, p["head_h"]))
    return items


def hardware(p):
    """All the screws as one shape (for the fit checks and the plain pictures)."""
    items = list(hardware_items(p).values())
    parts = items[0]
    for s in items[1:]:
        parts += s
    return parts


def insert_items(p):
    """Stand-ins for the heat-set inserts, in place (world frame), for the presentation only: a plain tube as wide as its hole."""
    def tube(d, bore, length):
        return bd.Cylinder(d / 2, length) - bd.Cylinder(bore / 2, length + 0.1)
    loc = pod_to_world(p)
    y_back_in = -(p["mon_thick"] + p["back_gap"])
    y_back_out = y_back_in - p["back_t"]
    items = {}
    for sx, side in ((-1, "L"), (1, "R")):                      # flush with the pod's back face
        items["Insert_M3_pod_%s" % side] = loc * (bd.Pos(sx * p["bolt_x"], p["bolt_v"], p["pod_depth"] - p["insert_l"] / 2) * tube(p["insert_hole_d"], 3.0, p["insert_l"]))
    items["Insert_M3_cap"] = bd.Pos(p["cap_bolt_x"], y_back_out + p["insert_l"] / 2, p["cap_bolt_z"]) * bd.Rot(X=90) * tube(p["insert_hole_d"], 3.0, p["insert_l"])
    items["Insert_M4_clamp"] = bd.Pos(p["bolt_x_clamp"], y_back_in - p["m4_insert_l"] / 2, p["bolt_z"]) * bd.Rot(X=90) * tube(p["m4_insert_hole_d"], 4.0, p["m4_insert_l"])
    return items


# ------------------------------------------------------------------------------------------------ assemble, check, export
UNCHECKED = []      # overlap checks that could not be computed; checks() reports each one as a problem


def overlap(a, b, what="overlap"):
    """Shared volume in mm3. A check that cannot be computed is recorded as a problem, never read as 'no overlap'."""
    try:
        return b3d.overlap_volume(a, b)
    except b3d.GeometryCheckError as e:
        UNCHECKED.append("%s could not be checked: %s" % (what, e))
        return 0.0


def build(p=P):
    loc = pod_to_world(p)
    pod_local, z_pcb = pod(p)
    cover_local, z_touch = cover(p, z_pcb)
    jaw_local, knob_local = jaw(p), knob(p)
    in_pod, in_world = dummies(p, z_pcb)
    jaw_world = bd.Pos(p["bolt_x_clamp"], -p["mon_thick"] - p["jaw_t"] / 2, p["jaw_z0"] + p["jaw_h"] / 2) * bd.Rot(X=90) * jaw_local
    head_y = -p["mon_thick"] - (p["jaw_t"] - p["jaw_socket"]) - p["m4_len"]             # underside of the screw head when clamped
    knob_world = bd.Pos(p["bolt_x_clamp"], head_y - p["m4_head_h"] - 0.3 + p["knob_h"] / 2, p["bolt_z"]) * bd.Rot(X=90) * knob_local
    bezel_local = bezel(p)
    world = {"Pod": loc * pod_local, "Cover": loc * cover_local, "Clamp": clamp(p), "Jaw": jaw_world, "Knob": knob_world, "Bezel": loc * bezel_local,
             "Board_Cap": board_cap(p)}
    extras = {k: loc * v for k, v in in_pod.items()}
    extras.update(in_world)
    extras["hardware"] = hardware(p)
    local = {"Pod": pod_local, "Cover": cover_local, "Jaw": jaw_local, "Knob": knob_local, "Bezel": bezel_local}
    return world, extras, local, {"z_pcb": z_pcb, "z_touch": z_touch}


def checks(p, world, extras, info):
    problems, notes = [], []
    names = list(world)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            v = overlap(world[a], world[b], "%s / %s" % (a, b))
            if v > 0.5:
                problems.append("%s and %s overlap by %.1f mm3" % (a, b, v))
    for name in ("display_pcb", "display_screen", "board"):
        for part in names:
            v = overlap(extras[name], world[part], "%s / %s" % (name, part))
            if v > 0.5:
                problems.append("%s collides with %s (%.1f mm3)" % (name, part, v))
    monitor = bd.Pos(0, -p["mon_thick"] / 2, 50) * bd.Box(200, p["mon_thick"], 100)
    for part in ("Pod", "Cover", "Clamp", "Bezel", "Board_Cap"):
        v = overlap(monitor, world[part], "monitor / %s" % part)
        if v > 0.5:
            problems.append("%s cuts into the monitor (%.1f mm3)" % (part, v))
    problems += UNCHECKED
    room = p["pod_depth"] - (info["z_pcb"] + TFT["pcb_t"] + TFT["smd_h"])
    notes.append("room behind the display's rear components for solder joints and wires: %.1f mm" % room)
    if room < 1.5:
        problems.append("only %.1f mm behind the display for its wires" % room)
    notes.append("front lip is %.0f mm tall (chin %.0f mm)" % (p["lip_h"], p["mon_chin"]))
    if p["lip_h"] > p["mon_chin"]:
        problems.append("front lip is taller than the monitor's chin")
    pod_parts = [world[n].bounding_box() for n in ("Pod", "Cover", "Clamp")]
    below = -min(b.min.Z for b in pod_parts)
    pb, cb = world["Pod"].bounding_box(), world["Cover"].bounding_box()
    notes.append("pod + cover are %.0f mm thick; the unit hangs %.0f mm below the monitor, %.0f mm in front of the bezel, %.0f mm wide" % (
        p["pod_depth"] + p["cover_t"], below, max(pb.max.Y, cb.max.Y), pb.size.X))
    notes.append("behind the monitor: back wall + board + cap reach %.0f mm past its back face (the plug and cable go up from there)" % (
        -world["Board_Cap"].bounding_box().min.Y - p["mon_thick"]))
    travel = p["m4_len"] - p["back_t"]                          # how far the screw can stand out of the wall's inner face
    eff = p["jaw_t"] - p["jaw_socket"]
    lo, hi = max(0.0, p["mon_thick"] + p["back_gap"] - eff - travel), p["mon_thick"] + p["back_gap"] - eff
    notes.append("clamp fits monitor thickness %.1f to %.1f mm bare, %.1f to %.1f mm with %.1f mm padding on both the lip and the jaw (screw travel %.0f mm)" % (
        lo, hi, max(0.0, lo - 2 * p["pad_t"]), hi - 2 * p["pad_t"], p["pad_t"], travel))
    stick_out = p["m4_len"] - p["back_t"] - (p["back_gap"] - eff) + p["m4_head_h"]
    notes.append("clamped on a %.1f mm monitor the screw head ends %.0f mm behind the back wall (knob %.0f mm dia)" % (p["mon_thick"], stick_out, p["knob_d"]))
    for label, a, c in (("bare", lo, hi), ("padded", lo - 2 * p["pad_t"], hi - 2 * p["pad_t"])):
        if not a + 0.3 <= p["mon_thick"] <= c - 0.3:
            problems.append("the %.1f mm monitor is outside the clamp's %s range %.1f-%.1f mm" % (p["mon_thick"], label, a, c))
    grip = p["bolt_l"] - p["hanger_t"] - p["cover_t"]
    notes.append("pod bolts reach %.1f mm into the %.1f mm inserts; %.1f mm of plastic is left in front of each insert" % (
        grip, p["insert_l"], p["pod_depth"] - p["insert_l"] - 0.5))
    if grip < 3.0 or grip > p["insert_l"] + 0.5:
        problems.append("pod bolt engagement %.1f mm is wrong for the insert" % grip)
    bx0, bx1, bz0, bz1, yf = board_pose(p)
    if bx1 + p["cap_play"] + 0.5 > p["wall_x1"]:
        problems.append("board does not fit on the back wall")
    # the board must be trapped: ledge lip in front of its lower edge, cap wall over its upper edge beside the USB socket
    lip_cover = (bz0 - 0.2 + p["ledge_lip_h"]) - bz0
    top_gap = 0.2
    side_cover = (MCU["w"] - MCU["usb_w"]) / 2 - 0.4
    notes.append("board is held by: ledge lip over %.1f mm of its lower edge; cap wall %.1f mm above its upper edge, covering %.1f mm each side of the USB socket; "
                 "%.1f mm side play in the cap" % (lip_cover, top_gap, side_cover, p["cap_play"]))
    if lip_cover < 0.5 or side_cover < 2.0:
        problems.append("the board is not properly trapped by the ledge lip / cap")
    sunk = (bz1 + MCU["usb_overhang"]) - p["back_h"]
    notes.append("USB socket face is %.1f mm below the cap's top face (a plug loses that much insertion)" % -sunk)
    if -sunk > 0.5:
        problems.append("the USB socket is recessed %.1f mm: plugs may not seat" % -sunk)
    cap_grip = p["bolt_l"] - p["cap_seat_t"]
    notes.append("cap bolt: %.1f mm under its head, %.1f mm into the back wall (insert %.1f; tip ends %.1f mm into the %.1f mm gap behind the monitor)" % (
        p["cap_seat_t"], min(cap_grip, p["back_t"]), p["insert_l"], max(0.0, cap_grip - p["back_t"]), p["back_gap"]))
    if p["cap_ear_x0"] - (p["bolt_x_clamp"] + p["knob_d"] / 2) < 1.0:
        problems.append("the cap's ear is too close to the clamp knob")
    if p["jaw_z0"] < p["root_fillet"] - (p["back_gap"] - p["jaw_t"]):
        problems.append("the jaw would foul the gusset at the root of the back wall")
    return problems, notes


COLOURS = {"Board_Cap": "#4a4e55", "Bezel": "#c8ccd2", "Pod": "#2b2d31", "Cover": "#3a3d42", "Clamp": "#2b2d31", "Jaw": "#8a8f98", "Knob": "#b0343a",
           "display_pcb": "#2f6fb5", "display_screen": "#0b0e11", "board": "#3f8a4a", "hardware": "#c9a227", "insert": "#b8862b", "steel": "#9aa0a8"}


def present_items(p, world, extras):
    """Everything to show in the presentation (Fusion document + labelled sheets): one item per physical thing.

    Explode moves are world vectors. The pod stack comes apart along the screen's own axis (tilted), the clamp parts
    along the clamp screw (Y). The Clamp stays where it is.
    """
    from mechkit.present import manifest as M

    t = math.radians(p["tilt_deg"])

    def n(d):                                                   # d mm out of the screen, toward the user
        return (0.0, d * math.cos(t), d * math.sin(t))

    hw, ins = hardware_items(p), insert_items(p)
    pr = dict(kind="printed", material="PETG")
    m3i = dict(label=6, kind="hardware", part="Heat-set insert M3", material="Brass", colour=COLOURS["insert"], part_number="MWD-H1",
               description="Brass heat-set insert M3, 5.1 long, in a 4.0 mm hole. Set with a soldering iron.")
    m3b = dict(label=7, kind="hardware", part="Bolt M3 x 10, socket head", material="Steel", colour=COLOURS["steel"], part_number="MWD-H2",
               description="Socket-head M3 x 10 machine screw.")
    disp = dict(label=3, kind="bought", part="Round display GC9A01 1.28 in", part_number="GC9A01-1.28", explode=n(40),
                description="1.28 inch round 240 x 240 display, 7-pin board with a tab. Seven wires soldered to its pads.")
    items = [
        M.item("Bezel", world["Bezel"], 1, colour=COLOURS["Bezel"], part_number="MWD-P1", explode=n(100),
               description="Decorative gauge ring. Five pins on its back press into the pod face; held by friction, no glue.", **pr),
        M.item("Pod", world["Pod"], 2, colour=COLOURS["Pod"], part_number="MWD-P2", explode=n(74),
               description="Shell that holds the round display behind its window. Two M3 inserts in its back.", **pr),
        M.item("Display_Board", extras["display_pcb"], colour=COLOURS["display_pcb"], name="Display GC9A01 (board)", **disp),
        M.item("Display_Screen", extras["display_screen"], colour=COLOURS["display_screen"], name="Display GC9A01 (screen)", count=0, **disp),
        M.item("Cover", world["Cover"], 4, colour=COLOURS["Cover"], part_number="MWD-P3", explode=n(20),
               description="Back plate of the pod. Four pads press the display board into its pocket; slot for the wires.", **pr),
        M.item("Clamp", world["Clamp"], 5, colour=COLOURS["Clamp"], part_number="MWD-P4",
               description="Saddle over the monitor's bottom edge, with the tilted hanger for the pod and the back wall that carries the board.", **pr),
        M.item("Insert_M3_pod_L", ins["Insert_M3_pod_L"], name="Insert M3 (pod, left)", explode=n(56), **m3i),
        M.item("Insert_M3_pod_R", ins["Insert_M3_pod_R"], name="Insert M3 (pod, right)", explode=n(56), **m3i),
        M.item("Insert_M3_cap", ins["Insert_M3_cap"], name="Insert M3 (board cap)", explode=(0, -10, 0), **m3i),
        M.item("Bolt_M3x10_pod_L", hw["Bolt_M3x10_pod_L"], name="Bolt M3 x 10 (pod, left)", explode=n(-30), **m3b),
        M.item("Bolt_M3x10_pod_R", hw["Bolt_M3x10_pod_R"], name="Bolt M3 x 10 (pod, right)", explode=n(-30), **m3b),
        M.item("Bolt_M3x10_cap", hw["Bolt_M3x10_cap"], name="Bolt M3 x 10 (board cap)", explode=(0, -68, 0), **m3b),
        M.item("Jaw", world["Jaw"], 8, colour=COLOURS["Jaw"], part_number="MWD-P5", explode=(0, 13, 0),
               description="Pressure plate between the clamp screw and the monitor's back. Spreads the grip so the unit cannot twist.", **pr),
        M.item("Insert_M4_clamp", ins["Insert_M4_clamp"], 9, kind="hardware", part="Heat-set insert M4", name="Insert M4 (clamp)", material="Brass",
               colour=COLOURS["insert"], part_number="MWD-H3", explode=(0, 6, 0),
               description="Brass heat-set insert M4 in a 4.5 mm pocket, set from inside the saddle so clamping seats it."),
        M.item("Screw_M4x30", hw["Screw_M4x30"], 10, kind="hardware", part="Screw M4 x 30, socket head", name="Clamp screw M4 x 30", material="Steel",
               colour=COLOURS["steel"], part_number="MWD-H4", explode=(0, -40, 0),
               description="Socket-head M4 x 30: the clamp screw. Runs through the M4 insert and presses on the jaw."),
        M.item("Knob", world["Knob"], 11, colour=COLOURS["Knob"], part_number="MWD-P6", explode=(0, -72, 0),
               description="Thumb knob pressed onto the clamp screw's head.", **pr),
        M.item("Board", extras["board"], 12, kind="bought", colour=COLOURS["board"], part_number="ESP32-C3-SuperMini", part="ESP32-C3 SuperMini",
               name="ESP32-C3 SuperMini", explode=(0, -22, 0),
               description="Microcontroller board, 22.5 x 18 mm, USB-C pointing up. Sits on the back wall with its lower edge in the ledge."),
        M.item("Board_Cap", world["Board_Cap"], 13, colour=COLOURS["Board_Cap"], part_number="MWD-P7", explode=(0, -46, 0),
               description="Cap over the board. Hooks round the end of the back wall and is bolted on; takes the pull when the cable is unplugged.", **pr),
        M.item("Monitor", bd.Pos(0, -p["mon_thick"] / 2, 45) * bd.Box(150, p["mon_thick"], 90), 0, kind="reference", colour="#3a3d42", opacity=0.25,
               name="Monitor (for context)", description="Piece of the monitor's bottom edge: 21.5 mm thick where the clamp sits."),
    ]
    views = [M.view("Front", (140, 250, 40), (0, -14, -14)), M.view("Side", (330, -15, -10), (0, -14, -14)),
             M.view("Rear", (120, -260, 60), (0, -22, -8)),
             M.view("Exploded", (330, 150, 150), (0, -20, -10), group="exploded"),
             M.view("Exploded rear", (300, -260, 150), (0, -20, -10), group="exploded")]
    return items, views


def present_steps(p=P):
    """The assembly order, as the user built it (2026-11-25). Keys are the items of present_items().

    Each step says where its picture is taken from and how its parts are drawn pulled out: along the way they really go
    on, so the part being fitted is never hidden inside the part it goes into."""
    from mechkit.present import manifest as M

    t = math.radians(p["tilt_deg"])

    def n(d):                                                   # d mm out of the screen, toward the user
        return (0.0, d * math.cos(t), d * math.sin(t))

    rear, side, front, top_rear = (150, -260, 120), (330, -70, 110), (220, 240, 120), (130, -170, 320)
    c_pod, c_clamp = (0, -6, -30), (5, -24, 8)
    pod_set = ("Pod", "Insert_M3_pod_L", "Insert_M3_pod_R")
    return [
        M.step("Set the inserts in the pod", "Press the two M3 inserts into the holes in the pod's back with a soldering iron, flush with the surface.",
               ["Pod", "Insert_M3_pod_L", "Insert_M3_pod_R"], view=(rear, c_pod),
               pull={"Insert_M3_pod_L": n(-16), "Insert_M3_pod_R": n(-16)}),
        M.step("Set the inserts in the clamp", "M3 insert into the back wall from behind (for the board cap). M4 insert into its pocket from INSIDE the "
               "saddle, so that clamping pushes it against the pocket's floor.", ["Clamp", "Insert_M3_cap", "Insert_M4_clamp"], view=(top_rear, c_clamp),
               pull={"Insert_M3_cap": (0, -14, 0), "Insert_M4_clamp": (0, 10, 0)}),
        M.step("Wire and seat the display", "Solder the seven wires to the display's pads (see the wiring page). Lay the display in the pod from the "
               "back, screen toward the window, tab toward the flat top. The ribbon fold and the solder ends have their own reliefs.",
               ["Display_Board", "Display_Screen"], view=(side, c_pod),
               pull={**{k: n(44) for k in pod_set}, "Display_Board": n(20), "Display_Screen": n(20)}),
        M.step("Close the pod and hang it on the clamp", "Feed the wires through the slot in the cover and the hanger. Put the cover on, hold the pod "
               "against the hanger and fasten with two M3 x 10 bolts from behind.", ["Cover", "Bolt_M3x10_pod_L", "Bolt_M3x10_pod_R"], view=(side, c_pod),
               pull={**{k: n(36) for k in pod_set}, "Display_Board": n(36), "Display_Screen": n(36), "Cover": n(16),
                     "Bolt_M3x10_pod_L": n(-26), "Bolt_M3x10_pod_R": n(-26)}),
        M.step("Press on the bezel", "Line up the five pins with the holes in the pod's face and press. It holds by friction; no glue needed.", ["Bezel"],
               view=(front, c_pod), pull={"Bezel": n(22)}),
        M.step("Fit the board and its cap", "Solder the wires to the ESP32-C3 board (see the wiring page). Tuck its lower edge behind the ledge lip on the "
               "back wall, USB socket up. Hook the cap round the end of the wall and fasten it with one M3 x 10 bolt.",
               ["Board", "Board_Cap", "Bolt_M3x10_cap"], view=(rear, c_clamp),
               pull={"Board": (0, -14, 0), "Board_Cap": (0, -34, 0), "Bolt_M3x10_cap": (0, -54, 0)}),
        M.step("Fit the clamp screw", "Press the knob onto the M4 x 30 screw's head. Run the screw through the M4 insert from behind. Stand the jaw in the "
               "saddle with its socket on the screw's tip. Hang the unit on the monitor's bottom edge and tighten gently.", ["Screw_M4x30", "Knob", "Jaw"],
               view=(top_rear, c_clamp), pull={"Screw_M4x30": (0, -34, 0), "Knob": (0, -58, 0), "Jaw": (0, 0, 34)}),
    ]


def present_guide():
    """The printed guide's other pages. Wiring comes from pinmap.json (the one place pins are written)."""
    from mechkit.present import manifest as M

    pm = json.loads((PROJECT / "pinmap.json").read_text(encoding="utf-8"))
    pad = lambda text: text.replace("display pad ", "")         # noqa: E731
    wires = [{"from": w["from"].replace("board ", ""), "to": pad(w["to"]), "signal": "power" if "3V3" in w["from"] else "ground", "note": ""}
             for w in pm["power"]]
    wires += [{"from": "GPIO%d" % x["gpio"], "to": pad(x["connects_to"]), "signal": x["signal"], "note": x["notes"]} for x in pm["pins"]]
    return M.guide(
        tools=[("Soldering iron, fine tip", "for the seven wires and for pressing in the four inserts"),
               ("Hex key 2.5 mm", "M3 socket-head bolts"), ("Hex key 3 mm", "the M4 clamp screw, before the knob is on"),
               ("Wire strippers and flush cutters", ""), ("Tweezers", "to hold the wires on the display's pads"),
               ("USB-C data cable", "power and firmware; a charge-only cable will not work for the firmware"),
               ("Computer with PlatformIO", "to load the firmware")],
        consumables=[("Solder", ""), ("Thin stranded hook-up wire", "7 pieces, about 80 mm each: from the display's tab, through the slot in the cover "
                                                                    "and hanger, under the saddle, up the back wall to the board"),
                     ("Felt or thin rubber pads (optional)", "on the jaw and the front lip; the build holds without them")],
        printing={"settings": [("Printer", "Bambu A1"), ("Material", "PETG"), ("Plate", "textured PEI"), ("Supports", "none: every part is oriented to print without"),
                               ("Other settings", "the slicer's standard PETG profile (layer height and infill were not recorded for this build)")],
                  "parts": [("Pod", "front face down"), ("Bezel", "front face down, pins up"), ("Cover", "plate down, pads up"),
                            ("Clamp", "lying on its left end, so the layers run along the U shape"), ("Jaw", "flat, socket up"),
                            ("Knob", "head pocket up"), ("Board_Cap", "outer skin down, cavity up")],
                  "note": "Print files: exports/%s/*.stl, already turned to these orientations." % VERSION},
        wiring={"title": "Wiring: display to board", "from": "ESP32-C3 SuperMini", "to": "Display GC9A01",
                "wires": wires,
                "notes": ["Match the wires to the NAMES printed beside the pads; the order of the pads differs between display boards.",
                          "The display runs on 3.3 V: connect VCC to the board's 3V3 pin, not to 5V.",
                          "Do not use GPIO2, GPIO8 or GPIO9 (boot pins) or GPIO18 / GPIO19 (USB).",
                          "Pin choice status in pinmap.json: %s." % pm["status"]]},
        commissioning=[
            {"title": "Load the firmware", "text": "Plug the board into the computer with the USB-C data cable. In the project's firmware folder run:  pio run -t upload",
             "checks": ["The upload ends with SUCCESS", "If the board is not found: hold its BOOT button while plugging in, then upload again"]},
            {"title": "First start", "text": "On first start the display opens its own Wi-Fi network, WeatherDisplay-Setup. Join it with a phone, choose your "
             "Wi-Fi network and enter its password. Latitude and longitude are optional; without them the location is estimated from the internet address.",
             "checks": ["The setup network appears", "After saving, the unit joins your Wi-Fi"]},
            {"title": "Functional test", "text": "Leave it running for a few minutes.",
             "checks": ["The picture is upright and centred in the bezel (if not: DISPLAY_ROTATION in firmware/src/main.cpp)",
                        "Day and 12-hour time are correct", "Temperature is shown in Fahrenheit and looks right for where you are",
                        "The background matches the time of day and the weather", "Colours are right (red is red, not blue)"]},
            {"title": "Final inspection", "text": "",
             "checks": ["The clamp screw is snug, the unit does not twist, and nothing presses on the picture area of the monitor",
                        "The cable can be unplugged and plugged without the board moving", "No wire is pinched under the saddle or the board cap",
                        "The bezel sits flat all round"]},
        ],
        notes=["Firmware status when this guide was made: it compiles, but had not yet been run on the finished unit. Treat the commissioning "
               "page as the first real test."])


def print_oriented(name, world, local):
    """Each part turned into its print orientation, sitting on z = 0."""
    if name == "Pod":
        s = local["Pod"]                                        # front face down
    elif name == "Cover":
        s = bd.Rot(X=180) * local["Cover"]                      # plate down, pads up
    elif name == "Jaw":
        s = local["Jaw"]                                        # flat, socket up
    elif name == "Knob":
        s = local["Knob"]                                       # head pocket up
    elif name == "Bezel":
        s = local["Bezel"]                                      # front face down, pins up
    elif name == "Board_Cap":
        s = bd.Rot(X=90) * world["Board_Cap"]                   # outer skin down, cavity up
    else:
        s = bd.Rot(Y=-90) * world["Clamp"]                      # lying on its -X end
    bb = s.bounding_box()
    return bd.Pos(-(bb.min.X + bb.max.X) / 2, -(bb.min.Y + bb.max.Y) / 2, -bb.min.Z) * s


def render(world, extras, path, eye, show_monitor=True, hide=(), target=(0, -14, -14)):
    import pyvista as pv

    pv.OFF_SCREEN = True
    tmp = PROJECT / "work"
    tmp.mkdir(exist_ok=True)
    plotter = pv.Plotter(off_screen=True, window_size=(1300, 950))
    colours = dict(COLOURS)
    items = {**world, **extras}
    if show_monitor:
        items["monitor"] = bd.Pos(0, -P["mon_thick"] / 2, 45) * bd.Box(150, P["mon_thick"], 90)
        items["picture"] = bd.Pos(0, 0.2, P["mon_chin"] + 33) * bd.Box(150, 0.4, 66)
        colours.update(monitor="#3a3d42", picture="#8fb8de")
    for name, solid in items.items():
        if name in hide:
            continue
        stl = tmp / ("_%s.stl" % name)
        bd.export_stl(solid, str(stl), tolerance=0.05)
        plotter.add_mesh(pv.read(str(stl)), color=colours[name], smooth_shading=True, split_sharp_edges=True)
        stl.unlink()
    plotter.set_background("white")
    plotter.camera_position = [eye, target, (0, 0, 1)]
    plotter.camera.zoom(1.2)
    plotter.screenshot(str(path))
    plotter.close()


def main():
    world, extras, local, info = build(P)
    problems, notes = checks(P, world, extras, info)
    out = PROJECT / "exports" / VERSION
    out.mkdir(parents=True, exist_ok=True)
    report = {"version": VERSION, "params": P, "parts": {}, "problems": problems, "notes": notes}
    printed = {}
    for name in world:
        s = printed[name] = print_oriented(name, world, local)
        b3d.save_stl(s, out / ("%s.stl" % name))
        b3d.save_step(world[name], out / ("%s_as_assembled.step" % name))
        bb = s.bounding_box()
        report["parts"][name] = {"volume_mm3": round(world[name].volume, 1), "print_size": [round(bb.size.X, 1), round(bb.size.Y, 1), round(bb.size.Z, 1)],
                                 "valid": bool(world[name].is_valid)}
        print("%-6s %7.0f mm3 (about %4.1f g solid)  prints %5.1f x %5.1f x %5.1f mm  valid=%s" % (
            name, world[name].volume, world[name].volume * 1.27e-3, bb.size.X, bb.size.Y, bb.size.Z, world[name].is_valid))
    # manufacturability (text-to-cad's general FDM rules, Bambu A1: 0.4 mm nozzle, 256 mm bed) and geometry soundness
    from mechkit import dfm
    fab = {"printing": dfm.printing(printed, material="petg", technology="fdm", nozzle=0.4, build_volume=(256, 256, 256)),
           "geometry": dfm.geometry(world)}
    print("DFM (%s): %s" % (fab["printing"]["checker"], ", ".join("%s %s" % (n, e["status"]) for n, e in fab["printing"]["parts"].items())))
    print("written:", dfm.write_report(out, fab))
    problems += dfm.problems(fab)
    from mechkit import drawing                     # one sheet per printed part, every number measured from the solid
    try:
        sheets = [drawing.part_sheet(printed[n], n.replace("_", " "), part_number="MWD-%s-%s" % (VERSION, n), material="PETG",
                                     source="build.py %s, print orientation" % VERSION) for n in printed]
        print("written:", drawing.write(sheets, out / "drawings.pdf"))
    except Exception as e:
        problems.append("drawings not written: %s: %s" % (type(e).__name__, e))
    (PROJECT / "logs").mkdir(exist_ok=True)
    (PROJECT / "logs" / ("build_%s.json" % VERSION)).write_text(json.dumps(report, indent=1), encoding="utf-8")
    from mechkit.present import manifest as M
    items, views = present_items(P, world, extras)
    for a, b, vol in M.exploded_overlaps(items):
        problems.append("exploded view: %s and %s %s" % (a, b, "could not be checked" if vol is None else "still overlap (%.1f mm3)" % vol))
    print("presentation manifest:", M.write(PROJECT, VERSION, "Monitor weather display", items, views, steps=present_steps(), guide=present_guide()))
    for n in notes:
        print("note:", n)
    for pr in problems:
        print("PROBLEM:", pr)
    (PROJECT / "renders").mkdir(exist_ok=True)
    render(world, extras, PROJECT / "renders" / ("%s_front.png" % VERSION), (140, 250, 40))
    render(world, extras, PROJECT / "renders" / ("%s_side.png" % VERSION), (330, -15, -10))
    render(world, extras, PROJECT / "renders" / ("%s_rear.png" % VERSION), (120, -260, 60), show_monitor=False, target=(0, -22, -8))
    render(world, extras, PROJECT / "renders" / ("%s_rear_cap_off.png" % VERSION), (120, -260, 60), show_monitor=False, hide=("Board_Cap",), target=(0, -22, -8))
    render(world, extras, PROJECT / "renders" / ("%s_inside.png" % VERSION), (-90, -220, -20), show_monitor=False, hide=("Clamp", "Pod", "hardware", "Jaw", "Knob", "board", "Board_Cap", "Bezel"),
           target=(0, 0, -34))
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
