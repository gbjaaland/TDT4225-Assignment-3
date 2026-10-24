from collections import defaultdict
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
            {"$match": {"movie_count": {"$gte": 5}}},
            
            # sort by highest median revenue
            {"$sort": {"median_revenue": -1}},
            
            # return top 10
            {"$limit": 10}
        ]

        self.fetch_documents_agg("movies", agg_query, 1)

    def q2(self):
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
        agg_query = [
            # expand cast and genres
            { "$unwind":  "$cast"}, 
            
            # groupby actor
            {"$group": {
                "_id": "$cast.id",
                "actor": {"$first": "$cast.name"},
                "movie_count": {"$sum": 1},
                "genres": {"$addToSet": "$genres"}
            }},

            # flatten genre lists into one set of distinct genres
            {"$set": {
                "genres": {
                    "$reduce": {
                        "input": "$genres",
                        "initialValue": [],
                        "in": {"$setUnion": ["$$value", "$$this"]}
                    }
                }
            }},

            # filter actors with at least 10 credited movies
            {"$match": {"movie_count": {"$gte": 10}}},
            
            # only display 5 example genres
            {"$project": {
                "_id": 0, 
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
        agg_query = [
            # only keep movies with a release date
            {"$match": {"release_date": {"$exists": True}}},
 
            # get decade and the 5 top-billed cast members (lowest order first)
            {"$project": {
                "decade": {
                    "$dateTrunc": {
                        "date": "$release_date",
                        "unit": "year",
                        "binSize": 10
                    }
                },
                "top_five_cast": {
                    "$slice": [{"$sortArray": {"input": "$cast", "sortBy": {"order": 1}}}, 5]
                }
            }},
 
            # ignore unknown gender (0), keep female (1) and male (2)
            {"$project": {
                "decade": 1,
                "known_gender": {
                    "$filter": {
                        "input": "$top_five_cast",
                        "cond": {"$in": ["$$this.gender", [1, 2]]}
                    }
                }
            }},
 
            # only keep movies where at least one of the top 5 has a known gender
            {"$match": {"known_gender.0": {"$exists": True}}},
 
            # proportion of female cast per movie
            {"$project": {
                "decade": 1,
                "female_proportion": {
                    "$divide": [
                        {"$size": {"$filter": {"input": "$known_gender", "cond": {"$eq": ["$$this.gender", 1]}}}},
                        {"$size": "$known_gender"}
                    ]
                }
            }},
 
            # group by decade
            {"$group": {
                "_id": {"$dateToString": {"format": "%Y", "date": "$decade"}},
                "avg_female_proportion": {"$avg": "$female_proportion"},
                "movie_count": {"$sum": 1}
            }},
 
            # format output
            {"$project": {
                "_id": 0,
                "decade": "$_id",
                "avg_female_proportion": {"$round": ["$avg_female_proportion", 3]},
                "movie_count": 1
            }},
 
            # sort by highest average female proportion
            {"$sort": {"avg_female_proportion": -1}}
        ]
 
        self.fetch_documents_agg("movies", agg_query, 6)

    def q7(self):
        # a text search requires a text index, a collection can only have one text index
        self.db["movies"].create_index([("overview", "text"), ("tagline", "text")], name="overview_tagline_text")
 
        agg_query = [
            # the text index splits words on hyphens, so "noir" also matches "neo-noir"
            # $text must be in the first stage of the pipeline
            {"$match": {
                "$text": {"$search": "noir"},
                "vote_count": {"$gte": 50}
            }},

            # only keep movies where the word is exactly "noir" or "neo-noir"
            {"$match": {"$or": [
                {"overview": {"$regex": r"(?<![\w-])(neo-)?noir(?![\w-])", "$options": "i"}},
                {"tagline": {"$regex": r"(?<![\w-])(neo-)?noir(?![\w-])", "$options": "i"}}
            ]}},
 
            # sort by highest vote_average
            {"$sort": {"vote_average": -1}},
 
            # return top 20
            {"$limit": 20},
 
            # format output
            {"$project": {
                "_id": 0,
                "title": 1,
                "year": {"$year": "$release_date"},
                "vote_average": 1,
                "vote_count": 1
            }}
        ]
 
        self.fetch_documents_agg("movies", agg_query, 7)
    
    def q8(self):
        agg_query = [
            # only movies with at least 100 votes
            {"$match": {"vote_count": {"$gte": 100}}},
 
            # directors and actors of each movie, cleaning secures that each person only appears once
            {"$project": {
                "vote_average": 1,
                "revenue": 1,
                "directors": {
                    "$filter": {
                        "input": "$crew",
                        "cond": {"$eq": ["$$this.job", "Director"]}
                    }
                }
            }},
 
            # one document per director-actor pair per movie
            {"$unwind": "$directors"},
            {"$unwind": "$actors"},
 
            # a director acting in their own movie is not a pair
            {"$match": {"$expr": {"$ne": ["$directors.id", "$cast.id"]}}},
 
            # group by pair
            {"$group": {
                "_id": {"director_id": "$directors.id", "actor_id": "$actors.id"},
                "director": {"$first": "$directors.name"},
                "actor": {"$first": "$actors.name"},
                "films_count": {"$sum": 1},
                "mean_vote_avg": {"$avg": "$vote_average"},
                "mean_revenue": {"$avg": "$revenue"}  # movies without revenue are ignored
            }},
 
            # filter pairs with at least 3 collaborations
            {"$match": {"films_count": {"$gte": 3}}},
 
            # format output
            {"$project": {
                "_id": 0,
                "director": 1,
                "actor": 1,
                "films_count": 1,
                "mean_vote_avg": {"$round": ["$mean_vote_avg", 2]},
                "mean_revenue": {"$round": ["$mean_revenue", 0]}
            }},
 
            # sort by highest mean vote_average
            {"$sort": {"mean_vote_avg": -1, "films_count": -1}},
 
            # return top 20
            {"$limit": 20}
        ]
 
        self.fetch_documents_agg("movies", agg_query, 8)
    
    def q9(self):
        agg_query = [
            # original_language must exist, since $ne also matches movies without the field
            # production companies have no country in the dataset, so only production_countries is used
            {"$match": {
                "original_language": {"$exists": True, "$ne": "en"},
                "production_countries": {"$in": ["United States of America"]}
            }},
 
            # group by original language
            {"$group": {
                "_id": "$original_language",
                "count": {"$sum": 1},
                "example_title": {"$first": "$title"}
            }},
 
            # format output
            {"$project": {
                "_id": 0,
                "original_language": "$_id",
                "count": 1,
                "example_title": 1
            }},
 
            # sort by highest count
            {"$sort": {"count": -1}},
 
            # return top 10
            {"$limit": 10}
        ]
 
        self.fetch_documents_agg("movies", agg_query, 9)
    
    def q10(self):
        # ratings count and population variance per user, computed in MongoDB
        agg_query = [
            # group by user
            {"$group": {
                "_id": "$user_id",
                "ratings_count": {"$sum": 1},
                "std_pop": {"$stdDevPop": "$rating"}
            }},
 
            # filter users with at least 20 ratings
            {"$match": {"ratings_count": {"$gte": 20}}},
 
            # population variance is the population standard deviation squared
            {"$project": {
                "_id": 0,
                "user_id": "$_id",
                "ratings_count": 1,
                "variance": {"$round": [{"$pow": ["$std_pop", 2]}, 3]}
            }}
        ]
        users = {u["user_id"]: u for u in self.db["ratings"].aggregate(agg_query, allowDiskUse=True)}
 
        # genres per movie in a dictionary, which is much faster than a $lookup for each of the 26 million ratings
        genres_by_movie = {m["_id"]: m.get("genres", []) for m in self.db["movies"].find({}, {"genres": 1})}
 
        # go through all ratings once and collect the distinct genres per user
        genres_by_user = defaultdict(set)
        for rating in self.db["ratings"].find({}, {"_id": 0, "user_id": 1, "movie_id": 1}, batch_size=10000):
            if rating["user_id"] in users:
                genres_by_user[rating["user_id"]].update(genres_by_movie.get(rating["movie_id"], []))
 
        for user_id, user in users.items():
            user["distinct_genres"] = len(genres_by_user[user_id])
 
        print("---QUERY NR: 10---")
 
        # most genre-diverse users, ties are broken by number of ratings
        print("Top 10 most genre-diverse users:")
        for user in sorted(users.values(), key=lambda u: (u["distinct_genres"], u["ratings_count"]), reverse=True)[:10]:
            pprint(user)
 
        # highest-variance users
        print("Top 10 highest-variance users:")
        for user in sorted(users.values(), key=lambda u: u["variance"], reverse=True)[:10]:
            pprint(user)
    
def main():
    program = None
    try:
        program = Queries()
        #for q in [program.q1, program.q2, program.q3, program.q4, program.q5, program.q6, program.q7, program.q8, program.q9, program.q10]: 
        for q in [program.q10]:
            q()
    except Exception as e:
        print("ERROR: Failed to use database:", str(e)[:500])
    finally:
        if program:
            program.connection.close_connection()


if __name__ == "__main__":
    main()