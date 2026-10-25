"""Dating-only intentions; these never belong in the general profile projection."""
INTENTIONS = [
    {'id': 'relationship', 'label': 'Looking for a relationship'},
    {'id': 'getting_to_know', 'label': 'Getting to know people'},
    {'id': 'figuring_out', 'label': 'Still figuring it out'},
]
INTENTION_LABELS = {item['id']: item['label'] for item in INTENTIONS}
