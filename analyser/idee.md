### Ziel
Die Analyse aus den Notebooks wird in eine Anwendung bzw. ein Skript migriert, die durchgehend läuft und die [Verarbeitungsschritte](#verarbeitungsschritte) jede Nacht abarbeitet.

### Input-Dateien
1. PCAPs aus dem S3 (von den Sensoren alle 10 Minuten abgelegt)
2. Handler-Logs aus dem S3 (von den Sensoren alle 10 Minuten abgelegt)
3. Sensor-Anmeldungen aus dem S3: Jeder Sensor legt beim Start eine Datei mit seiner IP und seiner Startzeit ab. Daraus werden die Sensor-IPs ermittelt.
4. Redaktionell erarbeitete Liste der Scanner aus einer manuell gepflegten Quelle (z. B. Konfiguration, GitHub oder S3):
   - Name und Typ der Scanner
   - PTR-Suffixe für die Zuordnung per rDNS
   - IP-Bereiche für `ip_range` und `validated` (bisher `scanner_ranges.csv`)
   - Abbildung der ISC-Namen auf die `actor_id`, z. B. `internetmeasurement` auf `driftnet`
5. ISC-Liste der Research-Scanner (täglicher Abruf): zweite Quelle für die Zuordnung
6. PTR- und A-Records (eigene ZDNS-Abfragen): Zuordnung per Suffix, `ptr`, `fcrdns` und Regeln 3 und 5
7. Webseiten-Prüfung (eigene HTTP-Abfragen): `web` und Regel 5
8. Tagesdateien (eigene Ergebnisse): Eingabe für die aggregierte Datei

### Sensor-Anmeldung
````
SensorRegistration:          # eine Datei pro Sensorstart im S3
    sensor_ip:   string      # öffentliche IP des Sensors
    started_at:  datetime    # Startzeit des Sensors in UTC
````

### OutputDatenstruktur
````
Protocol:  "ssh" | "telnet" | "smtp" | "ldap"    # untersuchte Protokolle (Ports 22, 23, 25, 389)
Transport_Level:   NO_CONNECTION (0) | SYN (1) | Handshake (2) | TLS_TESTED (3) | TLS_USED (4) 
Application_Level: NOT_USED (0) |  1 | 2 | 2.5 | 3 | 4 |    # 2.5 gibt es nur bei SMTP (VRFY/EXPN)
# Bedeutung der einzelnen Stufen je Protokoll: siehe Abschnitt "Levels"

SensorCount:                 # Verkehr, der an einem einzelnen Sensor ankam
    sensor_ip:    string     # öffentliche IP des Sensors (Spot-Instanz, kann täglich wechseln)
    connections:  int        # Handler-Log-Einträge, also volle Verbindungen
    half_open:    int        # SYN-Events ohne ACK

ProtocolResult:                     # Interaktionstiefe eines Scanners auf einem Protokoll
    max_transport_level:    Transport_Level     # höchstes erreichtes Transport-Level
    max_application_level:  Application_Level   # höchstes erreichtes Application-Level; kann aus einem anderen Event stammen als das Transport-Maximum
    score:                  float   # Interaktions-Score von 0 bis 1 aus beiden Maxima, Formel siehe Abschnitt "Levels"

Traffic:                                     # Verkehrs-Kennzahlen eines Scanners über alle seine IPs (Indikatoren für Regel 2)
    syn_packets:                      int        # Anzahl empfangener SYN-Pakete
    handshakes:                       int        # Anzahl vollständiger TCP-Handshakes
    half_open:                        int        # SYN-Events ohne ACK innerhalb von 90 Sekunden
    retransmissions:                  int        # wiederholte SYNs derselben Verbindung, zählen nicht als neue Probe
    sensors_hit:                      list<ip>   # Sensoren, die der Scanner kontaktiert hat
    max_probes_per_sensor_port_hour:  int        # höchste Probe-Zahl auf ein Paar aus Sensor und Port innerhalb einer Stunde
    max_probes_per_sensor_port_day:   int        # höchste Probe-Zahl auf ein Paar aus Sensor und Port innerhalb eines UTC-Tages

WebCheck:                                # Ergebnis der Erreichbarkeitsprüfung einer Webseite; HTML wird nicht gespeichert
    url:          string                 # geprüfte URL
    target:       "ip" | "ptr_domain"    # geprüft wurde die Scanner-IP selbst oder die Domain aus dem PTR-Record
    checked_on:   date                   # Tag der Prüfung, also das Datum des nächtlichen Laufs
    reachable:    bool                   # true, wenn die Seite geantwortet hat; sagt nichts über den Inhalt aus
    http_status:  int | null             # HTTP-Statuscode; null, wenn keine Antwort kam
````

````
DailyResult:                                      # Ergebnis eines einzelnen Tages
    schema_version:  int                          # Version dieser Datenstruktur
    date:            date                         # UTC-Tag
    generated_at:    datetime                     # Zeitpunkt der Erzeugung dieser Datei
    populations:     DailyPopulations             # Überblick nach Research-Scannern und unbekannten Quellen
    sensors:         list<SensorCount>            # alle Sensoren mit Events am Tag, gezählt über alle Quellen und Protokolle
    actors:          map<actor_id, DailyActor>    # nur am Tag beobachtete Scanner; actor_id ist die id aus scanners.csv

DailyPopulations:
    research_scanners:              # Quellen, die einem Scanner-Akteur zugeordnet sind
        ips:        int             # am Tag beobachtete verschiedene IPs
        protocols:  list<Protocol>  # Protokolle, auf denen diese Gruppe beobachtet wurden
    unknown:                        # Quellen ohne Zuordnung zu einem Akteur
        ips:        int             # am Tag beobachtete verschiedene IPs
        protocols:  list<Protocol>  # Protokolle, auf denen diese Gruppe beobachtet wurde

DailyActor:                                                # ein Scanner-Akteur an diesem Tag
    name:                 string                           # Anzeigename aus scanners.csv
    type:                 string                           # Akteurstyp aus scanners.csv, z. B. akademisch, kommerziell oder anonym
    ips:                  list<DailyIp>                    # am Tag beobachtete IPs des Akteurs
    protocols:            map<Protocol, ProtocolResult>    # alle IPs
    protocols_validated:  map<Protocol, ProtocolResult>    # nur validierte IPs, sonst leer
    ehlo_fqdns:           list<string>                     # im SMTP-EHLO genannte Hostnamen (Indikator für Regel 3)
    traffic:              Traffic                          # Verkehrs-Kennzahlen des Tages
    web:                  list<WebCheck>                   # Ergebnis der Prüfung aus dem Lauf dieses Tages

DailyIp:                            # eine IP eines Akteurs
    ip:           string            # IPv4-Adresse des Scanners
    validated:    bool              # true, wenn fcrdns oder ip_range true ist
    fcrdns:       bool              # PTR-Hostname zeigt per A-Record wieder auf diese IP
    ip_range:     bool              # IP liegt in einem Bereich des Akteurs aus scanner_ranges.csv
    ptr:          list<string>      # PTR-Hostnamen der IP; leer, wenn kein PTR-Record existiert
````


````
AggregatedResult:              # Stand aller Zeitfenster an einem Tag, berechnet aus den Tagesdateien
    schema_version:  int       # Version dieser Datenstruktur
    as_of:           date      # letzter UTC-Tag, der in die Fenster einfließt
    generated_at:    datetime  # Zeitpunkt der Erzeugung dieser Datei
    windows:
        last_7d:   Window         # letzte 7 Tage einschließlich as_of
        last_31d:  Window         # letzte 31 Tage einschließlich as_of
        "all":  Window         # gesamter Zeitraum seit der ersten Tagesdatei

Window:                                     # Ergebnis eines Zeitfensters
    start:        date                      # erster Tag des Fensters
    end:          date                      # letzter Tag des Fensters, entspricht as_of
    coverage:     Coverage                  # zeigt, wie vollständig das Fenster ist
    populations:  WindowPopulations         # Überblick über das Fenster
    sensors:      list<SensorCount>         # alle Sensoren mit Events im Fenster, Zähler je sensor_ip über die Tage summiert
    actors:       map<actor_id, WindowActor># im Fenster beobachtete Scanner

Coverage:
    days_expected:  int         # Anzahl der Tage im Fenster
    days_included:  int         # Anzahl der Tage mit vorhandener Tagesdatei
    days_missing:   list<date>  # Tage ohne Tagesdatei

WindowPopulations:
    research_scanners:              # Quellen, die einem Scanner-Akteur zugeordnet sind
        ips:        int             # verschiedene IPs im Fenster, ermittelt aus actors[].ips
        protocols:  list<Protocol>  # Vereinigung der Protokolle aus den Tagesdateien
    unknown:                        # Quellen ohne Zuordnung zu einem Akteur
        ip_days:    int             # Summe der Tageswerte; eine IP an mehreren Tagen zählt mehrfach
        protocols:  list<Protocol>  # Vereinigung der Protokolle aus den Tagesdateien

WindowActor:                                               # ein Scanner-Akteur im Zeitfenster
    name:                 string                           # Anzeigename aus scanners.csv
    type:                 string                           # Akteurstyp aus scanners.csv
    first_seen:           date                             # erster Tag im Fenster, an dem der Akteur beobachtet wurde
    last_seen:            date                             # letzter Tag im Fenster, an dem der Akteur beobachtet wurde
    days_seen:            int                              # Anzahl der Tage im Fenster mit Beobachtung
    ip_counts:
        total:            int                              # Anzahl eindeutiger IPs im Fenster
        validated:        int                              # davon validierte IPs
    ips:                  list<WindowIp>                   # im Fenster beobachtete IPs des Akteurs
    protocols:            map<Protocol, ProtocolResult>    # alle IPs: Maxima über alle Tage, Score daraus neu berechnet
    protocols_validated:  map<Protocol, ProtocolResult>    # nur validierte IPs, sonst leer; Berechnung wie bei protocols
    ehlo_fqdns:           list<string>                     # Vereinigung über alle Tage
    traffic:              Traffic                          # Zähler summiert, max_* als Maximum, sensors_hit als Vereinigung
    web:                  list<WebCheck>                   # Ergebnis aus der letzten Tagesdatei des Fensters, in der das Ziel vorkommt

WindowIp:                           # eine IP eines Akteurs im Zeitfenster
    ip:           string            # IPv4-Adresse des Scanners
    validated:    bool              # true, wenn fcrdns oder ip_range true ist; letzter bekannter Stand
    fcrdns:       bool              # PTR-Hostname zeigt per A-Record wieder auf diese IP; letzter bekannter Stand
    ip_range:     bool              # IP liegt in einem Bereich des Akteurs aus scanner_ranges.csv; letzter bekannter Stand
    ptr:          list<string>      # PTR-Hostnamen, letzter bekannter Stand
    first_seen:   date              # erster Tag im Fenster, an dem die IP beobachtet wurde
    last_seen:    date              # letzter Tag im Fenster, an dem die IP beobachtet wurde
    days_seen:    int               # Anzahl der Tage im Fenster mit Beobachtung
````

### Levels
````
transport:
    ssh, telnet:  0 keine Verbindung | 1 SYN | 2 Handshake
    smtp, ldap:   0 keine Verbindung | 1 SYN | 2 Handshake | 3 TLS getestet | 4 TLS genutzt

application:
    ssh:     0 keine | 1 Banner | 2 Login | 3 Befehl | 4 sudo
    telnet:  0 keine | 1 Login | 2 Befehl | 3 sudo
    smtp:    0 keine | 1 Befehl | 2 Capability | 2.5 VRFY/EXPN | 3 Mail | 4 AUTH
    ldap:    0 keine | 1 Befehl | 2 anonymer Bind | 3 Suche | 4 Bind mit Zugangsdaten

score = 0.3 * max_transport_level / transport_max
      + 0.7 * max_application_level / application_max
# transport_max und application_max sind die höchsten Stufen des jeweiligen Protokolls.
# Beispiel: transport_max ist bei SSH 2, bei SMTP 4; application_max ist bei Telnet 3, sonst 4.
````

### Entscheidungen

#### Geringe Verzerrung an den Tagesgrenzen akzeptieren
Die Sensoren schreiben ihre Logs und PCAPs alle 10 Minuten in den S3. Die Analyse wertet einen UTC-Tag einmalig aus. Geringe Abweichungen werden dabei bewusst in Kauf genommen:

- **Beendete Spot-Instanzen:** Daten seit dem letzten Upload können fehlen.
- **Verspätete Uploads:** Was erst nach dem Lauf ankommt, fließt nicht in den Tag ein.
- **SYNs kurz vor Mitternacht:** Ein SYN in den letzten 90 Sekunden des Tages kann als `half_open` zählen, auch wenn das ACK am Folgetag ankam.

#### PTRs nicht für alle IPs speichern
Wir haben uns gegen das Speichern von PTRs für alle IPs entschieden, um Speicher zu sparen. PTRs und FCrDNS-Ergebnisse werden nur für IPs gespeichert, die einem Scanner zugeordnet sind. Die Vermutung ist, dass PTR, FCrDNS und Info-Pages die meisten Scanner erkennen.

- **Nachteile:**
  - Ein später ergänztes PTR-Suffix gilt nur für neue Daten. Frühere Daten dieses Scanners bleiben unter `unknown`, und sein `first_seen` beginnt erst ab der Ergänzung.
  - Wird ein vergangener Tag neu berechnet, stammen PTRs und FCrDNS-Ergebnisse vom Tag der Neuberechnung. Zuordnung und `validated` können dadurch vom ursprünglichen Ergebnis abweichen.
- **Spätere Erweiterung:** Die täglichen ZDNS-Ergebnisse lassen sich als eigene Datei im S3 ablegen, z. B. `dns/YYYY-MM-DD.jsonl`. PTRs aus der Zeit davor lassen sich nicht nachträglich ermitteln.

#### Nur maximale Level speichern
`ProtocolResult` enthält nur die maximalen Level und den Score, keine Liste aller erreichten Level (`application_levels`).

- **Begründung:** Die Application-Levels sind aus Sicht von Regel 10 aufsteigend. Ein höheres Level ist also "mindestens so schlimm wie ein niedrigeres, und das Maximum reicht aus".
- **Einschränkung bei Regel 11:** Ein höheres Level schließt ein niedrigeres nicht ein. Aus dem Maximum folgt daher:

| Maximum | SMTP | LDAP | Aussage zu Regel 11 |
|---|---|---|---|
| Unter dem Regel-11-Level | unter 2.5 | unter 3 | eingehalten |
| Genau auf dem Level | 2.5 | 3 | verletzt |
| Darüber | 3, 4 | 4 | nicht bestimmbar, Regel 10 ist aber verletzt |

- **Spätere Erweiterung:** `application_levels` lässt sich später ergänzen. Die Tagesdateien bekommen dafür ein zusätzliches Feld, und das Level jedes Events wird ohnehin berechnet. Für vergangene Tage müssen die Tagesdateien dann aus den Logs im S3 neu berechnet werden.

### Verarbeitungsschritte
Die Schritte 1 bis 13 laufen jede Nacht für den vergangenen UTC-Tag, Schritt 14 danach für alle Zeitfenster. Die genannten Notebooks liegen in `02-notebooks/.ipynb_checkpoints/` und tragen dort zusätzlich die Endung `-checkpoint`. Sie sind eine Vorlage und müssen für den täglichen Lauf angepasst werden.

#### 1. Sensor-IPs ermitteln
- **Input:** Sensor-Anmeldungen aus dem S3
- **Output:** Liste der Sensor-IPs
- **Beschreibung:** Alle Anmeldungen einlesen, deren `started_at` vor dem Ende des Tages liegt. Die Liste dient als Filter in Schritt 3.
- **Notebook:** `06-descriptors` (nur das Einlesen der JSON-Dateien; `filter-pcap.sh` nutzt bisher die daraus erzeugte `ips_v4.csv`)

#### 2. Handler-Logs laden und bereinigen
- **Input:** Handler-Logs aus dem S3
- **Output:** Bereinigte Logs des Tages, getrennt nach Protokoll
- **Beschreibung:** Einträge über `ts` auf den UTC-Tag filtern, Duplikate entfernen und nur IPv4 behalten. SMTP-Header in eine Liste umwandeln und `duration` einheitlich benennen.
- **Notebook:** `01-clean_handlers`; den IPv4-Filter gibt es in `09b-unknown_scanner_interaction`

#### 3. TCP-Pakete aus den PCAPs ziehen
- **Input:** PCAPs aus dem S3, Sensor-IPs aus Schritt 1
- **Output:** Zeitlich sortierte Tabelle der SYN- und ACK-Pakete (Zeit, Client-IP, Sensor-IP, Ports, Flags, Sequenznummer)
- **Beschreibung:** Pakete des Tages zusammenführen, nach Zeit sortieren und mit `tshark` die benötigten Felder auslesen. Die Sequenznummer kommt neu dazu, damit Schritt 11 Retransmissions erkennt.
- **Notebook:** keines; Vorlage sind `01-interim_scripts/merge-pcaps.sh` und `01-interim_scripts/filter-pcap.sh`

#### 4. SYN-Events und Handshakes erkennen
- **Input:** Pakettabelle aus Schritt 3
- **Output:** `half_open`-Events und Liste der Client-IPs mit `half_open`-Events; neu auch abgeschlossene Handshakes
- **Beschreibung:** Einen SYN ohne ACK innerhalb von 90 Sekunden als `half_open` werten. Am Ende des Tages noch offene SYNs zählen ebenfalls als `half_open`. Abgeschlossene Handshakes werden neu mitgeschrieben, weil Schritt 11 sie braucht.
- **Notebook:** `02-identify_half_open_scans`

#### 5. PTR-Records aller Client-IPs abfragen
- **Input:** Bereinigte Logs aus Schritt 2, IPs aus Schritt 4
- **Output:** Flache Tabelle aus `ip`, `hostname`, `status`
- **Beschreibung:** Eindeutige Client-IPs sammeln, per ZDNS abfragen und das Ergebnis abflachen. Die Ergebnisse werden nur für diesen Lauf genutzt, siehe Entscheidung zu den PTRs.
- **Notebook:** `03-create_ZDNS_input`, `04-flatten_ptr_records` (nutzt `src/flatten_ptr.py`; `flatten_ptr_multiple` verwenden)

#### 6. ISC-Liste abrufen
- **Input:** ISC-Quelle
- **Output:** Tabelle aus IP und Scanner-Name, Namen auf `actor_id` abgebildet
- **Beschreibung:** Liste täglich abrufen und die Namen über die Scanner-Liste vereinheitlichen.
- **Notebook:** Abruf neu; das Einlesen und Umbenennen steht in `08_research_scanner_ip_identification-Copy1`

#### 7. IPs den Scannern zuordnen
- **Input:** PTR-Tabelle aus Schritt 5, ISC-Tabelle aus Schritt 6, Scanner-Liste
- **Output:** Tabelle je Client-IP mit `rdns_match`, `isc_match`, `ip_range_confirmed` und `scanner_id`
- **Beschreibung:** PTR-Suffixe, ISC-Liste und IP-Bereiche abgleichen. Mehrere PTRs einer IP zu einer Zeile zusammenführen. Die `scanner_id` ergibt sich aus `coalesce(rdns_match, isc_match, ip_range_confirmed)`. IPs nur mit Treffer im IP-Bereich gelten ebenfalls als Scanner-IPs. Der bisherige Filter im Notebook lässt sie aus und wird entsprechend erweitert.
- **Notebook:** `08_research_scanner_ip_identification-Copy1`; `scanner_id` aus `09-research_scanner_interaction`

#### 8. FCrDNS prüfen und `validated` setzen
- **Input:** Zuordnung aus Schritt 7
- **Output:** Zuordnung ergänzt um `fcrdns`, `ip_range` und `validated`
- **Beschreibung:** Die A-Records der PTR-Hostnamen per ZDNS abfragen. `fcrdns` ist true, wenn die IP in den Antworten vorkommt. `validated` ist true, wenn `fcrdns` oder `ip_range` true ist. Geprüft werden die Hostnamen aller zugeordneten IPs, also auch solcher, die nur über ISC gefunden wurden. Das Notebook prüft bisher nur rDNS-Treffer.
- **Notebook:** `08_research_scanner_ip_identification-Copy1`; `ip_confirmed` aus `09-research_scanner_interaction`

#### 9. Maximale Level und Score je Scanner berechnen
- **Input:** Bereinigte Logs aus Schritt 2, `half_open`-Events aus Schritt 4, Zuordnung aus Schritt 8
- **Output:** `protocols` und `protocols_validated` je Scanner
- **Beschreibung:** Level je Event bestimmen und je IP das Maximum bilden. Danach je Scanner erneut das Maximum bilden, einmal über alle IPs und einmal nur über validierte IPs. Der Score wird aus den Maxima berechnet. Anpassungen an der Level-Logik:
  - SMTP-Level 2.5 für VRFY/EXPN ergänzen
  - `%su%` durch eine genaue Erkennung von `su` und `sudo` ersetzen
  - beim Score feste Maximalwerte nutzen und `.astype(int)` entfernen, damit 2.5 erhalten bleibt
- **Notebook:** `09-research_scanner_interaction`; Score-Berechnung aus `10-plots` (`compute_interaction_heatmap`)

#### 10. Populationen und Sensor-Zahlen berechnen
- **Input:** Bereinigte Logs aus Schritt 2, `half_open`-Events aus Schritt 4, Zuordnung aus Schritt 8
- **Output:** `populations` und `sensors`
- **Beschreibung:** Client-IPs und Protokolle getrennt für zugeordnete und unbekannte Quellen ermitteln. Für jeden Sensor Log-Einträge als `connections` und SYN-Events als `half_open` zählen. Das setzt `sensor_ip` in den Handler-Logs voraus. Level werden für unbekannte Quellen nicht berechnet.
- **Notebook:** Abgrenzung der unbekannten Quellen per `left_anti` aus `09b-unknown_scanner_interaction`; die Zählungen sind neu

#### 11. Traffic und EHLO-Namen je Scanner berechnen
- **Input:** Pakettabelle aus Schritt 3, Events aus Schritt 4, Zuordnung aus Schritt 8, SMTP-Logs aus Schritt 2
- **Output:** `traffic` und `ehlo_fqdns` je Scanner
- **Beschreibung:** Pakete und Events je Scanner zählen. Retransmissions über gleiche Verbindung und Sequenznummer erkennen und nicht als Probe werten. Daraus die Maxima je Sensor und Port pro Stunde und Tag bilden. Die EHLO-Namen stammen aus dem Feld `client_hostname`.
- **Notebook:** neu; den Zugriff auf `client_hostname` zeigt `09-research_scanner_interaction`

#### 12. Webseiten prüfen
- **Input:** Scanner-IPs und PTR-Domains aus Schritt 8
- **Output:** `web` je Scanner
- **Beschreibung:** Bei jedem Lauf alle am Tag beobachteten Scanner-IPs und ihre PTR-Domains per HTTP und HTTPS abfragen. Es werden keine Ergebnisse aus früheren Läufen übernommen. Die Abfragen laufen mit kurzen Timeouts und Ratenbegrenzung, damit nicht erreichbare Ziele den Lauf nicht verlängern und die Scanner-IPs nicht unnötig belastet werden. Nur Erreichbarkeit und Statuscode festhalten, kein HTML speichern.
- **Notebook:** neu

#### 13. Tagesdatei schreiben
- **Input:** Ergebnisse aus den Schritten 8 bis 12, Name und Typ aus der Scanner-Liste
- **Output:** `DailyResult` als `results/daily/YYYY-MM-DD.json`
- **Beschreibung:** Alles nach dem Schema zusammensetzen und in den S3 schreiben. Eine erneute Berechnung ersetzt die Datei des Tages vollständig.
- **Notebook:** neu

#### 14. Aggregierte Datei berechnen
- **Input:** Tagesdateien der jeweiligen Fenster
- **Output:** `AggregatedResult` als `results/aggregated/YYYY-MM-DD.json`
- **Beschreibung:** Für `7d`, `31d` und `all` die Tagesdateien zusammenführen und `coverage` ermitteln. Die Zusammenführung folgt den Kommentaren im Schema: Zähler summieren, Maxima übernehmen, Listen vereinigen, bei `ptr`, `validated` und `web` den letzten Stand nehmen. Den Score aus den Fenster-Maxima neu berechnen. Rohdaten werden hier nicht mehr gelesen.
- **Notebook:** neu

#### Nicht benötigte Notebooks
- `05-create_rDNS_enrichment`: frühe Keyword-Suche; FCrDNS übernimmt `08_research_scanner_ip_identification-Copy1`
- `07-ASN-data`: AS-Zuordnung wird nicht genutzt
- `08_research_scanner_ip_identification`: ältere Fassung von `-Copy1`
- `09-research_levels_volume`, `09-unknown_levels_volume`: zählen Events je Level, das entfällt
- `10-plots`: außer der Score-Berechnung nicht nötig, da keine Abbildungen erzeugt werden
- `11-Syn-vs-connection`, `12-scanner_list`: leer
- `_filter_research_scans`: explorativ

### Offene Gedanken

#### Was für die Umsetzung noch fehlt

| Was | Warum es blockiert |
|---|---|
| **S3:** Bucket, Pfade, Dateinamen, Zugang | Ohne sie lassen sich weder Inputs lesen noch Ergebnisse schreiben; der S3 steht noch aus |
| **Beispieldaten:** echte PCAPs, Logs und Sensor-Anmeldungen | Ohne sie ist nichts testbar, vor allem nicht die Sensor-IP in den PCAPs |
| **`sensor_ip` in den Handler-Logs** | Schritt 10 setzt das Feld voraus, es wird erst noch ergänzt |
| **`scanners.csv`, `scanner_ranges.csv`** | Beide liegen nicht im Projekt, ihr Ablageort ist noch offen |
| **ISC-Liste:** URL oder API-Zugang | Schritt 6 hat bisher nur ein Einlesen aus einer alten TSV-Datei als Vorlage |
| **`multiple.ini`** | Die ZDNS-Abfragen in Schritt 5 und 8 brauchen sie, die Datei liegt nicht bei |
| **VM:** Größe, Betriebssystem, Netz | Die Notebooks setzen 32 GB Treiber-Speicher an, ob das nötig ist, ist unklar |

Zusätzlich müssen die Notebooks, `01-interim_scripts` und `src/flatten_ptr.py` übergeben werden, weil dieses Dokument nur auf sie verweist.

#### Was entschieden wurde
- **Engine:** PySpark lokal auf der VM
- **Abfragen:** ZDNS und Webabfragen laufen direkt von der VM. Steht die VM im Uni-Netz, sollte das NOC vorab informiert werden.
- **Keine Regel-Bewertung im Code:** Das Skript gibt nur Indikatoren aus. Die Bewertung der Regeln aus `notes.md` wird nicht implementiert.
- **Keine sensiblen Inhalte in den Ergebnissen:** Passwörter und Mail-Inhalte bleiben in den Rohdaten.

#### Was noch nicht genau definiert ist
Die Vorschläge sind noch nicht bestätigt.

| Punkt | Vorschlag |
|---|---|
| Ablauf von „durchgehend läuft“ | Systemd-Timer um 03:00 UTC statt eigenem Dauerprozess |
| Fehlerverhalten | Lauf bricht ab und meldet den Fehler, keine halbe Tagesdatei; `--date` für Neuberechnung |
| Webabfrage | Zertifikate nicht prüfen (bei IPs passen sie fast nie), Weiterleitungen nicht folgen, jede Antwort zählt als erreichbar |
| Werte für Timeout und Ratenbegrenzung | Zum Beispiel 5 Sekunden und 20 Anfragen pro Sekunde, als Konfiguration |
| Erkennung von `su`/`sudo` | Nur ganze Wörter, nur in Befehlen statt in Benutzername und Passwort |
| SMTP-Befehle | Nur das erste Wort prüfen; das Format von `commands` ist noch zu klären |
| Definition einer Probe | Neuer SYN ohne Retransmissions |
| Protokoll ohne Kontakt | Eintrag entfällt aus `protocols` |
| Tag ohne Daten | Keine Tagesdatei, der Tag erscheint in `days_missing` |
| Formate | Zeiten in ISO 8601 UTC, Ablageort `results/` in einer Konfiguration |
