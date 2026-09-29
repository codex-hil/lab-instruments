# Bramki Raspberry Pi USBTMC i Waveshare RS-232

Kod RPi, szablony i skrypty są w [lab-instruments](../README.md). Waveshare używa własnego
firmware: to zewnętrzna bramka transportowa, nie osobny driver przyrządu. Skrypty
pomiarowe nadal korzystają z modelowych driverów bez pośredniego serwera rezerwacji.

## Raspberry Pi → USBTMC

Droga: skrypt Python → HTTPS → Raspberry Pi → USBTMC → przyrząd.
Python 3.11+, Linux z `usbtmc`; [pełna instalacja](../docs/deployment.md).

1. Zbuduj `./scripts/bootstrap.sh`. Wynik `dist/labinst.pyz` można przenieść z PC na Pi.
2. Uruchom `./dist/labinst.pyz usb-list`, odczytaj serial USB i topologię portów.
3. Skopiuj [rpi-gateway.json](../examples/rpi-gateway.json), ustaw adres Pi i selektory
   slotów `usb1`–`usb4`. Zastąp wszystkie placeholdery. Slot może wskazywać numer seryjny
   urządzenia albo fizyczny port; przy wyborze portu klient sprawdza model przez `*IDN?`.
4. Administrator instaluje usługę przez `scripts/install.sh <konfiguracja.json>`,
   certyfikat przez `scripts/make-certificate.sh <IP-Pi>` i reguły USB wygenerowane
   przez `scripts/udev-rule.py`. Instalator sam nie uruchamia usługi.
5. Po ustawieniu reguł udev, certyfikatu i konfiguracji: `systemctl enable --now labinst`.
   Logi: `journalctl -u labinst -f`. Reguły i komendy administratora opisuje instrukcja.
6. Klient używa transportu `gateway`: URL HTTPS, slot, plik tokena i zaufany certyfikat.
   [Przykładowa konfiguracja klienta](../examples/usb-remote.json).

Bramka udostępnia panel WWW i `GET /v1/status`. Transakcje idą przez
`POST /v1/transaction`: JSON `{slot, data, reply}`, bajty `data` kodowane base64.
Token Bearer i weryfikacja TLS są wymagane. [README protokołów bramki](../docs/gateway/README.md).
Bramka przekazuje bajty; nie narzuca SCPI ani limitów napięcia/prądu.
Nie implementuje USB/IP, VXI-11, HiSLIP ani surowego gniazda VISA.

### Hotplug bez rebootu

Przed każdą transakcją bramka ponownie wyszukuje urządzenie po serialu/topologii.
Nie zapisuje na stałe numeru `/dev/usbtmcN`. Odłączenie kończy operację błędem;
następna transakcja po ponownym podłączeniu otwiera aktualny węzeł urządzenia.
Reguła udev nadaje uprawnienia przy każdym podłączeniu. Nie trzeba restartować Pi
ani usługi przy powrocie urządzenia pasującego do skonfigurowanego selektora.
Nowy, niepasujący serial wymaga zmiany konfiguracji slotu; nie ma jej hot-reloadu.

Nie powtarzamy przerwanej komendy, nie odtwarzamy nastaw i nie wysyłamy automatycznego ON.
Fizyczny stan wyjścia po utracie łączności wymaga sprawdzenia. Przy bezpośrednim lokalnym
`Transport(kind="usb")` po odłączeniu należy zamknąć uszkodzony kontekst i otworzyć nowy.

Jedna transakcja zajmuje bramkę; równoczesne żądanie dostaje HTTP 503 przed zapisem
komendy. Nie ma rezerwacji całego eksperymentu: jeden skrypt steruje danym urządzeniem.
Cztery fizyczne urządzenia sprawdzono na RPi 3 B+ przez HTTPS: identyfikacja, sterowanie
generatorami i odczyty częstotliwości/Vpp. Fizyczny hotplug w czasie pracy usługi
pozostaje do zrobienia. [Raport RPi](../reports/rpi-gateway-2026-09-29/README.md) ·
[mapa kabli](../reports/rpi-wiring-2026-09-29/README.md).

## Waveshare → RS-232

Droga: skrypt Python → surowy TCP → Waveshare → RS-232 → przyrząd.
Dla użytej bramki RS232/485 TO ETH zapisano konfigurację stanowiska:

| Ustawienie | Wartość |
|---|---|
| IP / maska | `192.168.2.201` / `255.255.255.0` |
| Brama sieciowa | `192.168.2.1` |
| Tryb portu RS-232 | TCP server, transparentny, port `4001` |
| Parametry szeregowe | `9600`, 8 bitów danych, brak parzystości, 1 bit stopu |
| Flow control | brak |
| Klienci | jeden klient sterujący |

Ustawienia sprawdź w panelu konkretnej bramki oraz w menu komunikacji instrumentu.
To zapis konfiguracji laboratoryjnej, nie gwarancja fabrycznych ustawień innego egzemplarza.
Wybieramy transparentne przekazywanie bajtów, bez konwersji Modbus.
Po stronie drivera jest zwykły `Transport(kind="tcp")`; RS-232 konfiguruje się w bramce,
a nie przez to połączenie. Nie używamy RFC2217 ani wirtualnego portu COM.

Keithley 6487 i B&K 8550 używały tego samego portu bramki **zamiennie**.
Obecnie według zgłoszenia użytkownika podłączony jest 6487, a obciążenie B&K jest odpięte.
Dla 6487 odpowiedzi są zakończone CR (`read_termination: "\r"`), zapis domyślnie LF;
profil CLI ustawia terminator odczytu. Dla B&K używany jest LF.
Przykłady: [inwentarz labu](../examples/lab.json), [B&K](../examples/bk8550.json).

Ostatnia próba HIL: bramka była nieosiągalna. Nie oznacza to potwierdzonej awarii
picoamperomierza; najpierw trzeba odzyskać dostęp do bramki, następnie sprawdzić `*IDN?`.
Nie zapisujemy haseł i kopii panelu administracyjnego w repo. Nie ma jeszcze uniwersalnego
skryptu konfigurującego Waveshare; konfigurację nowego egzemplarza wykonuje się jego
panelem według powyższych parametrów, po sprawdzeniu modelu/firmware i dostępności IP.

## Co pozostaje opcjonalne

[labinst.service](labinst.service) obsługuje obie role programu, ale uruchamiana jest
rola wskazana w konfiguracji. Tryb `control`, limity roota i dwa NIC to oddzielny,
opcjonalny wariant opisany w [architekturze](../docs/architecture.md).
Nie jest wymagany do korzystania z driverów i bramek. Pełne rezerwacje urządzeń dla
równoległych skryptów nie są zaimplementowane.
