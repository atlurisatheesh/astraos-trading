"""Test FinBERT sentiment analysis on stock market news."""
from transformers import pipeline

print("Downloading FinBERT model (first time ~500MB)...")
sentiment = pipeline("sentiment-analysis", model="ProsusAI/finbert")

test_headlines = [
    "RELIANCE shares surge 5% on strong quarterly results beating estimates",
    "Bank Nifty crashes 500 points on heavy FII selling",
    "RBI keeps repo rate unchanged at 6.5 percent",
    "TCS wins massive deal worth 2 billion dollars from US client",
    "Market outlook remains cautious ahead of US Fed decision",
    "Adani group stocks fall after short seller report",
    "HDFC Bank merger boosts banking sector sentiment",
    "India GDP growth at 7.2% beats all expectations",
    "Crude oil prices spike to $90 hurting Indian markets",
    "NIFTY hits all time high of 25000 on broad based buying",
]

print("\n" + "=" * 70)
print("  FinBERT Sentiment Analysis Results")
print("=" * 70 + "\n")

results = sentiment(test_headlines)

for headline, result in zip(test_headlines, results):
    label = result["label"]
    score = result["score"]

    if label == "positive":
        icon = "BULL"
    elif label == "negative":
        icon = "BEAR"
    else:
        icon = "    "

    print(f"  [{icon}] {label:10s} {score:5.0%}  {headline[:60]}")

print("\n" + "=" * 70)
print("  FinBERT is working! Sentiment agent will now use deep NLP.")
print("=" * 70)
