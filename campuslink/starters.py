"""Small, deterministic suggestions from information visible to a match."""
INTEREST_QUESTIONS = {
    'Technology': 'What is a bit of technology you are excited about?',
    'Cybersecurity': 'What got you interested in cybersecurity?',
    'Programming': 'What would you build if you could make any app?',
    'Gaming': 'What is your go-to game after a long day?',
    'Music': 'What song have you had on repeat lately?',
    'Sports': 'Which sport would you happily play after class?',
    'Reading': 'What is a book you keep recommending?',
    'Entrepreneurship': 'If you started a small campus business, what would it be?',
    'Art': 'What kind of art do you enjoy most?',
    'Movies': 'What is a movie you would happily watch again?',
    'Travel': 'If you had a free weekend, where would you go?',
    'Photography': 'What is your favourite thing to photograph?',
    'Science': 'What is a science fact you love sharing?',
    'Design': 'What is something well designed you noticed recently?',
}
CAMPUS_QUESTIONS = [
    'What has been the best part of your week on campus?',
    'What do you enjoy doing when classes are done?',
    'What is one thing you would like to try this semester?',
]


def conversation_starters(shared_interests, visible_prompts):
    interests = [
        {'id': 'interest:' + interest, 'source': 'shared_interest',
         'context': 'You both enjoy ' + interest, 'text': INTEREST_QUESTIONS[interest]}
        for interest in sorted(set(shared_interests)) if interest in INTEREST_QUESTIONS
    ]
    prompts = []
    for prompt in visible_prompts:
        # Keep suggestions short without copying a full profile answer into chat.
        answer = ' '.join(prompt['answer'].split())
        excerpt = answer[:96] + ('…' if len(answer) > 96 else '')
        prompts.append({
            'id': 'prompt:' + prompt['prompt_id'], 'source': 'profile_prompt',
            'context': 'Their answer · ' + prompt['question'],
            'text': f'Your answer “{excerpt}” caught my eye. What is the story behind it?',
        })
    # Give both shared interests and a profile answer a place when available.
    candidates = interests[:1] + prompts[:1] + interests[1:] + prompts[1:]
    candidates += [
        {'id': f'campus:{index}', 'source': 'campus',
         'context': 'A campus question', 'text': question}
        for index, question in enumerate(CAMPUS_QUESTIONS)
    ]
    return candidates[:3]
