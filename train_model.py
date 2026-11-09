import os
import pandas as pd
import joblib
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline
from sklearn.metrics import accuracy_score, classification_report

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "spam.csv")
MODEL_PATH = os.path.join(BASE_DIR, "spam_model.pkl")

data = pd.read_csv(
DATA_PATH,
sep="\t",
header=None,
names=["label", "message"],
encoding="latin-1",
skiprows=1
)

data = data.dropna(subset=["label", "message"])
data["label"] = data["label"].map({"ham": 0, "spam": 1})
data = data.dropna(subset=["label"])
data["label"] = data["label"].astype(int)

X_train, X_test, y_train, y_test = train_test_split(
data["message"],
data["label"],
test_size=0.2,
random_state=42,
stratify=data["label"]
)

model = Pipeline([
("tfidf", TfidfVectorizer(
lowercase=True,
ngram_range=(1, 2),
sublinear_tf=True
)),
("classifier", MultinomialNB(alpha=0.5))
])

model.fit(X_train, y_train)

predictions = model.predict(X_test)

print("Model Accuracy:", round(accuracy_score(y_test, predictions) * 100, 2), "%")
print("\nClassification Report:")
print(classification_report(
y_test,
predictions,
target_names=["Not Spam", "Spam"]
))

joblib.dump(model, MODEL_PATH)
print("\nImproved model saved successfully!")
