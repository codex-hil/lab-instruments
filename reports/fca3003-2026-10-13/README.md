# FCA3003 — wejście B, 2026-10-13

**Pomiar nadal niewalidowany.** Użytkownik potwierdził oscyloskopem sygnał
6 Vpp i podłączenie do wejścia B licznika. Wcześniejsze podłączenie do A
również było właściwe dla 1 MHz; wejście C nie było wymagane.

Wszystkie poniższe próby są fizyczne, `simulated: false`. FCA3003 `442678`,
firmware V1.31, USB `0699:3003`, Raspberry Pi `192.168.2.36`.
Nie zmieniano amplitudy, częstotliwości ani stanów wyjść generatora.

| Próba na kanale 2 | Wynik | Dowód |
|---|---|---|
| Driver: frequency i period | Timeout, bit 1024, SCPI -230 | [odczyty](hil-input-b-20261013.json) |
| Driver: Vpp | Pusta odpowiedź, odrzucona jako błędna | [odczyty](hil-input-b-20261013.json) |
| Ręczny próg 0 V: AC/DC ×1, AC ×10 | Timeout dla wszystkich trzech konfiguracji | [ręczny trigger](hil-input-b-manual-trigger-20261013.json) |
| Jawne INT, arming i trigger IMM, akwizycja ciągła, FETC? | Pusta odpowiedź, bit 1024, SCPI -230 | [continuous](hil-input-b-continuous-20261013.json) |
| Konfiguracja i READ? w jednej wiadomości SCPI | Pusta odpowiedź, bit 1024, SCPI -213 | [batched](hil-input-b-batched-20261013.json) |

Każdą ręczną nastawę sprawdzono odczytem: próg 0 V, AUTO OFF, AC/DC,
attenuation ×1/×10. Po konfiguracji nie było błędu SCPI. Wejście pozostawało
1 MΩ, filtry analogowy i cyfrowy OFF. Brak dodatniego wyniku nie jest
dowodem uszkodzenia licznika ani dowodem braku sygnału w kablu.

Odczytano również podłączony MSO2002B `C010257` i AFG1062 `1544477`:
[odczyty przyrządów](hil-scope-signal-20261013.json). Generator zgłaszał
1 MHz na obu kanałach, oba ON, CH2 SIN, nastawę amplitudy 1 i offset 0.
Immediate measurement oscyloskopu w jego zastanym stanie zwrócił 80 mVpp
na CH1 i 8 mVpp na CH2, z częstotliwościami innymi niż 1 MHz. Nie sprawdzono
podłączenia sond, współczynników sond, podstawy czasu ani świeżości przebiegu;
tych odczytów nie traktujemy jako ponownej walidacji sygnału ani jako
zaprzeczenia wcześniejszej obserwacji użytkownika 6 Vpp.

Driver poprawiono, usuwając przypisanie timeoutu do „missing input signal”.
Teraz zgłasza timeout i kod SCPI bez niepotwierdzonej diagnozy przyczyny.
42 testy biblioteki oraz budowa zipapp PASS. Historyczne JSON-y zachowują
oryginalne komunikaty z chwili wykonywania prób.

Na końcu pozostawiono licznik na częstotliwości **wejścia B**, z domyślnymi
nastawami wejścia po CONF, akwizycją ciągłą i timeoutem 3 s. Kod źródłowy
drivera na RPi zaktualizowano. Generator pozostał bez zmian.

Najbardziej rozstrzygający kolejny krok: sprawdzić, czy licznik mierzy ten
sam sygnał z panelu w trybie lokalnym, bez sterowania USB. Pozwoli to
oddzielić problem zdalnej akwizycji od wejścia i połączenia fizycznego.

## Ekran i przejście do trybu lokalnego

USB488 GOTO_LOCAL powiodło się. Po 3 s odczytano zrzut ekranu:
[Frequency B: No trig or Tout](counter-input-b.png).
[Wynik ioctl](hil-input-b-local-20261013.json). Sam odczyt zrzutu jest
komendą USB i może ponownie przełączyć przyrząd w remote, dlatego nie
traktujemy obrazu jako w pełni niezależnej próby panelowej bez USB.
Na końcu ponownie wykonano GOTO_LOCAL i nie wysyłano już żadnych komend
SCPI. Licznik pozostawiono na B w trybie lokalnym do dalszej próby panelowej.
