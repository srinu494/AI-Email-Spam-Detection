import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline
from sklearn.metrics import accuracy_score
import joblib

# Load dataset
data = pd.read_csv(
    "spam.csv",
    sep="\t",
    header=None,
    names=["label", "message"],
    encoding="latin-1"
)
# Convert labels
data['label'] = data['label'].map({'ham': 0, 'spam': 1})

# Split dataset
X_train, X_test, y_train, y_test = train_test_split(
    data['message'],
    data['label'],
    test_size=0.2,
    random_state=42
)

# Create model
model = Pipeline([
    ('tfidf', TfidfVectorizer()),
    ('classifier', MultinomialNB())
])

# Train model
model.fit(X_train, y_train)

# Test model
predictions = model.predict(X_test)

print("Accuracy:", accuracy_score(y_test, predictions))

# Save trained model
joblib.dump(model, "spam_model.pkl")

print("Model trained and saved successfully!")