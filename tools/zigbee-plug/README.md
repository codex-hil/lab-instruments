# Wspólna wtyczka HIL

Dostęp na Optiplexie: `~/.local/bin/hil-plug`. Backend na debug station 2:
`~/zigbee-lan-investigation/scripts/plugctl.py` (Python 3, ten sam interfejs).
Urządzenie: `0xa4c1386c56ee225b`, TS011F `_TZ3000_xzhnra8x`.

```bash
hil-plug reservation
hil-plug reserve --owner 'ID-watku: opis eksperymentu'
# Skopiuj token z JSON; przechowuj go w tym wątku, nie w AGENTS.md.
export HIL_PLUG_TOKEN='token-z-odpowiedzi'
hil-plug status
hil-plug power --timeout 20
hil-plug off
hil-plug on
hil-plug release
unset HIL_PLUG_TOKEN
```

ON/OFF wykonuj wyłącznie w ramach autoryzowanego testu po potwierdzeniu,
co fizycznie podłączono. Mapowanie gniazda na komputer nie jest ustalone.
Infrastruktura sterująca nie może być zasilana z tej wtyczki.
Rezerwacja obowiązuje także dla odczytów; `reservation` jest publiczny.
Można użyć `--token TOKEN` zamiast zmiennej środowiskowej.
Wyniki są JSON; kod wyjścia 1 oznacza błąd. Pole `null` oznacza brak danych,
a nie zerowy pobór. `power` odczytuje stan, żeby uzyskać publikację z dostępnymi pomiarami;
nie wymusza nowej próbki mocy. Timeout wynosi maks. 60 sekund.
`status` wysyła odczyt stanu, bez przełączania przekaźnika.

## Koordynacja

Jedna trwała rezerwacja, token losowy, brak automatycznego wygaśnięcia.
Przy zajęciu: LEASE_BUSY. Nie usuwaj cudzej rezerwacji. Po przerwaniu wątku
wznów z jego tokenem; jeśli token zaginął, uzgodnij ręczne odzyskanie z
właścicielem/użytkownikiem. Brak force takeover w CLI.
Rezerwacje w `~/.local/share/hil-plug/lease.json` na station2; flock
`operation.lock` serializuje odczyt lease i całą operację. Audit mutacji:
`audit.jsonl`. Zwolnienie rezerwacji nie zmienia zasilania. Lock operacji
zwalnia system po śmierci procesu, ale trwała rezerwacja pozostaje.

To blokada współpracujących wątków, nie granica bezpieczeństwa: wspólne konto
SSH i lokalny broker pozwalają ją ominąć. Wszystkie wątki mają korzystać z CLI,
nie publikować bezpośrednio MQTT. Usługi Z2M/Mosquitto muszą być uruchomione;
CLI nie uruchamia ich ani nie zmienia konfiguracji.

## Semantyka i ograniczenia

`on`/`off` publikuje nie-retained QoS1 i potwierdza dostarczenie do brokera.
To nie potwierdza fizycznego przełączenia. Następnie sprawdź `status` i stan
hosta niezależnie. Timeout po wysłaniu oznacza niepewny wynik; nie używamy TOGGLE.
Odczyty ignorują retained wiadomości, ale Z2M może scalać stare pola pomiarów
w nowej publikacji: czas odbioru nie jest czasem próbki każdego sensora.
CLI uczciwie zwraca `field_sample_age=UNKNOWN`.

Automatyczny power-cycle i countdown nie są wdrożone: brak potwierdzonego
lokalnego timera i trwałego watchdog przywracania ON. Nie zastępuj go
`off; sleep; on` w nietrwałej sesji sterującej komputerem.
Po wdrożeniu wykonano autoryzowany test ON→OFF; szczegóły poniżej.

Protokół: https://www.zigbee2mqtt.io/guide/usage/mqtt_topics_and_messages.html
Klient: https://mosquitto.org/man/mosquitto_sub-1.html

## Źródła i odtworzenie wdrożenia

Kod kanoniczny: `tools/zigbee-plug` w `codex-hil/lab-instruments`.
To sterownik CLI konkretnego stanowiska, nie plugin serwera labinstruments.
Python 3 (stdlib), Linux, SSH oraz Mosquitto CLI 2.1.2. Broker loopback
18884, topic `zigbee-poc`; Z2M 2.14.0 na debug station2. Ścieżka Nix klienta
jest przypięta w `plugctl.py`; runtime zachowany przez istniejące GC roots
`~/zigbee-lan-investigation/poc/slzb-06p7u/runtime-mqtt` i `runtime-z2m`.
Repo nie zawiera kluczy Zigbee/SSH ani aktualnych tokenów rezerwacji.

Na Optiplexie z katalogu repo (wdraża kod, nie przełącza zasilania):

```bash
install -m 755 tools/zigbee-plug/hil-plug ~/.local/bin/hil-plug
scp -i ~/.ssh/debug_station2 -o IdentitiesOnly=yes -o BatchMode=yes \
  tools/zigbee-plug/plugctl.py \
  codex-hil@codex-hil-debug-station2.local:zigbee-lan-investigation/scripts/plugctl.py
python3 -m unittest discover -s tools/zigbee-plug/tests
hil-plug reservation
```

Istniejące usługi `zigbee-poc.service` i `zigbee-poc-mosquitto.service`
są wymagane. Odtworzenie od zera obejmuje osobne przygotowanie Z2M, brokera,
koordynatora i sparowanie urządzenia; samo skopiowanie drivera tego nie robi.
Nie zmieniać katalogu lease ani tworzyć drugiego brokera do tej samej wtyczki.
Nie wdrażać zmiany protokołu blokad podczas aktywnej rezerwacji.

## Walidacja 2026-10-30

CONFIRMED: fizyczne sparowanie i odczyty; odmowa drugiej rezerwacji,
odmowa OFF z błędnym tokenem, zwolnienie rezerwacji. Użytkownik zlecił ON,
po 3 sekundach OFF; raport urządzenia OFF, użytkownik potwierdził słyszalne
kliknięcie przekaźnika. Wcześniejszy stan był ON, więc nie potwierdza to
osobnego przejścia OFF→ON. Brak pomiaru napięcia na wyjściu pod obciążeniem.
Testy offline sprawdzają publikację OFF, brak publikacji przy złym tokenie
i niezgodnej tożsamości; nie wymagają brokera ani sprzętu.

BLOCKED / niezweryfikowane: countdown bez MQTT, automatyczny power-cycle,
watchdog, przypisanie do konkretnego komputera i dokładność pomiarów mocy.
