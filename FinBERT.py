from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
import nltk
nltk.download('punkt')
from nltk import sent_tokenize

# Load FinBERT model and tokenizer
model_name = "yiyanghkust/finbert-tone"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForSequenceClassification.from_pretrained(model_name)

# Define sector keywords
sectors = {
    "Technology": ["technology", "software", "AI", "semiconductors", "tech"],
    "Energy": ["oil", "gas", "energy", "renewables"],
    "Healthcare": ["health", "hospital", "medicine", "biotech", "pharma"],
    "Finance": ["bank", "stocks", "market", "financial", "investment"],
    "Retail": ["retail", "e-commerce", "shopping", "consumer"]
}

# Sentiment labels
labels = ["negative", "neutral", "positive"]

def analyze_article(article_text):
    sector_sentiments = {sector: [] for sector in sectors}
    sentences = sent_tokenize(article_text)

    for sentence in sentences:
        inputs = tokenizer(sentence, return_tensors="pt", truncation=True)
        outputs = model(**inputs)
        scores = torch.nn.functional.softmax(outputs.logits, dim=1)
        sentiment = labels[torch.argmax(scores)]

        for sector, keywords in sectors.items():
            if any(keyword.lower() in sentence.lower() for keyword in keywords):
                sector_sentiments[sector].append(sentiment)

    # Aggregate results
    final_sentiment = {}
    for sector, sentiments in sector_sentiments.items():
        if sentiments:
            sentiment_score = sum(1 if s == "positive" else -1 if s == "negative" else 0 for s in sentiments)
            final_sentiment[sector] = "positive" if sentiment_score > 0 else "negative" if sentiment_score < 0 else "neutral"

    return final_sentiment

# Example usage
article = """
Tech companies like Apple and Nvidia saw strong growth this quarter due to rising demand in AI chips. 
Meanwhile, oil prices slumped amid fears of economic slowdown, hitting the energy sector hard.
"""

result = analyze_article(article)
print(result)
