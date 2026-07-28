Device Bridge and systemd notes

- A sample systemd unit file is provided at scripts/testscan-device-bridge.service. Edit it to update:
  - User (the linux user that should run the bridge)
  - WorkingDirectory (path to your cloned repository)
  - ExecStart path to your Python virtualenv and the device_bridge.py script
  - token value (replace YOUR_DEVICE_TOKEN_HERE with the token output from the seed command)

- Install and run (example):
  sudo cp scripts/testscan-device-bridge.service /etc/systemd/system/
  sudo systemctl daemon-reload
  sudo systemctl enable testscan-device-bridge
  sudo systemctl start testscan-device-bridge
  sudo journalctl -u testscan-device-bridge -f

- For Windows, use NSSM (Non-Sucking Service Manager) or a similar tool to wrap the Python script as a service. See README_DEVICE_BRIDGE.md for details.
