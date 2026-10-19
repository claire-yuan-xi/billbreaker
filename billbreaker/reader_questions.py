"""
The "about you" questions from the Bill Breaker Colab notebook, shown in the search
dialog. Every one is optional; answers stay in the reader's browser tab.
"""

QUESTIONS = [
    {"key": "state", "label": "Your state"},
    {"key": "age", "label": "Age", "choices": ["Under 18", "18-24", "25-44", "45-64", "65+"]},
    {"key": "work", "label": "Work", "hint": "Job, student, retired", "free": True},
    {
        "key": "household",
        "label": "Household",
        "choices": ["Just me", "Partner", "Kids", "An elderly parent"],
        "free": True,
    },
    {
        "key": "health",
        "label": "Health coverage",
        "choices": ["Employer", "Medicare", "Medicaid", "Marketplace", "VA", "None"],
    },
    {"key": "military", "label": "Military family", "choices": ["Yes", "No"]},
    {
        "key": "income",
        "label": "Household income",
        "choices": ["Under $30k", "$30-75k", "$75-150k", "Over $150k"],
    },
    {"key": "interests", "label": "Issues you care about", "hint": "Taxes, schools, climate", "free": True},
]
