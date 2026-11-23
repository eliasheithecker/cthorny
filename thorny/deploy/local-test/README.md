# Lokaler Test

Ein Sensor in Docker: Ubuntu 22.04 mit systemd, cron und sshd wie auf AWS, dazu [S3Mock](https://github.com/adobe/S3Mock) als S3 und ein Fake-Metadaten-Dienst (liefert [`imds/`](imds/) aus). `startup.sh` läuft unverändert wie in Produktion. Einzige Unterschiede: Skripte und thorny kommen aus deinem Arbeitsstand (`file://` statt GitHub), und die Datenfenster sind 2 statt 10 Minuten lang.

Alle Befehle in `thorny/deploy/local-test`.

## Starten

```bash
make -C ../.. release             # thorny bauen, nach jeder Änderung an thorny wiederholen
docker compose up -d --build
docker compose exec sensor tail -f /var/log/startup.log   # bis "We are operational"
```

Nach dem Start des Containers führt Compose `startup.sh` aus (`post_start` in der Compose-Datei), wie auf AWS cloud-init beim Boot. Das dauert beim ersten Mal ein paar Minuten.

## Ansehen

Bucket vom Mac aus, mit deiner AWS CLI (Dummy-Keys, damit deine echten nicht verwendet werden):

```bash
s3m() { AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test AWS_REGION=us-east-1 aws --endpoint-url http://localhost:9090 s3 "$@"; }
s3m ls --recursive s3://cthorny-test/
```

Im Sensor (`docker compose exec sensor bash`):

```bash
systemctl status thorny gotrace spot-watch
journalctl -u thorny -f
ls -la /var/spool/gotrace /var/spool/thorny    # Dateien des laufenden Fensters
cat /var/log/cthorny-upload.log                # Ausgabe der cron-Uploads
```

## Testen

- **Traffic:** `ssh -p 2222 root@localhost` oder `nc localhost 2525` (SMTP), `2323` (Telnet), `3389` (LDAP).
- **Upload:** passiert automatisch per cron, eine Minute nach jedem Fensterende (ungerade Minuten). Danach liegen pcap und thorny-Log unter `provider=aws/region=eu-central-1a/ip=203-0-113-10/year=…/hour=…/` im Bucket.
- **Spot-Unterbrechung:** Datei anlegen, dann macht spot-watch innerhalb von ca. 30 s den teardown und lädt `termination.txt` hoch:
  ```bash
  mkdir -p imds/latest/meta-data/spot && echo '{"action":"terminate"}' > imds/latest/meta-data/spot/instance-action
  ```
- **Neuer Lifecycle:** `rm -rf imds/latest/meta-data/spot`, dann `docker compose down sensor && docker compose up -d`. Das ist eine neue Instanz mit derselben IP, `startup.sh` läuft wieder automatisch. Nur den Sensor herunterfahren: Ein komplettes `docker compose down` entfernt auch S3Mock und damit den Bucket-Inhalt.

- **Webhook** (im Sensor, nur IPv6, Port 51337, Token `testpw`):
  ```bash
  curl -k "https://[::1]:51337/hooks/ping"
  curl -k "https://[::1]:51337/hooks/status"
  curl -k "https://[::1]:51337/hooks/teardown?token=falsch"   # abgelehnt
  curl -k "https://[::1]:51337/hooks/teardown?token=testpw"   # teardown wie bei der Spot-Warnung
  curl -k "https://[::1]:51337/hooks/restart?token=testpw"    # reboot: Container stoppt, mit docker compose up -d wieder starten
  ```

## Aufräumen

```bash
docker compose down -v
```

Nicht getestet werden cloud-init/`userData.sh.tpl`, der Webhook `redeploy` (braucht cloud-init) und das echte AWS.
