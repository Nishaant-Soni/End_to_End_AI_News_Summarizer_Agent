import re
from typing import List, Dict, Set
from collections import Counter
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from nltk.stem import PorterStemmer
from loguru import logger

class RelevanceFilter:
    """Tool for filtering and scoring article relevance to search topics"""
    
    def __init__(self):
        self.stemmer = PorterStemmer()
        self.stop_words = set(stopwords.words('english'))
        self._download_nltk_data()
    
    def _download_nltk_data(self):
        """Download required NLTK data"""
        try:
            nltk.data.find('tokenizers/punkt')
            nltk.data.find('corpora/stopwords')
        except LookupError:
            logger.info("Downloading NLTK data...")
            nltk.download('punkt', quiet=True)
            nltk.download('stopwords', quiet=True)
    
    def extract_keywords(self, text: str) -> Set[str]:
        """Extract relevant keywords from text"""
        if not text:
            return set()
        
        # Clean and tokenize
        text = re.sub(r'[^a-zA-Z\s]', '', text.lower())
        tokens = word_tokenize(text)
        
        # Remove stopwords and stem
        keywords = set()
        for token in tokens:
            if token not in self.stop_words and len(token) > 2:
                stemmed = self.stemmer.stem(token)
                keywords.add(stemmed)
        
        return keywords
    
    def calculate_relevance_score(self, article: Dict, search_topic: str) -> float:
        """Calculate simplified relevance score between article and search topic"""
        
        # Extract topic keywords
        topic_keywords = self.extract_keywords(search_topic)
        
        if not topic_keywords:
            return 0.5  # Give benefit of doubt if no keywords
        
        # Get article text
        title = article.get('title', '').lower()
        description = article.get('description', '').lower()
        content = article.get('text_content', '').lower()
        
        # Extract article keywords
        article_text = f"{title} {description} {content}"
        article_keywords = self.extract_keywords(article_text)
        
        if not article_keywords:
            return 0.3  # Still give some chance even with no keywords
        
        # Simplified scoring - just basic keyword overlap
        common_keywords = topic_keywords.intersection(article_keywords)
        keyword_score = len(common_keywords) / len(topic_keywords) if topic_keywords else 0
        
        # Simple word presence bonus (very lenient)
        original_words = [w.lower() for w in search_topic.split() if len(w) > 1]  # Allow shorter words
        word_bonus = 0.0
        for word in original_words:
            if word in article_text:
                word_bonus += 0.2  # Fixed bonus per word found
        
        # Title boost - give preference to title matches
        title_boost = 0.0
        for word in original_words:
            if word in title:
                title_boost += 0.3
        
        # Combine scores with base score for all articles
        base_score = 0.2  # Every article gets minimum 0.2
        total_score = base_score + keyword_score + word_bonus + title_boost
        
        # Cap at 1.0
        relevance_score = min(total_score, 1.0)
        
        return relevance_score
    
    def filter_relevant_articles(self, articles: List[Dict], search_topic: str, 
                                min_relevance: float = 0.4, max_articles: int = None) -> List[Dict]:
        """Filter articles by relevance score"""
        
        # Calculate relevance scores
        scored_articles = []
        for article in articles:
            score = self.calculate_relevance_score(article, search_topic)
            if score >= min_relevance:
                article_copy = article.copy()
                article_copy['relevance_score'] = score
                scored_articles.append(article_copy)
        
        # Sort by relevance score (descending)
        scored_articles.sort(key=lambda x: x['relevance_score'], reverse=True)
        
        # Limit number of articles if specified
        if max_articles:
            scored_articles = scored_articles[:max_articles]
        
        logger.info(f"Filtered {len(scored_articles)} relevant articles from {len(articles)} total")
        
        return scored_articles
    
    def enhance_search_terms(self, original_topic: str) -> str:
        """Generate simplified search terms for better API compatibility"""
        
        # For NewsAPI.org, just return the original topic
        # Complex OR queries seem to cause issues
        return original_topic
    
    def get_relevance_summary(self, articles: List[Dict]) -> Dict:
        """Get summary of relevance scores"""
        if not articles:
            return {"avg_relevance": 0.0, "min_relevance": 0.0, "max_relevance": 0.0}
        
        scores = [article.get('relevance_score', 0.0) for article in articles]
        
        return {
            "avg_relevance": sum(scores) / len(scores),
            "min_relevance": min(scores),
            "max_relevance": max(scores),
            "total_articles": len(articles)
        }
