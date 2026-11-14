# Physical controller

Start with the UNO controller. The Espressif photo only shows packaging; identify
the actual model before choosing an ESP32 board target or its pins.

## UNO R3 / Elegoo wiring

Disconnect USB while wiring. Use the breadboard ground rail for common ground.
The small four-leg switches have paired legs internally: use opposing switched
sides, rather than two already-connected legs.

| Part | Connection |
| --- | --- |
| Select button | D6 → switch → GND |
| Back button | D7 → switch → GND |
| Help button | D8 → switch → GND |
| Green LED | D9 → 220–330Ω resistor → LED anode; cathode → GND |
| Amber LED | D10 → 220–330Ω resistor → LED anode; cathode → GND |
| Red LED | D13 → 220–330Ω resistor → LED anode; cathode → GND |
| Passive buzzer | A1 → buzzer +; buzzer − → GND |
| Scan-speed potentiometer | Outer terminals → 5V and GND; center wiper → A0 |
| USB | UNO → laptop, data-capable cable |

Buttons use internal pull-ups; no external button resistors are needed. If the
knob isn't wired yet, remove the speed-reading block from the sketch so an
unconnected A0 cannot change scan speed.

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

The photographed kit lists one potentiometer. If it controls scan speed, try a
contrast divider: 10kΩ from 5V to VO, 1kΩ from VO to ground. Contrast varies by LCD;
if text is unreadable, dedicate the potentiometer to contrast instead (outer pins
5V/GND, wiper VO), and disable scan-speed readings in firmware. Adjust speed in the
app. A second potentiometer would let both be adjustable.

## Upload and connect

1. Open `bedside/bedside.ino` in Arduino IDE, choose Arduino Uno and the USB port.
2. Upload. Close Serial Monitor so the browser can own the serial port.
3. Run `python3 server.py` and open http://localhost:8080 in desktop Chrome/Edge.
4. Click **Connect bedside controller** and select the UNO.
5. Turn on **One-switch scanning**. Select chooses the highlighted option; another
   deliberate Select on **Confirm & speak** sends it. Back returns to choices.
   Help sends the literal request “Please help me” independently of recognition.
6. Amber means sent/waiting; red means a predefined help request is waiting;
   green means ready, acknowledged, or resolved (read the LCD/app for exact state).

Browser and firmware exchange newline-delimited ASCII at 115200 baud:

- Device → browser: `READY`, `SELECT`, `BACK`, `HELP`, `SPEED|2200`.
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
