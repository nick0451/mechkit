#include "sky.h"

#include <math.h>
#include <stdio.h>
#include <string.h>

namespace sky {

static const double DEG = 3.14159265358979323846 / 180.0;

static double wrap360(double a) {
  a = fmod(a, 360.0);
  return a < 0 ? a + 360.0 : a;
}

SunPosition sunPosition(int64_t unix_utc, float latitude_deg, float longitude_deg) {
  // Low-precision solar position (Astronomical Almanac). n = days since 2000-01-01 12:00 UTC.
  double n = (double)unix_utc / 86400.0 + 2440587.5 - 2451545.0;
  double mean_long = wrap360(280.460 + 0.9856474 * n);
  double anomaly = wrap360(357.528 + 0.9856003 * n) * DEG;
  double ecl_long = (mean_long + 1.915 * sin(anomaly) + 0.020 * sin(2 * anomaly)) * DEG;
  double obliquity = (23.439 - 0.0000004 * n) * DEG;
  double right_asc = atan2(cos(obliquity) * sin(ecl_long), cos(ecl_long));
  double declination = asin(sin(obliquity) * sin(ecl_long));
  double gmst_hours = fmod(18.697374558 + 24.06570982441908 * n, 24.0);
  double hour_angle = (gmst_hours * 15.0 + longitude_deg) * DEG - right_asc;
  double lat = latitude_deg * DEG;
  double elevation = asin(sin(lat) * sin(declination) + cos(lat) * cos(declination) * cos(hour_angle));
  double azimuth = atan2(-sin(hour_angle), tan(declination) * cos(lat) - sin(lat) * cos(hour_angle));
  SunPosition out;
  out.elevation_deg = (float)(elevation / DEG);
  out.azimuth_deg = (float)wrap360(azimuth / DEG);
  return out;
}

Season seasonFor(int month, float latitude_deg) {
  Season north;
  if (month == 12 || month <= 2) north = Season::Winter;
  else if (month <= 5) north = Season::Spring;
  else if (month <= 8) north = Season::Summer;
  else north = Season::Autumn;
  if (latitude_deg >= 0) return north;
  switch (north) {
    case Season::Winter: return Season::Summer;
    case Season::Spring: return Season::Autumn;
    case Season::Summer: return Season::Winter;
    default: return Season::Spring;
  }
}

Weather weatherFor(int code) {
  if (code == 0) return Weather::Clear;
  if (code == 1 || code == 2) return Weather::PartlyCloudy;
  if (code == 3) return Weather::Cloudy;
  if (code == 45 || code == 48) return Weather::Fog;
  if (code >= 51 && code <= 57) return Weather::Drizzle;
  if ((code >= 61 && code <= 67) || (code >= 80 && code <= 82)) return Weather::Rain;
  if ((code >= 71 && code <= 77) || code == 85 || code == 86) return Weather::Snow;
  if (code >= 95) return Weather::Thunder;
  return Weather::Cloudy;
}

const char *weatherWord(Weather w) {
  switch (w) {
    case Weather::Clear: return "CLEAR";
    case Weather::PartlyCloudy: return "PARTLY CLOUDY";
    case Weather::Cloudy: return "CLOUDY";
    case Weather::Fog: return "FOG";
    case Weather::Drizzle: return "DRIZZLE";
    case Weather::Rain: return "RAIN";
    case Weather::Snow: return "SNOW";
    default: return "STORM";
  }
}

// Civil date from days since 1970-01-01 (Howard Hinnant's algorithm).
static void civilFromDays(int64_t z, int &y, int &m, int &d) {
  z += 719468;
  int64_t era = (z >= 0 ? z : z - 146096) / 146097;
  unsigned doe = (unsigned)(z - era * 146097);
  unsigned yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
  unsigned doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
  unsigned mp = (5 * doy + 2) / 153;
  d = (int)(doy - (153 * mp + 2) / 5 + 1);
  m = (int)(mp < 10 ? mp + 3 : mp - 9);
  y = (int)(yoe + era * 400 + (m <= 2 ? 1 : 0));
}

int monthOf(int64_t local_seconds) {
  int y, m, d;
  int64_t days = local_seconds / 86400 - (local_seconds % 86400 < 0 ? 1 : 0);
  civilFromDays(days, y, m, d);
  return m;
}

ClockText clockText(int64_t local_seconds) {
  static const char *DAYS[] = {"THU", "FRI", "SAT", "SUN", "MON", "TUE", "WED"};   // 1970-01-01 was a Thursday
  static const char *MONTHS[] = {"JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"};
  int64_t days = local_seconds / 86400;
  int64_t rem = local_seconds % 86400;
  if (rem < 0) {
    rem += 86400;
    days -= 1;
  }
  int y, m, d;
  civilFromDays(days, y, m, d);
  int hour = (int)(rem / 3600), minute = (int)((rem % 3600) / 60);
  int hour12 = hour % 12 == 0 ? 12 : hour % 12;
  ClockText out;
  snprintf(out.time, sizeof(out.time), "%d:%02d", hour12, minute);
  strcpy(out.ampm, hour < 12 ? "AM" : "PM");
  snprintf(out.date, sizeof(out.date), "%s %s %d", DAYS[((days % 7) + 7) % 7], MONTHS[m - 1], d);
  return out;
}

static Rgb mix(Rgb a, Rgb b, float t) {
  if (t < 0) t = 0;
  if (t > 1) t = 1;
  Rgb o;
  o.r = (uint8_t)(a.r + (b.r - a.r) * t);
  o.g = (uint8_t)(a.g + (b.g - a.g) * t);
  o.b = (uint8_t)(a.b + (b.b - a.b) * t);
  return o;
}

Scene sceneFor(SunPosition sun, Season season, Weather weather, int cloud_cover_pct) {
  static const Rgb NIGHT_TOP = {4, 6, 24}, NIGHT_BOTTOM = {16, 24, 58};
  static const Rgb DUSK_TOP = {44, 48, 110}, DUSK_BOTTOM = {240, 138, 76};
  static const Rgb DAY_TOP = {40, 120, 215}, DAY_BOTTOM = {160, 208, 255};
  static const Rgb GREY_TOP = {70, 78, 90}, GREY_BOTTOM = {150, 158, 168};
  Scene s;
  float e = sun.elevation_deg;
  // night below -6 degrees, twilight from -6 to +8, full day above
  if (e <= -6) {
    s.sky_top = NIGHT_TOP;
    s.sky_bottom = NIGHT_BOTTOM;
  } else if (e < 1) {
    float t = (e + 6) / 7.0f;
    s.sky_top = mix(NIGHT_TOP, DUSK_TOP, t);
    s.sky_bottom = mix(NIGHT_BOTTOM, DUSK_BOTTOM, t);
  } else if (e < 8) {
    float t = (e - 1) / 7.0f;
    s.sky_top = mix(DUSK_TOP, DAY_TOP, t);
    s.sky_bottom = mix(DUSK_BOTTOM, DAY_BOTTOM, t);
  } else {
    s.sky_top = DAY_TOP;
    s.sky_bottom = DAY_BOTTOM;
  }
  // weather greys the sky: the more cloud, the greyer; storms darker still
  float grey = 0;
  switch (weather) {
    case Weather::Clear: grey = 0; break;
    case Weather::PartlyCloudy: grey = 0.2f; break;
    case Weather::Cloudy: grey = 0.65f; break;
    case Weather::Fog: grey = 0.8f; break;
    case Weather::Drizzle: grey = 0.7f; break;
    case Weather::Rain: grey = 0.8f; break;
    case Weather::Snow: grey = 0.75f; break;
    default: grey = 0.9f; break;
  }
  float night_dim = e <= -6 ? 0.25f : (e < 8 ? 0.25f + 0.75f * (e + 6) / 14.0f : 1.0f);
  Rgb gt = mix({0, 0, 0}, GREY_TOP, night_dim), gb = mix({0, 0, 0}, GREY_BOTTOM, night_dim);
  if (weather == Weather::Thunder) {
    gt = mix(gt, {20, 20, 30}, 0.6f);
    gb = mix(gb, {40, 40, 55}, 0.6f);
  }
  s.sky_top = mix(s.sky_top, gt, grey);
  s.sky_bottom = mix(s.sky_bottom, gb, grey);

  switch (season) {
    case Season::Spring: s.ground = {96, 180, 80}; break;
    case Season::Summer: s.ground = {40, 122, 52}; break;
    case Season::Autumn: s.ground = {196, 118, 44}; break;
    default: s.ground = {226, 234, 242}; break;
  }
  if (weather == Weather::Snow) s.ground = {236, 242, 248};
  s.ground = mix({0, 0, 0}, s.ground, 0.35f + 0.65f * night_dim);

  // sun (or moon) placed as seen facing the equator: east on the left, highest in the middle
  const float HORIZON_Y = 168.0f;
  s.sun_visible = e > -2;
  float az = sun.azimuth_deg, el = e;
  if (!s.sun_visible) {              // moon: opposite side of the sky, a fixed comfortable height
    az = az + 180.0f;
    el = 35.0f;
  }
  float x = 120.0f + 92.0f * (float)sin((az - 180.0f) * DEG);
  float y = HORIZON_Y - (el < 0 ? el * 2.0f : el / 90.0f * 128.0f);
  s.body_x = (int16_t)x;
  s.body_y = (int16_t)y;
  if (s.sun_visible) s.body = el < 8 ? Rgb{255, 150, 70} : Rgb{255, 224, 96};
  else s.body = {232, 236, 244};

  int cover = cloud_cover_pct < 0 ? 0 : (cloud_cover_pct > 100 ? 100 : cloud_cover_pct);
  s.clouds = (uint8_t)((cover + 10) / 20);                   // 0..5
  if (weather == Weather::Clear) s.clouds = 0;
  if (weather >= Weather::Cloudy && s.clouds < 4) s.clouds = 4;
  s.rain = weather == Weather::Drizzle ? 1 : (weather == Weather::Rain ? 2 : (weather == Weather::Thunder ? 3 : 0));
  s.snow = weather == Weather::Snow ? 2 : 0;
  s.lightning = weather == Weather::Thunder;
  s.stars = !s.sun_visible && grey < 0.5f;
  return s;
}

}  // namespace sky
