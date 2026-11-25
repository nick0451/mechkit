// Monitor weather display: firmware (first version, 2026-11-24). NOT yet run on hardware.
// ESP32-C3 SuperMini + GC9A01 240 x 240 round display.
//
// What it does: joins Wi-Fi (a set-up page appears the first time), gets the time from the network, fetches the
// current weather every 10 minutes, and draws day, time, temperature and conditions over a sky that follows the
// sun's real position, the weather and the season.
//
// Pin numbers come from pins.h, generated from ../pinmap.json (never typed here).
// Network services used (plain HTTP, no account): api.open-meteo.com for weather, ip-api.com to guess the location
// when none was entered on the set-up page, pool.ntp.org for the time.
#include <Arduino.h>
#include <Arduino_GFX_Library.h>
#include <ArduinoJson.h>
#include <HTTPClient.h>
#include <Preferences.h>
#include <WiFi.h>
#include <WiFiManager.h>
#include <time.h>

#include "pins.h"
#include "sky.h"

// ---- settings you may want to change -------------------------------------------------------------------------------
static const uint8_t DISPLAY_ROTATION = 2;            // 2 = the board's pin tab is at the TOP (as it sits in the pod)
static const char *SETUP_NETWORK = "WeatherDisplay-Setup";
static const uint32_t WEATHER_EVERY_MS = 10UL * 60UL * 1000UL;
static const bool USE_FAHRENHEIT = true;

// ---- display -------------------------------------------------------------------------------------------------------
static Arduino_DataBus *bus = new Arduino_ESP32SPI(PIN_TFT_DC, PIN_TFT_CS, PIN_TFT_SCLK, PIN_TFT_MOSI, GFX_NOT_DEFINED);
static Arduino_GFX *panel = new Arduino_GC9A01(bus, PIN_TFT_RST, DISPLAY_ROTATION, true /* IPS */);
static Arduino_Canvas *gfx = new Arduino_Canvas(240, 240, panel);   // drawn off-screen, then sent in one go (no flicker)

// ---- state ---------------------------------------------------------------------------------------------------------
static Preferences prefs;
static float latitude = 0, longitude = 0;
static bool have_location = false;
static bool have_weather = false;
static float temperature = 0;
static int weather_code = 0, cloud_cover = 0;
static long utc_offset_s = 0;
static uint32_t last_weather_ms = 0;
static int last_drawn_minute = -1;
static uint32_t frame = 0;

static uint16_t rgb(sky::Rgb c) { return gfx->color565(c.r, c.g, c.b); }

static void centred(const char *text, int y, uint8_t size, uint16_t colour) {
  int width = (int)strlen(text) * 6 * size;
  gfx->setTextSize(size);
  gfx->setTextColor(0x0000);                          // 1-pixel shadow so text reads on any sky
  gfx->setCursor(120 - width / 2 + size / 2 + 1, y + size / 2 + 1);
  gfx->print(text);
  gfx->setTextColor(colour);
  gfx->setCursor(120 - width / 2, y);
  gfx->print(text);
}

static void message(const char *line1, const char *line2 = "", const char *line3 = "") {
  gfx->fillScreen(0x0000);
  centred(line1, 84, 2, 0xFFFF);
  centred(line2, 114, 2, 0xFFE0);
  centred(line3, 144, 1, 0xC618);
  gfx->flush();
}

// ---- network -------------------------------------------------------------------------------------------------------
static bool getJson(const String &url, JsonDocument &doc) {
  WiFiClient client;
  HTTPClient http;
  http.setTimeout(8000);
  if (!http.begin(client, url)) return false;
  int status = http.GET();
  bool ok = false;
  if (status == 200) {
    DeserializationError err = deserializeJson(doc, http.getString());
    ok = !err;
    if (err) Serial.printf("JSON error from %s: %s\n", url.c_str(), err.c_str());
  } else {
    Serial.printf("HTTP %d from %s\n", status, url.c_str());
  }
  http.end();
  return ok;
}

static void locateByNetwork() {
  JsonDocument doc;
  if (getJson("http://ip-api.com/json/?fields=status,lat,lon", doc) && doc["status"] == "success") {
    latitude = doc["lat"].as<float>();
    longitude = doc["lon"].as<float>();
    have_location = true;
    Serial.printf("location guessed from the network: %.3f, %.3f\n", latitude, longitude);
  }
}

static void fetchWeather() {
  if (!have_location) locateByNetwork();
  if (!have_location) return;
  String url = "http://api.open-meteo.com/v1/forecast?latitude=" + String(latitude, 4) + "&longitude=" + String(longitude, 4) +
               "&current=temperature_2m,weather_code,cloud_cover&timezone=auto&forecast_days=1";
  if (USE_FAHRENHEIT) url += "&temperature_unit=fahrenheit";
  JsonDocument doc;
  if (!getJson(url, doc)) return;
  temperature = doc["current"]["temperature_2m"].as<float>();
  weather_code = doc["current"]["weather_code"].as<int>();
  cloud_cover = doc["current"]["cloud_cover"].as<int>();
  utc_offset_s = doc["utc_offset_seconds"].as<long>();
  have_weather = true;
  Serial.printf("weather: %.1f, code %d, cloud %d %%, utc offset %ld s\n", temperature, weather_code, cloud_cover, utc_offset_s);
}

// ---- drawing -------------------------------------------------------------------------------------------------------
static uint32_t scatter(uint32_t i) {                 // small repeatable pseudo-random number
  uint32_t x = i * 2654435761UL + 12345UL;
  x ^= x >> 13;
  x *= 0x5bd1e995UL;
  return x ^ (x >> 15);
}

static void drawCloud(int x, int y, uint16_t colour) {
  gfx->fillCircle(x, y, 13, colour);
  gfx->fillCircle(x + 15, y + 3, 10, colour);
  gfx->fillCircle(x - 15, y + 4, 9, colour);
  gfx->fillRect(x - 15, y + 4, 31, 10, colour);
}

static void drawScene(const sky::Scene &s) {
  for (int y = 0; y < 240; y++) {                     // sky gradient
    float t = y / 239.0f;
    sky::Rgb c = {(uint8_t)(s.sky_top.r + (s.sky_bottom.r - s.sky_top.r) * t), (uint8_t)(s.sky_top.g + (s.sky_bottom.g - s.sky_top.g) * t),
                  (uint8_t)(s.sky_top.b + (s.sky_bottom.b - s.sky_top.b) * t)};
    gfx->drawFastHLine(0, y, 240, rgb(c));
  }
  if (s.stars) {
    for (uint32_t i = 0; i < 40; i++) {
      uint32_t r = scatter(i);
      gfx->drawPixel(20 + r % 200, 14 + (r >> 8) % 140, 0xFFFF);
    }
  }
  gfx->fillCircle(s.body_x, s.body_y, s.sun_visible ? 17 : 13, rgb(s.body));     // sun or moon
  if (!s.sun_visible) gfx->fillCircle(s.body_x + 6, s.body_y - 4, 11, rgb(s.sky_top));   // bite out of the moon
  uint16_t cloud_colour = s.sun_visible ? gfx->color565(236, 240, 244) : gfx->color565(70, 76, 92);
  static const int16_t CLOUD_AT[5][2] = {{62, 44}, {176, 58}, {120, 30}, {40, 86}, {198, 96}};
  for (int i = 0; i < s.clouds && i < 5; i++) drawCloud(CLOUD_AT[i][0], CLOUD_AT[i][1], cloud_colour);
  gfx->fillCircle(120, 168 + 300, 304, rgb(s.ground));                           // a gently curved season-coloured ground
  for (uint32_t i = 0; i < (uint32_t)s.rain * 22; i++) {
    uint32_t r = scatter(i + frame * 97);
    int x = 14 + r % 212, y = 20 + (r >> 8) % 190;
    gfx->drawLine(x, y, x - 3, y + 9, gfx->color565(150, 190, 255));
  }
  for (uint32_t i = 0; i < (uint32_t)s.snow * 26; i++) {
    uint32_t r = scatter(i + frame * 131);
    gfx->fillCircle(14 + r % 212, 20 + (r >> 8) % 190, 1 + (r >> 20) % 2, 0xFFFF);
  }
  if (s.lightning && frame % 2 == 0) {
    gfx->drawLine(150, 60, 138, 96, 0xFFE0);
    gfx->drawLine(138, 96, 150, 96, 0xFFE0);
    gfx->drawLine(150, 96, 136, 134, 0xFFE0);
  }
}

static void drawFace(time_t utc_now) {
  int64_t local = (int64_t)utc_now + utc_offset_s;
  sky::SunPosition sun = sky::sunPosition((int64_t)utc_now, latitude, longitude);
  sky::Weather weather = sky::weatherFor(weather_code);
  sky::Scene scene = sky::sceneFor(sun, sky::seasonFor(sky::monthOf(local), latitude), weather, cloud_cover);
  drawScene(scene);
  sky::ClockText text = sky::clockText(local);
  centred(text.date, 40, 2, 0xFFFF);
  centred(text.time, 70, 6, 0xFFFF);
  centred(text.ampm, 122, 2, 0xFFFF);
  if (have_weather) {
    char temp[8];
    snprintf(temp, sizeof(temp), "%d", (int)lroundf(temperature));
    int width = (int)strlen(temp) * 24 + 10 + 24;     // digits, the degree ring, the unit letter
    int x = 120 - width / 2;
    gfx->setTextSize(4);
    gfx->setTextColor(0x0000);
    gfx->setCursor(x + 2, 148);
    gfx->print(temp);
    gfx->setTextColor(0xFFFF);
    gfx->setCursor(x, 146);
    gfx->print(temp);
    int ring_x = x + (int)strlen(temp) * 24 + 4;
    gfx->drawCircle(ring_x, 150, 3, 0xFFFF);
    gfx->drawCircle(ring_x, 150, 4, 0xFFFF);
    gfx->setCursor(ring_x + 8, 146);
    gfx->print(USE_FAHRENHEIT ? "F" : "C");
    centred(sky::weatherWord(weather), 190, 2, 0xFFFF);
  } else {
    centred("NO WEATHER YET", 190, 1, 0xC618);
  }
  gfx->flush();
  frame++;
}

// ---- set-up and main loop ------------------------------------------------------------------------------------------
void setup() {
  Serial.begin(115200);
  gfx->begin();
  message("STARTING");

  prefs.begin("weather", false);
  have_location = prefs.getBool("have_loc", false);
  latitude = prefs.getFloat("lat", 0);
  longitude = prefs.getFloat("lon", 0);

  // First start (or after the Wi-Fi changed): the device opens its own network with a set-up page.
  WiFiManager portal;
  WiFiManagerParameter lat_field("lat", "Latitude (blank = guess from the network)", "", 12);
  WiFiManagerParameter lon_field("lon", "Longitude", "", 12);
  portal.addParameter(&lat_field);
  portal.addParameter(&lon_field);
  portal.setAPCallback([](WiFiManager *) { message("JOIN WI-FI", SETUP_NETWORK, "then pick your network"); });
  portal.setConfigPortalTimeout(300);
  message("CONNECTING");
  if (!portal.autoConnect(SETUP_NETWORK)) {
    message("NO WI-FI", "RESTARTING");
    delay(3000);
    ESP.restart();
  }
  if (strlen(lat_field.getValue()) > 0 && strlen(lon_field.getValue()) > 0) {
    latitude = atof(lat_field.getValue());
    longitude = atof(lon_field.getValue());
    have_location = true;
    prefs.putFloat("lat", latitude);
    prefs.putFloat("lon", longitude);
    prefs.putBool("have_loc", true);
  }

  configTime(0, 0, "pool.ntp.org", "time.nist.gov");   // the clock runs on UTC; the weather service gives the local offset
  message("GETTING TIME");
  for (int i = 0; i < 40 && time(nullptr) < 1700000000; i++) delay(250);
  fetchWeather();
  last_weather_ms = millis();
}

void loop() {
  if (WiFi.status() == WL_CONNECTED && (millis() - last_weather_ms > WEATHER_EVERY_MS || !have_weather)) {
    fetchWeather();
    last_weather_ms = millis();
    last_drawn_minute = -1;
  }
  time_t now = time(nullptr);
  if (now < 1700000000) {                              // the network time has not arrived yet
    message("WAITING", "FOR TIME");
    delay(1000);
    return;
  }
  bool animated = sky::weatherFor(weather_code) >= sky::Weather::Drizzle;   // rain, snow and storms move a little
  int minute = (int)((now + utc_offset_s) / 60 % 60);
  if (minute != last_drawn_minute || animated) {
    drawFace(now);
    last_drawn_minute = minute;
  }
  delay(animated ? 400 : 1000);
}
