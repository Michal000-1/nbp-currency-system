# NBP Currency System

System do analizy kursow walut na podstawie danych z API Narodowego Banku Polskiego. Projekt jest realizowany w ramach pracy magisterskiej.

## Technologie

- Python 3.11
- FastAPI
- Streamlit
- Pandas
- HTTPX
- Requests
- NBP API

## Architektura

Projekt oparty jest na architekturze 3-warstwowej:

```text
NBP API -> FastAPI backend -> Streamlit frontend
```

Backend FastAPI odpowiada za komunikacje z API NBP, walidacje danych oraz logike analizy. Frontend Streamlit udostepnia prosty interfejs do uruchamiania zapytan i przegladania wynikow.

## Struktura projektu

```text
nbp-currency-system/
|-- app/
|   |-- main.py
|   |-- routers/
|   |   |-- analysis.py
|   |   `-- currencies.py
|   |-- models/
|   |   |-- analysis.py
|   |   `-- currency.py
|   `-- services/
|       |-- analysis_service.py
|       |-- events.py
|       |-- nbp_api.py
|       `-- pandas_analysis.py
|-- streamlit_app/
|   `-- ui.py
|-- tests/
|   `-- test_analysis_endpoint.py
|-- pyproject.toml
`-- README.md
```

## Endpointy

### Currencies

- `GET /currencies/{code}` - pobranie aktualnego kursu waluty.
- `GET /currencies/{code}/history?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD` - pobranie historycznych kursow waluty z podanego zakresu dat.

### Analysis

- `GET /analysis/event-impact?code=USD&event_date=2022-02-24&days_before=7&days_after=7` - analiza wplywu pojedynczego wydarzenia na kurs.
- `GET /analysis/events-impact?code=USD&window_business_days=7` - analiza wplywu wszystkich zdefiniowanych wydarzen.
- `GET /analysis/events-impact-compare?code=USD&short_window=7&long_window=21` - porownanie sily zmian pomiedzy krotkim i dlugim oknem czasowym.

## Wydarzenia

Aplikacja analizuje wplyw 12 zdefiniowanych wydarzen makroekonomicznych i geopolitycznych. Lista wydarzen znajduje sie w pliku:

```text
app/services/events.py
```

Kazde wydarzenie posiada:

- `event_id` - techniczny identyfikator wydarzenia.
- `name` - nazwe wydarzenia wyswietlana w wynikach.
- `event_date` - date wydarzenia.

## Walidacja i bledy

```text
code: dokladnie 3 litery (^[A-Za-z]{3}$)
short_window >= 1
long_window >= 1
long_window > short_window
```

Typowe kody odpowiedzi:

```text
200 - OK
400 - bledne parametry biznesowe
404 - brak danych lub brak waluty
422 - blad walidacji danych wejsciowych
503 - niedostepne API zewnetrzne
```

## Obslugiwane waluty

- EUR/PLN
- USD/PLN
- CHF/PLN

## Uruchomienie lokalne

### Backend

```bash
uvicorn app.main:app --reload --port 8000
```

Backend bedzie dostepny pod adresem:

```text
http://127.0.0.1:8000
```

Dokumentacja Swagger:

```text
http://127.0.0.1:8000/docs
```

### Frontend

Frontend nalezy uruchomic w drugim terminalu:

```bash
streamlit run streamlit_app/ui.py
```

Frontend bedzie dostepny zwykle pod adresem:

```text
http://localhost:8501
```

Domyslny adres backendu w aplikacji frontendowej to:

```text
http://127.0.0.1:8000
```

## Uruchomienie z uv

Instalacja zaleznosci z `pyproject.toml`:

```bash
uv sync
```

Backend:

```bash
uv run uvicorn app.main:app --reload --port 8000
```

Frontend:

```bash
uv run streamlit run streamlit_app/ui.py
```

## Testy

```bash
pytest
```

lub z `uv`:

```bash
uv run pytest
```

## Konteneryzacja

Aplikacja jest przygotowywana do uruchomienia w kontenerach Podman. Docelowo backend FastAPI i frontend Streamlit powinny dzialac jako dwa osobne kontenery.

Planowany podzial:

```text
backend  -> FastAPI / Uvicorn -> port 8000
frontend -> Streamlit         -> port 8501
```

Dla osobnych srodowisk testowego i produkcyjnego planowane sa oddzielne pliki compose oraz oddzielne sieci:

```text
net-test
net-prod
```

W kontenerach frontend powinien komunikowac sie z backendem po nazwie serwisu w danej sieci, np.:

```text
http://backend-test:8000
http://backend-prod:8000
```

Do dalszej konteneryzacji nalezy dodac:

```text
requirements.txt
Containerfile.backend
Containerfile.frontend
podman-compose.test.yml
podman-compose.prod.yml
```
