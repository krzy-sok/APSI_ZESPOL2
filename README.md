## Jak uruchomić serwer?

- uzupełnij pola w pliku ```.env-template``` i mznień jego nazwę na ```.env```
- uruchom ```docker-compose up``` jesli pojawia się błąd ```permission denied while trying to connect to the docker API ``` uruchom jako root
- zainstaluj narzędzie uv albo stwórz środowisko i uruchom wirtualne oraz zainstaluj zależności przez ```pip install .```
- uruchom projekt przez ```uv run manage.py migrate && uv run manage.py runserver``` lub ```python -m manage.py migrate && python -m run manage.py runserver```

## Jak wejść na stronę administracyjną?
- dodaj superusera ```uv run manage.py addsuperuser ``` albo ```python -m manage.py addsuperuser ```
- uruchom serwer i wejdź na ``` /admin ```

## Poradniki:
- https://www.youtube.com/playlist?list=PL0Zuz27SZ-6NamGNr7dEqzNFEcZ_FAUVX
- https://docs.djangoproject.com/en/6.1/intro/tutorial01/