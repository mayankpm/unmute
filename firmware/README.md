# Physical controller

Start with the UNO controller. The Espressif photo only shows packaging; identify
the actual model before choosing an ESP32 board target or its pins.

## UNO R3 / Elegoo wiring

Disconnect USB while wiring. Use the breadboard ground rail for common ground.
The small four-leg switches have paired legs internally: use opposing switched
sides, rather than two already-connected legs.

| Part | Connection |
| --- | --- |
| Confirm button | D7 → switch → GND (tap = Select, hold 1.5 s = Help) |
| Next button | D8 → switch → GND (tap = Next, hold 1.5 s = Back) |
| RGB LED (common cathode) | Longest leg → GND; red → D9, green → D10, blue → D6, each through 220Ω |
| Passive buzzer | A1 → buzzer +; buzzer − → GND |
| Photoresistor (bed light) | 5V → photoresistor → A0 → 10kΩ → GND |
| USB | UNO → laptop, data-capable cable |

Buttons use internal pull-ups; no external button resistors are needed. The LED
shows green (ready/acknowledged/resolved), amber (sent, waiting, or app offline)
and red (help waiting). If red and green come out swapped, swap the D9/D10 wires.
For an urgent request the buzzer beeps every second until any button is pressed.

## Optional LCD1602 (parallel pins, not an I²C module)

Set `USE_LCD` to 0 to skip the LCD. Otherwise:

| LCD pin | Connection |
| --- | --- |
| 1 VSS | GND |
| 2 VDD | 5V |
| 3 VO | Contrast voltage; see below |
| 4 RS | D12 |
| 5 RW | GND |
| 6 E | D11 |
| 7–10 D0–D3 | Unconnected |
| 11 D4 | D5 |
| 12 D5 | D4 |
| 13 D6 | D3 |
| 14 D7 | D2 |
| 15 backlight A | 5V through a 220Ω resistor |
| 16 backlight K | GND |

The potentiometer sets LCD contrast: outer pins to 5V and GND, wiper to VO. Turn it
until the text is dark and readable straight on. If it can't go dark enough, wire VO
straight to GND. Scan speed is adjusted in the app.

## Upload and connect

1. Open `bedside/bedside.ino` in Arduino IDE, choose Arduino Uno and the USB port.
2. Upload. Close Serial Monitor so the browser can own the serial port.
3. Run `python3 server.py` and open http://localhost:8080 in desktop Chrome/Edge.
4. Click **Connect bedside controller** and select the UNO.
5. Next moves the highlight to the next option (it turns on scanning if needed).
   Confirm chooses the highlighted option; another Confirm on **Confirm & speak**
   sends it. Holding Next goes back to the choices. Holding Confirm sends the
   literal request “Please help me”, whatever was recognised.
6. Amber means sent/waiting; red means a predefined help request is waiting;
   green means ready, acknowledged, or resolved (read the LCD/app for exact state).
7. If the photoresistor reads below `DARK_THRESHOLD` (in `web/app.js`, default 250),
   the app warns “Turn on the bed light”. Tune it halfway between the normal-light
   and covered readings.

Browser and firmware exchange newline-delimited ASCII at 115200 baud:

- Device → browser: `READY`, `SELECT`, `NEXT`, `BACK`, `HELP`, `LIGHT|0-1023`
  (once a second, higher = brighter). `SPEED|2200` is still accepted by the app
  but this wiring has no speed knob.
- Browser → device: `STATE|pending|I need water` (also `urgent`, `acknowledged`,
  `resolved`, `idle`). The browser repeats current state as a heartbeat.
- A missing heartbeat for 15 seconds displays a disconnected state. Demo events
  never drive the physical alarm.

The LCD shows at most the first 16 ASCII characters plus a status line. The full
message remains in the browser. Nothing here connects to hospital equipment.

## Optional ESP32 pager

This is an optional, separate sketch and requires **an actual ESP32**, ESP32
Arduino core, and ArduinoJson 7. Select a valid LED/buzzer GPIO pair for that board;
the placeholder GPIOs 2/25 do not exist on every Espressif variant.

Copy `pager/secrets.example.h` to `pager/secrets.h`, fill in local hotspot settings,
the laptop's LAN IP, and a long shared token. Put the same token in the server's
`.env` as `UNMUTE_TOKEN`, then run `python3 server.py --host 0.0.0.0`. Permit your
OS firewall's local-network access if needed. In the browser's Preferences, enter
the token once per tab. Use a trusted private hotspot: this optional prototype
connection is HTTP, not encrypted. Webcam and Web Serial still run from
`http://localhost:8080` on the laptop; camera permission isn't available from plain
HTTP on another device.

The pager polls `/api/pager` every 2 seconds, only chirps for a new pending real
help request, and clears when all such requests have been acknowledged. It does
not acknowledge requests itself. This is a demo accessory, not a medical alarm.
