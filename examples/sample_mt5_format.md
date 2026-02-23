# Sample MT5 CSV format (expected input draft)

Task 2 will implement the final parser and field mapping. This is a **draft example** of expected MT5 H1 export columns.

```csv
Date,Time,Open,High,Low,Close,TickVolume,Spread,RealVolume,Symbol
2024.01.02,00:00,1.10345,1.10412,1.10298,1.10387,1245,15,0,EURUSD
2024.01.02,01:00,1.10387,1.10420,1.10350,1.10361,987,14,0,EURUSD
```

Notes:
- Date/time format can vary by MT5 export settings.
- Symbol may be embedded in file name instead of a CSV column for some brokers.
- Final normalization schema and timezone handling will be implemented in Task 2.
