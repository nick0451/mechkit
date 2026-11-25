# Brief: Monitor weather display

Started 2026-11-23 from the user's description. Tags: **stated** (user said it / datasheet), **measured** (calipers),
**scaled**, **assumed** (my placeholder until checked).

## What it is for
A small round display clipped under the bottom edge of the monitor, showing day, weather and time over a background
that follows season, weather and sun position. The screen hangs underneath the monitor and is tilted slightly up
toward the eyes.

## What it must do
- Loads: its own weight (a few tens of grams) plus the pull of a USB cable; being bumped by a hand or a cleaning cloth.
  The clamp must not mark or stress the monitor.
- Things that move: only the clamp bolt. Nothing to click or slide in use.
- Where it lives: indoors on the monitor's bottom edge. The monitor's underside may be warm; the ESP32 and the
  backlight add a little heat inside a small closed pod.

## Size and shape limits
- Monitor bottom edge: **21.5 mm front to back where the clamp sits** (measured by the user 2026-11-24; 23.4 was first stated).
- Front bezel below the picture: **24 mm tall** (stated). Nothing may rise above that on the front, or it covers the screen.
- Unknown, to ask: is the back flat for the first 20-30 mm above the bottom edge? Is the underside flat? Are there
  buttons, vents, a logo or a stand near the middle of the bottom edge?
- Screen tilt: "ever so slightly up" (stated). Concept value 10 degrees (assumed; a parameter).

## Mounting (decided 2026-11-23)
Screw clamp: a saddle over the bottom edge; a brass insert in the back wall and an M3 x 10 bolt pressing a padded
shoe against the monitor's back.

## Parts on hand
| Part | Qty | Datasheet or listing | Measured yet? |
|---|---|---|---|
| ESP32-C3 SuperMini | 1 | typical 22.5 x 18 mm, USB-C (assumed until measured) | no |
| GC9A01 round display, 1.28", 240 x 240 | 1 | module type unknown: board outline, hole pattern and pin header NOT known | no |
| Brass heat-set inserts | ? | size unknown (an earlier build used M3 x L5 x OD4.5; assumed the same) | no |
| M3 x 10 bolts | ? | head type unknown (assumed socket head cap) | no |

## Electronics and firmware
- ESP32-C3 SuperMini driving the GC9A01 over SPI. No buttons planned.
- Firmware: Wi-Fi; time from the network (NTP); weather from an online service (a free one that needs no account is
  preferred); day, time and weather drawn over a background chosen from season, weather and the sun's position.
- Needs from the user later: Wi-Fi name / password entry method, and the location for weather and sun position.
- Power: USB-C cable (from a monitor USB port or a charger). Cable exit direction to be chosen at the concept gate.

## Making it
- Printer and material: Bambu A1, PETG (as for an earlier build, where the same clearances fitted first time).
- Soldering: assumed acceptable for the display's 7-8 wires (to confirm).
- Budget: parts are on hand; nothing should need buying (a felt or rubber pad for the clamp shoe may be useful).

## What "done" looks like
See requirements.json.
