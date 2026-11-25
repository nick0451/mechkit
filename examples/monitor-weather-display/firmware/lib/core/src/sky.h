// Pure logic for the weather display: sun position, season, weather categories and the scene to draw.
// No Arduino or display dependencies, so it can be checked on a PC.
#pragma once

#include <stdint.h>

namespace sky {

// ---- sun -----------------------------------------------------------------------------------------------------------
struct SunPosition {
  float elevation_deg;   // above the horizon (+) or below (-)
  float azimuth_deg;     // clockwise from north: 90 = east, 180 = south, 270 = west
};
// unix_utc: seconds since 1970 (UTC). Accuracy about 0.1 degree, plenty for drawing.
SunPosition sunPosition(int64_t unix_utc, float latitude_deg, float longitude_deg);

// ---- season --------------------------------------------------------------------------------------------------------
enum class Season : uint8_t { Winter, Spring, Summer, Autumn };
// month 1..12. Seasons flip in the southern hemisphere.
Season seasonFor(int month, float latitude_deg);

// ---- weather -------------------------------------------------------------------------------------------------------
enum class Weather : uint8_t { Clear, PartlyCloudy, Cloudy, Fog, Drizzle, Rain, Snow, Thunder };
// WMO weather interpretation code, as returned by Open-Meteo's `weather_code`.
Weather weatherFor(int wmo_code);
const char *weatherWord(Weather w);

// ---- time ----------------------------------------------------------------------------------------------------------
struct ClockText {
  char time[6];      // "9:41" or "12:05"
  char ampm[3];      // "AM" / "PM"
  char date[12];     // "TUE NOV 24"
};
// local_seconds: unix time already shifted to local time (UTC + offset).
ClockText clockText(int64_t local_seconds);
int monthOf(int64_t local_seconds);

// ---- scene ---------------------------------------------------------------------------------------------------------
struct Rgb {
  uint8_t r, g, b;
};
struct Scene {
  Rgb sky_top, sky_bottom;   // vertical gradient
  Rgb ground;                // season band along the bottom of the round face
  bool sun_visible;          // true: draw the sun; false: draw the moon and stars
  int16_t body_x, body_y;    // centre of the sun or moon on the 240 x 240 face
  Rgb body;                  // its colour
  uint8_t clouds;            // 0..5 cloud shapes
  uint8_t rain;              // 0..3 streak density
  uint8_t snow;              // 0..3 flake density
  bool lightning;
  bool stars;
};
// cloud_cover_pct: 0..100. The face is 240 x 240 with the horizon at y = 168.
Scene sceneFor(SunPosition sun, Season season, Weather weather, int cloud_cover_pct);

}  // namespace sky
