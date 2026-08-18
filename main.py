import math
import pickle
import requests
from collections import Counter
import datetime
import sys

wordle_file = "wordle.pkl"
challenge_file = "challenge.pkl"

try:
    with open(wordle_file, "rb") as f:
        wordle = pickle.load(f)
    with open(challenge_file, "rb") as f:
        challenge = pickle.load(f)
except FileNotFoundError:
    exit()

wordle_answers = wordle["answers"]
wordle_allowed = wordle["allowed_words"]
wordle_opener = wordle.get("best_opener", "raise")
challenge_answers = challenge["answers"]
challenge_allowed = challenge["allowed_words"]
challenge_opener = challenge.get("best_opener", "tares")
words_valid = set(wordle_allowed) | set(challenge_allowed)

def get_feedback_code(guess, secret):
    pattern = [0] * 5
    remaining = Counter()

    for i in range(5):
        if guess[i] == secret[i]:
            pattern[i] = 2
        else:
            remaining[secret[i]] += 1

    for i in range(5):
        if pattern[i] == 2:
            continue

        char = guess[i]

        if remaining[char] > 0:
            pattern[i] = 1
            remaining[char] -= 1

    return pattern[0] + pattern[1]*3 + pattern[2]*9 + pattern[3]*27 + pattern[4]*81

def get_feedback_pattern(guess, secret):
    code = get_feedback_code(guess, secret)
    pattern = [0] * 5

    for i in range(5):
        pattern[i] = code % 3
        code //= 3
        
    return tuple(pattern)

def filter_candidates(candidates, guess, feedback_tuple):
    target_code = feedback_tuple[0] + feedback_tuple[1]*3 + feedback_tuple[2]*9 + feedback_tuple[3]*27 + feedback_tuple[4]*81
    return [w for w in candidates if get_feedback_code(guess, w) == target_code]

def get_base_entropy(guess, candidates):
    total = len(candidates)
    buckets = {}
    entropy = 0.0

    for word in candidates:
        code = get_feedback_code(guess, word)
        buckets[code] = buckets.get(code, 0) + 1
        
    for count in buckets.values():
        prob = count / total
        entropy -= prob * math.log2(prob)

    return entropy

def choose_best_guess(candidates, allowed_words, guesses_used=None, attempt_num=1):
    if guesses_used is None:
        guesses_used = set()
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
        
    remaining_attempts = 6 - attempt_num

    if remaining_attempts <= 0:
        valid_pool = [w for w in candidates if w not in guesses_used]
        return valid_pool[0] if valid_pool else candidates[0]

    guess_pool = [w for w in allowed_words if w not in guesses_used]

    if len(candidates) <= 85:
        best_guess = None
        best_score = None
        
        if len(candidates) > 20:
            ranked_guesses = []

            for g in guess_pool:
                entropy = get_base_entropy(g, candidates)
                ranked_guesses.append((entropy + (2.0 if g in candidates else 0.0), g))

            ranked_guesses.sort(reverse=True)
            search_pool = [item[1] for item in ranked_guesses[:300]]
        else:
            search_pool = guess_pool
        
        for guess in search_pool:
            buckets = {}

            for c in candidates:
                code = get_feedback_code(guess, c)

                if code not in buckets:
                    buckets[code] = []

                buckets[code].append(c)
            
            max_size = max(len(v) for v in buckets.values())
            is_candidate = guess in candidates
            guaranteed = max_size <= remaining_attempts
            lookahead_penalty = 0

            if remaining_attempts > 1 and max_size > 1:
                for sub_bucket in buckets.values():
                    if len(sub_bucket) <= 1:
                        continue
                    if len(sub_bucket) > remaining_attempts:
                        lookahead_penalty += len(sub_bucket) * 2
            
            sum_squares = sum(len(v)*len(v) for v in buckets.values())
            score = (not guaranteed, max_size, lookahead_penalty, sum_squares, not is_candidate)
            
            if best_score is None or score < best_score:
                best_score = score
                best_guess = guess
                
            if score == (False, 1, 0, len(candidates), False):
                break
                
        return best_guess

    sample_pool = candidates[:100]
    filtered_guesses = []

    for w in guess_pool:
        approx_entropy = get_base_entropy(w, sample_pool)
        filtered_guesses.append((approx_entropy, w))

    filtered_guesses.sort(reverse=True)
    optimized_search_pool = [item[1] for item in filtered_guesses[:300]]
    best_guess = max(optimized_search_pool, key=lambda w: get_base_entropy(w, candidates) + (2.0 if w in candidates else 0.0))
    
    return best_guess

class BotState:
    def __init__(self):
        self.current = wordle_opener
        self.candidates = list(wordle_allowed)
        self.used = set()

    def advance(self, feedback):
        self.used.add(self.current)
        self.candidates = filter_candidates(self.candidates, self.current, feedback)

        if len(self.candidates) == 1:
            self.current = self.candidates[0]
            return

        current_attempt = len(self.used) + 1
        self.current = choose_best_guess(self.candidates, wordle_allowed, self.used, attempt_num=current_attempt)

class ChallengeBotState:
    def __init__(self, target_word=None):
        self.current = challenge_opener
        self.candidates = list(challenge_allowed)

        if target_word and target_word not in self.candidates:
            self.candidates.append(target_word)

        self.used = set()

    def advance(self, feedback):
        self.used.add(self.current)
        self.candidates = filter_candidates(self.candidates, self.current, feedback)

        if len(self.candidates) == 1:
            self.current = self.candidates[0]
            return

        current_attempt = len(self.used) + 1
        self.current = choose_best_guess(self.candidates, challenge_allowed, self.used, attempt_num=current_attempt)

def get_daily_word():
    try:
        today = datetime.date.today().isoformat()
        url = f"https://www.nytimes.com/svc/wordle/v2/{today}.json"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        return response.json()["solution"].lower()
    except Exception:
        return "The Wordle Failed to Load"