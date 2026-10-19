import ast
import csv, io
from collections import defaultdict
from DbConnector import DbConnector
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from pprint import pprint 


class DataCleaning:
    
    def __init__(self):
        self.connection = DbConnector()
        self.client = self.connection.client
        self.db = self.connection.db
    
    def read_movies_metadata(self):
        with open('data' + '/movies_metadata.csv', encoding='utf-8', newline='') as f:
            rows = list(csv.reader(f))

        # merge records that were split by a line break in overview
        fixed = [rows[0]]
        bad_rows = 0 
        for row in rows[1:]:
            if len(fixed[-1]) < len(rows[0]):          # previous row is incomplete
                first_half = fixed.pop()
                row = first_half[:-1] + [first_half[-1] + ' ' + row[0].strip()] + row[1:]
                bad_rows += 1
            fixed.append(row)

        # let pandas read the repaired data
        buf = io.StringIO()
        csv.writer(buf).writerows(fixed)
        buf.seek(0)

        return pd.read_csv(buf)

    def clean_whitespace(self, df):
        # collapse repeated whitespace, trim ends, and turn remaining empty strings into NaN
        text_cols = df.select_dtypes(include=["object", "string"]).columns
        for col in text_cols:
            df[col] = (
                df[col]
                .str.replace(r"\s+", " ", regex=True)
                .str.strip()
                .replace("", np.nan)
            )
        return df

    def explode_credits(self, credits_df, column):
        # one row per cast/crew entry, keeping which movie it belongs to
        exploded = credits_df[["id", column]].explode(column).dropna(subset=[column])
        df = pd.json_normalize(exploded[column].tolist())
        df["movie_id"] = exploded["id"].to_numpy()
        return df
    
    
    def build_movie_docs(self, mm_df, cast_df, crew_df):
        mm_df = mm_df.copy()
        mm_df["production_companies"] = mm_df["production_companies"].apply(self.parse_names)
        mm_df["production_countries"] = mm_df["production_countries"].apply(self.parse_names)
        mm_df["release_date"] = pd.to_datetime(mm_df["release_date"], errors="coerce")

        cast_by_movie = self.group_by_movie(cast_df, ["id", "name", "order", "gender"])
        crew_by_movie = self.group_by_movie(crew_df, ["id", "name", "job"])

        movie_cols = [
            "id", "title", "genres", "original_language", "production_companies",
            "production_countries", "release_date", "revenue", "runtime",
            "vote_count", "vote_average", "overview", "tagline"
        ]
        
        movies = []
        
        for record in mm_df[movie_cols].to_dict(orient="records"):
            doc = self.drop_missing(record)
            doc["_id"] = doc.pop("id")
            doc["cast"] = cast_by_movie.get(doc["_id"], [])
            doc["crew"] = crew_by_movie.get(doc["_id"], [])
            movies.append(doc)
            
        return movies

    def build_collection_docs(self, mm_df):
        mm_df = mm_df.copy()
        mm_df["collection"] = mm_df["belongs_to_collection"].apply(self.parse_dict)
        mm_df["release_date"] = pd.to_datetime(mm_df["release_date"], errors="coerce")
        in_collection = mm_df[mm_df["collection"].notna()]

        collections = {}
        
        cols = ["collection", "id", "title", "genres", "original_language", 
            "production_companies", "production_countries", "release_date", "revenue", 
            "runtime", "vote_count", "vote_average", "overview", "tagline"
        ]
        
        for record in in_collection[cols].to_dict(orient="records"):
            coll = record.pop("collection")
            entry = collections.setdefault(
                coll["id"], {"_id": coll["id"], "name": coll["name"], "movies": []}
            )
            entry["movies"].append(self.drop_missing(record))
            
        return list(collections.values())

    def group_by_movie(self, df, cols):
        grouped = defaultdict(list)
        for record in df[["movie_id"] + cols].to_dict(orient="records"):
            movie_id = record.pop("movie_id")
            grouped[movie_id].append(self.drop_missing(record))
        return grouped

    def parse_names(self, value):
        if not isinstance(value, str):
            return []
        parsed = ast.literal_eval(value)
        return [item["name"] for item in parsed] if isinstance(parsed, list) else []

    def parse_dict(self, value):
        if not isinstance(value, str):
            return None
        parsed = ast.literal_eval(value)
        return parsed if isinstance(parsed, dict) else None

    def drop_missing(self, record):
        # leave out NaN so the field is absent instead of stored as NaN
        return {
            k: v for k, v in record.items()
            if isinstance(v, (list, dict)) or not pd.isna(v)
        }

    def cleaning(self):
        mm_df = self.read_movies_metadata()
        
        # remove duplicate ids
        mm_df_unique = mm_df.drop_duplicates(subset="id", keep="last")
        print(f"Removed {mm_df.shape[0] - mm_df_unique.shape[0]:,} duplicate movie rows")
        
        # clean text columns
        nan_before = mm_df_unique.isna().sum().sum()
        mm_df_stripped = self.clean_whitespace(mm_df_unique.copy())
        print(f"Replaced {mm_df_stripped.isna().sum().sum() - nan_before:,} empty text values with NaN")

        # replace 0 values with NaN for vote_average where vote_count = 0
        no_votes = mm_df_stripped["vote_count"] == 0
        mm_df_stripped.loc[no_votes, "vote_average"] = np.nan
        print(f"Replaced {no_votes.sum():,} vote_average values with NaN where vote_count is 0")

        # replace 0 with Nan for budget, revenue and runtime
        zero_cols = ["budget", "revenue", "runtime"]
        zero_counts = (mm_df_stripped[zero_cols] == 0).sum()
        mm_df_stripped[zero_cols] = mm_df_stripped[zero_cols].replace(0, np.nan).astype("Int64") 
        print(f"Replaced 0 with NaN: {zero_counts.to_dict()}")
        
        # replace the strange values for tagline and overview
        place_holders = ["-", "", "...", "x", "No overview found", "No Overview"]
        text_cols = ["tagline", "overview"]
        placeholder_counts = mm_df_stripped[text_cols].isin(place_holders).sum()
        mm_df_stripped[text_cols] = mm_df_stripped[text_cols].replace(place_holders, np.nan)
        print(f"Replaced placeholders with NaN: {placeholder_counts.to_dict()}")
        
        # remove values for tagline where it is identical to overview or title
        same_tagline = (mm_df_stripped["tagline"] == mm_df_stripped["overview"]) | (mm_df_stripped["tagline"] == mm_df_stripped["title"])
        mm_df_stripped.loc[same_tagline, "tagline"] = np.nan
        print(f"Removed {same_tagline.sum():,} taglines identical to overview or title")
        
        # remove values for overview where it is identical to title
        same_overview = mm_df_stripped["overview"] == mm_df_stripped["title"]
        mm_df_stripped.loc[same_overview, "overview"] = np.nan
        print(f"Removed {same_overview.sum():,} overviews identical to title")   
           
        # only keep genre name
        mm_df_stripped["genres"] = mm_df_stripped["genres"].apply(
            lambda g: [genre["name"] for genre in ast.literal_eval(g)] if isinstance(g, str) else []
        )
        
        # read credits
        credits_df = pd.read_csv('data' + '/credits.csv', converters={'cast': ast.literal_eval, 'crew': ast.literal_eval})

        # keep first duplicate
        credits_unique = credits_df.drop_duplicates(subset="id", keep="first")
        print(f"Removed {credits_df.shape[0] - credits_unique.shape[0]:,} duplicate credit rows")
        
        cast_df = self.explode_credits(credits_unique, "cast")
        crew_df = self.explode_credits(credits_unique, "crew")
        
        for df in (cast_df, crew_df):
            # keep the name with the higher index, replace all others names with that na,e
            df["name"] = df.groupby("id")["name"].transform("last")

            # keep the non-zero gender values
            df["gender"] = df.groupby("id")["gender"].transform("max")
        
        # remove actors listed for the same character twice
        before = cast_df.shape[0]
        cast_df = cast_df.drop_duplicates(subset=["movie_id", "id", "character"])
        print(f"Removed {before - cast_df.shape[0]:,} actors listed twice for the same character")
    
        # create documents on the format that fits the collections
        movies = self.build_movie_docs(mm_df_stripped, cast_df, crew_df)
        collections = self.build_collection_docs(mm_df_stripped)
        print(f"Built {len(movies):,} movie documents and {len(collections):,} collection documents")

        return {"movies": movies, "collections": collections}

    def create_coll(self, collection_name):
        collection = self.db.create_collection(collection_name)    
        print('Created collection: ', collection)

    def insert_documents(self, collection_name, docs):
        collection = self.db[collection_name]
        collection.insert_many(docs, ordered=False)
        print(f"Inserted {len(docs):,} documents into {collection_name}")
        
        
    def fetch_documents(self, collection_name):
        collection = self.db[collection_name]
        documents = collection.find({})
        for doc in documents: 
            pprint(doc)
        

    def drop_coll(self, collection_name):
        collection = self.db[collection_name]
        collection.drop()

def main():
    program = None
    try:
        program = DataCleaning()
        docs = program.cleaning()
        program.insert_documents("movies", docs["movies"])
        program.insert_documents("collections", docs["collections"])
    except Exception as e:
        print("ERROR: Failed to use database:", e)
    finally:
        if program:
            program.connection.close_connection()


if __name__ == '__main__':
    main()
