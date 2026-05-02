# PlexIntel Sora Cleanup Timer

Use a systemd timer to remove temporary Sora MP4 files instead of running an in-process scheduler.

Store generated MP4s on the Raspberry Pi where PlexIntel runs. OpenWebUI on the NAS should stream
the returned URL over HTTP instead of reading these files from disk.

Use this PlexIntel `.env` value:

```env
SORA_STORAGE_ROOT=/home/jmnovak/.sora
SORA_RETENTION_HOURS=24
```

`/etc/systemd/system/plexintel-sora-cleanup.service`

```ini
[Unit]
Description=Clean up old PlexIntel Sora video files

[Service]
Type=oneshot
User=jmnovak
WorkingDirectory=/home/jmnovak/projects/plexintel
EnvironmentFile=/home/jmnovak/projects/plexintel/.env
ExecStart=/home/jmnovak/projects/plexintel/plexenv/bin/python -m api.scripts.cleanup_sora_files
```

`/etc/systemd/system/plexintel-sora-cleanup.timer`

```ini
[Unit]
Description=Run PlexIntel Sora cleanup hourly

[Timer]
OnBootSec=10min
OnUnitActiveSec=1h
Persistent=true

[Install]
WantedBy=timers.target
```

Enable it with:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now plexintel-sora-cleanup.timer
```
