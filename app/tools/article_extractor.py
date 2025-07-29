import requests
import trafilatura
from newspaper import Article
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import time
from typing import Dict, Optional, List
from loguru import logger
import re
import concurrent.futures

class ArticleExtractor:
    """Tool for extracting full article content from URLs"""
    
    def __init__(self, timeout: int = 10, max_retries: int = 2):
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def extract_article_content(self, url: str) -> Dict:
        """Extract article content using multiple methods"""
        if not url or not url.startswith('http'):
            return {
                'success': False,
                'content': '',
                'title': '',
                'text': '',
                'error': 'Invalid URL'
            }
        
        # Try multiple extraction methods
        methods = [
            self._extract_with_trafilatura,
            self._extract_with_newspaper,
            self._extract_with_beautifulsoup
        ]
        
        for method in methods:
            try:
                result = method(url)
                if result['success'] and result['text'] and len(result['text'].strip()) > 100:
                    logger.info(f"Successfully extracted content using {method.__name__}")
                    return result
            except Exception as e:
                logger.warning(f"Method {method.__name__} failed for {url}: {e}")
                continue
        
        return {
            'success': False,
            'content': '',
            'title': '',
            'text': '',
            'error': 'All extraction methods failed'
        }
    
    def _extract_with_trafilatura(self, url: str) -> Dict:
        """Extract using trafilatura (best for modern websites)"""
        try:
            logger.info(f"Trying trafilatura extraction for: {url}")
            downloaded = trafilatura.fetch_url(url)
            if downloaded is None:
                logger.warning(f"Trafilatura failed to download: {url}")
                return {'success': False, 'content': '', 'title': '', 'text': '', 'error': 'Failed to download'}
            
            # Extract main content
            text = trafilatura.extract(downloaded, include_formatting=True, include_links=True)
            
            # Safely extract metadata
            title = ''
            try:
                metadata = trafilatura.extract_metadata(downloaded)
                if metadata and hasattr(metadata, 'get'):
                    title = metadata.get('title', '')
                elif metadata and isinstance(metadata, dict):
                    title = metadata.get('title', '')
                elif hasattr(metadata, 'title'):
                    title = getattr(metadata, 'title', '')
            except Exception as e:
                logger.warning(f"Metadata extraction failed: {e}")
                title = ''
            
            if text and len(text.strip()) > 50:
                logger.info(f"Trafilatura successful: {len(text)} characters")
                return {
                    'success': True,
                    'content': text,
                    'title': title,
                    'text': text,
                    'method': 'trafilatura'
                }
            
            logger.warning(f"Trafilatura found no content: {url}")
            return {'success': False, 'content': '', 'title': '', 'text': '', 'error': 'No content found'}
            
        except Exception as e:
            logger.error(f"Trafilatura exception: {e}")
            return {'success': False, 'content': '', 'title': '', 'text': '', 'error': str(e)}
    
    def _extract_with_newspaper(self, url: str) -> Dict:
        """Extract using newspaper3k"""
        try:
            article = Article(url)
            article.download()
            article.parse()
            
            if article.text and len(article.text.strip()) > 50:
                return {
                    'success': True,
                    'content': article.text,
                    'title': article.title or '',
                    'text': article.text,
                    'method': 'newspaper'
                }
            
            return {'success': False, 'content': '', 'title': '', 'text': '', 'error': 'No content found'}
            
        except Exception as e:
            return {'success': False, 'content': '', 'title': '', 'text': '', 'error': str(e)}
    
    def _extract_with_beautifulsoup(self, url: str) -> Dict:
        """Extract using BeautifulSoup as fallback"""
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            
            # Try to find main content areas
            content_selectors = [
                'article',
                '[role="main"]',
                '.content',
                '.article-content',
                '.post-content',
                '.entry-content',
                'main',
                '.main-content'
            ]
            
            content = ''
            for selector in content_selectors:
                elements = soup.select(selector)
                if elements:
                    content = ' '.join([elem.get_text() for elem in elements])
                    if len(content.strip()) > 100:
                        break
            
            # If no specific content area found, get body text
            if not content or len(content.strip()) < 100:
                content = soup.get_text()
            
            # Clean up the text
            content = re.sub(r'\s+', ' ', content).strip()
            
            if content and len(content) > 100:
                return {
                    'success': True,
                    'content': content,
                    'title': soup.title.string if soup.title else '',
                    'text': content,
                    'method': 'beautifulsoup'
                }
            
            return {'success': False, 'content': '', 'title': '', 'text': '', 'error': 'No content found'}
            
        except Exception as e:
            return {'success': False, 'content': '', 'title': '', 'text': '', 'error': str(e)}
    
    def extract_multiple_articles(self, articles: List[Dict], max_concurrent: int = 3, timeout: int = 180) -> List[Dict]:
        """Extract content from multiple articles with per-article timeout and rate limiting"""
        enhanced_articles = []
        
        def extract_one(article):
            url = article.get('url', '')
            if not url:
                return article
            logger.info(f"Extracting content from article: {url}")
            extraction_result = self.extract_article_content(url)
            enhanced_article = article.copy()
            if extraction_result['success']:
                enhanced_article['extracted_content'] = extraction_result['text']
                enhanced_article['extraction_method'] = extraction_result.get('method', 'unknown')
                enhanced_article['extraction_success'] = True
                if not enhanced_article.get('text_content') or 'ONLY AVAILABLE IN PAID PLANS' in enhanced_article.get('text_content', ''):
                    enhanced_article['text_content'] = extraction_result['text']
            else:
                enhanced_article['extraction_success'] = False
                enhanced_article['extraction_error'] = extraction_result.get('error', 'Unknown error')
            return enhanced_article
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrent) as executor:
            future_to_article = {executor.submit(extract_one, article): article for article in articles}
            for future in concurrent.futures.as_completed(future_to_article, timeout=timeout*len(articles)):
                try:
                    result = future.result(timeout=timeout)
                    # Only keep articles that were extracted within timeout
                    if result.get('extraction_success', True) or result.get('extracted_content'):
                        enhanced_articles.append(result)
                    else:
                        logger.warning(f"Article extraction failed or timed out, skipping article: {result.get('url', '')}")
                except concurrent.futures.TimeoutError:
                    logger.warning("Article extraction timed out, skipping article.")
                    continue
        return enhanced_articles
    
    def is_extractable_url(self, url: str) -> bool:
        """Check if URL is likely to be extractable"""
        if not url:
            return False
        
        # Skip certain domains that are known to block scraping
        blocked_domains = [
            'facebook.com', 'twitter.com', 'instagram.com', 'linkedin.com',
            'youtube.com', 'tiktok.com', 'reddit.com'
        ]
        
        domain = urlparse(url).netloc.lower()
        for blocked in blocked_domains:
            if blocked in domain:
                return False
        
        return True 