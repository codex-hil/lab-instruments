# Potwierdzone połączenia generatorów z oscyloskopami

2026-09-29, pomiar fizycznego stanowiska przez HTTPS RPI-USBTMC. Użyto istniejących
`Transport(kind='gateway')` oraz `Driver.apply/read/off`. Po potwierdzeniu przez
użytkownika połączeń wykonano aktywny test kolejnych wyjść, bez ręcznego przekładania kabli.

| Generator | Wyjście | Oscyloskop | Wejście | Test / odczyt, Hz |
|---|---|---|---|---|
| AFG1062, 1544477 | CH1 | TBS1022, C012657 | CH1 | 1100 / 1101.32; 1700 / 1700.68 |
| AFG1062, 1544477 | CH2 | MSO2002B, C010257 | CH1 | 2300 / 2304.6; 3100 / 3106.4 |
| MP750288, 1944201 | CH1 | TBS1022, C012657 | CH2 | 4300 / 4347.83; 5300 / 5317.26 |
| MP750288, 1944201 | CH2 | MSO2002B, C010257 | CH2 | 6700 / 6684.5; 7900 / 7851.8 |

Każde połączenie potwierdzono dwiema częstotliwościami przy jednym włączonym wyjściu.
W każdej próbie mierzono wszystkie cztery wejścia. Kryterium: zgodność częstotliwości
w granicach 2% oraz amplituda ponad tłem (0.015–0.6 Vpp po przeliczeniu ustawienia sondy).
Każda para częstotliwości wskazała dokładnie to samo pojedyncze wejście.
To identyfikacja połączeń, nie kalibracja dokładności częstotliwości ani amplitudy.

Nastawy źródeł: sinus, offset 0, AFG1062 98 mVpp, MP750288 100 mVpp.
AFG1062 na żądanie 100 mV zwracał 98 mV; pierwsza próba została zatrzymana
przez kontrolę readback w driverze przed włączeniem wyjścia. Nastawa 98 mV dawała
zgodny readback. Nie rozszerzano tolerancji drivera ani nie obchodzono jego kontroli.
Pomocnicze zapytanie `SOUR1:VOLT:UNIT?` nie dało odpowiedzi na tym firmware; nie było
używane w teście i nie zmieniało nastaw.

## Przywrócenie stanowiska

Wszystkie cztery wyjścia generatorów OFF, potwierdzone odczytem.
Przywrócono i porównano odczyty zapisanych nastaw obu generatorów i oscyloskopów:
częstotliwości, amplitudy, offsety i tryby generatorów, skale, pozycje, sprzężenia,
podstawy czasu, wyświetlanie kanałów, akwizycję, tryb wyzwalania, immediate measurement
oraz HEADER. Wszystkie porównania przeszły; brak błędów przywracania.

Ustawień współczynnika sondy nie zmieniano. MSO2002B CH1 miał gain 0.1 (10×), CH2 1×;
TBS1022 oba kanały 10×. Amplitudy w raporcie przeliczono przy założeniu bezpośrednich
kabli. Te ustawienia należy uwzględnić przy przyszłych pomiarach napięcia.

## Artefakty

- [connections.json](connections.json): mapa połączeń i częstotliwości potwierdzające.
- [pre-test-settings.json](pre-test-settings.json): pełny zapis zmienianych nastaw przed testem.
- [active-test.json](active-test.json): osiem prób, 32 pary odczytów frequency/Vpp, readback
  źródeł i kontrolne odczyty po przywróceniu.
- [first-attempt.json](first-attempt.json): przerwana próba 100 mV i potwierdzenie przywrócenia.
- [baseline.json](baseline.json), [passive-measurements.json](passive-measurements.json):
  wcześniejsze odczyty, zanim użytkownik potwierdził możliwość testu aktywnego.

Dodano dokładny profil `tbs1022` (`TBS 1022` z *IDN?), korzystający ze wspólnej
implementacji frequency/Vpp. Nie tworzono osobnego drivera. Test profilu i cała
lokalna seria: 72 testy PASS.
Komendy pomiarowe TBS zweryfikowano w [instrukcji Tektronix 077044403 Rev B](https://www.tek.com/en/oscilloscope/tds1000-manual),
MEASUrement:IMMed, s. 2-137–2-144. Profil nie dodaje waveform acquisition dla TBS1022.
