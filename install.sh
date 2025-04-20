CWD=$(pwd)

check_if_running_as_root() {
  if [[ "$(id -u)" -eq 0 ]]; then
    return 0
  else
    echo "error: You must run this script as root to enable autostart!"
    return 1
  fi
}

init_daemon() {
  cat > /etc/systemd/system/climbing-competitions-bot.service << EOF
[Unit]
Description=Bot for climbing competitions
Documentation=https://github.com/xtls
After=network.target

[Service]
User=$INSTALL_USER
ExecStart="$CWD"/.venv/bin/python "$CWD"/main.py
Restart=on-failure
RestartPreventExitStatus=23
LimitNPROC=10000
LimitNOFILE=1000000

[Install]
WantedBy=multi-user.target
EOF
  systemctl enable climbing-competitions-bot.service
  systemctl start climbing-competitions-bot.service
  if systemctl -q is-active climbing-competitions-bot; then
    echo "info: Enable and start Bot for climbing competitions"
  else
    echo "warning: Failed to enable and start Bot for climbing competitions"
  fi
}

main() {
  python3 -m venv .venv
  echo "info: setup Python virtual environment"
  source "$CWD"/.venv/bin/activate
  echo "info: activated virtual environment"
  pip install -r requirements.txt
  echo "info: installed requirements"
  check_if_running_as_root || return 1
  init_daemon
}

main