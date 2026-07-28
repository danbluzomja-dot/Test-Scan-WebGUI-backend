# Device Bridge README

This document explains how to use the serial device bridge (scripts/device_bridge.py) to forward
scanner/Arduino events to the backend API.

Overview
--------
The device bridge listens on a serial port and expects simple newline-terminated commands from an
attached device (Arduino, USB scanner that outputs serial, etc.). It translates those commands into
HTTP requests against the backend API.

Typical workflow
----------------
1. Connect your Arduino or USB serial scanner to the machine running the bridge.
2. Ensure the backend server is accessible (e.g., http://localhost:5000).
3. Start the bridge:

   python scripts/device_bridge.py --port /dev/ttyACM0 --baud 9600 --server http://localhost:5000 --badge ADMIN123

   The --badge option is optional. If provided the bridge will attempt to login using the badge
   so subsequent START/COMPLETE commands are executed as that user (using session cookie).

Serial command format
---------------------
Send newline-terminated strings in one of these formats:

- BADGE:<badge_id>          -> login as this badge
- START:<product_barcode>   -> start current step for the product
- COMPLETE:<product_barcode>-> complete current step and advance
- GET:<product_barcode>     -> fetch product JSON and print to console
- TRAVELER:<product_barcode>-> download traveler PDF to traveler_<barcode>.pdf

Arduino example
---------------
On the Arduino (Serial over USB) simply write the command followed by a newline. Example (pseudo):

  Serial.println("BADGE:ADMIN123");
  delay(100);
  Serial.println("START:PROD0001");
  delay(1000);
  Serial.println("COMPLETE:PROD0001");

Security note
-------------
This bridge uses badge-based login (session cookie) to authenticate. For production consider:
- Using HTTPS for the server
- Using device-specific API keys or tokens and server support for token auth
- Restricting network access between devices and the server

Troubleshooting
---------------
- If the bridge fails to open the serial port, ensure you have permission to access the device and
  the correct port name.
- Use a serial terminal (screen/minicom/putty) to test the device sending simple lines before using the bridge.
