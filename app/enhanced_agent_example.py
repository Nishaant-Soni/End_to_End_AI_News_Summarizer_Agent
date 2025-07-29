# Enhanced News Summarizer Agent with LangGraph
# This shows what we can achieve with a more sophisticated agent framework

from typing import Dict, List, Optional, TypedDict, Annotated
from datetime import datetime
import operator
from loguru import logger

# LangGraph imports (would need to be installed)
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.tools import Tool

# Current tools (enhanced)
from .tools.fetch_news import NewsFetcher
from .tools.summarize import TextSummarizer

class AgentState(TypedDict):
    """State that flows through the agent workflow"""
    topic: str
    max_articles: int
    language: str
    articles: List[Dict]
    summarized_articles: List[Dict]
    digest: Dict
    quality_score: float
    should_retry: bool
    error_count: int
    metadata: Dict
    messages: Annotated[List, operator.add]

class EnhancedNewsAgent:
    """Enhanced News Agent with LangGraph for intelligent workflow"""
    
    def __init__(self, api_key: str, model_name: str = "facebook/bart-large-cnn", cache_dir: str = "./cache"):
        self.news_fetcher = NewsFetcher(api_key, cache_dir)
        self.summarizer = TextSummarizer(model_name, cache_dir)
        
        # Build the agent workflow graph
        self.graph = self._build_workflow()
        
        logger.info("Enhanced News Agent with LangGraph initialized")
    
    def _build_workflow(self) -> StateGraph:
        """Build the agent workflow using LangGraph"""
        
        # Define the workflow graph
        workflow = StateGraph(AgentState)
        
        # Add nodes (steps in the workflow)
        workflow.add_node("plan_search", self._plan_search_strategy)
        workflow.add_node("fetch_news", self._fetch_news)
        workflow.add_node("quality_check", self._quality_check)
        workflow.add_node("enhance_search", self._enhance_search)
        workflow.add_node("summarize", self._summarize_articles)
        workflow.add_node("create_digest", self._create_digest)
        workflow.add_node("final_quality_check", self._final_quality_check)
        workflow.add_node("error_handler", self._handle_errors)
        
        # Define the workflow edges (transitions)
        workflow.set_entry_point("plan_search")
        
        # From plan_search, always go to fetch_news
        workflow.add_edge("plan_search", "fetch_news")
        
        # From fetch_news, go to quality_check
        workflow.add_edge("fetch_news", "quality_check")
        
        # Conditional edges from quality_check
        workflow.add_conditional_edges(
            "quality_check",
            self._should_enhance_search,
            {
                "enhance": "enhance_search",
                "proceed": "summarize",
                "error": "error_handler"
            }
        )
        
        # From enhance_search, retry fetch_news
        workflow.add_edge("enhance_search", "fetch_news")
        
        # From summarize, go to create_digest
        workflow.add_edge("summarize", "create_digest")
        
        # From create_digest, do final quality check
        workflow.add_edge("create_digest", "final_quality_check")
        
        # From final_quality_check, either end or retry
        workflow.add_conditional_edges(
            "final_quality_check",
            self._should_retry_workflow,
            {
                "retry": "plan_search",
                "finish": END
            }
        )
        
        # Error handler can either retry or end
        workflow.add_conditional_edges(
            "error_handler",
            self._handle_error_decision,
            {
                "retry": "plan_search",
                "finish": END
            }
        )
        
        return workflow.compile()
    
    def _plan_search_strategy(self, state: AgentState) -> AgentState:
        """Plan the search strategy based on topic"""
        topic = state["topic"]
        
        # Intelligent topic analysis and search planning
        search_variations = self._generate_search_variations(topic)
        
        state["messages"].append(HumanMessage(content=f"Planning search strategy for: {topic}"))
        state["metadata"] = {
            "search_variations": search_variations,
            "strategy": "multi_query" if len(search_variations) > 1 else "single_query"
        }
        
        logger.info(f"Planned search strategy: {state['metadata']['strategy']}")
        return state
    
    def _fetch_news(self, state: AgentState) -> AgentState:
        """Fetch news with intelligent retry logic"""
        try:
            articles = self.news_fetcher.search_news(
                topic=state["topic"],
                language=state["language"],
                max_articles=state["max_articles"]
            )
            
            state["articles"] = articles
            state["messages"].append(AIMessage(content=f"Fetched {len(articles)} articles"))
            
        except Exception as e:
            state["articles"] = []
            state["error_count"] = state.get("error_count", 0) + 1
            logger.error(f"Error fetching news: {e}")
        
        return state
    
    def _quality_check(self, state: AgentState) -> AgentState:
        """Check quality of fetched articles"""
        articles = state["articles"]
        
        if not articles:
            state["quality_score"] = 0.0
            return state
        
        # Quality metrics
        quality_factors = {
            "count": min(len(articles) / state["max_articles"], 1.0),
            "content_richness": sum(1 for a in articles if len(a.get("text_content", "")) > 100) / len(articles),
            "source_diversity": len(set(a.get("source", "") for a in articles)) / len(articles),
            "recency": 1.0  # Could analyze publication dates
        }
        
        state["quality_score"] = sum(quality_factors.values()) / len(quality_factors)
        state["messages"].append(AIMessage(content=f"Quality score: {state['quality_score']:.2f}"))
        
        logger.info(f"Article quality score: {state['quality_score']:.2f}")
        return state
    
    def _should_enhance_search(self, state: AgentState) -> str:
        """Decide whether to enhance search or proceed"""
        quality_score = state.get("quality_score", 0)
        error_count = state.get("error_count", 0)
        
        if error_count > 2:
            return "error"
        elif quality_score < 0.5 and error_count < 2:
            return "enhance"
        else:
            return "proceed"
    
    def _enhance_search(self, state: AgentState) -> AgentState:
        """Enhance search with alternative queries"""
        current_topic = state["topic"]
        
        # Generate alternative search terms
        alternatives = self._generate_search_variations(current_topic)
        
        if alternatives:
            # Try the first alternative
            state["topic"] = alternatives[0]
            state["messages"].append(AIMessage(content=f"Enhancing search with: {alternatives[0]}"))
            logger.info(f"Enhanced search query: {alternatives[0]}")
        
        return state
    
    def _summarize_articles(self, state: AgentState) -> AgentState:
        """Summarize articles with quality awareness"""
        articles = state["articles"]
        
        # Adaptive summarization based on article count and quality
        if len(articles) > 15:
            # For many articles, use shorter summaries
            max_length = 100
        elif len(articles) < 5:
            # For few articles, use longer summaries
            max_length = 200
        else:
            max_length = 150
        
        summarized_articles = self.summarizer.summarize_articles(
            articles, 
            max_length=max_length
        )
        
        state["summarized_articles"] = summarized_articles
        state["messages"].append(AIMessage(content=f"Summarized {len(summarized_articles)} articles"))
        
        return state
    
    def _create_digest(self, state: AgentState) -> AgentState:
        """Create intelligent digest summary"""
        summarized_articles = state["summarized_articles"]
        
        # Adaptive digest length based on content
        digest_length = min(300, 50 * len(summarized_articles))
        
        digest = self.summarizer.create_digest_summary(
            summarized_articles,
            max_length=digest_length
        )
        
        state["digest"] = digest
        state["messages"].append(AIMessage(content="Created digest summary"))
        
        return state
    
    def _final_quality_check(self, state: AgentState) -> AgentState:
        """Final quality assessment"""
        # Check if results meet quality standards
        articles_count = len(state.get("summarized_articles", []))
        digest_quality = len(state.get("digest", {}).get("digest", ""))
        
        final_score = (articles_count / max(state["max_articles"], 10)) * 0.7 + \
                     min(digest_quality / 100, 1.0) * 0.3
        
        state["quality_score"] = final_score
        state["should_retry"] = final_score < 0.3 and state.get("error_count", 0) < 2
        
        return state
    
    def _should_retry_workflow(self, state: AgentState) -> str:
        """Decide whether to retry the entire workflow"""
        return "retry" if state.get("should_retry", False) else "finish"
    
    def _handle_errors(self, state: AgentState) -> AgentState:
        """Handle errors intelligently"""
        error_count = state.get("error_count", 0)
        
        if error_count < 3:
            # Try with a broader search term
            state["topic"] = self._broaden_topic(state["topic"])
            state["max_articles"] = min(state["max_articles"] + 5, 30)
            
        state["messages"].append(AIMessage(content=f"Handling error (attempt {error_count})"))
        return state
    
    def _handle_error_decision(self, state: AgentState) -> str:
        """Decide how to handle errors"""
        error_count = state.get("error_count", 0)
        return "retry" if error_count < 3 else "finish"
    
    def _generate_search_variations(self, topic: str) -> List[str]:
        """Generate search query variations"""
        # Simple variation generation - could be enhanced with LLM
        variations = []
        
        # Add broader terms
        if " " in topic:
            words = topic.split()
            if len(words) > 1:
                variations.append(words[0])  # First word only
                variations.append(" ".join(words[:2]))  # First two words
        
        # Add related terms (could use a proper knowledge graph)
        topic_lower = topic.lower()
        if "ai" in topic_lower or "artificial intelligence" in topic_lower:
            variations.extend(["machine learning", "AI technology", "artificial intelligence"])
        elif "climate" in topic_lower:
            variations.extend(["environment", "global warming", "sustainability"])
        
        return variations[:3]  # Limit variations
    
    def _broaden_topic(self, topic: str) -> str:
        """Broaden the search topic"""
        words = topic.split()
        if len(words) > 2:
            return " ".join(words[:2])  # Take first two words
        elif len(words) == 2:
            return words[0]  # Take first word
        else:
            return "news"  # Fallback
    
    # Public API methods
    def process_topic(self, topic: str, max_articles: int = 20, language: str = "en") -> Dict:
        """Process a topic using the intelligent workflow"""
        initial_state = AgentState(
            topic=topic,
            max_articles=max_articles,
            language=language,
            articles=[],
            summarized_articles=[],
            digest={},
            quality_score=0.0,
            should_retry=False,
            error_count=0,
            metadata={},
            messages=[]
        )
        
        try:
            # Run the workflow
            final_state = self.graph.invoke(initial_state)
            
            # Format response
            response = {
                "status": "success",
                "topic": final_state["topic"],
                "timestamp": datetime.now().isoformat(),
                "digest": final_state["digest"],
                "articles": final_state["summarized_articles"],
                "metadata": {
                    "total_articles": len(final_state["summarized_articles"]),
                    "language": language,
                    "quality_score": final_state["quality_score"],
                    "workflow_messages": [msg.content for msg in final_state["messages"]],
                    "cached_articles": sum(1 for a in final_state["summarized_articles"] if a.get('cached', False)),
                    "sources": list(set(a.get('source', 'Unknown') for a in final_state["summarized_articles"]))
                }
            }
            
            logger.info(f"Successfully processed topic with LangGraph: {topic}")
            return response
            
        except Exception as e:
            logger.error(f"Error in LangGraph workflow: {e}")
            return {
                "status": "error",
                "message": f"Workflow failed: {str(e)}",
                "topic": topic,
                "timestamp": datetime.now().isoformat()
            }

# Usage comparison:
# 
# Current: Simple linear flow
# 1. Fetch news
# 2. Summarize
# 3. Create digest
# 4. Return
#
# Enhanced with LangGraph: Intelligent adaptive flow
# 1. Plan search strategy
# 2. Fetch news
# 3. Quality check → (enhance search if needed)
# 4. Summarize with adaptive parameters
# 5. Create intelligent digest
# 6. Final quality check → (retry if needed)
# 7. Return with rich metadata
