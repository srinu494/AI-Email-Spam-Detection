from flask import Flask, request, jsonify
import joblib

# Create Flask app
app = Flask(__name__)

# Load trained model
model = joblib.load("spam_model.pkl")

@app.route("/predict", methods=["POST"])
def predict():
    data = request.get_json()

    message = data["message"]

    prediction = model.predict([message])[0]

    if prediction == 1:
        result = "Spam"
    else:
        result = "Not Spam"

    return jsonify({"prediction": result})

if __name__ == "__main__":
    app.run(debug=True)