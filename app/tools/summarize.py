from typing import List, Dict, Optional
import torch
from transformers import pipeline, AutoTokenizer, AutoModelForSeq2SeqLM
import diskcache as dc
from loguru import logger
import hashlib
import json
import threading
import asyncio
from concurrent.futures import ThreadPoolExecutor

class TextSummarizer:
    """Tool for summarizing text using Hugging Face transformers"""
    
    def __init__(self, model_name: str = "facebook/bart-large-cnn", cache_dir: str = "./cache", cache_ttl: int = 3600):
        self.model_name = model_name
        self.cache = dc.Cache(cache_dir)
        self.cache_ttl = cache_ttl
        self.summarizer = None
        self.tokenizer = None
        self._model_lock = threading.Lock()  # Add thread lock for model safety
        
        # Initialize the model
        self._load_model()
    
    def _load_model(self):
        """Load the summarization model and tokenizer"""
        try:
            logger.info(f"Loading model: {self.model_name}")
            
            # Load tokenizer and model
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            
            # Use GPU if available
            device = 0 if torch.cuda.is_available() else -1
            
            self.summarizer = pipeline(
                "summarization",
                model=self.model_name,
                tokenizer=self.tokenizer,
                device=device,
                framework="pt"
            )
            
            logger.info(f"Model loaded successfully on device: {'GPU' if device == 0 else 'CPU'}")
            
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise
    
    def _generate_cache_key(self, text: str, max_length: int, min_length: int) -> str:
        """Generate a cache key for the given text and parameters"""
        content = f"{text}_{max_length}_{min_length}_{self.model_name}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def _preprocess_text(self, text: str) -> str:
        """Preprocess text for summarization, strictly truncate to 1024 tokens using tokenizer"""
        text = ' '.join(text.split())
        # Use tokenizer to count tokens
        if self.tokenizer:
            tokens = self.tokenizer.encode(text, truncation=True, max_length=1024)
            text = self.tokenizer.decode(tokens, skip_special_tokens=True)
        else:
            # Fallback: truncate by words
            max_input_length = 1000
            if len(text.split()) > max_input_length:
                text = ' '.join(text.split()[:max_input_length])
        return text
    
    def summarize_text(self, text: str, max_length: int = 150, min_length: int = 50) -> Dict:
        """Summarize a single piece of text with improved error handling"""
        if not text or len(text.strip()) < 50:
            return {
                "summary": "Content not available for summarization (requires paid plan).",
                "original_length": len(text),
                "summary_length": 0,
                "cached": False
            }
        
        # Check cache first
        cache_key = self._generate_cache_key(text, max_length, min_length)
        cached_result = self.cache.get(cache_key)
        if cached_result:
            logger.info("Retrieved cached summary")
            cached_result["cached"] = True
            return cached_result
        
        # Initialize retry mechanism
        max_retries = 3
        last_error = None
        
        for attempt in range(max_retries):
            try:
                # Preprocess text
                processed_text = self._preprocess_text(text)
                
                if attempt == 0:
                    logger.info(f"Summarizing text of length: {len(processed_text)}")
                else:
                    logger.info(f"Retry attempt {attempt + 1} for summarization")
                
                # Use thread lock to prevent "Already borrowed" error
                with self._model_lock:
                    # Generate summary with timeout protection
                    summary_result = self.summarizer(
                        processed_text,
                        max_length=max_length,
                        min_length=min_length,
                        do_sample=False,
                        num_beams=4,
                        length_penalty=2.0,
                        early_stopping=True
                    )
                
                summary = summary_result[0]['summary_text']
                
                result = {
                    "summary": summary,
                    "original_length": len(text),
                    "summary_length": len(summary),
                    "cached": False
                }
                
                # Cache the result
                self.cache.set(cache_key, result, expire=self.cache_ttl)
                
                logger.info(f"Summary generated: {len(summary)} characters")
                return result
                
            except Exception as e:
                last_error = e
                error_msg = str(e).lower()
                
                if "already borrowed" in error_msg:
                    logger.warning(f"Model busy (attempt {attempt + 1}), waiting...")
                    # Wait a bit before retrying
                    import time
                    time.sleep(0.5 * (attempt + 1))  # Exponential backoff
                    continue
                elif "out of memory" in error_msg or "cuda" in error_msg:
                    logger.error(f"GPU memory issue: {e}")
                    break
                else:
                    logger.error(f"Summarization attempt {attempt + 1} failed: {e}")
                    if attempt < max_retries - 1:
                        continue
        
        # If all retries failed
        logger.error(f"All summarization attempts failed. Last error: {last_error}")
        return {
            "summary": "Unable to generate summary due to technical limitations.",
            "original_length": len(text),
            "summary_length": 0,
            "cached": False
        }
    
    def summarize_articles(self, articles: List[Dict], max_length: int = 150, min_length: int = 50) -> List[Dict]:
        """Summarize multiple articles efficiently (sequential but optimized)"""
        summarized_articles = []
        
        if not articles:
            return []
        
        logger.info(f"Starting summarization of {len(articles)} articles")
        
        for i, article in enumerate(articles):
            logger.info(f"Summarizing article {i+1}/{len(articles)}: {article.get('title', 'No title')[:50]}...")
            
            # Get text content
            text_content = article.get('text_content', article.get('description', ''))
            
            # Summarize with error handling
            try:
                summary_result = self.summarize_text(text_content, max_length, min_length)
            except Exception as e:
                logger.error(f"Failed to summarize article {i+1}: {e}")
                summary_result = {
                    "summary": "Unable to generate summary for this article.",
                    "original_length": len(text_content),
                    "summary_length": 0,
                    "cached": False
                }
            
            # Create summarized article
            summarized_article = article.copy()
            summarized_article.update({
                'summary': summary_result['summary'],
                'summary_length': summary_result['summary_length'],
                'original_length': summary_result['original_length'],
                'cached': summary_result['cached']
            })
            
            summarized_articles.append(summarized_article)
        
        logger.info(f"Completed summarization of {len(summarized_articles)} articles")
        return summarized_articles
    
    async def summarize_articles_async(self, articles: List[Dict], max_length: int = 150, min_length: int = 50) -> List[Dict]:
        """Async wrapper for article summarization (for future use)"""
        return await asyncio.get_event_loop().run_in_executor(
            None, 
            self.summarize_articles,
            articles,
            max_length,
            min_length
        )
    
    def create_digest_summary(self, articles: List[Dict], max_length: int = 200) -> Dict:
        """Create an overall digest summary from multiple articles"""
        if not articles:
            return {
                "digest": "No articles to summarize.",
                "article_count": 0,
                "cached": False
            }
        
        # Check if we have meaningful content to summarize
        meaningful_articles = []
        for article in articles:
            text_content = article.get('text_content', '')
            if text_content and len(text_content.strip()) > 100 and 'ONLY AVAILABLE IN PAID PLANS' not in text_content:
                meaningful_articles.append(article)
        
        if not meaningful_articles:
            return {
                "digest": f"Found {len(articles)} articles, but full content requires a paid NewsData.io plan. Only article titles and descriptions are available in the free tier.",
                "article_count": len(articles),
                "cached": False
            }
        
        # Combine all summaries or descriptions
        combined_text = ""
        for article in articles:
            if 'summary' in article and article['summary'] and 'Content not available' not in article['summary']:
                combined_text += f"{article['summary']} "
            else:
                text_content = article.get('text_content', article.get('description', ''))
                if text_content and 'ONLY AVAILABLE IN PAID PLANS' not in text_content:
                    combined_text += f"{text_content[:200]}... "
        
        if not combined_text.strip():
            return {
                "digest": "No content available for digest.",
                "article_count": len(articles),
                "cached": False
            }
        
        # Create cache key for digest
        cache_key = self._generate_cache_key(f"digest_{combined_text}", max_length, 30)
        cached_result = self.cache.get(cache_key)
        if cached_result:
            logger.info("Retrieved cached digest summary")
            cached_result["cached"] = True
            return cached_result
        
        # Summarize the combined text
        digest_result = self.summarize_text(combined_text, max_length=max_length, min_length=30)
        
        result = {
            "digest": digest_result['summary'],
            "article_count": len(articles),
            "cached": False
        }
        
        # Cache the digest
        self.cache.set(cache_key, result, expire=self.cache_ttl)
        
        return result
    
    def clear_cache(self):
        """Clear the summarization cache"""
        self.cache.clear()
        logger.info("Summarization cache cleared")
