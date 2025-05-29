#!/bin/bash
uv tool install --reinstall --no-managed-python --compile-bytecode .
sed -i 's/\(include-system-site-packages = \)false/\1true/' ~/.local/share/uv/tools/hardware-solvro-bot-office-cam/pyvenv.cfg
sudo cp ./motion_detect.service /etc/systemd/system/ &&
	sudo systemctl daemon-reload &&
	sudo systemctl restart motion_detect.service
