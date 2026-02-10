#!/usr/bin/env python3
"""
PDF Visual Renderer

Renders Enhancv JSON data into a visual PDF using HTML/CSS and weasyprint.
This solves the issue where JSON data is updated but visual PDF doesn't refresh.
"""

import json
import re
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

try:
    from weasyprint import HTML, CSS
    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False

try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

from pdf_resume_updater import PDFResumeUpdater


class PDFRenderer:
    """Renders resume JSON data into a visual PDF."""
    
    def __init__(self, json_data: Dict[str, Any]):
        # CRITICAL: Make a deep copy to avoid reference issues
        import copy
        self.data = copy.deepcopy(json_data)
        self.style = self.data.get('style', {})
        self.header = self.data.get('header', {})
        self.sections = self.data.get('sections', [])
        
        # DEBUG: Verify data received
        summary_check = ""
        for section in self.sections:
            if section.get('__t') == 'SummarySection':
                if section.get('items'):
                    summary_check = section['items'][0].get('text', '')
                    break
        print(f"[DEBUG PDFRenderer] Initialized with summary: {len(summary_check)} chars, Has HTML: {'<strong>' in summary_check}")
        if summary_check:
            print(f"[DEBUG PDFRenderer] Summary preview: {summary_check[:100]}...")
    
    def clean_html_text(self, text: str) -> str:
        """Remove HTML tags from text."""
        if not text:
            return ""
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        # Decode HTML entities
        text = text.replace('&nbsp;', ' ')
        text = text.replace('&amp;', '&')
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        return text.strip()
    
    def format_date_range(self, date_range: Dict[str, Any]) -> str:
        """Format date range for display."""
        if not date_range:
            return ""
        
        from_month = date_range.get('fromMonth')
        from_year = date_range.get('fromYear')
        to_month = date_range.get('toMonth')
        to_year = date_range.get('toYear')
        is_ongoing = date_range.get('isOngoing', False)
        
        months = ['', '01', '02', '03', '04', '05', '06', 
                 '07', '08', '09', '10', '11', '12']
        
        from_str = ""
        if from_month and from_year:
            from_str = f"{months[from_month] if from_month < len(months) else str(from_month).zfill(2)}/{from_year}"
        
        if is_ongoing:
            to_str = "Present"
        elif to_month and to_year:
            to_str = f"{months[to_month] if to_month < len(months) else str(to_month).zfill(2)}/{to_year}"
        elif to_year:
            to_str = str(to_year)
        else:
            to_str = ""
        
        if from_str and to_str:
            return f"{from_str} - {to_str}"
        elif from_str:
            return from_str
        return ""
    
    def render_with_reportlab(self, output_path: str):
        """Render PDF using reportlab."""
        if not REPORTLAB_AVAILABLE:
            raise ImportError("reportlab not installed. Install with: pip install reportlab")
        
        doc = SimpleDocTemplate(output_path, pagesize=letter,
                              rightMargin=72, leftMargin=72,
                              topMargin=72, bottomMargin=72)
        
        story = []
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1E90FF'),
            spaceAfter=12,
            alignment=TA_LEFT
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#000000'),
            spaceAfter=6,
            spaceBefore=12,
            alignment=TA_LEFT
        )
        
        # Header
        name = self.header.get('name', '')
        title = self.header.get('title', '')
        email = self.header.get('email', '')
        location = self.header.get('location', '')
        link = self.header.get('link', '')
        
        if name:
            story.append(Paragraph(f"<b>{name.upper()}</b>", title_style))
            story.append(Spacer(1, 6))
        
        header_info = []
        if title:
            header_info.append(title)
        if email:
            header_info.append(email)
        if location:
            header_info.append(location)
        if link:
            header_info.append(link)
        
        if header_info:
            story.append(Paragraph(" | ".join(header_info), styles['Normal']))
            story.append(Spacer(1, 12))
        
        # Sections
        for section in self.sections:
            if not section.get('enabled', True):
                continue
            
            section_type = section.get('__t', '')
            
            if section_type == 'SummarySection':
                story.append(Paragraph("<b>SUMMARY</b>", heading_style))
                for item in section.get('items', []):
                    text = self.clean_html_text(item.get('text', ''))
                    if text:
                        story.append(Paragraph(text, styles['Normal']))
                story.append(Spacer(1, 12))
            
            elif section_type == 'ExperienceSection':
                story.append(Paragraph("<b>EXPERIENCE</b>", heading_style))
                for item in section.get('items', []):
                    position = item.get('position', '')
                    company = item.get('workplace', '')
                    location = item.get('location', '')
                    date_range = self.format_date_range(item.get('dateRange', {}))
                    
                    # Position and company
                    exp_title = f"<b>{position}</b>"
                    if company:
                        exp_title += f" | {company}"
                    if location:
                        exp_title += f" | {location}"
                    if date_range:
                        exp_title += f" | {date_range}"
                    
                    story.append(Paragraph(exp_title, styles['Normal']))
                    story.append(Spacer(1, 6))
                    
                    # Bullets
                    for bullet in item.get('bullets', []):
                        story.append(Paragraph(f"• {self.clean_html_text(bullet)}", 
                                              styles['Normal']))
                        story.append(Spacer(1, 3))
                    
                    story.append(Spacer(1, 12))
            
            elif section_type == 'EducationSection':
                story.append(Paragraph("<b>EDUCATION</b>", heading_style))
                for item in section.get('items', []):
                    degree = item.get('degree', '')
                    institution = item.get('institution', '')
                    location = item.get('location', '')
                    date_range = self.format_date_range(item.get('dateRange', {}))
                    gpa = item.get('gpa', '')
                    
                    edu_text = f"<b>{degree}</b>"
                    if institution:
                        edu_text += f" | {institution}"
                    if location:
                        edu_text += f" | {location}"
                    if date_range:
                        edu_text += f" | {date_range}"
                    if gpa:
                        edu_text += f" | GPA: {gpa}"
                    
                    story.append(Paragraph(edu_text, styles['Normal']))
                    story.append(Spacer(1, 12))
            
            elif section_type == 'TechnologySection':
                story.append(Paragraph("<b>SKILLS</b>", heading_style))
                for item in section.get('items', []):
                    tags = item.get('tags', [])
                    if tags:
                        skills_text = " • ".join(tags)
                        story.append(Paragraph(skills_text, styles['Normal']))
                        story.append(Spacer(1, 6))
                story.append(Spacer(1, 12))
        
        doc.build(story)
    
    def render_with_weasyprint(self, output_path: str):
        """Render PDF using weasyprint (HTML/CSS to PDF)."""
        if not WEASYPRINT_AVAILABLE:
            raise ImportError("weasyprint not installed. Install with: pip install weasyprint")
        
        html_content = self.generate_html()
        css_content = self.generate_css()
        
        HTML(string=html_content).write_pdf(
            output_path,
            stylesheets=[CSS(string=css_content)]
        )
    
    def generate_html(self) -> str:
        """Generate HTML from JSON data."""
        html_parts = ['<html><head><meta charset="UTF-8"></head><body>']
        
        # Header - matching Enhancv layout
        name = self.header.get('name', '')
        title = self.header.get('title', '')
        email = self.header.get('email', '')
        location = self.header.get('location', '')
        link = self.header.get('link', '')
        
        html_parts.append('<div class="header">')
        if name:
            html_parts.append(f'<h1 class="name">{name.upper()}</h1>')
        
        # Title line with separators
        if title:
            html_parts.append(f'<div class="title-line">{title}</div>')
        
        # Contact line (all on one line, space-separated)
        contact_parts = []
        if email:
            contact_parts.append(email)
        if link:
            contact_parts.append(f'linkedin.com/in/{link}' if not link.startswith('linkedin.com') else link)
        if location:
            contact_parts.append(location)
        
        if contact_parts:
            html_parts.append(f'<div class="contact-line">{" ".join(contact_parts)}</div>')
        
        html_parts.append('</div>')
        
        # Sections
        for section in self.sections:
            if not section.get('enabled', True):
                continue
            
            section_type = section.get('__t', '')
            
            if section_type == 'SummarySection':
                html_parts.append('<div class="section">')
                html_parts.append('<h2>SUMMARY</h2>')
                for item in section.get('items', []):
                    text = item.get('text', '')
                    # CRITICAL: Clean HTML tags - the text should already be clean, but ensure it is
                    text = self.clean_html_text(text)
                    # DEBUG: Log what we're rendering
                    if len(html_parts) < 10:  # Only log first time to avoid spam
                        print(f"[DEBUG generate_html] Summary text: {len(text)} chars, Has HTML: {'<' in text and '>' in text}")
                        print(f"[DEBUG generate_html] Summary preview: {text[:100]}...")
                    html_parts.append(f'<p class="summary">{text}</p>')
                html_parts.append('</div>')
            
            elif section_type == 'ExperienceSection':
                html_parts.append('<div class="section">')
                html_parts.append('<h2>EXPERIENCE</h2>')
                for item in section.get('items', []):
                    html_parts.append('<div class="experience-item">')
                    position = item.get('position', '')
                    company = item.get('workplace', '')
                    location = item.get('location', '')
                    date_range = self.format_date_range(item.get('dateRange', {}))
                    
                    # Position on its own line
                    if position:
                        html_parts.append(f'<div class="exp-position">{position}</div>')
                    
                    # Company on its own line
                    if company:
                        html_parts.append(f'<div class="exp-company">{company}</div>')
                    
                    # Date and location on one line
                    details_parts = []
                    if date_range:
                        details_parts.append(date_range)
                    if location:
                        details_parts.append(location)
                    if details_parts:
                        html_parts.append(f'<div class="exp-details">{"  ".join(details_parts)}</div>')
                    
                    # Bullets
                    if item.get('bullets'):
                        html_parts.append('<ul class="bullets">')
                        for bullet in item.get('bullets', []):
                            html_parts.append(f'<li>{self.clean_html_text(bullet)}</li>')
                        html_parts.append('</ul>')
                    
                    html_parts.append('</div>')
                html_parts.append('</div>')
            
            elif section_type == 'EducationSection':
                html_parts.append('<div class="section">')
                html_parts.append('<h2>EDUCATION</h2>')
                for item in section.get('items', []):
                    html_parts.append('<div class="education-item">')
                    degree = item.get('degree', '')
                    institution = item.get('institution', '')
                    location = item.get('location', '')
                    date_range = self.format_date_range(item.get('dateRange', {}))
                    gpa = item.get('gpa', '')
                    max_gpa = item.get('maxGpa', '5.0')
                    
                    # Degree on its own line
                    if degree:
                        html_parts.append(f'<div class="edu-degree">{degree}</div>')
                    
                    # Details on second line
                    details_parts = []
                    if institution:
                        details_parts.append(institution)
                    if location:
                        details_parts.append(location)
                    if date_range:
                        details_parts.append(date_range)
                    if details_parts:
                        html_parts.append(f'<div class="edu-details">{"  ".join(details_parts)}</div>')
                    
                    # GPA on third line if present
                    if gpa:
                        html_parts.append(f'<div class="edu-details">GPA: {gpa}/{max_gpa}</div>')
                    
                    html_parts.append('</div>')
                html_parts.append('</div>')
            
            elif section_type == 'TechnologySection':
                html_parts.append('<div class="section">')
                html_parts.append('<h2>SKILLS</h2>')
                # Render skills by category if organized, otherwise as flat list
                for item in section.get('items', []):
                    tags = item.get('tags', [])
                    title = item.get('title', '')
                    
                    if title:
                        # Category-based format
                        html_parts.append(f'<div class="skill-category"><strong>{title}:</strong> {" • ".join(tags)}</div>')
                    else:
                        # Flat list format
                        if tags:
                            html_parts.append(f'<div class="skills">{" ".join(tags)}</div>')
                html_parts.append('</div>')
            
            elif section_type == 'ActivitySection':
                html_parts.append('<div class="section">')
                html_parts.append('<h2>PROJECTS</h2>')
                for item in section.get('items', []):
                    html_parts.append('<div class="experience-item">')
                    title = item.get('title', '')
                    location = item.get('location', '')
                    date_range = self.format_date_range(item.get('dateRange', {}))
                    
                    # Title on its own line
                    if title:
                        html_parts.append(f'<div class="exp-position">{title}</div>')
                    
                    # Location and date on one line
                    details_parts = []
                    if location:
                        details_parts.append(location)
                    if date_range:
                        details_parts.append(date_range)
                    if details_parts:
                        html_parts.append(f'<div class="exp-details">{"  ".join(details_parts)}</div>')
                    
                    # Bullets/description
                    if item.get('bullets'):
                        html_parts.append('<ul class="bullets">')
                        for bullet in item.get('bullets', []):
                            html_parts.append(f'<li>{self.clean_html_text(bullet)}</li>')
                        html_parts.append('</ul>')
                    
                    html_parts.append('</div>')
                html_parts.append('</div>')
            
            elif section_type == 'LanguageSection':
                html_parts.append('<div class="section">')
                html_parts.append('<h2>LANGUAGES</h2>')
                for item in section.get('items', []):
                    name = item.get('name', '')
                    level = item.get('levelText', '')
                    if name:
                        lang_text = f"{name}"
                        if level:
                            lang_text += f": {level}"
                        html_parts.append(f'<div class="language-item">{lang_text}</div>')
                html_parts.append('</div>')
            
            elif section_type == 'CertificateSection':
                html_parts.append('<div class="section">')
                html_parts.append('<h2>CERTIFICATIONS</h2>')
                for item in section.get('items', []):
                    title = item.get('title', '')
                    issuer = item.get('issuer', '')
                    date_range = self.format_date_range(item.get('dateRange', {}))
                    
                    cert_text = f"<strong>{title}</strong>"
                    if issuer:
                        cert_text += f" | {issuer}"
                    if date_range:
                        cert_text += f" | {date_range}"
                    
                    html_parts.append(f'<div class="education-item">{cert_text}</div>')
                html_parts.append('</div>')
        
        html_parts.append('</body></html>')
        return '\n'.join(html_parts)
    
    def generate_css(self) -> str:
        """Generate CSS styling matching Enhancv layout."""
        return """
        @page {
            size: A4;
            margin: 0.5in 0.7in;
        }
        body {
            font-family: 'Arial', 'Helvetica', sans-serif;
            font-size: 10pt;
            line-height: 1.4;
            color: #000000;
            margin: 0;
            padding: 0;
            text-align: left;
        }
        .header {
            margin-bottom: 8px;
            padding-bottom: 6px;
            border-bottom: 1px solid #e0e0e0;
        }
        .name {
            font-size: 16pt;
            font-weight: bold;
            color: #000000;
            margin: 0 0 3px 0;
            text-transform: uppercase;
            letter-spacing: 0.3px;
        }
        .title-line {
            font-size: 10pt;
            color: #000000;
            margin: 0 0 3px 0;
            font-weight: normal;
        }
        .contact-line {
            font-size: 9pt;
            color: #000000;
            margin: 0 0 8px 0;
        }
        .header-info {
            font-size: 9pt;
            color: #000000;
        }
        .section {
            margin-bottom: 10px;
        }
        h2 {
            font-size: 11pt;
            font-weight: bold;
            color: #000000;
            margin: 10px 0 6px 0;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            border-bottom: 2px solid #000000;
            padding-bottom: 3px;
        }
        .summary {
            text-align: left;
            margin: 0 0 8px 0;
            font-size: 10pt;
            line-height: 1.4;
            word-wrap: break-word;
        }
        .experience-item {
            margin-bottom: 12px;
            padding-bottom: 8px;
            border-bottom: 1px solid #e8e8e8;
        }
        .experience-item:last-child {
            border-bottom: none;
        }
        .exp-position {
            font-weight: bold;
            font-size: 10pt;
            margin: 0 0 2px 0;
            color: #000000;
        }
        .exp-company {
            font-size: 10pt;
            margin: 0 0 2px 0;
            color: #000000;
        }
        .exp-details {
            font-size: 9pt;
            margin: 0 0 6px 0;
            color: #666666;
            font-style: normal;
        }
        .bullets {
            margin: 4px 0 4px 0;
            padding-left: 0;
            list-style-type: none;
        }
        .bullets li {
            margin: 3px 0;
            font-size: 10pt;
            line-height: 1.4;
            text-indent: 0;
            padding-left: 15px;
            word-wrap: break-word;
            position: relative;
        }
        .bullets li:before {
            content: "•";
            position: absolute;
            left: 0;
            font-weight: bold;
            color: #000000;
        }
        .education-item {
            margin: 0 0 8px 0;
            padding-bottom: 6px;
            border-bottom: 1px solid #e8e8e8;
        }
        .education-item:last-child {
            border-bottom: none;
        }
        .edu-degree {
            font-weight: bold;
            font-size: 10pt;
            margin: 0 0 2px 0;
        }
        .edu-details {
            font-size: 9pt;
            margin: 0;
            color: #333;
        }
        .skills {
            margin: 4px 0;
            font-size: 10pt;
            line-height: 1.6;
        }
        .skill-category {
            margin: 6px 0;
            font-size: 10pt;
            line-height: 1.5;
            padding: 4px 0;
        }
        .skill-category strong {
            font-weight: bold;
            margin-right: 10px;
            color: #000000;
        }
        .language-item {
            margin: 4px 0;
            font-size: 10pt;
            padding: 2px 0;
        }
        strong {
            font-weight: bold;
        }
        a {
            color: #000000;
            text-decoration: none;
        }
        """
    
    def render_pdf(self, output_path: str, method: str = 'auto'):
        """Render PDF using the best available method."""
        if method == 'auto':
            if WEASYPRINT_AVAILABLE:
                method = 'weasyprint'
            elif REPORTLAB_AVAILABLE:
                method = 'reportlab'
            else:
                raise ImportError(
                    "No PDF rendering library available. Install one of:\n"
                    "  pip install weasyprint  (recommended)\n"
                    "  pip install reportlab"
                )
        
        if method == 'weasyprint':
            self.render_with_weasyprint(output_path)
        elif method == 'reportlab':
            self.render_with_reportlab(output_path)
        else:
            raise ValueError(f"Unknown rendering method: {method}")


def render_resume_from_pdf(pdf_path: str, output_path: str, method: str = 'auto'):
    """Extract data from PDF and render as new visual PDF."""
    updater = PDFResumeUpdater(pdf_path)
    updater.extract_json_data()
    
    renderer = PDFRenderer(updater.data)
    renderer.render_pdf(output_path, method=method)
    
    print(f"✅ Rendered visual PDF to: {output_path}")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Render resume JSON to visual PDF')
    parser.add_argument('pdf_path', help='Input PDF with JSON data')
    parser.add_argument('--output', '-o', required=True, help='Output PDF path')
    parser.add_argument('--method', choices=['auto', 'weasyprint', 'reportlab'],
                       default='auto', help='Rendering method')
    
    args = parser.parse_args()
    
    render_resume_from_pdf(args.pdf_path, args.output, args.method)
