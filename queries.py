from pprint import pprint 
from DbConnector import DbConnector

class Queries:
    def __init__(self):
        self.connection = DbConnector()
        self.client = self.connection.client
        self.db = self.connection.db
    
    def fetch_documents_agg(self, collection_name, agg_query, query_nr):
        collection = self.db[collection_name]
        documents = collection.aggregate(agg_query)
        print(f"---QUERY NR: {query_nr}---")
        for doc in documents: 
            pprint(doc)
            
    def q1(self):
        """
        Considering only crew with job = Director, which 10 directors with ≥ 5 movies
        have the highest median revenue?
        Also report each director’s movie count and mean vote_average.
        """
        agg_query = [
            # expand crew
            { "$unwind":  "$crew"}, 
            
            # filter on directors
            { "$match":  {"crew.job":"Director"}}, 
            
            # groupby director
            {"$group": {
                "_id": "$crew.id",
                "director": {"$first": "$crew.name"},
                "movie_count": {"$sum": 1},
                "mean_vote_avg": { 
                    "$avg": {
                        "$cond" : [
                            {"$gt": ["$vote_count", 0]}, # don't include vote_average where vote_count = 0
                            "$vote_average",
                            None
                        ]
                    }
                },
                "median_revenue": {
                    "$median": {
                        "input": "$revenue",
                        "method": "approximate"
                    }
                }
            }
            },
            
            # format output
            {"$project":
                {"_id":0,
                "director": 1, 
                "median_revenue": 1,
                "movie_count": 1,
                "mean_vote_avg": {"$round": ["$mean_vote_avg", 2]}
                }  
            },
            
            # filter directors with more than 5 movies
            {"$match": {"movie_count": {"$gt": 5}}},
            
            # sort by highest median revenue
            {"$sort": {"median_revenue": -1}},
            
            # return top 10
            {"$limit": 10}
        ]

        self.fetch_documents_agg("movies", agg_query, 1)

    def q2(self):
        """
        List actor pairs have co-starred in >= 3 movies together, their number of
        co-appearances, and their average movie vote_average. Sort by number of
        co-appearances.
        """
        
        agg_query = [
            # duplicate cast to construct co-starred pairs
            {"$project": {
                    "movie_id": "_id",
                    "vote_count": 1,
                    "vote_average": 1,
                    "cast": 1,
                    "cast_duplicated": "$cast"
                }
            },
                
            # unwind both casts 
            {"$unwind": "$cast"},
            {"$unwind": "$cast_duplicated"},

            # only keep one pair and don't pair an actor with themselves
            {"$match": {
                    "$expr": {
                        "$lt": ["$cast.id", "$cast_duplicated.id"]
                    }
                }
            },
            
            # group by pairs
            {"$group": {
                "_id": {
                    "actor_id_1": "$cast.id",
                    "actor_id_2": "$cast_duplicated.id"
                },
                "actor_name_1": {"$first": "$cast.name"},
                "actor_name_2": {"$first": "$cast_duplicated.name"},
                "co_appearance_nr": {"$sum": 1},
                "mean_vote_avg": { 
                        "$avg": {
                            "$cond" : [
                                {"$gt": ["$vote_count", 0]}, # don't include vote_average where vote_count = 0
                                "$vote_average",
                                None
                            ]
                        }
                },
            }},
            
            # format output
            {"$project":
                {"_id":0,
                "actor_name_1": 1, 
                "actor_name_2": 1, 
                "co_appearance_nr": 1,
                "mean_vote_avg": {"$round": ["$mean_vote_avg", 2]}
                }  
            },
            
            # filter on co-appearance >= 3
            {"$match": {"co_appearance_nr": {"$gte": 3}}},
            
            # sort by highest nr of co-appearance 
            {"$sort": {"co_appearance_nr": -1}},
            
            # return top 10 if wanted
            {"$limit": 10}
                
        ]
        
        self.fetch_documents_agg("movies", agg_query, 2)
    
    def q3(self):
        """
        List the top 10 actors (with ≥ 10 credited movies) that have the widest genre
        breadth. Report the actor, the number of distinct genres they’ve appeared in,
        and up to 5 example genres.
        """
        
        agg_query = [
            # expand cast and genres
            { "$unwind":  "$cast"}, 
            
            # groupby actor
            {"$group": {
                "_id": "$cast.id",
                "actor": {"$first": "$cast.name"},
                "movie_count": {"$sum": 1},
                "genres": {"$setUnion": "$genres"}
            }},
            
            # filter actors with at least 10 credited movies
            {"$match": {"movie_count": {"$gte": 10}}},
            
            # only display 5 example genres
            {"$project": {
                "actor": 1,
                "genres_count": {"$size": "$genres"},
                "first_five_genres": {"$slice": ["$genres", 5]}
            }},
            
            # sort by widest genre breadth
            {"$sort": {"genres_count": -1}},
            
            # return top 10
            {"$limit": 10}
        ]
        
        self.fetch_documents_agg("movies", agg_query, 3)
    
    def q4(self):
        """
        For film collections (belongs_to_collection.name not null) with ≥ 3 movies, which
        10 collections have the largest total revenue?
        For each, report movie count, total revenue, median vote_average, and the
        earliest → latest release date.
        """
        agg_query = [
            
            # project movie count, total revenue, median vote_average, and the earliest  and latest release date
            {"$project": {
                "_id": 0,
                "name": 1,
                "movie_count": {"$size": "$movies"},
                "total_revenue": {"$sum": "$movies.revenue"},
                "median_vote_avg": {
                    "$median": {
                        "input": {
                            "$map": {
                                "input": "$movies",
                                "in": {
                                    "$cond": [
                                        {"$gt": ["$$this.vote_count", 0]},
                                        "$$this.vote_average",
                                        None
                                    ]
                                }
                            }
                        },
                        "method": "approximate"
                    }
                },
                "earliest_release_date": {
                    "$dateToString": {
                        "format": "%Y-%m-%d", 
                        "date": {"$min": "$movies.release_date"}
                    },
                },
                "latest_release_date": {
                    "$dateToString": {
                        "format": "%Y-%m-%d", 
                        "date": {"$max": "$movies.release_date"}
                    },
                }
            }},
            
            # filter collections with at least 3 movies
            {"$match": {"movie_count": {"$gte": 3}}},
            
            # sort by revenue
            {"$sort": {"total_revenue": -1}},
                        
            # return top 10
            {"$limit": 10} 
        ]
        
        self.fetch_documents_agg("collections", agg_query, 4)
    
    def q5(self):
        """
        By decade (e.g., 1970s, 1980s, ...) and primary genre (first element in genres),
        what is the median runtime and movie count?
        List results sorted by decade then median runtime (desc).
        """
        
        agg_query = [
            # only keep movies with a releasedate and genres
            {"$match": {"release_date": {"$exists": True}, "genres.0": {"$exists": True}}},

            # get decade, primary genre and runtime
            {"$project": {
                "decade": {
                    "$dateTrunc": {
                        "date": {"$toDate": "$release_date"}, 
                        "unit": "year", 
                        "binSize":10
                    },
                },
                "primary_genre": {
                    "$arrayElemAt": ["$genres", 0]
                },
                "runtime": 1
            }},
            
            # group by decade and primary genre
            {"$group": {
                "_id": {
                    "decade": {
                        "$dateToString": {
                            "format": "%Y",
                            "date": "$decade"
                        }
                    },
                    "primary_genre": "$primary_genre"
                },
                "movie_count": {"$sum": 1},
                "median_runtime": {
                    "$median": {
                        "input": "$runtime",
                        "method": "approximate"
                    }
                }
            }},
            
            # format output 
            {"$project": {
                "_id": 0,
                "decade": "$_id.decade",
                "primary_genre": "$_id.primary_genre",
                "median_runtime": 1,
                "movie_count": 1
            }},
            
            # sort by decade ascending and median runtime descending
            {"$sort": {"decade": 1, "median_runtime": -1}},
        ]
        
        self.fetch_documents_agg("movies", agg_query, 5)

    def q6(self):
        return 

    def q7(self):
        return 
    
    def q8(self):
        return 
    
    def q9(self):
        return 
    
    def q10(self):
        return 
    
def main():
    program = None
    try:
        program = Queries()
        for q in [program.q1, program.q2, program.q3, program.q4, program.q5, program.q6, program.q7, program.q8, program.q9, program.q10]: 
            q()
    except Exception as e:
        print("ERROR: Failed to use database:", str(e)[:500])
    finally:
        if program:
            program.connection.close_connection()


if __name__ == "__main__":
    main()