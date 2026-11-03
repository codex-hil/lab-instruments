# Inwentarz Zigbee — 2026-11-03

| CLI | Nazwa MQTT / Zigbee2MQTT | IEEE (trwała tożsamość) | Rozpoznany model | Producent Zigbee |
|---|---|---|---|---|
| `--plug 1` (domyślna) | `0xa4c1386c56ee225b` | `0xa4c1386c56ee225b` | Tuya TS011F / TS011F_plug_1 | `_TZ3000_xzhnra8x` |
| `--plug 2` | `plug02` | `0xa4c13842b71b5267` | Nous A7Z / TS011F | `_TZ3008_reatplte` |
| `--plug 3` | `plug03` | `0xa4c13833ca1c3e80` | Nous A7Z / TS011F | `_TZ3008_reatplte` |

Wtyczki mają adresy Zigbee IEEE, nie indywidualne IP w LAN. Krótkie adresy
sieciowe Zigbee są zmienne i nie służą do identyfikacji. Fizyczne obciążenia
oraz przypisanie do komputerów pozostają nieustalone.

## Infrastruktura

- Koordynator SMLIGHT SLZB-06p7U, CC2652P7, ZNP/zstack przez Ethernet.
- Ostatni potwierdzony LAN: `192.168.2.21`, mDNS `slzb-06p7u.local`, TCP 6638.
- Ethernet MAC `9e:13:9e:35:9f:e0`; bazowy MAC API `9c:13:9e:35:9f:e0`.
- IEEE koordynatora `0x00124b0028d6cca2`, kanał Zigbee 15.
- Z2M i Mosquitto na `codex-hil-debug-station2.local`, obserwowany IP `192.168.2.33`.
- MQTT `127.0.0.1:18884` **na station2**, prefix `zigbee-poc`.
- Tematy urządzeń: `zigbee-poc/<nazwa MQTT>`, komendy `/set`, odczyty `/get`.
  Wątki korzystają z CLI i rezerwacji zamiast bezpośredniej publikacji MQTT.
- Usługi użytkownika: `zigbee-poc.service`, `zigbee-poc-mosquitto.service`.
- Optiplex: `~/.local/bin/hil-plug`; SSH kluczem `~/.ssh/debug_station2`.
- Backend: `~/zigbee-lan-investigation/scripts/plugctl.py` na station2.

Adresy IP są obserwacjami, nie potwierdzonymi rezerwacjami DHCP.
Nie uruchamiaj drugiego klienta koordynatora TCP ani innej sieci Zigbee.
Klucze sieci, tokeny lease i klucze SSH nie są częścią repozytorium.

## Potwierdzenie i ograniczenia

CONFIRMED: wszystkie trzy urządzenia sparowane, interview SUCCESSFUL,
obsługiwane przez działające Z2M. Okna parowania zamknięte.
Pierwsza wtyczka: autoryzowane ON→OFF, raport OFF i potwierdzone przez użytkownika
kliknięcie 2026-10-30. Druga i trzecia: parowanie 2026-11-03, bez testu przekaźnika.
Konwertery udostępniają ON/OFF, moc W, prąd A, napięcie V, energię kWh i countdown.
Pomiary zwracane przez CLI mogą zawierać buforowane pola; świeżość próbek nieznana.

Niezweryfikowane: dokładność pomiarów, fizyczne przełączenie drugiej/trzeciej,
autonomiczny countdown bez MQTT, power-cycle i watchdog, działanie pod obciążeniem.
Nie wyłączaj zasilania hosta/brokera/switcha utrzymującego ścieżkę sterowania.

Read-only validation: [JSON](validation-20261103.json). All three reported ON;
plug1 9 W, plug2 0 W, plug3 power/current not yet reported (null), voltage 231 V.
These are received snapshots, not independently verified electrical measurements.
All validation reservations released. No relay commands during this validation.
