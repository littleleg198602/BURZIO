# news_impact_yahoo

`news_impact_yahoo` je modulární Python projekt pro analýzu toho, jak jsou zprávy z Yahoo Finance následované pohybem cen akcií u tickerů `NVDA`, `AAPL`, `MSFT`, `AMD` a `TSLA`.

Projekt používá pouze bezplatné zdroje založené na Yahoo:

- historické denní ceny z `yfinance`
- zprávy pro jednotlivé tickery z Yahoo Finance RSS feedů

Data se ukládají do SQLite, aby se dala opakovaně používat bez duplicit. Pipeline počítá cenovou reakci po každé zprávě pro +1, +3, +5 a +10 obchodních dní, extrahuje slova, bigramy a trigramy z titulků a souhrnů, vypočítá statistiky frází a exportuje Excel se samostatným listem pro každý ticker a listem `PHRASE_STATS`.

> Projekt je pouze analytický. Neobchoduje a negeneruje obchodní pokyny.

## Instalace

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Pro vývojové testy:

```bash
pip install -e '.[dev]'
```

## Spuštění

```bash
python -m src.main
```

Volitelné argumenty:

```bash
python -m src.main --db data/news_impact_yahoo.sqlite --output data/news_impact_yahoo.xlsx --tickers NVDA AAPL MSFT AMD TSLA
```

## Výstup

- SQLite databáze s tabulkami `prices`, `news`, `reactions` a `phrase_stats`
- Excel soubor s listy pro jednotlivé tickery a souhrnným listem `PHRASE_STATS`
