# -*- coding: utf-8 -*-
"""Untitled7.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1srOZcnIfb32Bk4J3dCNMMpEDluPsU-xq

## LIBRARY OR TOOL USED
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px
import plotly.graph_objects as go
from pyspark.sql import SparkSession
from pyspark.ml.recommendation import ALS
from pyspark.ml.evaluation import RegressionEvaluator
from pyspark.sql.functions import col
from pyspark.sql.types import FloatType, IntegerType
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel
from tabulate import tabulate

"""# load the CSV files"""

listings_df = pd.read_csv('listings.csv')
reviews_df = pd.read_csv('reviews.csv')
neighbourhoods_df = pd.read_csv('neighbourhoods.csv')
listings_df

"""# data cleaning
in this section we drop rows with missing values. dropped columns that werent important for m work and changed the dtype of listing_df
"""

if 'reviews_per_month' in listings_df.columns:
  listings_df['reviews_per_month' ] = listings_df['reviews_per_month' ]. fillna(0)
listings_df.dropna(inplace=True)
columns_to_drop = ['longitude', 'latitude', 'license']
listings_df = listings_df.drop(columns=[col for col in columns_to_drop if col in listings_df.columns])
if 'last_review' in listings_df.columns:
  listings_df['last_review' ] = pd.to_datetime(listings_df['last_review' ])
listings_df

"""in thus section we dropped duplicate data and changed the data type of reviews_df"""

reviews_df['date'] = pd.to_datetime(reviews_df['date'])
reviews_df = reviews_df. drop_duplicates()

"""light cleaning since its not a big dataset"""

neighbourhoods_df = neighbourhoods_df.drop_duplicates () .dropna()

listings_df.info()
reviews_df.info()
neighbourhoods_df.info()

"""# Merging
we merge listing, review and neighbourhood data set
"""

reviews_df = reviews_df.rename(columns={'listing_id': 'id'})
merge_df = pd.merge(listings_df, reviews_df, on='id', how ='left')
if 'neighbourhood' in neighbourhoods_df.columns and 'neighbourhood' in merge_df.columns:
  merge_df = pd.merge(merge_df, neighbourhoods_df, on='neighbourhood', how='left')
merge_df

"""

* selected the features and target(what we want to predict) and drops rows with missing data.
* did the train test split





"""

features = ['room_type', 'number_of_reviews','availability_365', 'neighbourhood_group_x']
target = 'price'
model_df = merge_df[features + [target]].dropna()

model_df = pd.get_dummies(model_df, columns=['room_type', 'neighbourhood_group_x'])

from sklearn.model_selection import train_test_split
X = model_df.drop(columns=['price'])
y = model_df['price']
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
model_df

print("X_train shape:", X_train.shape)
print("X_test shape:", X_test.shape)
print("y_train shape:", y_train.shape)
print("y_test shape:", y_test.shape)

"""# Data Visualisation
Bar chart of the average price of a listing per neighbourhood group
"""

average_price = merge_df.groupby('neighbourhood_group_x')['price'].mean().sort_values(ascending=False)
sns.barplot(x=average_price.index, y=average_price.values, palette='bone')

plt.xlabel('Neighbourhood Group')
plt.xticks(rotation=90)

plt.ylabel('Average Price')
plt.title('Average Price by Neighbourhood Group')
plt.show()

"""strip plot showing how manz reviews a month each neighbourhood grouop gets"""

plt.figure(figsize=(10, 6))
sns.stripplot(data=merge_df, x='neighbourhood_group_x', y='reviews_per_month',palette='Oranges_d', jitter=True, alpha=0.4)
plt.title('Reviews per Month by Neighbourhood Group')
plt.xlabel('Neighbourhood Group')
plt.ylabel('Reviews per Month')
plt.xticks(rotation=45, ha='right')
plt.grid(True)
plt.show()

"""line chart showing how availabilitz can affect pricing"""

bins = list(range(0, 366, 30))
bins[-1] = 366
labels = [f"{i}-{i+29}" if i+29 < 365 else f"{i}-365" for i in bins[:-1]]

merge_df['availability_bin_30'] = pd.cut(
    merge_df['availability_365'],
    bins=bins,
    labels=labels,
    right=False
)
avg_price_by_bin = (
    merge_df.groupby('availability_bin_30')['price']
    .mean()
    .reset_index()
    .rename(columns={'price': 'average_price'})
)
plt.figure(figsize=(12, 6))
sns.lineplot(
    data=avg_price_by_bin,
    x='availability_bin_30',
    y='average_price',
    marker='o'
)
plt.title('Average Price by Availability')
plt.xlabel('Availability Range')
plt.ylabel('Average Price')
plt.xticks(rotation=45)
plt.grid(True)
plt.tight_layout()
plt.show()

"""# collaborative filtering
since the reviews data set had no ratings i assigned a random number between 1-1000 as a reviewer_id
then i trained the recommendation szstem so that itll recommend listing based on the similarities between zou and another user.
"""

spark = SparkSession.builder.appName("AirbnbRecommender").getOrCreate()
reviews_df = pd.read_csv('reviews.csv', parse_dates=['date'])
np.random.seed(42)
reviews_df['reviewer_id'] = np.random.randint(1, 1001, reviews_df.shape[0])
reviews_df['rating'] = 1

spark_df = spark.createDataFrame(reviews_df[['reviewer_id', 'listing_id', 'rating']])
ratings = spark_df.select(
    col('reviewer_id').cast(IntegerType()).alias('userId'),
    col('listing_id').cast(IntegerType()).alias('itemId'),
    col('rating').cast(FloatType())
)
(train, test) = ratings.randomSplit([0.8, 0.2], seed=42)

als = ALS(
    maxIter=10,
    regParam=0.1,
    rank=10,
    userCol='userId',
    itemCol='itemId',
    ratingCol='rating',
    coldStartStrategy='drop',
    nonnegative=True,
    implicitPrefs=True
)
model = als.fit(train)
user_recs = model.recommendForAllUsers(5)
user_recs.show(truncate=False)

itemRecs = model.recommendForAllItems(5)
itemRecs.show(5, truncate=False)

"""# Content based filtering
uses the content(text) to find other content that are similar to it eg room type, neighbourhoog group etc then recommends other listings baased on that
"""

df = pd.read_csv('listings.csv')
#data cleaning
df['price'] = df.groupby(['neighbourhood_group', 'room_type'])['price'].transform(lambda x: x.fillna(x.median()))
df['name'] = df['name'].fillna('')
df['neighbourhood'] = df['neighbourhood'].fillna('')

# Create a combined text feature for content analysis
df['content_features'] = (
    df['name'] + ' ' +
    df['neighbourhood_group'] + ' ' +
    df['neighbourhood'] + ' ' +
    df['room_type']
)

tfidf = TfidfVectorizer(stop_words='english')
tfidf_matrix = tfidf.fit_transform(df['content_features'])

#get the cosine similarity matrix
cosine_sim = linear_kernel(tfidf_matrix, tfidf_matrix)

# Create a reverse mapping of indices to listing names
indices = pd.Series(df.index, index=df['name']).drop_duplicates()

def get_content_based_recommendations(title, n=5):
    try:
        idx = indices[title]

        # Get the pairwise similarity scores
        sim_scores = list(enumerate(cosine_sim[idx]))

        # Sort the listings based on the similarity scores
        sim_scores = sorted(sim_scores, key=lambda x: x[1], reverse=True)

        # Get the scores of the most similar listings
        sim_scores = sim_scores[1:n+1]

        # Get the listing indices
        listing_indices = [i[0] for i in sim_scores]

        # Return the top n most similar listings
        recommendations = df.iloc[listing_indices][[
            'name', 'neighbourhood_group', 'neighbourhood',
            'room_type', 'price', 'number_of_reviews'
        ]]

        # to make it more readable
        recommendations['similarity'] = [f"{s[1]*100:.1f}%" for s in sim_scores]
        recommendations['price'] = '€' + recommendations['price'].astype(int).astype(str)

        # show the name of the airbnb you want to recommend
        original = df.iloc[idx]
        print("\n" + "-"*80) #to divide everything neatly
        print(f"FINDING RECOMMENDATIONS SIMILAR TO:")
        print(f"Name: {original['name']}")
        print(f"Type: {original['room_type']}")
        print(f"Area: {original['neighbourhood_group']} ({original['neighbourhood']})")
        print(f"Price: €{original['price']:.0f}")
        print("-"*80 + "\n")

        # Print recommendations as a table
        print(tabulate(
            recommendations.rename(columns={
                'name': 'Recommended Listing',
                'neighbourhood_group': 'District',
                'neighbourhood': 'Neighborhood',
                'room_type': 'Type',
                'number_of_reviews': 'Reviews'
            }),
            headers='keys',
            tablefmt='pretty',
            showindex=False
        ))
    #if theres a mistake
    except KeyError:
        print("Listing not available")


#put the name of the listing here to check for recommendations:
get_content_based_recommendations("Fabulous Flat in great Location")

"""# Mean Squared Error
MSE of collaborative filtering
"""

from pyspark.ml.evaluation import RegressionEvaluator

# get the predictions on test data
predictions = model.transform(test)

# Evaluate using MSE
evaluator = RegressionEvaluator(metricName="mse",
                              labelCol="rating",
                              predictionCol="prediction")
mse = evaluator.evaluate(predictions)
print(f"MSE of collaborative filtering: {mse}")

"""MSE for content based filtering"""

#Prepare the data
df = pd.read_csv('listings.csv')

#turns texts to numerical values
tfidf = TfidfVectorizer(stop_words='english')
df['content_features'] = (
    df['name'] + ' ' +
    df['neighbourhood_group'] + ' ' +
    df['neighbourhood'] + ' ' +
    df['room_type']
)
tfidf_matrix = tfidf.fit_transform(df['content_features'])

#get the cosine similarity matrix
cosine_sim = linear_kernel(tfidf_matrix, tfidf_matrix)


def content_based_mse(df, cosine_sim):
    y_true = []
    y_pred = []

    # Compare each listing to 1000 random others
    np.random.seed(42)
    sample_indices = np.random.choice(len(df), 1000, replace=False)

    for idx in sample_indices:
        original = df.iloc[idx]
        # Compare to 10 random listings
        for j in np.random.choice(len(df), 10, replace=False):
            recommended = df.iloc[j]

            truth = 1.0 if (original['neighbourhood_group'] == recommended['neighbourhood_group']) and \
                          (original['room_type'] == recommended['room_type']) else 0.0
            y_true.append(truth)
            y_pred.append(cosine_sim[idx][j])

    return mean_squared_error(y_true, y_pred)

mse = content_based_mse(df, cosine_sim)
print(f"MSE of Content-Based filtering: {mse:.4f}")

"""# MSE Comparison
compare to understand which works better then visualise the data
"""

systems = ["Content-Based", "Collaborative)"]
mse_values = [ 0.0635, 0.566872516565989]

plt.figure(figsize=(6, 4))
bars = plt.bar(systems, mse_values, color=["skyblue", "lightgreen"])
plt.title("MSE Comparison", fontsize=14)
plt.ylabel("Mean Squared Error", fontsize=12)
plt.ylim(0, 0.7)

plt.grid(axis="y", linestyle="--", alpha=0.3)
plt.show()