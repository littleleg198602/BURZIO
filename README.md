# news_impact_yahoo

`news_impact_yahoo` je modulární Python projekt pro analýzu toho, jak jsou zprávy z Yahoo Finance následované pohybem cen akcií u tickerů `NVDA`, `AAPL`, `MSFT`, `AMD` a `TSLA`.

Projekt používá pouze bezplatné zdroje založené na Yahoo:

- historické denní ceny z `yfinance`
- zprávy pro jednotlivé tickery z Yahoo Finance RSS feedů a Yahoo Search výsledků

Ceny se stahují za 5 let. Zprávy se systém pokusí doplnit z Yahoo RSS i Yahoo Search pro 5leté okno, ale Yahoo zdarma negarantuje kompletní historický archiv zpráv. Data se ukládají do SQLite, aby se dala opakovaně používat bez duplicit. Pipeline počítá cenovou reakci po každé zprávě pro +1, +3, +5 a +10 obchodních dní, extrahuje slova, bigramy a trigramy z titulků a souhrnů, vypočítá statistiky frází a exportuje Excel se samostatným listem pro každý ticker a listem `PHRASE_STATS`.

> Projekt je pouze analytický. Neobchoduje a negeneruje obchodní pokyny.

## Nejjednodušší spuštění na Windows

V kořenové složce projektu dvakrát klikni na:

```bat
Spustit_Yahoo_Analyzer.bat
```

Tenhle spouštěč sám vytvoří lokální složku `.venv`, do ní nainstaluje potřebné knihovny a spustí Streamlit web. Ručně tedy nemusíš psát instalační příkazy do terminálu. Při prvním spuštění to může chvíli trvat, další spuštění už jen otevře aplikaci.

Zachovaný kratší alias:

```bat
run_streamlit.bat
```

## Ruční instalace, pokud ji chceš dělat sám

Otevři terminál v kořenové složce projektu, tedy ve složce, kde je `pyproject.toml`.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .
```

Na macOS/Linux aktivuj prostředí takto:

```bash
source .venv/bin/activate
```

Pro vývojové testy:

```bash
pip install -e '.[dev]'
```

## Streamlit aplikace ručně

```bash
python -m streamlit run src/streamlit_app.py
```

Streamlit otevře lokální webovou aplikaci, kde zadáš tickery, cestu k SQLite databázi, cestu k Excel výstupu a klikneš na **Spustit analýzu**.

Alternativní Python spouštěč:

```bash
python run_streamlit.py
```

Na macOS/Linux můžeš použít:

```bash
./run_streamlit.sh
```

## CLI spuštění bez webového rozhraní

```bash
python -m src.main
```

Volitelné argumenty:

```bash
python -m src.main --db data/news_impact_yahoo.sqlite --output data/news_impact_yahoo.xlsx --tickers NVDA AAPL MSFT AMD TSLA
```

## Výstup

- SQLite databáze s tabulkami `prices`, `news`, `reactions` a `phrase_stats`
- Excel soubor s listem `NAVOD`, listy pro jednotlivé tickery a souhrnným listem `PHRASE_STATS`
- Ticker listy obsahují titulky, shrnutí, vytažené fráze, cenu při zprávě, budoucí ceny, procentní reakce, směr a `Impact score`
- České popisky v Excelu: `Reakce +1 den`, `Průměrný výnos`, `Úspěšnost růstu`, `Skóre jistoty`
- Pokud je `PHRASE_STATS` prázdný, znamená to obvykle, že Yahoo RSS vrátilo příliš nové zprávy a ještě nejsou dostupné budoucí obchodní dny pro výpočet reakcí
- Streamlit náhled statistik frází, detailů tickeru a tlačítko pro stažení Excelu
