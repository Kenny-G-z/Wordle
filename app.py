import uuid
from flask import Flask, render_template, request, jsonify, session
import main

app = Flask(__name__)
app.secret_key = "wordle_key"
bot_instances = {}

@app.route("/")
def index():
    secret_word = main.get_daily_word()
    
    if "user_id" not in session:
        session["user_id"] = uuid.uuid4().hex
        
    user_id = session["user_id"]

    if session.get("secret") != secret_word or user_id not in bot_instances:
        session["secret"] = secret_word
        session["round"] = 0
        session["ai_won"] = False

        if secret_word != "the wordle failed to load":
            bot_instances[user_id] = main.BotState()

    return render_template("index.html", load_failed=(secret_word == "the wordle failed to load"))

@app.route("/turn", methods=["POST"])
def turn():
    user_id = session.get("user_id")
    secret = session.get("secret")

    if secret == "the wordle failed to load":
        return jsonify({"error": "the wordle failed to load"}), 500

    data = request.get_json()
    user_guess = data.get("guess", "").strip().lower()

    if len(user_guess) != 5:
        return jsonify({"error": "Word must be 5 letters."}), 400
    if user_guess not in main.words_valid:
        return jsonify({"error": "Not in word list!"}), 400

    bot = bot_instances.get(user_id)
    user_feedback = main.get_feedback_pattern(user_guess, secret)
    user_won = (user_guess == secret)
    ai_response = None

    if not session.get("ai_won", False) and bot:
        if session.get("round", 0) == 0:
            ai_guess = main.wordle_opener
        else:
            ai_guess = bot.current

        ai_feedback = main.get_feedback_pattern(ai_guess, secret)
        ai_won = (ai_guess == secret)

        if ai_won:
            session["ai_won"] = True
        else:
            bot.advance(ai_feedback)

        ai_response = {
            "guess": ai_guess,
            "feedback": list(ai_feedback),
            "won": ai_won
        }

    session["round"] = session.get("round", 0) + 1
    
    if user_won or session.get("ai_won", False) or session["round"] >= 6:
        if user_id in bot_instances:
            del bot_instances[user_id]

    return jsonify({
        "user": {"guess": user_guess, "feedback": list(user_feedback), "won": user_won},
        "ai": ai_response,
        "ai_already_finished": session.get("ai_won", False),
        "round": session["round"],
        "target": secret
    })

@app.route("/challenge")
def challenge():
    return render_template("index_challange.html")

@app.route("/start_challenge", methods=["POST"])
def start_challenge():
    data = request.get_json()
    secret = data.get("secret", "").strip().lower()

    if len(secret) != 5:
        return jsonify({"error": "Word must be exactly 5 letters."}), 400
        
    if secret not in main.words_valid:
        return jsonify({"error": "Must be a Valid Word!"}), 400

    challenge_id = uuid.uuid4().hex
    bot = main.ChallengeBotState(secret)
    bot_instances[challenge_id] = bot
    guess = bot.current
    feedback = main.get_feedback_pattern(guess, secret)

    return jsonify({
        "challenge_id": challenge_id,
        "guess": guess,
        "feedback": list(feedback),
        "solved": (guess == secret)
    })

@app.route("/step_challenge", methods=["POST"])
def step_challenge():
    data = request.get_json()
    challenge_id = data.get("challenge_id")
    secret = data.get("secret", "").strip().lower()
    bot = bot_instances.get(challenge_id)

    if not bot:
        return jsonify({"error": "Session Expired or not Found."}), 400

    current_feedback = main.get_feedback_pattern(bot.current, secret)
    bot.advance(current_feedback)
    next_guess = bot.current

    if not next_guess:
        if challenge_id in bot_instances:
            del bot_instances[challenge_id]
        return jsonify({"solved": False, "ended": True})

    next_feedback = main.get_feedback_pattern(next_guess, secret)
    solved = (next_guess == secret)

    if solved:
        if challenge_id in bot_instances:
            del bot_instances[challenge_id]

    return jsonify({"guess": next_guess, "feedback": list(next_feedback), "solved": solved, "ended": False})

if __name__ == "__main__":
    app.run(debug=True, port=5000)