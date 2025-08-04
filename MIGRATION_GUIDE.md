# Migration Guide: TheNewsAPI to NewsAPI.org

This document outlines the changes made to migrate from TheNewsAPI to NewsAPI.org.

## Key Changes

### 1. Environment Variable
- **Old**: `THENEWSAPI_TOKEN`
- **New**: `NEWSAPI_KEY`

### 2. API Configuration
- **Old Base URL**: `https://api.thenewsapi.com/v1/news`
- **New Base URL**: `https://newsapi.org/v2`

### 3. Authentication
- **Old**: `api_token` parameter
- **New**: `apiKey` parameter

### 4. Endpoint Changes
- **Search endpoint**: `all` → `everything`
- **Trending endpoint**: `top` → `top-headlines`

### 5. Parameter Changes
- **Search query**: `search` → `q`
- **Results limit**: `limit` → `pageSize`
- **Date filter**: `published_after` → `from`
- **Categories**: `categories` → `category` (singular)

### 6. Response Structure Changes
- **Articles location**: `data` → `articles`
- **Source field**: String → Object with `name` property
- **Published date**: `published_at` → `publishedAt`
- **Image URL**: `image_url` → `urlToImage`
- **Content field**: `snippet` → `content` (truncated to 200 chars)

## Setup Instructions

1. **Get NewsAPI.org API Key**:
   - Visit https://newsapi.org/register
   - Sign up for a free account
   - Copy your API key

2. **Update Environment Variables**:
   ```bash
   # Create .env.dev file (copy from .env.example)
   cp .env.example .env.dev
   
   # Edit .env.dev and set your NewsAPI key
   NEWSAPI_KEY=your_newsapi_key_here
   ```

3. **Test the Migration**:
   ```bash
   # Start the application
   uvicorn app.main:app --reload --port 8000
   
   # Test a simple endpoint
   curl "http://localhost:8000/status"
   
   # Test news search
   curl "http://localhost:8000/summarize?topic=technology&max_articles=5"
   ```

## API Limitations

### NewsAPI.org Free Tier Limitations:
- **Requests**: 1,000 requests per day
- **Articles**: Up to 100 articles per request
- **Historical data**: Limited to 1 month for free tier
- **Commercial use**: Requires paid plan

### Features Maintained:
- ✅ Article search and summarization
- ✅ Trending topics extraction
- ✅ Content extraction (when needed)
- ✅ Caching system
- ✅ PDF export
- ✅ All existing API endpoints

## Migration Benefits

1. **More Reliable**: NewsAPI.org is a well-established service
2. **Better Documentation**: Comprehensive API documentation
3. **Wider Coverage**: Access to 150,000+ news sources
4. **Better Quality**: Higher quality article metadata
5. **Active Development**: Regular updates and improvements

## Troubleshooting

### Common Issues:
1. **"Invalid API key" error**: Make sure you're using `NEWSAPI_KEY` instead of `THENEWSAPI_TOKEN`
2. **No results returned**: Check if your search query is properly URL encoded
3. **Rate limit exceeded**: You may need to upgrade to a paid plan for higher usage

### Support:
- NewsAPI.org Documentation: https://newsapi.org/docs
- Contact: support@newsapi.org

## Files Modified

- `app/main.py`: Updated environment variable name
- `app/tools/fetch_news.py`: Complete API integration rewrite
- `app/tools/relevance_filter.py`: Updated comment
- `README.md`: Updated documentation
- `.env.example`: New environment file template

The migration maintains full backward compatibility with the existing application interface while switching to the more robust NewsAPI.org service.
