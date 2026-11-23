# PoC: ein cthorny-Sensor als AWS-Spot-Instanz (Uni-S3)

Diese Anleitung startet **eine** Spot-Instanz von Hand über die AWS-Konsole, ohne Terraform. Die Daten landen in einem S3-kompatiblen Speicher der Universität. Hintergrund zu Bootstrap, Upload und Teardown steht in der [README](README.md).

## 0. Voraussetzungen: Tag und Release

Die Instanz lädt beim Boot alles aus **einem Git-Tag** (`THORNY_VERSION`, siehe [Versionierung](README.md#versionierung)):

- `startup.sh` und die übrigen Skripte aus dem Tag (`raw.githubusercontent.com/…/<tag>/thorny/deploy`)
- `thorny-linux-amd64` und `aws-config.yaml` aus dem Release zu diesem Tag

1. **Stand committen und pushen** (inklusive `.github/workflows/thorny-release.yml`).
2. **Taggen und den Tag pushen:**
   ```bash
   git tag thorny-v0.1.0
   git push origin thorny-v0.1.0
   ```
   Das startet die GitHub Action *thorny release* (Tab *Actions* im Repo). Nach 1–2 Minuten gibt es unter *Releases* das Release `thorny-v0.1.0` mit den drei Dateien.
3. **Prüfen** (beide Befehle müssen `200` ausgeben):
   ```bash
   curl -sL -o /dev/null -w "%{http_code}\n" https://raw.githubusercontent.com/eliasheithecker/cthorny/thorny-v0.1.0/thorny/deploy/startup.sh
   curl -sL -o /dev/null -w "%{http_code}\n" https://github.com/eliasheithecker/cthorny/releases/download/thorny-v0.1.0/thorny-linux-amd64
   ```

## 1. Werte festlegen

| Wert | Einsetzen | Hinweis |
|---|---|---|
| Version | `thorny-v0.1.0` | Git-Tag aus Schritt 0 |
| Bucket | `<bucket>`, z. B. `cthorny-data` | im Uni-S3 anlegen |
| S3-Endpoint | `<https://s3.uni-…>` | vollständige URL mit `https://` |
| Access Key | `<ACCESS_KEY>` | eigene Keys nur für diesen Zweck, nur für diesen Bucket |
| Secret Key | `<SECRET_KEY>` | |
| Webhook-Passwort | Ausgabe von `openssl rand -hex 24` | hex, also kein `/` und kein `&` (startup.sh setzt es per `sed` ein) |
| AWS-Region | `eu-central-1` (Frankfurt) | |
| Availability Zone | `eu-central-1a` | muss zum Subnet in Schritt 4 passen |
| S3-Region | `us-east-1` (Standard, nicht setzen) | nur ändern, wenn die Uni eine Region vorgibt |

## 2. Uni-S3 von außen testen

Am besten außerhalb von Uni-Netz und VPN, z. B. über einen Handy-Hotspot. Die EC2-Instanz greift auch von außen zu.

```bash
export AWS_ACCESS_KEY_ID='<ACCESS_KEY>' AWS_SECRET_ACCESS_KEY='<SECRET_KEY>'
aws --endpoint-url '<https://s3.uni-…>' --region us-east-1 s3 cp README.md s3://<bucket>/test.txt
aws --endpoint-url '<https://s3.uni-…>' --region us-east-1 s3 ls s3://<bucket>/
aws --endpoint-url '<https://s3.uni-…>' --region us-east-1 s3 rm s3://<bucket>/test.txt
```

| Fehler | Ursache | Lösung |
|---|---|---|
| Timeout, keine Verbindung | Endpoint nur intern erreichbar | mit dem Uni-Rechenzentrum klären, ob es eine externe Adresse gibt |
| `MissingContentLength`, `InvalidArgument`, `XAmzContentSHA256Mismatch` | AWS CLI ≥ 2.23 sendet standardmäßig CRC-Checksummen, die viele Nicht-AWS-S3s nicht kennen | in `startup.sh` für Nicht-AWS-Endpoints `request_checksum_calculation = when_required` und `response_checksum_validation = when_required` in die Config schreiben |
| `AuthorizationHeaderMalformed`, Signaturfehler | falsche Region | richtige Region bei der Uni erfragen und als `S3_REGION` setzen (Schritt 4) |

## 3. Security Group anlegen

EC2 → *Security Groups* → *Create security group*:

- **Name:** `cthorny-sensor`
- **VPC:** Default-VPC
- **Inbound rules:**

  | Type | Source | Wozu |
  |---|---|---|
  | All traffic | `0.0.0.0/0` | Teleskop: gotrace sieht alles, thorny antwortet auf 22/23/25/389 |

- **Outbound:** Standard (alles erlaubt)

Lässt die Security Group einen Port nicht durch, erreicht der Traffic die Instanz nie und fehlt auch im pcap. Mit „All traffic“ ist auch das echte sshd auf Port 28763 offen. Das ist in Ordnung, weil dort nur Key-Login möglich ist.

Der Webhook (Port 51337) lauscht nur auf IPv6, und die Default-VPC hat kein IPv6. Für den PoC wird er nicht gebraucht, spot-watch und teardown funktionieren ohne ihn.

## 4. Instanz starten

Oben rechts die Region **Europe (Frankfurt) eu-central-1** wählen. Dann EC2 → *Launch instance*:

| Feld | Wert |
|---|---|
| Name | `cthorny-poc-1` |
| AMI | **Ubuntu Server 22.04 LTS**, Architecture **64-bit (x86)** (gotrace gibt es nur für amd64) |
| Instance type | `t3.small` |
| Key pair | eigenes (oder neu anlegen, `.pem` speichern) |
| Network settings → *Edit* | VPC: Default, **Subnet: das in `eu-central-1a`**, Auto-assign public IP: **Enable**, Security group: **`cthorny-sensor`** |
| Storage | 16 GiB gp3 |
| Advanced details → Purchasing option | ☑ **Spot instances** → *Customize*: Maximum price *No maximum price*, Request type **One-time**, Interruption behavior **Terminate** |
| Advanced details → IAM instance profile | keins (Zugang zum Uni-S3 läuft über die Keys) |
| Advanced details → Metadata accessible | Enabled (Version „V2 only“ ist ok, `lib.sh` holt ein Token) |
| Advanced details → User data | siehe unten |

### User Data

Das ist [`userData.sh.tpl`](userData.sh.tpl) mit eingesetzten Werten. Die Werte stehen in einfachen Anführungszeichen, damit bash ein `$` im Secret nicht auflöst.

```
Content-Type: multipart/mixed; boundary="//"
MIME-Version: 1.0

--//
Content-Type: text/cloud-config; charset="us-ascii"
MIME-Version: 1.0
Content-Transfer-Encoding: 7bit
Content-Disposition: attachment; filename="cloud-config.txt"

#cloud-config
cloud_final_modules:
- [scripts-user, always]

--//
Content-Type: text/x-shellscript; charset="us-ascii"
MIME-Version: 1.0
Content-Transfer-Encoding: 7bit
Content-Disposition: attachment; filename="001.txt"

#!/bin/bash
VERSION='thorny-v0.1.0'
curl -fsSL "https://raw.githubusercontent.com/eliasheithecker/cthorny/$VERSION/thorny/deploy/startup.sh" \
  | THORNY_VERSION="$VERSION" bash -s -- '<bucket>' '<https://s3.uni-…>' '<ACCESS_KEY>' '<SECRET_KEY>' '<WEBHOOK_PW>' 'aws' 'eu-central-1a'

--//--
```

Gibt die Uni eine S3-Region vor: `| THORNY_VERSION="$VERSION" S3_REGION='<region>' bash -s -- …`

`startup.sh` schreibt daraus `/root/config/aws/config` (Endpoint, Path-Style, Region) und `/root/config/aws/credentials` (Keys, `chmod 600`).

Dann *Launch instance*.

## 5. Prüfen, ob der Sensor läuft

Etwa 3 Minuten nach dem Start (die öffentliche IP steht in der Konsole):

```bash
ssh -i <key.pem> -p 28763 ubuntu@<public-ip>

sudo tail -n 50 /var/log/cloud-init-output.log        # Ausgabe von startup.sh, auf Fehler achten
systemctl status thorny gotrace spot-watch --no-pager
sudo cat /root/config/aws/config                      # endpoint_url + path style
ls -l /var/spool/gotrace /var/spool/thorny
```

Vom eigenen Rechner aus:
```bash
ssh root@<public-ip>        # Port 22 muss bei thorny landen (beliebiges Passwort)
```

Im Bucket sollte Folgendes erscheinen:
- **sofort:** `provider=aws/region=eu-central-1a/ip=<a-b-c-d>/<start>/descriptor.txt`, dazu `ssh/` und `tls/`
- **nach dem ersten vollen 10-Minuten-Fenster plus 1 Minute:** `…/year=…/hour=…/packets-*.pcap.gz`, `thorny-*.jsonl.gz` und `descriptor-link.txt`

Upload verfolgen: `sudo tail -f /var/log/cthorny-upload.log`

## 6. Teardown testen

**a) Von Hand:**
```bash
sudo /var/scripts/teardown.sh
sudo cat /root/config/termination.txt
```
Danach liegt `<start>/termination.txt` im Bucket. Die Dienste sind dann gestoppt. Mit `sudo reboot` beginnt ein neuer Lifecycle.

**b) Echte Spot-Unterbrechung mit AWS FIS:**
1. *AWS FIS* → *Experiment templates* → *Create experiment template*
2. Action: `aws:ec2:send-spot-instance-interruptions`, `durationBeforeInterruption` = `PT2M`
3. Target: Resource type `aws:ec2:spot-instance`, *Resource IDs* = die Instanz
4. Service access: *Create a new role*
5. Speichern → *Start experiment*

Etwa 30 Sekunden nach der Warnung sollte `termination.txt` im Bucket liegen, danach terminiert AWS die Instanz.

## 7. Aufräumen, Kosten, Secrets

- **Instanz terminieren**, wenn der Test vorbei ist. Ein Spot-`t3.small` kostet nur wenige Cent pro Stunde.
- **Traffic:** Ausgehender Traffic zum Uni-S3 kostet etwa 0,09 $ pro GB. Nach den ersten Stunden prüfen, wie viel pro Fenster hochgeladen wird.
- **Secrets:** Die Keys stehen im Klartext in den User Data. Sichtbar sind sie in der Konsole (*Edit user data*), über IMDS (`/latest/user-data`) und für root auf der Instanz (`/root/config/storage*.txt`, `/root/config/aws/credentials`, `/var/lib/cloud/instance/user-data.txt`). Deshalb eigene, auf den Bucket beschränkte Keys verwenden (möglichst ohne Delete-Recht) und sie nach der Testphase rotieren. Für den Terraform-Betrieb ist der SSM Parameter Store (SecureString, Abruf in `startup.sh`) der bessere Weg.
