"""
Results copied from cy's Colab run ("Bill Breaker: plain-English, personalized bill
explanations", FLAN-T5-base fine-tuned on BillSum, Tesla T4). Static until the model
is hosted; see endpoint.py.
"""

MODEL_CARD = {
    "base": "google/flan-t5-base",
    "params": "250M",
    "trainedOn": "BillSum (bill text to official CRS summary), 1,800 train / 200 validation",
    "personalizer": "Qwen/Qwen2.5-1.5B-Instruct (not fine-tuned)",
    "evalSet": "25 of cy's 100 bills, held out from training, scored against their official summaries",
    "weightsSaved": False,
}

ROUGE = [
    {"name": "FLAN-T5 (no training)", "rouge1": 0.209, "rouge2": 0.127, "rougeL": 0.169, "rougeLsum": 0.18},
    {"name": "Bill Breaker (fine-tuned)", "rouge1": 0.422, "rouge2": 0.279, "rougeL": 0.341, "rougeLsum": 0.357},
]

# The notebook printed these truncated by pandas; the cut is marked with an ellipsis.
SAMPLES = [
    {
        "title": "bill_001 (no short title)",
        "tuned": "Amends the Internal Revenue Code to prohibit a business entity from being subject to civil liability relating to any…",
        "reference": "Shields a business entity from civil liability relating to any injury or death occurring at a facility of that entit…",
    },
    {
        "title": "Human Rights Information Act",
        "tuned": "Human Rights Information Act - Requires the U.S. to continue to receive requests from foreign authorities for legal …",
        "reference": "Human Rights Information Act - Requires certain Federal agencies to identify and organize all human rights records r…",
    },
    {
        "title": "Jackie Robinson Commemorative Coin Act",
        "tuned": "Jackie Robinson Commemorative Coin Act - Directs the Secretary of the Treasury to mint and issue not more than 500,0…",
        "reference": "Jackie Robinson Commemorative Coin Act - Directs the Secretary of the Treasury to: (1) mint and issue one-dollar si…",
    },
]

EXAMPLE_PROFILE = {
    "state": "Colorado",
    "age": "18-24",
    "work": "college student, part-time retail",
    "household": "just me",
    "health": "on my parents' employer plan",
    "military": "no",
    "income": "under $30k",
    "interests": "environment, student loans, public lands",
}

EXAMPLE_RUN = {
    "billId": "bill_009",
    "title": "Marine Debris Act Amendments of 2012",
    "general": (
        "Marine Debris Act Amendments of 2012 - Amends the National Oceanic and Atmospheric Administration (NOAA) marine debris research, prevention, and reduction Act to: (1) identify, determine sources of, assess, prevent, reduce, and remove marine debris, with a focus on marine debris posing a threat to living marine resources and navigation safety; (2) provide national and regional coordination to assist States, Indian tribes, and regional organizations in identification, determination of sources, assessment, prevention"
    ),
    "sections": [
        {"section": "5", "heading": "NOAA MARINE DEBRIS PROGRAM", "score": 6, "matchedTerms": ["education", "environment", "pollution"]},
        {"section": "2", "heading": "(33 U.S.C. 1951) is amended to read as follows", "score": 1, "matchedTerms": ["environment"]},
        {"section": "2203", "heading": "of the Marine Plastic Pollution Research and", "score": 1, "matchedTerms": ["pollution"]},
    ],
    "personalized": """**What This Bill Does**

This bill aims to improve our understanding and management of marine debris across the country. It will help us:

1. Identify where marine debris comes from.
2. Determine its sources more accurately.
3. Assess the impact of marine debris on our oceans and waterways.
4. Prevent and reduce marine debris.
5. Remove existing marine debris effectively.

By focusing on marine debris that poses a threat to living marine resources and navigation safety, we can better protect our environment and ensure safe travel.

**What It Could Mean For You**

As a college student working part-time at a retail job, your life might be affected indirectly if this bill becomes law. Here's what you should know:

1. **Environmental Awareness**: The bill encourages awareness about marine debris, which means you'll likely hear more about environmental issues around you.

2. **Public Lands**: Since you live near public lands, any new regulations or initiatives aimed at protecting them could influence your daily activities.

3. **Healthcare Costs**: While you're covered under your parents' employer plan, increased funding for marine debris programs might lead to higher healthcare costs down the line due to pollution-related illnesses.

4. **Financial Impact**: Depending on the implementation of new regulations, there might be additional expenses associated with compliance, but overall, the benefits outweigh the costs.

In summary, while you won't directly benefit from this bill, it has broader implications for the environment and public health, potentially affecting your community and lifestyle over time.""",
}
