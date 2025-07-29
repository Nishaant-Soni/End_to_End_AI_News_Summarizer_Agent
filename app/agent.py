from typing import Dict, List, Optional, TypedDict, Annotated
from datetime import datetime
import os
from loguru import logger

from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

from .tools.fetch_news import NewsFetcher
from .tools.summarize import TextSummarizer

class AgentState(TypedDict):
    """State for the news summarization agent"""
    messages: Annotated[List[BaseMessage], add_messages]
    topic: str
    language: str
    max_articles: int
    articles: List[Dict]
    summarized_articles: List[Dict]
    digest: Dict
    error: Optional[str]
    retry_count: int
    quality_score: float

class NewsAgent:
    """LangGraph-powered AI agent that orchestrates news fetching and summarization"""
    
    def __init__(self, api_key: str, model_name: str = "facebook/bart-large-cnn", cache_dir: str = "./cache", use_timeframe: bool = False, enable_extraction: bool = True):
        self.news_fetcher = NewsFetcher(api_key, cache_dir, use_timeframe=use_timeframe, enable_extraction=enable_extraction)
        self.summarizer = TextSummarizer(model_name, cache_dir)
        self.graph = self._build_graph()
        
        logger.info("LangGraph News Agent initialized successfully")
    
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow"""
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("validate_input", self._validate_input)
        workflow.add_node("fetch_news", self._fetch_news)
        workflow.add_node("quality_check", self._quality_check)
        workflow.add_node("enhance_search", self._enhance_search)
        workflow.add_node("summarize_articles", self._summarize_articles)
        workflow.add_node("create_digest", self._create_digest)
        workflow.add_node("format_response", self._format_response)
        workflow.add_node("handle_error", self._handle_error)
        
        # Set entry point
        workflow.set_entry_point("validate_input")
        
        # Add edges
        workflow.add_edge("validate_input", "fetch_news")
        workflow.add_edge("fetch_news", "quality_check")
        
        # Conditional routing based on quality
        workflow.add_conditional_edges(
            "quality_check",
            self._should_enhance_search,
            {
                "enhance": "enhance_search",
                "proceed": "summarize_articles",
                "error": "handle_error"
            }
        )
        
        workflow.add_edge("enhance_search", "fetch_news")
        workflow.add_edge("summarize_articles", "create_digest")
        workflow.add_edge("create_digest", "format_response")
        workflow.add_edge("format_response", END)
        workflow.add_edge("handle_error", END)
        
        return workflow.compile()
    
    def _validate_input(self, state: AgentState) -> AgentState:
        """Validate and prepare input"""
        logger.info(f"Validating input for topic: {state['topic']}")
        
        if not state["topic"] or len(state["topic"].strip()) < 2:
            state["error"] = "Topic must be at least 2 characters long"
            return state
        
        # Initialize state
        state["retry_count"] = 0
        state["quality_score"] = 0.0
        state["articles"] = []
        state["summarized_articles"] = []
        state["digest"] = {}
        
        # Add user message to conversation
        state["messages"].append(HumanMessage(content=f"Summarize news about: {state['topic']}"))
        
        return state
    
    def _fetch_news(self, state: AgentState) -> AgentState:
        """Fetch news articles"""
        logger.info(f"Fetching news for: {state['topic']}")
        
        try:
            articles = self.news_fetcher.search_news(
                topic=state["topic"],
                language=state["language"],
                max_articles=state["max_articles"]
            )
            # Filter out articles that failed extraction (extraction_success is False)
            articles = [a for a in articles if a.get('extraction_success', True)]
            state["articles"] = articles
            # Add AI message about fetching
            state["messages"].append(
                AIMessage(content=f"Found {len(articles)} articles about {state['topic']}")
            )
        except Exception as e:
            logger.error(f"Error fetching news: {e}")
            state["error"] = f"Failed to fetch news: {str(e)}"
        
        return state
    
    def _quality_check(self, state: AgentState) -> AgentState:
        """Check the quality of fetched articles"""
        articles = state["articles"]
        
        if not articles:
            state["quality_score"] = 0.0
            state["error"] = "No articles found for this topic. Please try a different search term."
            return state
        
        # Calculate quality score based on various factors
        quality_factors = []
        
        # Factor 1: Number of articles
        article_score = min(len(articles) / state["max_articles"], 1.0)
        quality_factors.append(article_score)
        
        # Factor 2: Content richness
        content_scores = []
        for article in articles:
            content = article.get('text_content', '')
            if len(content) > 200:
                content_scores.append(1.0)
            elif len(content) > 100:
                content_scores.append(0.7)
            elif len(content) > 50:
                content_scores.append(0.4)
            else:
                content_scores.append(0.1)
        
        avg_content_score = sum(content_scores) / len(content_scores) if content_scores else 0.0
        quality_factors.append(avg_content_score)
        
        # Factor 3: Source diversity
        sources = set(article.get('source', 'unknown') for article in articles)
        source_diversity = min(len(sources) / max(len(articles) * 0.7, 1), 1.0)
        quality_factors.append(source_diversity)
        
        # Calculate overall quality score
        state["quality_score"] = sum(quality_factors) / len(quality_factors)
        
        logger.info(f"Quality score: {state['quality_score']:.2f}")
        
        return state
    
    def _should_enhance_search(self, state: AgentState) -> str:
        """Determine if search should be enhanced"""
        if state.get("error"):
            return "error"
        
        # If quality is low and we haven't retried too many times
        if state["quality_score"] < 0.5 and state["retry_count"] < 2:
            return "enhance"
        
        if not state["articles"]:
            return "error"
        
        return "proceed"
    
    def _enhance_search(self, state: AgentState) -> AgentState:
        """Enhance search with alternative terms"""
        state["retry_count"] += 1
        original_topic = state["topic"]
        
        logger.info(f"Enhancing search for: {original_topic} (attempt {state['retry_count']})")
        
        # Add synonyms or related terms
        enhancement_strategies = [
            f"{original_topic} news",
            f"{original_topic} latest",
            f"{original_topic} updates",
        ]
        
        if state["retry_count"] <= len(enhancement_strategies):
            enhanced_topic = enhancement_strategies[state["retry_count"] - 1]
            state["topic"] = enhanced_topic
            
            state["messages"].append(
                AIMessage(content=f"Enhancing search with: {enhanced_topic}")
            )
        
        return state
    
    def _summarize_articles(self, state: AgentState) -> AgentState:
        """Summarize the articles"""
        logger.info("Summarizing articles")
        
        try:
            # Adjust summary length based on number of articles
            article_count = len(state["articles"])
            if article_count > 15:
                max_length, min_length = 100, 30
            elif article_count > 10:
                max_length, min_length = 130, 40
            else:
                max_length, min_length = 150, 50
            summarized_articles = self.summarizer.summarize_articles(
                state["articles"],
                max_length=max_length,
                min_length=min_length
            )
            state["summarized_articles"] = summarized_articles
            state["messages"].append(
                AIMessage(content=f"Summarized {len(summarized_articles)} articles")
            )
        except Exception as e:
            logger.error(f"Error summarizing articles: {e}")
            state["error"] = f"Failed to summarize articles: {str(e)}"
        
        return state
    
    def _create_digest(self, state: AgentState) -> AgentState:
        """Create digest summary"""
        logger.info("Creating digest summary")
        
        try:
            # Adjust digest length based on article count
            article_count = len(state["summarized_articles"])
            digest_length = min(200 + (article_count * 10), 300)
            
            digest = self.summarizer.create_digest_summary(
                state["summarized_articles"],
                max_length=digest_length
            )
            
            state["digest"] = digest
            
            state["messages"].append(
                AIMessage(content=f"Created executive summary covering {article_count} articles")
            )
            
        except Exception as e:
            logger.error(f"Error creating digest: {e}")
            state["error"] = f"Failed to create digest: {str(e)}"
        
        return state
    
    def _format_response(self, state: AgentState) -> AgentState:
        """Format the final response"""
        logger.info("Formatting response")
        
        # Response is already in the state, no additional formatting needed
        state["messages"].append(
            AIMessage(content="News summary completed successfully!")
        )
        
        return state
    
    def _handle_error(self, state: AgentState) -> AgentState:
        """Handle errors gracefully"""
        error_msg = state.get("error", "Unknown error occurred")
        logger.error(f"Handling error: {error_msg}")
        
        state["messages"].append(
            AIMessage(content=f"Error: {error_msg}")
        )
        
        return state

    def process_topic(self, topic: str, max_articles: int = 20, language: str = "en") -> Dict:
        """Process a topic using LangGraph workflow"""
        logger.info(f"Processing topic with LangGraph: {topic}")
        
        try:
            # Initialize state
            initial_state = AgentState(
                messages=[],
                topic=topic,
                language=language,
                max_articles=max_articles,
                articles=[],
                summarized_articles=[],
                digest={},
                error=None,
                retry_count=0,
                quality_score=0.0
            )
            
            # Run the graph
            final_state = self.graph.invoke(initial_state)
            
            # Check for errors
            if final_state.get("error"):
                return {
                    "status": "error",
                    "message": final_state["error"],
                    "topic": topic,
                    "timestamp": datetime.now().isoformat(),
                    "workflow_messages": [msg.content for msg in final_state.get("messages", [])]
                }
            
            # Prepare successful response
            response = {
                "status": "success",
                "topic": topic,
                "timestamp": datetime.now().isoformat(),
                "digest": final_state.get("digest", {}),
                "articles": final_state.get("summarized_articles", []),
                "metadata": {
                    "total_articles": len(final_state.get("summarized_articles", [])),
                    "language": language,
                    "cached_articles": sum(1 for a in final_state.get("summarized_articles", []) if a.get('cached', False)),
                    "sources": list(set(a.get('source', 'Unknown') for a in final_state.get("summarized_articles", []))),
                    "quality_score": final_state.get("quality_score", 0.0),
                    "retry_count": final_state.get("retry_count", 0),
                    "workflow_steps": len(final_state.get("messages", []))
                },
                "workflow_messages": [msg.content for msg in final_state.get("messages", [])]
            }
            
            logger.info(f"Successfully processed topic: {topic} ({len(final_state.get('summarized_articles', []))} articles)")
            return response
            
        except Exception as e:
            logger.error(f"Error in LangGraph workflow for topic {topic}: {e}")
            return {
                "status": "error",
                "message": f"Workflow failed: {str(e)}",
                "topic": topic,
                "timestamp": datetime.now().isoformat()
            }
    
    def get_trending_topics(self, language: str = "en") -> Dict:
        """Get trending topics"""
        logger.info("Fetching trending topics")
        
        try:
            trending = self.news_fetcher.get_trending_topics(language)
            
            return {
                "status": "success",
                "trending_topics": trending,
                "timestamp": datetime.now().isoformat(),
                "language": language
            }
            
        except Exception as e:
            logger.error(f"Error fetching trending topics: {e}")
            return {
                "status": "error",
                "message": f"Failed to fetch trending topics: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }
    
    def process_trending_topic(self, topic_name: str, max_articles: int = 10, language: str = "en") -> Dict:
        """Process a specific trending topic using LangGraph"""
        return self.process_topic(topic_name, max_articles, language)
    
    def get_cached_topics(self) -> List[str]:
        """Get list of cached topics (for memory feature)"""
        try:
            # This is a simplified implementation - in practice, you'd want to 
            # store metadata about cached queries
            cache_keys = list(self.news_fetcher.cache.iterkeys())
            topics = []
            
            for key in cache_keys:
                if key.startswith('search_'):
                    # Extract topic from cache key
                    parts = key.split('_', 2)
                    if len(parts) >= 3:
                        topic = parts[1]
                        topics.append(topic)
            
            return list(set(topics))  # Remove duplicates
            
        except Exception as e:
            logger.error(f"Error getting cached topics: {e}")
            return []
    
    def clear_all_cache(self):
        """Clear all caches"""
        try:
            self.news_fetcher.clear_cache()
            self.summarizer.clear_cache()
            logger.info("All caches cleared")
            
        except Exception as e:
            logger.error(f"Error clearing caches: {e}")
    
    def get_agent_status(self) -> Dict:
        """Get agent status and statistics"""
        try:
            cached_topics = self.get_cached_topics()
            
            return {
                "status": "online",
                "agent_type": "LangGraph News Agent",
                "model": self.summarizer.model_name,
                "cached_topics_count": len(cached_topics),
                "cached_topics": cached_topics[:10],  # Show first 10
                "capabilities": [
                    "Intelligent news fetching",
                    "Quality-based search enhancement",
                    "Adaptive summarization",
                    "Workflow-based processing",
                    "Error recovery"
                ],
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting agent status: {e}")
            return {
                "status": "error",
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            }
