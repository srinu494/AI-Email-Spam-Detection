from flask import Flask, request, jsonify
from flask_cors import CORS
import joblib
import os
import json
import time
import hashlib
import gmail_test
from googleapiclient.errors import HttpError

app = Flask(__name__)
CORS(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "spam_model.pkl")

model = joblib.load(MODEL_PATH)

BATCH_SIZE = 75

gmail_service = None
current_email = None

cache = {
    "message_ids": [],
    "next_index": 0,
    "emails": {}
}


# ---------------- CACHE ----------------

def cache_path(email):
    safe_id = hashlib.sha256(
        email.lower().encode("utf-8")
    ).hexdigest()[:20]

    return os.path.join(
        BASE_DIR,
        f"scan_cache_{safe_id}.json"
    )


def load_cache(email):
    path = cache_path(email)

    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as file:
                saved = json.load(file)

            if isinstance(saved, dict):
                saved.setdefault("message_ids", [])
                saved.setdefault("next_index", 0)
                saved.setdefault("emails", {})
                saved["account"] = email
                return saved

        except (json.JSONDecodeError, OSError):
            pass

    return {
        "account": email,
        "message_ids": [],
        "next_index": 0,
        "emails": {}
    }


def save_cache(data):
    if not current_email:
        return

    path = cache_path(current_email)
    temp_path = path + ".tmp"

    with open(temp_path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)

    os.replace(temp_path, path)


# ---------------- GMAIL REQUEST ----------------

def gmail_request_with_retry(request_object):
    delay = 2

    for attempt in range(6):
        try:
            return request_object.execute()

        except HttpError as error:
            status = error.resp.status

            if status not in [403, 429, 500, 503] or attempt == 5:
                raise

            time.sleep(delay)
            delay = min(delay * 2, 60)

    raise RuntimeError("Gmail request failed.")


# ---------------- GET EMAIL IDS ----------------

def get_message_ids(label):
    ids = []
    page_token = None

    while True:
        params = {
            "userId": "me",
            "labelIds": [label],
            "maxResults": 500
        }

        if page_token:
            params["pageToken"] = page_token

        response = gmail_request_with_retry(
            gmail_service.users().messages().list(**params)
        )

        ids.extend(
            item["id"]
            for item in response.get("messages", [])
        )

        page_token = response.get("nextPageToken")

        if not page_token:
            break

        time.sleep(0.05)

    return ids


def get_all_message_ids():
    inbox_ids = get_message_ids("INBOX")
    spam_ids = get_message_ids("SPAM")

    return list(dict.fromkeys(inbox_ids + spam_ids))


# ---------------- SCAN ONE EMAIL ----------------

def scan_one_email(message_id):

    email_data = gmail_request_with_retry(
        gmail_service.users().messages().get(
            userId="me",
            id=message_id,
            format="full"
        )
    )

    payload = email_data.get("payload", {})
    headers = payload.get("headers", [])

    sender = gmail_test.get_header(headers, "From")
    subject = gmail_test.get_header(headers, "Subject")
    body = gmail_test.decode_email_body(payload)

    text_to_check = (
        (subject or "") + "\n" + (body or "")
    )

    if not text_to_check.strip():
        text_to_check = sender or "(Empty email)"

    # AI MODEL PREDICTION
    ai_result = model.predict([text_to_check])[0]

    ai_prediction = (
        "Spam" if ai_result == 1 else "Not Spam"
    )

    # IMPORTANT:
    # Classification depends only on AI prediction.
    # Gmail's SPAM label will not automatically make it Spam.
    prediction = ai_prediction

    if prediction == "Spam":
        source = "Detected as Spam by AI"
    else:
        source = "Classified as Not Spam by AI"

    return {
        "id": message_id,
        "sender": sender,
        "subject": subject,
        "prediction": prediction,
        "ai_prediction": ai_prediction,
        "source": source
    }


# ---------------- CACHE RESULTS ----------------

def results_for_cache():

    results = [
        cache["emails"][mid]
        for mid in cache.get("message_ids", [])
        if cache.get("emails", {}).get(mid) is not None
    ]

    spam = [
        item for item in results
        if item.get("prediction") == "Spam"
    ]

    not_spam = [
        item for item in results
        if item.get("prediction") == "Not Spam"
    ]

    return results, spam, not_spam


# ---------------- PREDICT ----------------

@app.route("/predict", methods=["POST"])
def predict():

    data = request.get_json(silent=True) or {}
    message = data.get("message", "")

    if not isinstance(message, str) or not message.strip():
        return jsonify({
            "error": "Please provide a valid email message."
        }), 400

    result = model.predict([message.strip()])[0]

    return jsonify({
        "prediction": "Spam" if result == 1 else "Not Spam"
    })


# ---------------- CONNECT GMAIL ----------------

@app.route("/connect-gmail", methods=["POST"])
def connect_gmail():

    global gmail_service, current_email, cache

    try:

        gmail_service = gmail_test.connect_gmail(
            force_account_selection=True
        )

        profile = gmail_request_with_retry(
            gmail_service.users().getProfile(userId="me")
        )

        current_email = profile.get("emailAddress", "")

        if not current_email:
            raise RuntimeError(
                "Google did not return the Gmail account address."
            )

        cache = load_cache(current_email)

        return jsonify({
            "status": "success",
            "message": "Gmail connected successfully!",
            "email": current_email
        })

    except Exception as error:

        gmail_service = None
        current_email = None

        return jsonify({
            "status": "error",
            "message": str(error)
        }), 500


# ---------------- LOGOUT ----------------

@app.route("/logout", methods=["POST"])
def logout():

    global gmail_service, current_email, cache

    old_email = current_email

    gmail_service = None
    current_email = None

    cache = {
        "message_ids": [],
        "next_index": 0,
        "emails": {}
    }

    try:
        gmail_test.clear_saved_token()

    except OSError as error:
        return jsonify({
            "status": "error",
            "message": str(error)
        }), 500

    return jsonify({
        "status": "success",
        "previous_account": old_email
    })


# ---------------- START FULL SCAN ----------------

@app.route("/start-scan", methods=["POST"])
def start_scan():

    global cache

    if gmail_service is None or not current_email:
        return jsonify({
            "error": "Please connect Gmail first."
        }), 401

    try:

        all_ids = get_all_message_ids()

        # FRESH SCAN:
        # Remove old predictions so every email is classified again.
        cache = {
            "account": current_email,
            "message_ids": all_ids,
            "next_index": 0,
            "emails": {}
        }

        save_cache(cache)

        return jsonify({
            "total_emails": len(all_ids),
            "scanned": 0,
            "message": "Fresh scan prepared successfully."
        })

    except Exception as error:

        return jsonify({
            "error": str(error)
        }), 500


# ---------------- SCAN BATCH ----------------

@app.route("/scan-batch", methods=["POST"])
def scan_batch():

    global cache

    if gmail_service is None or not current_email:
        return jsonify({
            "error": "Please connect Gmail first."
        }), 401

    try:

        ids = cache.get("message_ids", [])
        start = cache.get("next_index", 0)

        if not ids:
            return jsonify({
                "error": "Please start the scan first."
            }), 400

        end = min(start + BATCH_SIZE, len(ids))

        for index in range(start, end):

            message_id = ids[index]

            if cache["emails"].get(message_id) is None:

                cache["emails"][message_id] = scan_one_email(
                    message_id
                )

                save_cache(cache)
                time.sleep(0.2)

            cache["next_index"] = index + 1

        save_cache(cache)

        all_results, spam, not_spam = results_for_cache()

        scanned = len(all_results)

        return jsonify({
            "completed": cache["next_index"] >= len(ids),
            "total_emails": len(ids),
            "scanned": scanned,
            "spam_count": len(spam),
            "not_spam_count": len(not_spam),
            "emails": all_results
        })

    except Exception as error:

        save_cache(cache)

        return jsonify({
            "error": str(error)
        }), 500


# ---------------- GET EMAIL RESULTS ----------------

@app.route("/emails", methods=["GET"])
def get_emails():

    all_results, spam, not_spam = results_for_cache()

    total = len(cache.get("message_ids", []))

    return jsonify({
        "account": current_email,
        "total_emails": total,
        "total_scanned": len(all_results),
        "spam_count": len(spam),
        "not_spam_count": len(not_spam),
        "completed": (
            cache.get("next_index", 0) >= total
            and total > 0
        ),
        "emails": all_results
    })


# ---------------- CHECK NEW EMAILS ----------------

@app.route("/check-new-emails", methods=["POST"])
def check_new_emails():

    global cache

    if gmail_service is None or not current_email:
        return jsonify({
            "error": "Please connect Gmail first."
        }), 401

    try:

        new_ids = get_all_message_ids()

        known_ids = set(cache.get("emails", {}).keys())

        added = 0

        for message_id in new_ids:

            if message_id not in known_ids:

                cache["emails"][message_id] = scan_one_email(
                    message_id
                )

                added += 1

                save_cache(cache)

                time.sleep(0.2)

        cache["message_ids"] = list(
            dict.fromkeys(
                cache.get("message_ids", []) + new_ids
            )
        )

        save_cache(cache)

        all_results, spam, not_spam = results_for_cache()

        return jsonify({
            "new_emails_scanned": added,
            "total_scanned": len(all_results),
            "spam_count": len(spam),
            "not_spam_count": len(not_spam),
            "emails": all_results
        })

    except Exception as error:

        save_cache(cache)

        return jsonify({
            "error": str(error)
        }), 500


# ---------------- RUN SERVER ----------------

if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False
    )