# Start OneAquaHealth at boot on Ubuntu

The [systemd unit](../deploy/systemd/oneaquahealth.service) runs `run.py`, which
starts the ingestion gateway and evidence dashboard and reads the repository's
`.env`. It starts at boot without a desktop login, logs to the journal, and
restarts after a failure.

1. On the Ubuntu machine, install the dependencies into the project's virtual
   environment. From the repository root:

   ```bash
   sudo apt install python3-venv
   python3 -m venv .venv
   .venv/bin/python -m pip install -r requirements.txt
   .venv/bin/python -m pip install -e .
   ```

   Create or update `.env` with the settings for this machine. Create the virtual
   environment on Ubuntu rather than copying one from another machine.

2. Edit `deploy/systemd/oneaquahealth.service` so `User`, `WorkingDirectory`, and
   both paths in `ExecStart` match the Ubuntu username and checkout location.
   The supplied values use `werfree` and
   `/home/werfree/Projects/OneAquaHealth`. That user must be able to read the
   project and `.env` and execute its virtual-environment Python.

   The unit uses the same broker settings as `python run.py`. If MQTT/RabbitMQ
   consumers are enabled, arrange for those brokers to be available at boot.
   For HTTP-only operation, append `--no-brokers` to `ExecStart`. For the
   repository's Docker Compose RabbitMQ, append `--rabbitmq`, add
   `Requires=docker.service` and `After=docker.service` under `[Unit]`, and ensure
   the service user can run Docker. The launcher leaves that container running
   when the Python service stops.

3. Stop any manually launched copy using the same ports, then install and enable
   the unit from the repository root:

   ```bash
   sudo install -m 644 deploy/systemd/oneaquahealth.service /etc/systemd/system/oneaquahealth.service
   sudo systemd-analyze verify /etc/systemd/system/oneaquahealth.service
   sudo systemctl daemon-reload
   sudo systemctl enable --now oneaquahealth.service
   ```

Check status and follow logs:

```bash
sudo systemctl status oneaquahealth.service
sudo journalctl -u oneaquahealth.service -f
```

After changing `.env` or application code, run
`sudo systemctl restart oneaquahealth.service`. After changing the unit, repeat
the install command, run `sudo systemctl daemon-reload`, then restart it.
To stop it and disable startup, run
`sudo systemctl disable --now oneaquahealth.service`.

For access from other devices, set `DASHBOARD_HOST=0.0.0.0` in `.env` and use
`http://<Ubuntu-machine-IP>:8090` (or the configured dashboard port).
