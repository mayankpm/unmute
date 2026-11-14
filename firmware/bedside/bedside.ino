/* Unmute bedside controller — Arduino UNO R3 / Elegoo compatible.
 * USB serial: 115200 baud. See firmware/README.md before wiring.
 * Uses only Arduino's bundled LiquidCrystal library. Set USE_LCD=0 for buttons/LEDs only.
 */
#include <LiquidCrystal.h>
#define USE_LCD 1

LiquidCrystal lcd(12, 11, 5, 4, 3, 2);
const byte SELECT_PIN = 6, BACK_PIN = 7, HELP_PIN = 8;
const byte GREEN_PIN = 9, AMBER_PIN = 10, RED_PIN = 13;
const byte BUZZER_PIN = A1, SPEED_PIN = A0;
const byte BUTTONS[] = {SELECT_PIN, BACK_PIN, HELP_PIN};
const char* COMMANDS[] = {"SELECT", "BACK", "HELP"};
bool lastRaw[3] = {HIGH, HIGH, HIGH}, stable[3] = {HIGH, HIGH, HIGH};
unsigned long changed[3] = {0, 0, 0};
unsigned long lastReceived = 0, lastSpeedRead = 0;
int previousSpeed = -1000;
char serialLine[100];
byte serialLength = 0;
bool overflowing = false, disconnected = false;
char currentState[20] = "idle";
char currentText[61] = "Ready to listen";

void displayMessage(const char* state, const char* text) {
  bool isNew = strcmp(state, currentState) != 0 || strcmp(text, currentText) != 0;
  strncpy(currentState, state, sizeof(currentState) - 1);
  currentState[sizeof(currentState) - 1] = 0;
  strncpy(currentText, text, sizeof(currentText) - 1);
  currentText[sizeof(currentText) - 1] = 0;
  bool urgent = strcmp(state, "urgent") == 0;
  bool pending = strcmp(state, "pending") == 0;
  digitalWrite(RED_PIN, urgent);
  digitalWrite(AMBER_PIN, pending);
  digitalWrite(GREEN_PIN, !urgent && !pending);
  if (isNew && urgent) tone(BUZZER_PIN, 1500, 300);
  else if (isNew && strcmp(state, "acknowledged") == 0) tone(BUZZER_PIN, 900, 100);
#if USE_LCD
  lcd.clear();
  lcd.setCursor(0, 0);
  for (byte i = 0; i < 16 && text[i]; i++) lcd.print(text[i]);
  lcd.setCursor(0, 1);
  if (strcmp(state, "acknowledged") == 0) lcd.print("Acknowledged");
  else if (urgent) lcd.print("Help: waiting");
  else if (pending) lcd.print("Sent: waiting");
  else if (strcmp(state, "resolved") == 0) lcd.print("Marked resolved");
  else if (strcmp(state, "offline") == 0) lcd.print("Check connection");
  else lcd.print("Unmute ready");
#endif
}

void processLine() {
  serialLine[serialLength] = 0;
  if (strncmp(serialLine, "STATE|", 6) != 0) return;
  char* separator = strchr(serialLine + 6, '|');
  if (!separator) return;
  *separator = 0;
  lastReceived = millis();
  disconnected = false;
  displayMessage(serialLine + 6, separator + 1);
}

void setup() {
  Serial.begin(115200);
  for (byte i = 0; i < 3; i++) pinMode(BUTTONS[i], INPUT_PULLUP);
  pinMode(GREEN_PIN, OUTPUT);
  pinMode(AMBER_PIN, OUTPUT);
  pinMode(RED_PIN, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
#if USE_LCD
  lcd.begin(16, 2);
#endif
  displayMessage("idle", "Ready to listen");
  Serial.println("READY");
  lastReceived = millis();
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') {
      if (!overflowing) processLine();
      serialLength = 0;
      overflowing = false;
    } else if (c != '\r') {
      if (serialLength < sizeof(serialLine) - 1 && !overflowing) serialLine[serialLength++] = c;
      else overflowing = true;
    }
  }
  unsigned long t = millis();
  for (byte i = 0; i < 3; i++) {
    bool raw = digitalRead(BUTTONS[i]);
    if (raw != lastRaw[i]) { changed[i] = t; lastRaw[i] = raw; }
    if (t - changed[i] >= 35 && stable[i] != raw) {
      stable[i] = raw;
      if (raw == LOW) Serial.println(COMMANDS[i]);
    }
  }
  if (t - lastSpeedRead >= 500) {
    lastSpeedRead = t;
    int speed = map(analogRead(SPEED_PIN), 0, 1023, 800, 6000);
    if (abs(speed - previousSpeed) > 150) {
      previousSpeed = speed;
      Serial.print("SPEED|");
      Serial.println(speed);
    }
  }
  if (t - lastReceived > 15000 && !disconnected) {
    disconnected = true;
    displayMessage("offline", "App disconnected");
    digitalWrite(GREEN_PIN, LOW);
    digitalWrite(AMBER_PIN, HIGH);
    digitalWrite(RED_PIN, LOW);
  }
}
