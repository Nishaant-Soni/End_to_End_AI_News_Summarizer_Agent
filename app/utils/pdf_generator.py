from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from datetime import datetime
import os
import tempfile
from typing import Dict
from loguru import logger

class PDFGenerator:
    """Tool for generating PDF reports from news summaries"""
    
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
    
    def _setup_custom_styles(self):
        """Set up custom styles for the PDF"""
        # Title style
        self.title_style = ParagraphStyle(
            'CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            textColor=colors.HexColor('#2c3e50'),
            alignment=1  # Center alignment
        )
        
        # Subtitle style
        self.subtitle_style = ParagraphStyle(
            'CustomSubtitle',
            parent=self.styles['Heading2'],
            fontSize=16,
            spaceAfter=20,
            textColor=colors.HexColor('#34495e')
        )
        
        # Article title style
        self.article_title_style = ParagraphStyle(
            'ArticleTitle',
            parent=self.styles['Heading3'],
            fontSize=14,
            spaceAfter=10,
            textColor=colors.HexColor('#2980b9'),
            leftIndent=20
        )
        
        # Summary style
        self.summary_style = ParagraphStyle(
            'SummaryStyle',
            parent=self.styles['Normal'],
            fontSize=11,
            spaceAfter=15,
            leftIndent=30,
            rightIndent=30,
            alignment=0  # Left alignment
        )
        
        # Metadata style
        self.metadata_style = ParagraphStyle(
            'MetadataStyle',
            parent=self.styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor('#7f8c8d'),
            leftIndent=30
        )
    
    def generate_summary_pdf(self, topic: str, content: Dict) -> str:
        """Generate a PDF report from news summary content"""
        try:
            # Create temporary file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
            temp_path = temp_file.name
            temp_file.close()
            
            # Create PDF document
            doc = SimpleDocTemplate(
                temp_path,
                pagesize=A4,
                rightMargin=72,
                leftMargin=72,
                topMargin=72,
                bottomMargin=18
            )
            
            # Build the story (content)
            story = []
            
            # Title
            title = f"News Summary Report: {topic}"
            story.append(Paragraph(title, self.title_style))
            story.append(Spacer(1, 20))
            
            # Metadata
            timestamp = content.get('timestamp', datetime.now().isoformat())
            metadata = content.get('metadata', {})
            total_articles = metadata.get('total_articles', 0)
            sources = metadata.get('sources', [])
            
            # Report info
            report_info = f"""
            <b>Generated:</b> {timestamp}<br/>
            <b>Total Articles:</b> {total_articles}<br/>
            <b>Sources:</b> {', '.join(sources[:5])}{'...' if len(sources) > 5 else ''}<br/>
            <b>Language:</b> {metadata.get('language', 'en').upper()}
            """
            story.append(Paragraph(report_info, self.metadata_style))
            story.append(Spacer(1, 30))
            
            # Digest Summary
            digest = content.get('digest', {})
            if digest and digest.get('digest'):
                story.append(Paragraph("Executive Summary", self.subtitle_style))
                story.append(Paragraph(digest['digest'], self.summary_style))
                story.append(Spacer(1, 30))
            
            # Articles
            articles = content.get('articles', [])
            if articles:
                story.append(Paragraph("Detailed Articles", self.subtitle_style))
                story.append(Spacer(1, 20))
                
                for i, article in enumerate(articles[:10], 1):  # Limit to 10 articles for PDF
                    # Article title
                    article_title = f"{i}. {article.get('title', 'No title')}"
                    story.append(Paragraph(article_title, self.article_title_style))
                    
                    # Article summary
                    summary = article.get('summary', article.get('description', 'No summary available'))
                    story.append(Paragraph(summary, self.summary_style))
                    
                    # Article metadata
                    source = article.get('source', 'Unknown')
                    published = article.get('published_at', '')
                    url = article.get('url', '')
                    
                    metadata_text = f"<b>Source:</b> {source}"
                    if published:
                        metadata_text += f" | <b>Published:</b> {published}"
                    if url:
                        metadata_text += f"<br/><b>URL:</b> <link href='{url}'>{url}</link>"
                    
                    story.append(Paragraph(metadata_text, self.metadata_style))
                    story.append(Spacer(1, 20))
            
            # Footer
            story.append(Spacer(1, 50))
            footer_text = "Generated by AI News Summarizer Agent"
            footer_style = ParagraphStyle(
                'Footer',
                parent=self.styles['Normal'],
                fontSize=8,
                textColor=colors.HexColor('#95a5a6'),
                alignment=1  # Center
            )
            story.append(Paragraph(footer_text, footer_style))
            
            # Build PDF
            doc.build(story)
            
            logger.info(f"PDF generated successfully: {temp_path}")
            return temp_path
            
        except Exception as e:
            logger.error(f"Error generating PDF: {e}")
            raise Exception(f"Failed to generate PDF: {str(e)}")
    
    def generate_trending_topics_pdf(self, trending_data: Dict) -> str:
        """Generate a PDF report for trending topics"""
        try:
            # Create temporary file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
            temp_path = temp_file.name
            temp_file.close()
            
            # Create PDF document
            doc = SimpleDocTemplate(temp_path, pagesize=A4)
            story = []
            
            # Title
            story.append(Paragraph("Trending Topics Report", self.title_style))
            story.append(Spacer(1, 20))
            
            # Timestamp
            timestamp = trending_data.get('timestamp', datetime.now().isoformat())
            story.append(Paragraph(f"Generated: {timestamp}", self.metadata_style))
            story.append(Spacer(1, 30))
            
            # Trending topics
            trending_topics = trending_data.get('trending_topics', [])
            if trending_topics:
                for i, topic in enumerate(trending_topics, 1):
                    topic_name = topic.get('topic', 'Unknown Topic')
                    count = topic.get('count', 0)
                    
                    story.append(Paragraph(f"{i}. {topic_name}", self.article_title_style))
                    story.append(Paragraph(f"Mentions: {count}", self.metadata_style))
                    
                    latest_article = topic.get('latest_article')
                    if latest_article:
                        article_title = latest_article.get('title', '')
                        if article_title:
                            story.append(Paragraph(f"Latest: {article_title}", self.summary_style))
                    
                    story.append(Spacer(1, 15))
            
            # Build PDF
            doc.build(story)
            
            logger.info(f"Trending topics PDF generated: {temp_path}")
            return temp_path
            
        except Exception as e:
            logger.error(f"Error generating trending topics PDF: {e}")
            raise Exception(f"Failed to generate trending topics PDF: {str(e)}")
