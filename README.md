## Jak uruchomić serwer?

- uzupełnij pola w pliku ```.env-template``` i mznień jego nazwę na ```.env```
- uruchom ```docker-compose up``` jesli pojawia się błąd ```permission denied while trying to connect to the docker API ``` uruchom jako root
- zainstaluj narzędzie uv albo stwórz środowisko i uruchom wirtualne oraz zainstaluj zależności przez ```pip install .```
- uruchom projekt przez ```uv run manage.py migrate && uv run manage.py runserver``` lub ```python -m manage.py migrate && python -m run manage.py runserver```

## Jak wejść na stronę administracyjną?
- dodaj superusera przez `uv run manage.py createsuperuser` albo `python manage.py createsuperuser`
- uruchom serwer i wejdź na ``` /admin ```

## Ruff i precommit

Przed commitem Ruff sprawdza pliki Pythona, poprawia automatycznie naprawialne
błędy, sortuje importy i formatuje kod. Jeżeli zmodyfikują pliki, przejrzyj zmiany, dodaj je ponownie przez `git add` i ponów commit.

Instalacja:

```bash
uv sync
uv run pre-commit install
```

Ręczne uruchomienie:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pre-commit run --all-files
```

Automatyczne poprawki: `uv run ruff check --fix .` oraz `uv run ruff format .`.

## Poradniki:
- https://www.youtube.com/playlist?list=PL0Zuz27SZ-6NamGNr7dEqzNFEcZ_FAUVX
- https://docs.djangoproject.com/en/6.1/intro/tutorial01/
