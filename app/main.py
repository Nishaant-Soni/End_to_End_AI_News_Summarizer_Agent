from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List
import os
from dotenv import load_dotenv
from loguru import logger
import uvicorn

from .agent import NewsAgent
from .utils.pdf_generator import PDFGenerator

# Load environment variables
load_dotenv(".env.dev")

# Initialize FastAPI app
app = FastAPI(
    title="AI News Summarizer Agent",
    description="An intelligent agent that fetches and summarizes news articles",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize the news agent
api_key = os.getenv("THENEWSAPI_TOKEN")
logger.info(f"API key loaded: {'Yes' if api_key else 'No'}")
if api_key:
    logger.info(f"API key length: {len(api_key)}")
    logger.info(f"API key starts with: {api_key[:10]}...")

if not api_key:
    logger.error("THENEWSAPI_TOKEN environment variable not set")
    raise ValueError("THENEWSAPI_TOKEN environment variable must be set")

model_name = os.getenv("MODEL_NAME", "facebook/bart-large-cnn")
cache_dir = os.getenv("CACHE_DIR", "./cache")
use_timeframe = os.getenv("USE_TIMEFRAME", "false").lower() == "true"
enable_extraction = os.getenv("ENABLE_EXTRACTION", "true").lower() == "true"

agent = NewsAgent(api_key=api_key, model_name=model_name, cache_dir=cache_dir, use_timeframe=use_timeframe, enable_extraction=enable_extraction)
pdf_generator = PDFGenerator()

# Pydantic models for request/response
class SummarizeRequest(BaseModel):
    topic: str
    max_articles: Optional[int] = 25
    language: Optional[str] = "en"

class PDFRequest(BaseModel):
    topic: str
    content: dict

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "AI News Summarizer Agent is running!", "status": "online"}

@app.get("/status")
async def get_status():
    """Get agent status and statistics"""
    return agent.get_agent_status()

@app.post("/summarize")
async def summarize_topic(request: SummarizeRequest):
    """Summarize news for a given topic"""
    try:
        result = agent.process_topic(
            topic=request.topic,
            max_articles=request.max_articles,
            language=request.language
        )
        
        if result["status"] == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        
        return result
        
    except Exception as e:
        logger.error(f"Error in summarize endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/summarize")
async def summarize_topic_get(
    topic: str = Query(..., description="Topic to search for"),
    max_articles: int = Query(25, description="Maximum number of articles"),
    language: str = Query("en", description="Language code")
):
    """GET version of summarize endpoint for direct URL access"""
    request = SummarizeRequest(topic=topic, max_articles=max_articles, language=language)
    return await summarize_topic(request)

@app.get("/trending")
async def get_trending_topics(language: str = Query("en", description="Language code")):
    """Get trending topics"""
    try:
        result = agent.get_trending_topics(language=language)
        
        if result["status"] == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        
        return result
        
    except Exception as e:
        logger.error(f"Error in trending endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/trending/{topic}")
async def process_trending_topic(
    topic: str,
    max_articles: int = Query(25, description="Maximum number of articles"),
    language: str = Query("en", description="Language code")
):
    """Process a specific trending topic"""
    try:
        result = agent.process_trending_topic(
            topic_name=topic,
            max_articles=max_articles,
            language=language
        )
        
        if result["status"] == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        
        return result
        
    except Exception as e:
        logger.error(f"Error in process trending topic endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/cache")
async def get_cached_topics():
    """Get list of cached topics (memory feature)"""
    try:
        cached_topics = agent.get_cached_topics()
        return {
            "status": "success",
            "cached_topics": cached_topics,
            "count": len(cached_topics)
        }
        
    except Exception as e:
        logger.error(f"Error getting cached topics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/cache")
async def clear_cache():
    """Clear all caches"""
    try:
        agent.clear_all_cache()
        return {"status": "success", "message": "All caches cleared"}
        
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/export/pdf")
async def export_to_pdf(request: PDFRequest, background_tasks: BackgroundTasks):
    """Export summary to PDF"""
    try:
        # Generate PDF
        pdf_path = pdf_generator.generate_summary_pdf(
            topic=request.topic,
            content=request.content
        )
        
        # Schedule cleanup of the PDF file after response
        background_tasks.add_task(cleanup_file, pdf_path)
        
        return FileResponse(
            path=pdf_path,
            filename=f"news_summary_{request.topic.replace(' ', '_')}.pdf",
            media_type="application/pdf"
        )
        
    except Exception as e:
        logger.error(f"Error generating PDF: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {str(e)}")

def cleanup_file(file_path: str):
    """Background task to cleanup temporary files"""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Cleaned up temporary file: {file_path}")
    except Exception as e:
        logger.error(f"Error cleaning up file {file_path}: {e}")

if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    
    logger.info(f"Starting server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)
