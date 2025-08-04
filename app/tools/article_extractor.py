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
    
    def __init__(self, timeout: int = 10, max_retries: int = 2):  # Reduced timeout
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # Blacklist problematic domains/patterns
        self.blacklisted_patterns = [
            'yahoo.com/news/videos/',  # Yahoo video pages
            'youtube.com',
            'tiktok.com',
            'instagram.com',
            'facebook.com',
            'twitter.com',
            'x.com'
        ]
    
    def extract_article_content(self, url: str) -> Dict:
        """Extract article content using multiple methods with timeout"""
        if not url or not url.startswith('http'):
            return {
                'success': False,
                'content': '',
                'title': '',
                'text': '',
                'error': 'Invalid URL'
            }
        
        # Check if URL is blacklisted
        if self._is_blacklisted(url):
            logger.warning(f"URL is blacklisted for extraction: {url}")
            return {
                'success': False,
                'content': '',
                'title': '',
                'text': '',
                'error': 'URL blacklisted for extraction'
            }
        
        # Try multiple extraction methods with timeout
        methods = [
            self._extract_with_trafilatura,
            self._extract_with_newspaper,
            self._extract_with_beautifulsoup
        ]
        
        for method in methods:
            try:
                # Use concurrent.futures to enforce timeout
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(method, url)
                    try:
                        result = future.result(timeout=self.timeout)  # Strict timeout
                        if result['success'] and result['text'] and len(result['text'].strip()) > 100:
                            logger.info(f"Successfully extracted content using {method.__name__}: {len(result['text'])} chars")
                            return result
                    except concurrent.futures.TimeoutError:
                        logger.warning(f"Method {method.__name__} timed out for {url}")
                        continue
            except Exception as e:
                logger.warning(f"Method {method.__name__} failed for {url}: {e}")
                continue
        
        return {
            'success': False,
            'content': '',
            'title': '',
            'text': '',
            'error': 'All extraction methods failed or timed out'
        }
    
    def _is_blacklisted(self, url: str) -> bool:
        """Check if URL matches blacklisted patterns"""
        for pattern in self.blacklisted_patterns:
            if pattern in url.lower():
                return True
        return False
    
    def _extract_with_trafilatura(self, url: str) -> Dict:
        """Extract using trafilatura (best for modern websites)"""
        try:
            logger.info(f"Trying trafilatura extraction for: {url}")
            
            # Use requests with shorter timeout
            response = self.session.get(url, timeout=self.timeout // 2)
            if response.status_code != 200:
                return {'success': False, 'content': '', 'title': '', 'text': '', 'error': f'HTTP {response.status_code}'}
            
            downloaded = response.text
            
            # Limit response size to prevent memory issues
            if len(downloaded) > 1_000_000:  # 1MB limit
                logger.warning(f"Response too large ({len(downloaded)} chars), truncating")
                downloaded = downloaded[:1_000_000]
            
            # Extract main content with simpler configuration (faster)
            text = trafilatura.extract(
                downloaded, 
                include_formatting=False,  # Disable formatting for speed
                include_links=False,       # Disable links for speed
                include_images=False,      # Disable images for speed
                include_tables=False       # Disable tables for speed
            )
            
            # Simple title extraction from HTML
            title = ''
            try:
                title_match = re.search(r'<title[^>]*>([^<]+)</title>', downloaded, re.IGNORECASE)
                if title_match:
                    title = title_match.group(1).strip()
            except Exception:
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
            logger.info(f"Trying newspaper extraction for: {url}")
            
            article = Article(url)
            article.set_config(
                timeout=self.timeout // 2,
                browser_user_agent=self.session.headers['User-Agent']
            )
            
            article.download()
            article.parse()
            
            if article.text and len(article.text.strip()) > 50:
                logger.info(f"Newspaper successful: {len(article.text)} characters")
                return {
                    'success': True,
                    'content': article.text,
                    'title': article.title or '',
                    'text': article.text,
                    'method': 'newspaper'
                }
            
            return {'success': False, 'content': '', 'title': '', 'text': '', 'error': 'No content found'}
            
        except Exception as e:
            logger.error(f"Newspaper exception: {e}")
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
        
        # Skip certain domains that are known to block scraping or cause issues
        blocked_domains = [
            'facebook.com', 'twitter.com', 'instagram.com', 'linkedin.com',
            'youtube.com', 'tiktok.com', 'reddit.com'
        ]
        
        # Also check for problematic URL patterns
        blocked_patterns = [
            'yahoo.com/news/videos/',  # Yahoo video pages often hang
            'finance.yahoo.com/video/', 
            'news.yahoo.com/video/'
        ]
        
        domain = urlparse(url).netloc.lower()
        for blocked in blocked_domains:
            if blocked in domain:
                return False
        
        # Check for blocked patterns        
        for pattern in blocked_patterns:
            if pattern in url.lower():
                return False
        
        return True 