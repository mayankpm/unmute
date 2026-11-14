/* Optional ESP32 pager. Requires ESP32 Arduino core + ArduinoJson 7.
 * Copy secrets.example.h to secrets.h and configure it locally.
 * No patient identification is displayed or logged by this sketch.
 */
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include "secrets.h"

// Change to suitable free GPIOs after identifying the actual Espressif board.
#define ALERT_LED 2
#define BUZZER_PIN 25
unsigned long lastPoll = 0, lastReconnect = 0;
bool ledOn = false;
String lastAlertId = "";

void setup() {
  pinMode(ALERT_LED, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  Serial.begin(115200);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    // Blink on loss of connectivity. Never interpret network failure as "no requests".
    digitalWrite(ALERT_LED, (millis() / 500) % 2);
    if (millis() - lastReconnect > 10000) { lastReconnect = millis(); WiFi.reconnect(); }
    delay(20);
    return;
  }
  if (millis() - lastPoll < 2000) return;
  lastPoll = millis();
  HTTPClient http;
  http.setConnectTimeout(2000);
  http.setTimeout(2500);
  http.begin(String(UNMUTE_SERVER) + "/api/pager");
  http.addHeader("Authorization", String("Bearer ") + UNMUTE_TOKEN);
  int code = http.GET();
  if (code == 200) {
    JsonDocument doc;
    DeserializationError error = deserializeJson(doc, http.getString());
    if (!error && doc["pending"].is<int>() && doc["id"].is<const char*>()) {
      bool pending = doc["pending"].as<int>() > 0;
      digitalWrite(ALERT_LED, pending ? HIGH : LOW);
      String id = doc["id"].as<String>();
      if (pending && id != lastAlertId) {
        // Passive piezo; short startup chirp. Current ESP32 core provides tone().
        tone(BUZZER_PIN, 1500, 300);
        lastAlertId = id;
      }
      if (!pending) lastAlertId = "";
    } else Serial.println("Invalid server response");
  } else {
    Serial.println("Pager connection unavailable");
    digitalWrite(ALERT_LED, !digitalRead(ALERT_LED));
  }
  http.end();
}
