# NBP Currency System
System do analizy kursów walut na podstawie danych z API Narodowego Banku Polskiego. Realizowany w ramach pracy magisterskiej 

## Technologie
- Python 3.11
- FastAPI
- Pandas
- Streamlit
- NBP API

## Architektura
Projekt oparty na architekturze 3-warstwowej:
```
NBP API → FastAPI backend → Streamlit frontend
```

## Endpointy

## Currencies
- `GET /currencies/{code}` - aktualny kurs waluty
- `GET /currencies/{code}/history?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD` - historyczne kursy w zakresie dat

## Analysis
- `GET /analysis/event-impact?code=USD&event_date=2022-02-24&days_before=7&days_after=7`- analiza wpływu pojedynczego wydarzenia na kurs
- `GET /analysis/events-impact?code=USD&window_business_days=7` - analiza wpływu wszystkich zdefiniowanych wydarzeń
- `GET /analysis/events-impact-compare?code=USD&short_window=7&long_window=21`- porównanie siły zmian między krótkim i długim oknem czasowym


## Walidacja i błędy

```
code: dokładnie 3 litery (^[A-Za-z]{3}$)

short_window >= 1

long_window >= 1

long_window > short_window

Typowe kody odpowiedzi:
200 - OK
400 - błędne parametry biznesowe
404 - brak danych / brak waluty
422 - błąd walidacji wejścia
503 - niedostępne API zewnętrzne
```
## Obsługiwane waluty
- EUR/PLN
- USD/PLN
- CHF/PLN

## Uruchomienie
uvicorn app.main:app --reload



