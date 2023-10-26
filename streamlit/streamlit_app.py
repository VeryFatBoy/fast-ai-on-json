# streamlit_app.py

# Code adapted from:
# https://github.com/singlestore-labs/devrel-notebook-examples/blob/main/json-vector-search-books-example/json-vector-search-books-example.ipynb

import streamlit as st
import json
import openai
import pymongo
import struct

# Constants.

DB_NAME = "bookstore"
EMBEDDINGS_COLLECTION_NAME = "books_with_embedding"
BOOK_EMBEDDINGS_NUMBER = 50

# Initialize connection.
# Uses st.cache_resource to only run once.
@st.cache_resource
def init_connection():
    return pymongo.MongoClient("mongodb://<username>:<password>@<host>:27017/?authMechanism=PLAIN&tls=true&loadBalanced=true")

client = init_connection()

class JSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, ObjectId):
            return str(o)
        return super().default(o)

def create_embedding(data: str | dict) -> list[float]:
    global create_embedding_retries

    if type(data) is dict:
        data = json.dumps(data, cls=JSONEncoder)

    try:
        data = data.replace("\n", " ")
        response = openai.Embedding.create(input=data, model="text-embedding-ada-002")
        create_embedding_retries = 0
        return response["data"][0]["embedding"]
    except Exception as e:
        if create_embedding_retries < 5:
            st.write("An error occurred while creating the embedding. Retrying...", "\n", e)
            create_embedding_retries = create_embedding_retries + 1
            return create_embedding(data)
        else:
            st.write("Maximum retries reached.", "\n", e)

def data_to_binary(data: list[float]):
    format_string = "f" * len(data)
    return struct.pack(format_string, *data)

def search(query: str):
    st.sidebar.write("Searching for", f'"{query}"')

    query_embedding = create_embedding(query)
    query_binary = data_to_binary(query_embedding)
    query_result = embeddingsCollection.aggregate([
        {"$addFields": {"dot": {"$dotProduct": ["$embedding", query_binary]}}},
        {"$project": {"embedding": 0}},
        {"$sort": {"dot": -1}},
        {"$limit": 5},
    ])

    result = list(query_result)

    # st.json(json.dumps(result, cls=JSONEncoder, indent=4))
    
    data = []
    for book in result:
        data.append({
           "Title": book["title"],
           "Description": book["description"][:200] + " ..." if len(book["description"]) > 200 else book["description"],
           "Price": "{:.2f}".format(book["price"])
        })
    st.table(data)

    return

db = client.get_database(DB_NAME)
embeddingsCollection = db[EMBEDDINGS_COLLECTION_NAME]

create_embedding_retries = 0

st.image("images/book-open-cover.png", use_column_width = False)
st.subheader("Book Recommendations")

st.sidebar.subheader("Enter your request")

search_string = st.sidebar.text_input("Enter your request", label_visibility = "hidden")

if search_string:
   search(search_string)
