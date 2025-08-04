import os
import requests
import re
from typing import List, Dict, Optional
from datetime import datetime
import diskcache as dc
from loguru import logger
from .relevance_filter import RelevanceFilter
from .article_extractor import ArticleExtractor

class NewsFetcher:
    """Tool for fetching news articles from NewsAPI.org"""
    
    def __init__(self, api_key: str, cache_dir: str = "./cache", cache_ttl: int = 3600, use_timeframe: bool = False, enable_extraction: bool = True):
        self.api_key = api_key
        self.base_url = "https://newsapi.org/v2"
        self.cache = dc.Cache(cache_dir)
        self.cache_ttl = cache_ttl
        self.relevance_filter = RelevanceFilter()
        self.use_timeframe = use_timeframe
        self.enable_extraction = enable_extraction
        
        # Initialize article extractor if needed
        self.article_extractor = ArticleExtractor() if enable_extraction else None
        
    def _make_request(self, endpoint: str, params: Dict) -> Dict:
        """Make a request to NewsAPI.org with error handling"""
        params['apiKey'] = self.api_key
        
        try:
            url = f"{self.base_url}/{endpoint}"
            logger.info(f"Making API request to: {url}")
            logger.info(f"Parameters: {params}")
            
            response = requests.get(url, params=params, timeout=180)
            
            if response.status_code != 200:
                logger.error(f"API request failed with status {response.status_code}: {response.text}")
                return {"status": "error", "message": f"HTTP {response.status_code}: {response.text}"}
            
            result = response.json()
            # NewsAPI.org returns status field directly
            if result.get('status') == 'error':
                return {"status": "error", "message": result.get('message', 'Unknown error')}
            
            return {"status": "success", "data": result.get('articles', []), "totalResults": result.get('totalResults', 0)}
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            return {"status": "error", "message": str(e)}
    
    def search_news(self, topic: str, language: str = "en", max_articles: int = 40) -> List[Dict]:
        """Search for news articles by topic with high relevance filtering"""
        cache_key = f"search_{topic}_{language}_{max_articles}"
        
        # Check cache first
        cached_result = self.cache.get(cache_key)
        if cached_result:
            logger.info(f"Retrieved cached results for topic: {topic}")
            return cached_result
        
        # Enhance search terms for better results
        enhanced_search = self.relevance_filter.enhance_search_terms(topic)

        # Use the enhanced search directly (now returns a string)
        search_query = enhanced_search

        params = {
            'q': search_query,  # NewsAPI.org uses 'q' parameter
            'language': language,
            'pageSize': min(max_articles * 2, 100),  # NewsAPI.org allows up to 100
            'sortBy': 'relevancy',  # Sort by relevancy for better results
        }
        
        # Add date filter if enabled
        if self.use_timeframe:
            from datetime import datetime, timedelta
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            params['from'] = yesterday
            logger.info("Using date filter (last 24 hours)")
        else:
            logger.info("No date filter applied")
        
        logger.info(f"Fetching news for topic: {topic}")
        response = self._make_request("everything", params)
        
        if response.get("status") == "success":
            articles = self._process_articles(response.get("data", []))
            
            # Extract full content if enabled
            if self.enable_extraction and self.article_extractor:
                logger.info(f"Extracting full content for {len(articles)} articles...")
                articles = self._enhance_articles_with_extraction(articles)
            
            # Filter articles for relevance (very lenient)
            logger.info(f"Filtering {len(articles)} articles for relevance to: {topic}")
            relevant_articles = self.relevance_filter.filter_relevant_articles(
                articles, topic, min_relevance=0.1  # Very lenient threshold
            )
            
            # Limit to requested number
            final_articles = relevant_articles[:max_articles]
            
            # Cache the results
            self.cache.set(cache_key, final_articles, expire=self.cache_ttl)
            logger.info(f"Found {len(final_articles)} highly relevant articles for topic: {topic}")
            return final_articles
        else:
            logger.error(f"Failed to fetch news: {response.get('message', 'Unknown error')}")
            return []
    
    def get_trending_topics(self, language: str = "en") -> List[Dict]:
        """Fetch trending topics using NewsAPI.org"""
        cache_key = f"trending_{language}"
        
        # Check cache first
        cached_result = self.cache.get(cache_key)
        if cached_result:
            logger.info("Retrieved cached trending topics")
            return cached_result
        
        params = {
            'language': language,
            'pageSize': 20,  # Get more articles to extract topics from
            'category': 'general'  # NewsAPI.org uses singular 'category'
        }
        
        logger.info("Fetching trending topics")
        response = self._make_request("top-headlines", params)  # NewsAPI.org uses 'top-headlines' for trending
        
        if response.get("status") == "success":
            articles = response.get("data", [])
            trending_topics = self._extract_trending_topics(articles)
            # Cache the results
            self.cache.set(cache_key, trending_topics, expire=self.cache_ttl // 2)  # Shorter cache for trending
            logger.info(f"Found {len(trending_topics)} trending topics")
            return trending_topics
        else:
            logger.error(f"Failed to fetch trending topics: {response.get('message', 'Unknown error')}")
            return []
    
    def _process_articles(self, articles: List[Dict]) -> List[Dict]:
        """Process and filter articles from NewsAPI.org"""
        processed = []
        
        for article in articles:
            # Skip articles without content or description
            if not article.get('description') and not article.get('content'):
                continue
                
            processed_article = {
                'title': article.get('title', 'No title'),
                'description': article.get('description', ''),
                'content': article.get('content', ''),  # NewsAPI.org provides content (truncated to 200 chars)
                'url': article.get('url', ''),
                'source': article.get('source', {}).get('name', 'Unknown') if article.get('source') else 'Unknown',
                'published_at': article.get('publishedAt', ''),
                'image_url': article.get('urlToImage', ''),
                'category': []  # NewsAPI.org doesn't provide categories in articles
            }
            
            # Use content if available, otherwise use description
            content_text = processed_article['content'] or processed_article['description']
            
            # Clean up truncated content indicators
            if content_text and '[+' in content_text and 'chars]' in content_text:
                # Remove the truncation indicator for cleaner text
                content_text = re.sub(r'\s*\[\+\d+\s+chars\].*$', '', content_text)
            
            processed_article['text_content'] = content_text
            
            processed.append(processed_article)
        
        return processed
    
    def _extract_trending_topics(self, articles: List[Dict]) -> List[Dict]:
        """Extract trending topics from latest articles (NewsAPI.org format)"""
        topics = {}
        
        for article in articles:
            categories = article.get('categories', [])
            # Also extract keywords from titles for better trending detection
            title_words = article.get('title', '').split()
            significant_words = [word.lower() for word in title_words if len(word) > 4]
            
            all_topics = categories + significant_words[:2]  # Take first 2 significant words
            
            for topic in all_topics:
                if topic and len(topic) > 3:
                    topic_key = topic.lower()
                    if topic_key not in topics:
                        topics[topic_key] = {
                            'topic': topic.title(),
                            'count': 0,
                            'latest_article': None
                        }
                    topics[topic_key]['count'] += 1
                    if not topics[topic_key]['latest_article']:
                        topics[topic_key]['latest_article'] = {
                            'title': article.get('title', ''),
                            'url': article.get('url', ''),
                            'published_at': article.get('publishedAt', '')
                        }
        
        # Sort by count and return top topics
        trending = sorted(topics.values(), key=lambda x: x['count'], reverse=True)
        return trending[:10]
    
    def _enhance_articles_with_extraction(self, articles: List[Dict]) -> List[Dict]:
        """Enhance articles with extracted content"""
        if not self.article_extractor:
            return articles
        
        enhanced_articles = []
        
        for article in articles:
            url = article.get('url', '')
            
            # Skip if no URL or if URL is not extractable
            if not url or not self.article_extractor.is_extractable_url(url):
                enhanced_articles.append(article)
                continue
            
            # Check if we already have good content (not truncated)
            text_content = article.get('text_content', '')
            
            # Detect various truncation patterns
            has_truncation = (
                '[+' in text_content and 'chars]' in text_content or  # NewsAPI.org pattern
                text_content.endswith('...') or  # Common truncation
                len(text_content) == 200 or  # NewsAPI.org exact truncation length
                'ONLY AVAILABLE IN PAID PLANS' in text_content  # Paywall message
            )
            
            # Only skip extraction if we have substantial content AND it's not truncated
            if text_content and len(text_content) > 500 and not has_truncation:
                logger.info(f"Skipping extraction - already have good content ({len(text_content)} chars): {url}")
                enhanced_articles.append(article)
                continue
            
            # Skip problematic domains that often hang
            problematic_domains = ['yahoo.com', 'finance.yahoo.com', 'news.yahoo.com']
            if any(domain in url.lower() for domain in problematic_domains):
                logger.info(f"Skipping extraction for problematic domain: {url}")
                enhanced_articles.append(article)
                continue
            
            # Extract content with timeout
            logger.info(f"Attempting extraction for: {url}")
            extraction_result = self.article_extractor.extract_article_content(url)
            
            if extraction_result['success']:
                article['text_content'] = extraction_result['text']
                article['extraction_method'] = extraction_result.get('method', 'unknown')
                article['extraction_success'] = True
                logger.info(f"Successfully extracted content from {url} using {extraction_result.get('method', 'unknown')}")
            else:
                article['extraction_success'] = False
                article['extraction_error'] = extraction_result.get('error', 'Unknown error')
                logger.warning(f"Failed to extract content from {url}: {extraction_result.get('error', 'Unknown error')}")
            
            enhanced_articles.append(article)
        
        return enhanced_articles
    
    def clear_cache(self):
        """Clear the cache"""
        self.cache.clear()
        logger.info("Cache cleared")
