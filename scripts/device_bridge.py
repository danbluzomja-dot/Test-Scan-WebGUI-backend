"""Device bridge for Arduino / serial scanners.

This script connects to a serial port (USB/COM) and forwards scanned events to the backend API.
It supports simple text protocols from devices. It uses badge-based login to obtain a session
cookie so subsequent start/complete actions are performed as that user.

Supported serial commands (each line should end with a newline):
- BADGE:<badge_id>           -- Performs badge login (POST /api/auth/login) and keeps session
- START:<barcode>            -- POST /api/product/<barcode>/start
- COMPLETE:<barcode>         -- POST /api/product/<barcode>/complete
- GET:<barcode>              -- GET /api/product/<barcode> and prints JSON
- TRAVELER:<barcode>         -- Downloads traveler PDF to local file

Example usage:
  python scripts/device_bridge.py --port /dev/ttyACM0 --baud 9600 --server http://localhost:5000

Notes:
- The bridge uses requests.Session() to preserve the cookie returned by the badge login endpoint.
- For production, consider adding device API keys, TLS verification, and stronger authentication.
"""

import argparse
import logging
import os
import sys
import time
from urllib.parse import urljoin

import requests
import serial

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')
logger = logging.getLogger('device-bridge')


def make_session(server, badge_id=None):
    s = requests.Session()
    s.headers.update({'User-Agent': 'TestScanDeviceBridge/1.0'})
    if badge_id:
        login_url = urljoin(server, '/api/auth/login')
        try:
            r = s.post(login_url, json={'badge_id': badge_id}, timeout=5)
            r.raise_for_status()
            logger.info('Logged in as badge %s', badge_id)
        except Exception as exc:
            logger.error('Badge login failed: %s', exc)
    return s


class DeviceBridge:
    def __init__(self, port, baud, server, badge_id=None, reconnect_delay=2.0):
        self.port = port
        self.baud = baud
        self.server = server.rstrip('/')
        self.reconnect_delay = reconnect_delay
        self.session = make_session(self.server, badge_id=badge_id)
        self.serial = None

    def start(self):
        while True:
            try:
                logger.info('Opening serial port %s @ %d', self.port, self.baud)
                with serial.Serial(self.port, self.baud, timeout=1) as ser:
                    self.serial = ser
                    logger.info('Serial port opened')
                    self._read_loop(ser)
            except serial.SerialException as exc:
                logger.error('Serial error: %s', exc)
                logger.info('Reconnecting in %.1f seconds...', self.reconnect_delay)
                time.sleep(self.reconnect_delay)
            except KeyboardInterrupt:
                logger.info('Interrupted, exiting')
                return
            except Exception as exc:
                logger.exception('Unexpected error: %s', exc)
                time.sleep(self.reconnect_delay)

    def _read_loop(self, ser):
        buffer = b''
        while True:
            try:
                data = ser.readline()
                if not data:
                    continue
                line = data.decode(errors='ignore').strip()
                if not line:
                    continue
                logger.info('Received from device: %s', line)
                try:
                    self.handle_line(line)
                except Exception as exc:
                    logger.exception('Error handling line: %s', exc)
            except serial.SerialException as exc:
                logger.error('Serial disconnected: %s', exc)
                raise

    def handle_line(self, line):
        # Expected formats: PREFIX:PAYLOAD
        if ':' not in line:
            logger.warning('Unrecognized line format (no colon): %s', line)
            return
        prefix, payload = line.split(':', 1)
        prefix = prefix.strip().upper()
        payload = payload.strip()

        if prefix == 'BADGE':
            # perform badge login and renew session
            self.session = make_session(self.server, badge_id=payload)
            return

        if prefix == 'START':
            self._post_action(payload, 'start')
            return

        if prefix == 'COMPLETE':
            self._post_action(payload, 'complete')
            return

        if prefix == 'GET':
            self._get_product(payload)
            return

        if prefix == 'TRAVELER':
            self._download_traveler(payload)
            return

        logger.warning('Unknown prefix: %s', prefix)

    def _post_action(self, barcode, action):
        url = urljoin(self.server, f'/api/product/{barcode}/{action}')
        try:
            r = self.session.post(url, timeout=6)
            try:
                body = r.json()
            except ValueError:
                body = r.text
            if r.status_code >= 400:
                logger.error('Server returned %d: %s', r.status_code, body)
            else:
                logger.info('Action %s for %s succeeded: %s', action, barcode, body)
        except requests.RequestException as exc:
            logger.error('Request failed: %s', exc)

    def _get_product(self, barcode):
        url = urljoin(self.server, f'/api/product/{barcode}')
        try:
            r = self.session.get(url, timeout=6)
            r.raise_for_status()
            logger.info('Product %s: %s', barcode, r.json())
        except requests.RequestException as exc:
            logger.error('Request failed: %s', exc)

    def _download_traveler(self, barcode):
        url = urljoin(self.server, f'/api/product/{barcode}/traveler.pdf')
        try:
            r = self.session.get(url, timeout=10)
            if r.status_code == 200 and r.headers.get('content-type') == 'application/pdf':
                filename = f'traveler_{barcode}.pdf'
                with open(filename, 'wb') as f:
                    f.write(r.content)
                logger.info('Saved traveler PDF to %s', filename)
            else:
                logger.error('Failed to download traveler: %s %s', r.status_code, r.text)
        except requests.RequestException as exc:
            logger.error('Request failed: %s', exc)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Serial-to-API device bridge')
    parser.add_argument('--port', '-p', required=True, help='Serial port (e.g., /dev/ttyUSB0 or COM3)')
    parser.add_argument('--baud', '-b', type=int, default=9600, help='Baud rate (default 9600)')
    parser.add_argument('--server', '-s', default=os.environ.get('DEVICE_SERVER', 'http://localhost:5000'),
                        help='Server base URL (default: http://localhost:5000)')
    parser.add_argument('--badge', help='Optional badge id to log in as on startup (e.g., ADMIN123)')
    args = parser.parse_args(argv or sys.argv[1:])

    bridge = DeviceBridge(port=args.port, baud=args.baud, server=args.server, badge_id=args.badge)
    bridge.start()


if __name__ == '__main__':
    main()
