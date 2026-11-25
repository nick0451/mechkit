"""Check the formulas used in firmware/lib/core/src/sky.cpp against known answers (Python copy of the same maths).

    python tests/check_sky_maths.py

This checks the METHOD (sun position, date and 12-hour clock). It does not run the C++ itself: there is no PC compiler
on this machine, so the firmware's own code is only compile-checked until it runs on the board.
"""
import math
from datetime import datetime, timezone

DEG = math.pi / 180


def sun_position(unix_utc, lat, lon):
    n = unix_utc / 86400.0 + 2440587.5 - 2451545.0
    mean_long = (280.460 + 0.9856474 * n) % 360
    anomaly = ((357.528 + 0.9856003 * n) % 360) * DEG
    ecl = (mean_long + 1.915 * math.sin(anomaly) + 0.020 * math.sin(2 * anomaly)) * DEG
    obl = (23.439 - 0.0000004 * n) * DEG
    ra = math.atan2(math.cos(obl) * math.sin(ecl), math.cos(ecl))
    dec = math.asin(math.sin(obl) * math.sin(ecl))
    gmst = (18.697374558 + 24.06570982441908 * n) % 24
    ha = (gmst * 15 + lon) * DEG - ra
    la = lat * DEG
    el = math.asin(math.sin(la) * math.sin(dec) + math.cos(la) * math.cos(dec) * math.cos(ha))
    az = math.atan2(-math.sin(ha), math.tan(dec) * math.cos(la) - math.sin(la) * math.cos(ha))
    return el / DEG, (az / DEG) % 360


def civil(days):
    z = days + 719468
    era = (z if z >= 0 else z - 146096) // 146097
    doe = z - era * 146097
    yoe = (doe - doe // 1460 + doe // 36524 - doe // 146096) // 365
    doy = doe - (365 * yoe + yoe // 4 - yoe // 100)
    mp = (5 * doy + 2) // 153
    d = doy - (153 * mp + 2) // 5 + 1
    m = mp + 3 if mp < 10 else mp - 9
    return yoe + era * 400 + (1 if m <= 2 else 0), m, d


def clock(local):
    days, rem = divmod(local, 86400)
    y, m, d = civil(days)
    hour, minute = rem // 3600, rem % 3600 // 60
    return "%d:%02d" % (12 if hour % 12 == 0 else hour % 12, minute), "AM" if hour < 12 else "PM", \
        "%s %s %d" % (["THU", "FRI", "SAT", "SUN", "MON", "TUE", "WED"][days % 7],
                      ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"][m - 1], d)


bad = 0


def check(name, ok, detail=""):
    global bad
    bad += not ok
    print("  %-4s %s  %s" % ("ok" if ok else "FAIL", name, detail))


def ts(*a):
    return int(datetime(*a, tzinfo=timezone.utc).timestamp())


# June solstice, local solar noon at 40 N, 75 W (17:02 UTC): the sun is due south at 90 - 40 + 23.44 = 73.4 degrees
el, az = sun_position(ts(2026, 6, 21, 17, 2), 40.0, -75.0)
check("June solstice noon, 40 N: elevation about 73.4, due south", abs(el - 73.4) < 0.4 and abs(az - 180) < 3, "%.2f, %.1f" % (el, az))
# December solstice noon: 90 - 40 - 23.44 = 26.6
el, az = sun_position(ts(2026, 12, 21, 16, 58), 40.0, -75.0)
check("December solstice noon, 40 N: elevation about 26.6", abs(el - 26.6) < 0.4 and abs(az - 180) < 3, "%.2f, %.1f" % (el, az))
# equinox on the equator at Greenwich: nearly overhead at 12:07 UTC
el, az = sun_position(ts(2026, 3, 20, 12, 7), 0.0, 0.0)
check("March equinox, equator: nearly overhead", el > 88.5, "%.2f" % el)
# midnight is night; morning sun is in the east, evening sun in the west
el, az = sun_position(ts(2026, 6, 21, 5, 0), 40.0, -75.0)
check("local midnight: sun well below the horizon", el < -20, "%.1f" % el)
el, az = sun_position(ts(2026, 6, 21, 12, 0), 40.0, -75.0)
check("mid-morning: sun in the east (azimuth under 120)", 60 < az < 120 and el > 0, "%.1f at %.1f" % (az, el))
el, az = sun_position(ts(2026, 6, 21, 22, 30), 40.0, -75.0)
check("evening: sun in the west (azimuth over 270)", 270 < az < 310, "%.1f at %.1f" % (az, el))
for stamp, offset, want in [((2026, 11, 24, 14, 41), -5 * 3600, ("9:41", "AM", "TUE NOV 24")),
                            ((2026, 11, 24, 5, 5), -5 * 3600, ("12:05", "AM", "TUE NOV 24")),
                            ((2026, 11, 24, 17, 0), -5 * 3600, ("12:00", "PM", "TUE NOV 24")),
                            ((2027, 1, 1, 3, 59), -5 * 3600, ("10:59", "PM", "THU DEC 31")),
                            ((2028, 2, 29, 23, 30), 0, ("11:30", "PM", "TUE FEB 29"))]:
    got = clock(ts(*stamp) + offset)
    check("clock %s UTC%+d -> %s" % (stamp, offset // 3600, want), got == want, got)
print("%d failed" % bad)
raise SystemExit(1 if bad else 0)
