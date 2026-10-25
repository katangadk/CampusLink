"""Shared prompt catalog and validation for optional profile answers."""
import unicodedata

MAX_PROMPTS = 3
MAX_ANSWER = 280
PROMPTS = [
    {'id': 'talk_hours', 'question': 'I can talk for hours about…'},
    {'id': 'campus_date', 'question': 'My ideal campus date would be…'},
    {'id': 'small_joy', 'question': 'A small thing that makes my day…'},
    {'id': 'teach_me', 'question': 'Teach me something about…'},
    {'id': 'free_afternoon', 'question': 'With a free afternoon, you’ll find me…'},
    {'id': 'green_flag', 'question': 'A green flag I appreciate…'},
    {'id': 'campus_spot', 'question': 'My favourite campus spot is…'},
    {'id': 'perfect_playlist', 'question': 'The first song on my perfect playlist…'},
]
QUESTIONS = {prompt['id']: prompt['question'] for prompt in PROMPTS}


def validate_answers(value):
    if not isinstance(value, list) or len(value) > MAX_PROMPTS:
        raise ValueError('Choose up to three prompt answers.')
    answers = []
    seen = set()
    for item in value:
        if not isinstance(item, dict) or set(item) != {'prompt_id', 'answer'}:
            raise ValueError('Each answer needs a prompt and answer text.')
        prompt_id, answer = item['prompt_id'], item['answer']
        if not isinstance(prompt_id, str) or prompt_id not in QUESTIONS:
            raise ValueError('Choose a question from the prompt menu.')
        if prompt_id in seen:
            raise ValueError('Choose a different question for each answer.')
        if not isinstance(answer, str) or not 1 <= len(answer.strip()) <= MAX_ANSWER:
            raise ValueError(f'Each answer must be 1–{MAX_ANSWER} characters. Remove a prompt to leave it unanswered.')
        if any(unicodedata.category(char) in ('Cc', 'Cs') and char not in '\n\t' for char in answer):
            raise ValueError('Answers must contain plain text.')
        seen.add(prompt_id)
        answers.append((prompt_id, answer.strip()))
    return answers
