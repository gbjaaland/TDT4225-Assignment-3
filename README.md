# TDT4225-Assignment-3

## Code structure

```
.
├── data/                  # uncommitted raw CSV files from The Movies Dataset
├── EDA/                   # Jupyter notebooks with exploratory data analysis
├── results/               # output of each query, one file per query
├── DbConnector.py         # connection to the MongoDB database
├── data_cleaning.py       # cleans the CSV files and inserts them into MongoDB
├── queries.py             # aggregation pipelines for queries 1-10
├── example.py             # example program from the assignment handout
└── requirements.txt
```

### `DbConnector.py`
Connects to the `movies` database on MongoDB. Host, user and password are set as default arguments in the constructor.

### `data_cleaning.py`
The `DataCleaning` class reads the raw CSV files, cleans them and inserts three collections:

- **`movies`**: one document per movie, with cast, crew and keywords embedded.
- **`collections`**: one document per film collection (e.g. a franchise), with its movies embedded.
- **`ratings`**: one document per rating, linked to `movies` through `movie_id` (the TMDB id).

### `queries.py`
The `Queries` class has one method per query (`q1`-`q10`). Each method builds an aggregation pipeline and prints the result. 

### `EDA/`
One notebook per source file (`movies_metadata`, `credits`, `keywords`, `links`, `ratings`) and one for checks across files (`cross_file`).

## How to run
1. Install the dependencies: `pip install -r requirements.txt`.
2. Put the CSV files in `data/`.
3. Set the connection details in `DbConnector.py`.
4. Clean and insert the data: `python data_cleaning.py`
5. Run all queries: `python run_queries.py`
