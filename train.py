import math
import pickle
import requests
from collections import Counter
import time

wordle_url = "https://gist.githubusercontent.com/scholtes/94f3c0303ba6a7768b47583aff36654d/raw/wordle-La.txt"
words_url = "https://gist.githubusercontent.com/shmookey/b28e342e1b1756c4700f42f17102c2ff/raw/WORDS"
guesses_url = "https://raw.githubusercontent.com/tabatkins/wordle-list/main/words"
wordle = "wordle.pkl"
challenge = "challenge.pkl"
version = 1

def download_words():
    race_res = requests.get(wordle_url, timeout=15)
    common_res = requests.get(words_url, timeout=15)
    massive_res = requests.get(guesses_url, timeout=15)

    race_res.raise_for_status()
    common_res.raise_for_status()
    massive_res.raise_for_status()

    wordle_list = sorted({w.strip().lower() for w in race_res.text.splitlines() if len(w.strip()) == 5 and w.strip().isalpha()})
    words = [w.strip().lower() for w in common_res.text.splitlines() if w.strip().isalpha()]
    
    common_5_letters = {w for w in words if len(w) == 5}
    common_4_letters = {w for w in words if len(w) == 4}
    variant_5_letters = {w + 's' for w in common_4_letters}

    challenge_set = common_5_letters.union(variant_5_letters)
    challenge_set.add("ploys")
    challenge_answers = sorted(challenge_set)

    guesses = sorted({w.strip().lower() for w in massive_res.text.splitlines() if len(w.strip()) == 5 and w.strip().isalpha()})
    valid_guesses = sorted(set(guesses) | set(wordle_list) | set(challenge_answers))
    
    return wordle_list, challenge_answers, valid_guesses

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

def calculate_opener_entropy(guess, answers):
    total = len(answers)
    buckets = Counter()
    entropy = 0.0   

    for secret in answers:
        code = get_feedback_code(guess, secret)
        buckets[code] += 1

    for count in buckets.values():
        probability = count / total
        entropy -= probability * math.log2(probability)

    return entropy

def find_best_opener(answers, guess_pool, name):
    leaders = []
    best_word = None
    best_score = float("-inf")

    for word in guess_pool:
        score = calculate_opener_entropy(word, answers)
        
        leaders.append((score, word))
        leaders.sort(reverse=True)

        if len(leaders) > 10:
            leaders.pop()

        if score > best_score:
            best_score = score
            best_word = word

    return best_word

def compile_brain(answers, allowed_words, opener_pool, output_path, name):
    best_opener = find_best_opener(answers, opener_pool, name)

    brain = {
        "version": version,
        "name": name,
        "answers": answers,
        "allowed_words": allowed_words,
        "best_opener": best_opener,
    }

    with open(output_path, "wb") as file:
        pickle.dump(brain, file, protocol=pickle.HIGHEST_PROTOCOL)

if __name__ == "__main__":
    wordle_answers, challenge_answers, valid_guesses = download_words()

    compile_brain(
        answers=wordle_answers,
        allowed_words=valid_guesses,
        opener_pool=wordle_answers, 
        output_path=wordle,
        name="wordle"
    )

    compile_brain(
        answers=challenge_answers,
        allowed_words=challenge_answers,
        opener_pool=challenge_answers,
        output_path=challenge,
        name="challenge"
    )