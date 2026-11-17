/* Unmute bedside controller — Arduino UNO R3 / Elegoo starter kit.
 * USB serial: 115200 baud. See firmware/README.md before wiring.
 * Uses only Arduino's bundled LiquidCrystal library. Set USE_LCD=0 for buttons/LEDs only.
 *
 * Wiring: LCD1602 RS,E,D4-D7 = 12,11,5,4,3,2 (potentiometer = LCD contrast)
 *         common-cathode RGB LED red/green/blue = 9/10/6 (each through 220 ohm)
 *         Confirm button = 7, Next button = 8 (other leg to GND)
 *         passive buzzer = A1, photoresistor divider = A0
 *
 * Buttons: Confirm tap = SELECT, Confirm hold = HELP,
 *          Next tap    = NEXT,   Next hold    = BACK.
 * Any button press silences the bedside alarm.
 */
#include <LiquidCrystal.h>
#define USE_LCD 1

LiquidCrystal lcd(12, 11, 5, 4, 3, 2);
const byte RED_PIN = 9, GREEN_PIN = 10, BLUE_PIN = 6;
const byte CONFIRM_PIN = 7, NEXT_PIN = 8;
const byte BUZZER_PIN = A1, LIGHT_PIN = A0;
const unsigned long HOLD_MS = 1500;

const byte BUTTONS[] = {CONFIRM_PIN, NEXT_PIN};
const char* TAP[] = {"SELECT", "NEXT"};
const char* HOLD[] = {"HELP", "BACK"};
bool lastRaw[2] = {HIGH, HIGH}, stable[2] = {HIGH, HIGH}, held[2] = {false, false};
unsigned long changed[2] = {0, 0}, pressedAt[2] = {0, 0};

unsigned long lastReceived = 0, lastLightReport = 0, lastBeep = 0;
char serialLine[100];
byte serialLength = 0;
bool overflowing = false, disconnected = false, alarmOn = false;
char currentState[20] = "idle";
char currentText[61] = "Ready to listen";

void setColor(byte r, byte g, byte b) {
  analogWrite(RED_PIN, r);
  analogWrite(GREEN_PIN, g);
  analogWrite(BLUE_PIN, b);
}

void displayMessage(const char* state, const char* text) {
  bool isNew = strcmp(state, currentState) != 0 || strcmp(text, currentText) != 0;
  strncpy(currentState, state, sizeof(currentState) - 1);
  currentState[sizeof(currentState) - 1] = 0;
  strncpy(currentText, text, sizeof(currentText) - 1);
  currentText[sizeof(currentText) - 1] = 0;
  bool urgent = strcmp(state, "urgent") == 0;
  bool pending = strcmp(state, "pending") == 0;
  bool offline = strcmp(state, "offline") == 0;
  if (urgent) setColor(255, 0, 0);                 // red
  else if (pending || offline) setColor(255, 80, 0); // amber
  else setColor(0, 180, 0);                        // green
  if (isNew) {
    alarmOn = urgent;  // repeat-beep until a button is pressed or the state changes
    lastBeep = 0;
    if (strcmp(state, "acknowledged") == 0) tone(BUZZER_PIN, 900, 100);
  }
#if USE_LCD
  lcd.clear();
  lcd.setCursor(0, 0);
  for (byte i = 0; i < 16 && text[i]; i++) lcd.print(text[i]);
  lcd.setCursor(0, 1);
  if (strcmp(state, "acknowledged") == 0) lcd.print("Acknowledged");
  else if (urgent) lcd.print("Help: waiting");
  else if (pending) lcd.print("Sent: waiting");
  else if (strcmp(state, "resolved") == 0) lcd.print("Marked resolved");
  else if (offline) lcd.print("Check connection");
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

void readButtons(unsigned long t) {
  for (byte i = 0; i < 2; i++) {
    bool raw = digitalRead(BUTTONS[i]);
    if (raw != lastRaw[i]) { changed[i] = t; lastRaw[i] = raw; }
    if (t - changed[i] >= 35 && stable[i] != raw) {
      stable[i] = raw;
      if (raw == LOW) {            // pressed
        pressedAt[i] = t;
        held[i] = false;
        alarmOn = false;
        noTone(BUZZER_PIN);
      } else if (!held[i]) {       // released before the hold time: a tap
        Serial.println(TAP[i]);
      }
    }
    if (stable[i] == LOW && !held[i] && t - pressedAt[i] >= HOLD_MS) {
      held[i] = true;
      Serial.println(HOLD[i]);
    }
  }
}

void setup() {
  Serial.begin(115200);
  for (byte i = 0; i < 2; i++) pinMode(BUTTONS[i], INPUT_PULLUP);
  pinMode(RED_PIN, OUTPUT);
  pinMode(GREEN_PIN, OUTPUT);
  pinMode(BLUE_PIN, OUTPUT);
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
  readButtons(t);
  if (alarmOn && (lastBeep == 0 || t - lastBeep >= 1000)) {
    lastBeep = t;
    tone(BUZZER_PIN, 1500, 300);
  }
  if (t - lastLightReport >= 1000) {
    lastLightReport = t;
    Serial.print("LIGHT|");
    Serial.println(analogRead(LIGHT_PIN));  // 0-1023, higher = brighter
  }
  if (t - lastReceived > 15000 && !disconnected) {
    disconnected = true;
    displayMessage("offline", "App disconnected");
  }
}
