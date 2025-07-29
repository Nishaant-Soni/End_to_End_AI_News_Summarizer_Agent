# AI News Summarizer Agent 🤖

A comprehensive AI-powered news aggregation and summarization system that uses **LangGraph** for intelligent workflow orchestration, fetches real-time news articles, and provides intelligent summaries using state-of-the-art transformer models.

## 🌟 Key Features

 **🧠 LangGraph Workflow**: Intelligent decision-making and error recovery
 **🤖 AI Summarization**: Powered by Facebook's BART-large-CNN
 **📈 Trending Topics**: Discover what's trending in the news
 **⚖️ Quality Assessment**: Automatic content evaluation and search enhancement
 **📥 PDF Export**: Download summaries as professional reports
 **🧠 Smart Caching**: Intelligent memory system for faster responses
 **🌍 Multi-language Support**: Support for multiple languages
 **📊 Rich Analytics**: Detailed statistics and workflow insights
 **🖥️ Interactive UI**: Beautiful Streamlit-based web interface

## 🏗️ LangGraph Architecture

```
📝 Input Validation → 🔍 Fetch News → 📊 Quality Check
                                           ↓
🔄 Search Enhancement ← (if low quality) ← Decision Point
                                           ↓
📝 Summarize Articles → 📋 Create Digest → ✅ Format Response
```

The agent uses **LangGraph** to create an intelligent workflow that:
- **Validates** input and prepares the search
- **Fetches** news articles from NewsData API
- **Evaluates** content quality automatically
- **Enhances** search terms if results are poor quality
- **Adapts** summarization length based on article count
- **Recovers** gracefully from errors

## 🛠️ Technology Stack

| Component | Technology |
|-----------|------------|
| **Agent Framework** | **LangGraph** (intelligent workflows) |
| **LLM/Summarization** | HuggingFace `facebook/bart-large-cnn` |
| **News API** | TheNewsAPI |
| **Backend API** | FastAPI |
| **Frontend** | Streamlit |
| **PDF Generation** | ReportLab |
| **Caching** | DiskCache |
| **Deployment** | Docker |

## 📦 Installation

### Prerequisites

1. **Python 3.9+**
2. **TheNewsAPI API Key** - Get it free from (https://www.thenewsapi.com)

### Local Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd News_Summarizer_AI_agent
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application**
   
   **Option A: Run both services separately**
   ```bash
   # Terminal 1 - Start FastAPI backend
   uvicorn app.main:app --reload --port 8000
   
   # Terminal 2 - Start Streamlit frontend
   streamlit run frontend/streamlit_app.py --server.port 8501
   ```
   
   **Option B: Using Docker**
   ```bash
   docker build -t news-summarizer .
   docker run -p 8000:8000 -p 8501:8501 news-summarizer
   ```

5. **Access the application**
   - **Frontend UI**: http://localhost:8501
   - **API Documentation**: http://localhost:8000/docs

## 🚀 Usage

### Web Interface

1. **Navigate to** http://localhost:8501
2. **Search News**: Enter any topic in the search box
3. **View Results**: Get AI-generated summaries and source links
4. **Export PDF**: Download professional reports
5. **Explore Trending**: Check what's currently trending
6. **Manage Cache**: View and manage cached results

### API Endpoints

#### Health Check
```bash
curl "http://localhost:8000/"
```

#### Status
```bash
curl "http://localhost:8000/status"
```

#### Summarize News
**POST /summarize**
```bash
curl -X POST "http://localhost:8000/summarize" \
     -H "Content-Type: application/json" \
     -d '{"topic": "artificial intelligence", "max_articles": 10, "language": "en"}'
```

**GET /summarize**
```bash
curl "http://localhost:8000/summarize?topic=artificial%20intelligence&max_articles=10&language=en"
```

#### Trending Topics
**GET /trending**
```bash
curl "http://localhost:8000/trending?language=en"
```

**POST /trending/{topic}**
```bash
curl -X POST "http://localhost:8000/trending/technology?max_articles=5&language=en"
```

#### Cache Management
**GET /cache**
```bash
curl "http://localhost:8000/cache"
```

**DELETE /cache**
```bash
curl -X DELETE "http://localhost:8000/cache"
```

#### Export to PDF
**POST /export/pdf**
```bash
curl -X POST "http://localhost:8000/export/pdf" \
     -H "Content-Type: application/json" \
     -d '{"topic": "AI", "content": {...}}' --output news_summary_AI.pdf
```

### Customization

- **Change AI Model**: Update `MODEL_NAME` in `.env`
- **Adjust Cache**: Modify `CACHE_TTL` for different cache durations
- **Language Support**: Add more languages in the Streamlit interface

## 🎯 Features Deep Dive

### 🤖 AI Summarization

- **Model**: Facebook's BART-large-CNN (state-of-the-art)
- **Compression**: Typically 80-85% reduction in text length
- **Quality**: Maintains key information and context
- **Speed**: GPU acceleration when available

### 📈 Trending Topics

- **Real-time**: Based on latest news categories
- **Popularity**: Ranked by mention frequency
- **Interactive**: Click to analyze any trending topic

### 🧠 Smart Caching

- **Performance**: 10x faster for repeated queries
- **Storage**: Disk-based persistent cache
- **Management**: Automatic expiration and manual clearing
- **Memory**: Shows cached topics for easy re-access

### 📄 PDF Export

- **Professional**: Clean, readable reports
- **Comprehensive**: Includes summaries, sources, and metadata
- **Downloadable**: One-click PDF generation
- **Formatted**: Proper typography and layout

## 🔧 Development

### Adding New Features

1. **New Tool**: Add to `app/tools/`
2. **API Endpoint**: Add to `app/main.py`
3. **UI Component**: Add to `frontend/streamlit_app.py`
4. **Dependencies**: Update `requirements.txt`

### Testing

```bash
# Test API endpoints
curl http://localhost:8000/status

# Test with different topics
curl -X POST "http://localhost:8000/summarize" \
     -H "Content-Type: application/json" \
     -d '{"topic": "climate change"}'
```

## 🚀 Deployment Options

### Docker Deployment

```bash
# Build and run
docker build -t news-summarizer .
docker run -p 8000:8000 -p 8501:8501 -e NEWSDATA_API_KEY=your_key news-summarizer
```

### Cloud Deployment

- **Render**: Deploy using the Dockerfile
- **Streamlit Cloud**: Deploy frontend separately
- **Heroku**: Use container deployment
- **AWS/GCP**: Deploy using container services

## 📊 Performance

- **Summarization**: ~2-5 seconds per article
- **Cache Hit**: <100ms response time
- **Memory Usage**: ~2GB RAM for full model
- **Concurrent Users**: Scales with hardware

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

- **Issues**: Report bugs or request features
- **Documentation**: Check the `/docs` endpoint

## 🙏 Acknowledgments

- **HuggingFace** for the transformer models
- **TheNEWSAPI** for the news API
- **Streamlit** for the amazing UI framework
- **FastAPI** for the high-performance backend

---
