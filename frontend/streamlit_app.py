import streamlit as st
import requests
import json
from datetime import datetime
import base64
from io import BytesIO
import pandas as pd
from streamlit_option_menu import option_menu

# Configuration
API_BASE_URL = "http://localhost:8000"

# Page config
st.set_page_config(
    page_title="AI News Summarizer",
    page_icon="📰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        color: #2c3e50;
        text-align: center;
        margin-bottom: 2rem;
    }
    .summary-card {
        background-color: #f8f9fa;
        padding: 1.5rem;
        border-radius: 10px;
        border-left: 5px solid #3498db;
        margin-bottom: 1rem;
        min-height: 50px;
        word-wrap: break-word;
        white-space: pre-wrap;
    }
        .article-card {
        background-color: #2c3e50;
        color: #ffffff;
        padding: 1rem;
        border-radius: 8px;
        border: 1px solid #34495e;
        margin-bottom: 1rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.3);
    }
    .trending-item {
        background-color: #f1f3f4;
        padding: 1rem;
        border-radius: 8px;
        margin-bottom: 0.5rem;
        border-left: 4px solid #e74c3c;
    }
    .cache-item {
        background-color: #34495e;
        color: #ffffff;
        padding: 0.5rem;
        border-radius: 5px;
        margin-bottom: 0.3rem;
        border-left: 3px solid #27ae60;
    }
</style>
""", unsafe_allow_html=True)

def call_api(endpoint: str, method: str = "GET", data: dict = None, params: dict = None):
    """Make API calls to the backend"""
    try:
        url = f"{API_BASE_URL}{endpoint}"
        timeout = 200  # Increase timeout to 200 seconds
        if method == "GET":
            response = requests.get(url, params=params, timeout=timeout)
        elif method == "POST":
            response = requests.post(url, json=data, timeout=timeout)
        elif method == "DELETE":
            response = requests.delete(url, timeout=timeout)
        else:
            st.error(f"Unsupported HTTP method: {method}")
            return None
        response.raise_for_status()
        return response.json()
    except requests.exceptions.ConnectionError:
        st.error("❌ Cannot connect to the backend API. Please ensure the FastAPI server is running on localhost:8000")
        return None
    except requests.exceptions.Timeout:
        st.error("⏱️ Request timed out. The API might be processing a large request.")
        return None
    except requests.exceptions.RequestException as e:
        st.error(f"❌ API Error: {str(e)}")
        return None
    except Exception as e:
        st.error(f"❌ Unexpected error: {str(e)}")
        return None

def download_pdf(topic: str, content: dict):
    """Download PDF report"""
    try:
        response = requests.post(
            f"{API_BASE_URL}/export/pdf",
            json={"topic": topic, "content": content},
            timeout=60
        )
        response.raise_for_status()
        
        # Create download button
        st.download_button(
            label="📄 Download PDF Report",
            data=response.content,
            file_name=f"news_summary_{topic.replace(' ', '_')}.pdf",
            mime="application/pdf"
        )
        
    except Exception as e:
        st.error(f"Failed to generate PDF: {str(e)}")

def display_summary_result(result: dict):
    """Display the summary result"""
    if result.get("status") != "success":
        st.error(f"❌ {result.get('message', 'Unknown error')}")
        return
    
    # Display workflow information if available
    workflow_messages = result.get("workflow_messages", [])
    if workflow_messages:
        with st.expander("🔄 Agent Workflow Steps", expanded=False):
            for i, msg in enumerate(workflow_messages, 1):
                st.write(f"{i}. {msg}")
    
    # Display metadata
    metadata = result.get("metadata", {})
    if metadata:
        st.markdown("## 📊 Summary Statistics")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Articles", metadata.get("total_articles", 0))
        with col2:
            st.metric("Cached Results", metadata.get("cached_articles", 0))
        with col3:
            st.metric("Quality Score", f"{metadata.get('quality_score', 0):.2f}")
        with col4:
            st.metric("Retry Count", metadata.get("retry_count", 0))
        
        # Additional metrics
        col5, col6, col7, col8 = st.columns(4)
        with col5:
            st.metric("Language", metadata.get("language", "en").upper())
        with col6:
            sources = metadata.get("sources", [])
            st.metric("Unique Sources", len(sources))
        with col7:
            st.metric("Workflow Steps", metadata.get("workflow_steps", 0))
        with col8:
            # Quality indicator
            quality = metadata.get("quality_score", 0)
            if quality >= 0.8:
                st.success("🌟 High Quality")
            elif quality >= 0.6:
                st.info("👍 Good Quality")
            elif quality >= 0.4:
                st.warning("⚠️ Fair Quality")
            else:
                st.error("❌ Low Quality")
    
    # Display articles
    articles = result.get("articles", [])
    if articles:
        st.markdown("## 📰 Individual Articles")
        
        for i, article in enumerate(articles, 1):
            with st.expander(f"📄 {i}. {article.get('title', 'No title')}", expanded=i <= 3):
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    # Display only the article summary in the dark card (remove duplicates)
                    summary_text = article.get("summary", "").strip()
                    if summary_text and len(summary_text) > 20 and 'Content not available' not in summary_text:
                        st.markdown(f'<div class="article-card">{summary_text}</div>', unsafe_allow_html=True)
                    else:
                        # Try to show description if summary is empty or unavailable
                        description = article.get("description", "").strip()
                        if description and len(description) > 20:
                            st.markdown(f'<div class="article-card"><strong>📰 Article Description:</strong><br/>{description}</div>', unsafe_allow_html=True)
                        else:
                            # Try to show text content if everything else is empty
                            text_content = article.get("text_content", "").strip()
                            if text_content and len(text_content) > 50 and 'ONLY AVAILABLE IN PAID PLANS' not in text_content:
                                # Show first 200 characters of content
                                preview = text_content[:200] + "..." if len(text_content) > 200 else text_content
                                st.markdown(f'<div class="article-card"><strong>📄 Content Preview:</strong><br/>{preview}</div>', unsafe_allow_html=True)
                            else:
                                st.warning("⚠️ Full content requires a paid Newsapi.org plan")
                
                with col2:
                    st.markdown("**Source:**")
                    st.write(article.get("source", "Unknown"))
                    
                    if article.get("published_at"):
                        st.markdown("**Published:**")
                        st.write(article.get("published_at"))
                    
                    if article.get("url"):
                        st.markdown("**Link:**")
                        st.markdown(f"[Read Full Article]({article['url']})")
                    
                    if article.get("cached"):
                        st.success("📦 Cached")
                    
                    # Show extraction info if available
                    if article.get("extraction_success"):
                        st.success(f"✅ Content extracted ({article.get('extraction_method', 'unknown')})")
                    elif article.get("extraction_success") is False:
                        st.warning("⚠️ Extraction failed")
                    
                    # Article stats
                    st.markdown("**Stats:**")
                    original_len = article.get("original_length", 0)
                    summary_len = article.get("summary_length", 0)
                    if original_len > 0 and summary_len > 0:
                        # Handle cases where original content is truncated (NewsAPI limitation)
                        text_content = article.get("text_content", "")
                        is_truncated = "[+" in text_content and "chars]" in text_content
                        
                        if is_truncated:
                            st.warning("⚠️ Original content truncated by API")
                        else:
                            compression = round((1 - summary_len/original_len) * 100, 1)
                            if compression > 0:
                                st.write(f"Compression: {compression}%")
                            else:
                                st.write("Summary expanded content")
                    elif summary_len > 0:
                        st.write(f"Summary: {summary_len} chars")
    
    # PDF download button
    if result:
        st.markdown("---")
        download_pdf(result.get("topic", "news_summary"), result)

def main():
    """Main Streamlit application"""
    
    # Initialize session state
    if 'initialized' not in st.session_state:
        st.session_state.initialized = True
    
    # Header
    st.markdown('<h1 class="main-header">🤖 AI News Summarizer Agent</h1>', unsafe_allow_html=True)
    
    # Sidebar navigation
    with st.sidebar:
        
        selected = option_menu(
            "Navigation",
            ["🔍 News Search", "📈 Trending Topics", "🧠 Memory", "⚙️ Settings"],
            icons=['search', 'trending-up', 'brain', 'gear'],
            menu_icon="cast",
            default_index=0,
        )
        
        # API Status
        st.markdown("---")
        status_result = call_api("/status")
        if status_result:
            st.success("✅ API Connected")
            agent_type = status_result.get('agent_type', 'Unknown Agent')
            st.caption(f"Agent: {agent_type}")
            model = status_result.get('model', 'Unknown')
            st.caption(f"Model: {model}")
            
            # Show capabilities if available
            capabilities = status_result.get('capabilities', [])
            if capabilities:
                with st.expander("🚀 Agent Capabilities"):
                    for cap in capabilities:
                        st.write(f"• {cap}")
        else:
            st.error("❌ API Disconnected")
    
    # Main content based on selection
    if selected == "🔍 News Search":
        st.markdown("## 🔍 Search & Summarize News")
        
        # Input form
        with st.form("search_form"):
            col1, col2 = st.columns([3, 1])
            
            with col1:
                topic = st.text_input(
                    "Enter a topic to search:",
                    placeholder="e.g., AI in healthcare, climate change, cryptocurrency...",
                    help="Enter any topic you want to get news summaries for"
                )
            
            with col2:
                max_articles = st.selectbox("Max Articles", list(range(1, 6)), index=2)
                language = st.selectbox("Language", ["en", "es", "fr", "de"], index=0)
            
            submitted = st.form_submit_button("🚀 Get Summary", type="primary")
        
        if submitted and topic:
            with st.spinner("🔄 Fetching and summarizing news..."):
                result = call_api(
                    "/summarize",
                    method="POST",
                    data={
                        "topic": topic,
                        "max_articles": max_articles,
                        "language": language
                    }
                )
                
                if result:
                    display_summary_result(result)
    
    elif selected == "📈 Trending Topics":
        st.markdown("## 📈 Trending Topics")
        
        col1, col2 = st.columns([1, 3])
        with col1:
            language = st.selectbox("Language", ["en", "es", "fr", "de"], key="trending_lang")
            
            if st.button("🔄 Refresh Trending", type="primary"):
                st.rerun()
        
        with col2:
            with st.spinner("📈 Fetching trending topics..."):
                trending_result = call_api("/trending", params={"language": language})
                
                if trending_result and trending_result.get("status") == "success":
                    trending_topics = trending_result.get("trending_topics", [])
                    
                    if trending_topics:
                        st.markdown("### 🔥 Current Trending Topics")
                        
                        for i, topic in enumerate(trending_topics, 1):
                            topic_name = topic.get("topic", "Unknown")
                            count = topic.get("count", 0)
                            
                            with st.container():
                                st.markdown(f'<div class="trending-item">', unsafe_allow_html=True)
                                col_a, col_b = st.columns([3, 1])
                                
                                with col_a:
                                    st.markdown(f"**{i}. {topic_name}**")
                                    latest = topic.get("latest_article", {})
                                    if latest.get("title"):
                                        st.caption(f"Latest: {latest['title'][:100]}...")
                                
                                with col_b:
                                    st.metric("Mentions", count)
                                    if st.button(f"Analyze", key=f"analyze_{i}"):
                                        with st.spinner(f"Analyzing {topic_name}..."):
                                            analysis_result = call_api(f"/trending/{topic_name}", method="POST")
                                            if analysis_result:
                                                st.session_state[f"trending_analysis_{i}"] = analysis_result
                                
                                st.markdown('</div>', unsafe_allow_html=True)
                                
                                # Show analysis if available
                                if f"trending_analysis_{i}" in st.session_state:
                                    with st.expander(f"📊 Analysis: {topic_name}"):
                                        display_summary_result(st.session_state[f"trending_analysis_{i}"])
                    else:
                        st.info("No trending topics found.")
    
    elif selected == "🧠 Memory":
        st.markdown("## 🧠 Memory & Cache Management")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 📦 Cached Topics")
            cache_result = call_api("/cache")
            
            if cache_result and cache_result.get("status") == "success":
                cached_topics = cache_result.get("cached_topics", [])
                
                if cached_topics:
                    for topic in cached_topics:
                        st.markdown(f'<div class="cache-item">🔍 {topic}</div>', unsafe_allow_html=True)
                        
                    st.info(f"💾 {len(cached_topics)} topics cached")
                else:
                    st.info("No cached topics found.")
        
        with col2:
            st.markdown("### ⚡ Quick Actions")
            
            if st.button("🗑️ Clear All Cache", type="secondary"):
                with st.spinner("Clearing cache..."):
                    clear_result = call_api("/cache", method="DELETE")
                    if clear_result:
                        st.success("✅ Cache cleared successfully!")
                        st.rerun()
            
            st.markdown("### 📊 Cache Statistics")
            if cache_result:
                total_cached = cache_result.get("count", 0)
                st.metric("Cached Queries", total_cached)
                
                if total_cached > 0:
                    st.progress(min(total_cached / 50, 1.0))  # Assuming 50 as max for visualization
                    st.caption("Cache utilization")
    
    elif selected == "⚙️ Settings":
        st.markdown("## ⚙️ Settings & Configuration")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 🔧 API Settings")
            
            # Test API connection
            if st.button("🔍 Test API Connection"):
                with st.spinner("Testing connection..."):
                    status = call_api("/status")
                    if status:
                        st.success("✅ API connection successful!")
                        st.json(status)
                    else:
                        st.error("❌ API connection failed!")
            
            st.markdown("### 📈 Performance")
            if status_result:
                cached_count = status_result.get("cached_topics_count", 0)
                st.metric("Cached Topics", cached_count)
                
                model_name = status_result.get("model", "Unknown")
                st.text(f"AI Model: {model_name}")
        
        with col2:
            st.markdown("### ℹ️ About")
            st.markdown("""
            **AI News Summarizer Agent** v2.0.0 🚀
            
            🤖 **Enhanced Features:**
            - **LangGraph Workflow**: Intelligent decision-making
            - **Quality Assessment**: Automatic content evaluation
            - **Search Enhancement**: Retry with better terms
            - **Adaptive Summarization**: Length adjustment
            - **Error Recovery**: Graceful failure handling
            - **PDF Export**: Professional reports
            
            🛠️ **Technology Stack:**
            - **Agent Framework**: LangGraph
            - **Backend**: FastAPI + HuggingFace
            - **Frontend**: Streamlit
            - **AI Model**: BART Large CNN
            - **News API**: Newsapi.org
            """)
            
            # Show LangGraph workflow diagram
            st.markdown("### 🔄 Workflow Diagram")
            st.text("""
            📝 Input Validation
                    ↓
            🔍 Fetch News
                    ↓
            📊 Quality Check
                    ↓
            🔄 Enhance Search? (if low quality)
                    ↓
            📝 Summarize Articles
                    ↓
            📋 Create Digest
                    ↓
            ✅ Format Response
            """)
            
            st.markdown("### 🔗 Quick Links")
            st.markdown("""
            - [API Documentation](http://localhost:8000/docs)
            - [Source Code](https://github.com/your-repo)
            - [Report Issues](https://github.com/your-repo/issues)
            """)

if __name__ == "__main__":
    main()
