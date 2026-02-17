#!/usr/bin/env python3
"""
PDF Visual Renderer

Renders Enhancv JSON data into a visual PDF using HTML/CSS and weasyprint.
This solves the issue where JSON data is updated but visual PDF doesn't refresh.
"""

import json
import os
import re
import sys
import shutil
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

try:
    from weasyprint import HTML, CSS
    WEASYPRINT_AVAILABLE = True
except (ImportError, OSError):
    # OSError: WeasyPrint can fail loading native libs (e.g. GTK/gobject DLL) on Windows
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

# Design: accent color and subtle gray for borders/backgrounds
ACCENT = colors.HexColor('#1a5276')
ACCENT_LIGHT = colors.HexColor('#e8f0f4')
GRAY_BORDER = colors.HexColor('#d0d8dc')

from pdf_resume_updater import PDFResumeUpdater


def _section_has_summary_items(section: Dict[str, Any]) -> bool:
    """True if section has summary-like items (items with 'text')."""
    for item in section.get('items', []):
        if item.get('text') is not None and str(item.get('text', '')).strip():
            return True
    return False


def _section_has_experience_items(section: Dict[str, Any]) -> bool:
    """True if section has experience-like items (position/title + workplace/company)."""
    for item in section.get('items', []):
        has_role = 'position' in item or 'title' in item
        has_company = 'workplace' in item or 'company' in item
        if (has_role or has_company) and isinstance(section.get('items'), list):
            return True
    return False


def _section_has_project_items(section: Dict[str, Any]) -> bool:
    """True if section has project-like items (title/name/projectName + description/text/bullets)."""
    for item in section.get('items', []):
        has_title = any(item.get(k) for k in ('title', 'name', 'projectName'))
        has_content = any(item.get(k) is not None for k in ('description', 'text', 'bullets'))
        if has_title or has_content:
            return True
    return False


def _section_has_skill_items(section: Dict[str, Any]) -> bool:
    """True if section has skill-like items (items with 'tags')."""
    for item in section.get('items', []):
        if 'tags' in item and isinstance(item.get('tags'), list):
            return True
    return False


def _resolve_section_type(section: Dict[str, Any]) -> str:
    """Resolve section type from __t or from content shape so updated content renders correctly."""
    section_type = section.get('__t', '')
    known = (
        'SummarySection', 'ExperienceSection', 'EducationSection',
        'TechnologySection', 'ActivitySection', 'ProjectSection',
        'LanguageSection', 'CertificateSection'
    )
    if section_type in known:
        return section_type
    if _section_has_summary_items(section):
        return 'SummarySection'
    if _section_has_experience_items(section):
        return 'ExperienceSection'
    if _section_has_skill_items(section):
        return 'TechnologySection'
    if _section_has_project_items(section):
        return 'ProjectSection'
    return section_type or 'Other'


class PDFRenderer:
    """Renders resume JSON data into a visual PDF."""
    
    def __init__(self, json_data: Dict[str, Any]):
        # CRITICAL: Make a deep copy to avoid reference issues
        import copy
        self.data = copy.deepcopy(json_data)
        self.style = self.data.get('style', {})
        self.header = self.data.get('header', {})
        self.sections = self.data.get('sections', [])
        
        summary_check = ""
        for section in self.sections:
            if section.get('__t') == 'SummarySection':
                if section.get('items'):
                    summary_check = section['items'][0].get('text', '')
                    break
    
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
    
    def _normalize_display_title(self, raw: str) -> str:
        """Strip leading list markers / stray chars so updated content displays correctly."""
        if not raw or not isinstance(raw, str):
            return raw or ""
        s = raw.strip()
        # Remove leading numbering ("1. ", "2. "), bullets ("• ", "- ", "– "), or stray "n " (corrupted marker)
        s = re.sub(r'^\s*\d+\.\s*', '', s)
        s = re.sub(r'^[•\-–—]\s*', '', s)
        # Strip single leading char when followed by space (handles "n ", "1 ", or mis-encoded bullet)
        if len(s) > 2 and s[1] in (' ', '\t') and (
            s[0] in ('n', 'N') or (s[2:3] and s[2].isupper())
        ):
            s = s[2:].lstrip()
        return s.strip()

    def _normalize_paragraph(self, raw: str) -> str:
        """Strip leading stray 'n ', list markers, or any single-char+space before uppercase from paragraph."""
        if not raw or not isinstance(raw, str):
            return raw or ""
        s = raw.strip()
        s = re.sub(r'^\s*\d+\.\s*', '', s)
        s = re.sub(r'^[•\-–—]\s*', '', s)
        # Strip any single character + space when followed by uppercase (loop for multiple prefixes)
        while True:
            s2 = re.sub(r'^.\s+(?=[A-Z])', '', s)
            if s2 == s:
                break
            s = s2.strip()
        return s.strip()

    def _project_description_display(self, raw_desc: str, project_name: str) -> str:
        """Return description safe for display: normalize and drop first line if it duplicates project name."""
        if not raw_desc:
            return ''
        s = self._normalize_paragraph(raw_desc)
        if not s:
            return ''
        pn = (project_name or '').strip()
        if not pn:
            return s
        # Remove first line if it equals or is a duplicate of project name (with or without subtitle)
        lines = s.splitlines()
        if lines:
            first = lines[0].strip()
            first_norm = self._normalize_paragraph(first)
            if (first_norm == pn or first_norm.lower() == pn.lower() or
                    pn in first_norm or first_norm.startswith(pn) or
                    (len(first_norm) > len(pn) and first_norm[:len(pn)] == pn and first_norm[len(pn):len(pn)+1] in (' ', ':', '-'))):
                lines = lines[1:]
                s = '\n'.join(lines).strip()
        return s

    def _item_title(self, item: Dict[str, Any]) -> str:
        """Get display title from item (project/section item)."""
        raw = (
            item.get('title', '') or
            item.get('name', '') or
            item.get('projectName', '') or
            ''
        )
        return self._normalize_display_title(raw)
    
    def _project_display(self, item: Dict[str, Any]) -> Tuple[str, str, str]:
        """Get (project_name, org_and_date_line, role) for correct project rendering.
        Enhancv project items use projectName/name for project name, title/position for role, workplace for org.
        """
        project_name = self._normalize_display_title(
            item.get('projectName', '') or item.get('name', '') or item.get('title', '') or ''
        )
        role = (item.get('position', '') or item.get('title', '')).strip()
        if role and role == project_name:
            role = ''
        workplace = (item.get('workplace', '') or item.get('company', '') or '').strip()
        location = (item.get('location', '') or '').strip()
        date_range = self.format_date_range(item.get('dateRange', {}))
        parts = [p for p in [workplace, location, date_range] if p]
        org_line = ' | '.join(parts) if parts else ''
        return (project_name, org_line, role)
    
    def render_with_reportlab(self, output_path: str):
        """Render PDF using reportlab."""
        if not REPORTLAB_AVAILABLE:
            raise ImportError("reportlab not installed. Install with: pip install reportlab")
        
        left_margin = right_margin = top_margin = bottom_margin = 28
        doc = SimpleDocTemplate(output_path, pagesize=letter,
                              rightMargin=right_margin, leftMargin=left_margin,
                              topMargin=top_margin, bottomMargin=bottom_margin)
        # Explicit content size so ReportLab's frame never has None width/height (avoids int(None) in Table.wrap)
        content_width = letter[0] - left_margin - right_margin
        content_height = letter[1] - top_margin - bottom_margin
        story = []
        styles = getSampleStyleSheet()
        
        # Compact layout for ~2 pages
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Normal'],
            fontSize=16,
            textColor=ACCENT,
            spaceAfter=0,
            spaceBefore=0,
            leading=18,
            alignment=TA_LEFT,
            fontName='Helvetica-Bold',
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Normal'],
            fontSize=10,
            textColor=ACCENT,
            spaceAfter=0,
            spaceBefore=6,
            leading=12,
            alignment=TA_LEFT,
            fontName='Helvetica-Bold',
        )
        
        body_style = ParagraphStyle(
            'Body',
            parent=styles['Normal'],
            fontSize=9.5,
            leading=10,
            spaceAfter=0,
            alignment=TA_LEFT,
        )
        
        sub_style = ParagraphStyle(
            'Sub',
            parent=styles['Normal'],
            fontSize=8.5,
            leading=9,
            textColor=colors.HexColor('#444444'),
            spaceAfter=0,
            alignment=TA_LEFT,
        )
        
        bullet_style = ParagraphStyle(
            'Bullet',
            parent=styles['Normal'],
            fontSize=9.5,
            leading=10,
            leftIndent=8,
            spaceAfter=0,
            alignment=TA_LEFT,
        )
        
        def add_section_header(story, title_str):
            """Section title with bottom border separating sections."""
            story.append(Paragraph(title_str, heading_style))
            line_t = Table([['']], colWidths=[content_width], rowHeights=[2])
            line_t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), GRAY_BORDER)]))
            story.append(line_t)
            story.append(Spacer(1, 6))
        
        def add_bordered_block(story, flowables):
            """Content block only (no accent bar, no side border)."""
            if not flowables:
                return
            t = Table([[f] for f in flowables], colWidths=[content_width])
            t.setStyle(TableStyle([
                ('LEFTPADDING', (0, 0), (-1, -1), 2),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            story.append(t)
            story.append(Spacer(1, 4))
        
        # Profile header: name + title (tagline) + contact, with accent bar
        name = self.header.get('name', '')
        title = self.header.get('title', '')
        email = self.header.get('email', '')
        location = self.header.get('location', '')
        link = self.header.get('link', '')
        
        header_rows = []
        if name:
            header_rows.append([Paragraph(f"<b>{name.upper()}</b>", title_style)])
        if title:
            tagline_style = ParagraphStyle('Tagline', parent=sub_style, fontSize=9, textColor=colors.HexColor('#555'), spaceAfter=0, leading=10)
            header_rows.append([Paragraph(title, tagline_style)])
        contact_parts = []
        if email:
            contact_parts.append(email)
        if location:
            contact_parts.append(location)
        if link:
            contact_parts.append(link)
        if contact_parts:
            header_rows.append([Paragraph(" &nbsp;&#8226;&nbsp; ".join(contact_parts), sub_style)])
        if header_rows:
            # Header with left accent stripe
            header_table = Table(header_rows, colWidths=[content_width])
            header_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), ACCENT_LIGHT),
                ('LINEBELOW', (0, -1), (-1, -1), 1.5, ACCENT),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            story.append(header_table)
            story.append(Spacer(1, 5))
        
        # Sections
        for section in self.sections:
            if not section.get('enabled', True):
                continue
            
            section_type = _resolve_section_type(section)
            
            if section_type == 'SummarySection':
                add_section_header(story, "SUMMARY")
                summary_paras = []
                for item in section.get('items', []):
                    text = self.clean_html_text(item.get('text', ''))
                    if text:
                        summary_paras.append(Paragraph(text, body_style))
                if summary_paras:
                    add_bordered_block(story, summary_paras)
            
            elif section_type == 'ExperienceSection':
                add_section_header(story, "EXPERIENCE")
                for item in section.get('items', []):
                    position = item.get('position', '') or item.get('title', '')
                    company = item.get('workplace', '') or item.get('company', '')
                    location = item.get('location', '')
                    date_range = self.format_date_range(item.get('dateRange', {}))
                    block = [
                        Paragraph(f'<font color="#1a5276"><b>{position}</b></font>', body_style),
                    ]
                    sub_parts = [p for p in [company, location, date_range] if p]
                    if sub_parts:
                        block.append(Paragraph(" &nbsp;|&nbsp; ".join(sub_parts), sub_style))
                    for bullet in item.get('bullets', []):
                        block.append(Paragraph(f"• {self.clean_html_text(bullet)}", bullet_style))
                    add_bordered_block(story, block)
            
            elif section_type == 'EducationSection':
                add_section_header(story, "EDUCATION")
                for item in section.get('items', []):
                    degree = item.get('degree', '')
                    institution = item.get('institution', '')
                    location = item.get('location', '')
                    date_range = self.format_date_range(item.get('dateRange', {}))
                    gpa = item.get('gpa', '')
                    block = [
                        Paragraph(f'<font color="#1a5276"><b>{degree}</b></font>', body_style),
                    ]
                    detail_parts = [p for p in [institution, location, date_range] if p]
                    if detail_parts:
                        block.append(Paragraph(" &nbsp;|&nbsp; ".join(detail_parts), sub_style))
                    if gpa:
                        block.append(Paragraph(f"GPA: {gpa}", sub_style))
                    add_bordered_block(story, block)
            
            elif section_type == 'TechnologySection':
                add_section_header(story, "SKILLS")
                skill_paras = []
                for item in section.get('items', []):
                    title = item.get('title', '')
                    tags = item.get('tags', [])
                    if title:
                        skill_paras.append(Paragraph(f'<font color="#1a5276"><b>{title}</b></font>: {" • ".join(tags)}', body_style))
                    elif tags:
                        skill_paras.append(Paragraph(" • ".join(tags), body_style))
                if skill_paras:
                    add_bordered_block(story, skill_paras)
            
            elif section_type in ('ActivitySection', 'ProjectSection'):
                add_section_header(story, "PROJECTS")
                for item in section.get('items', []):
                    project_name, org_line, role = self._project_display(item)
                    raw_desc = self.clean_html_text(item.get('description', '') or item.get('text', ''))
                    description = self._project_description_display(raw_desc, project_name)
                    block = []
                    if project_name:
                        block.append(Paragraph(f'<font color="#1a5276"><b>{project_name}</b></font>', body_style))
                    if org_line:
                        block.append(Paragraph(org_line, sub_style))
                    if role:
                        block.append(Paragraph(role, body_style))
                    if description:
                        block.append(Paragraph(description, body_style))
                    for bullet in item.get('bullets', []):
                        block.append(Paragraph(f"• {self.clean_html_text(bullet)}", bullet_style))
                    if block:
                        add_bordered_block(story, block)
            
            elif section_type == 'LanguageSection':
                add_section_header(story, "LANGUAGES")
                lang_paras = []
                for item in section.get('items', []):
                    name = item.get('name', '')
                    level = item.get('levelText', '')
                    if name:
                        lang_paras.append(Paragraph(name if not level else f"{name}: {level}", body_style))
                if lang_paras:
                    add_bordered_block(story, lang_paras)
            
            elif section_type == 'CertificateSection':
                add_section_header(story, "CERTIFICATIONS")
                cert_paras = []
                for item in section.get('items', []):
                    title = item.get('title', '')
                    issuer = item.get('issuer', '')
                    date_range = self.format_date_range(item.get('dateRange', {}))
                    cert_parts = [f'<font color="#1a5276"><b>{title}</b></font>']
                    if issuer:
                        cert_parts.append(issuer)
                    if date_range:
                        cert_parts.append(date_range)
                    cert_paras.append(Paragraph(" &nbsp;|&nbsp; ".join(cert_parts), body_style))
                if cert_paras:
                    add_bordered_block(story, cert_paras)
            
            else:
                section_name = section.get('name', section_type or 'Other')
                if section_name:
                    add_section_header(story, section_name.upper())
                for item in section.get('items', []):
                    text = item.get('text', '') or item.get('description', '')
                    text = self._normalize_paragraph(self.clean_html_text(text)) if text else ''
                    title = self._item_title(item)
                    if title:
                        story.append(Paragraph(f"<b>{title}</b>", body_style))
                    if text:
                        story.append(Paragraph(text, body_style))
                    for bullet in item.get('bullets', []):
                        story.append(Paragraph(f"• {self.clean_html_text(bullet)}", bullet_style))
                    story.append(Spacer(1, 2))
                story.append(Spacer(1, 3))
        
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
        html_parts = ['<html><head><meta charset="UTF-8"></head><body><div class="resume">']
        
        # Header
        name = self.header.get('name', '')
        title = self.header.get('title', '')
        email = self.header.get('email', '')
        location = self.header.get('location', '')
        link = self.header.get('link', '')
        
        html_parts.append('<div class="header">')
        if name:
            html_parts.append(f'<h1 class="name">{name.upper()}</h1>')
        if title:
            html_parts.append(f'<div class="profile-title">{title}</div>')
        contact_parts = []
        if email:
            contact_parts.append(email)
        if location:
            contact_parts.append(location)
        if link:
            contact_parts.append(f'linkedin.com/in/{link}' if not link.startswith('linkedin.com') else link)
        if contact_parts:
            sep = ' <span class="sep">&#8226;</span> '
            html_parts.append(f'<div class="contact-line">{sep.join(contact_parts)}</div>')
        html_parts.append('</div>')
        
        # Sections
        for section in self.sections:
            if not section.get('enabled', True):
                continue
            
            section_type = _resolve_section_type(section)
            
            if section_type == 'SummarySection':
                html_parts.append('<div class="section">')
                html_parts.append('<h2>SUMMARY</h2>')
                html_parts.append('<div class="summary-box">')
                for item in section.get('items', []):
                    text = item.get('text', '')
                    text = self.clean_html_text(text)
                    html_parts.append(f'<p class="summary">{text}</p>')
                html_parts.append('</div>')
                html_parts.append('</div>')
            
            elif section_type == 'ExperienceSection':
                html_parts.append('<div class="section">')
                html_parts.append('<h2>EXPERIENCE</h2>')
                for item in section.get('items', []):
                    html_parts.append('<div class="experience-item">')
                    position = item.get('position', '') or item.get('title', '')
                    company = item.get('workplace', '') or item.get('company', '')
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
                html_parts.append('<div class="skills-block">')
                for item in section.get('items', []):
                    tags = item.get('tags', [])
                    title = item.get('title', '')
                    if title:
                        html_parts.append(f'<div class="skill-line"><strong>{title}:</strong> {" • ".join(tags)}</div>')
                    elif tags:
                        html_parts.append(f'<div class="skill-line">{" • ".join(tags)}</div>')
                html_parts.append('</div>')
                html_parts.append('</div>')
            
            elif section_type in ('ActivitySection', 'ProjectSection'):
                html_parts.append('<div class="section">')
                html_parts.append('<h2>PROJECTS</h2>')
                for item in section.get('items', []):
                    html_parts.append('<div class="experience-item">')
                    project_name, org_line, role = self._project_display(item)
                    
                    if project_name:
                        html_parts.append(f'<div class="exp-position">{project_name}</div>')
                    if org_line:
                        html_parts.append(f'<div class="exp-details">{org_line}</div>')
                    if role:
                        html_parts.append(f'<div class="exp-role">{role}</div>')
                    
                    raw_desc = self.clean_html_text(item.get('description', '') or item.get('text', ''))
                    desc = self._project_description_display(raw_desc, project_name)
                    if desc:
                        html_parts.append(f'<p class="summary">{desc}</p>')
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
                html_parts.append('<div class="cert-block">')
                for item in section.get('items', []):
                    title = item.get('title', '')
                    issuer = item.get('issuer', '')
                    date_range = self.format_date_range(item.get('dateRange', {}))
                    cert_text = f"<strong>{title}</strong>"
                    if issuer:
                        cert_text += f" | {issuer}"
                    if date_range:
                        cert_text += f" | {date_range}"
                    html_parts.append(f'<div class="cert-line">{cert_text}</div>')
                html_parts.append('</div>')
                html_parts.append('</div>')
            
            else:
                # Generic fallback for any other section type
                section_name = section.get('name', section_type or 'Other')
                if section_name:
                    html_parts.append('<div class="section">')
                    html_parts.append(f'<h2>{section_name.upper()}</h2>')
                for item in section.get('items', []):
                    html_parts.append('<div class="experience-item">')
                    title = self._item_title(item)
                    if title:
                        html_parts.append(f'<div class="exp-position">{title}</div>')
                    text = item.get('text', '') or item.get('description', '')
                    text = self._normalize_paragraph(self.clean_html_text(text)) if text else ''
                    if text:
                        html_parts.append(f'<p class="summary">{text}</p>')
                    if item.get('bullets'):
                        html_parts.append('<ul class="bullets">')
                        for bullet in item.get('bullets', []):
                            html_parts.append(f'<li>{self.clean_html_text(bullet)}</li>')
                        html_parts.append('</ul>')
                    html_parts.append('</div>')
                if section_name:
                    html_parts.append('</div>')
        
        html_parts.append('</div></body></html>')
        return '\n'.join(html_parts)
    
    def generate_css(self) -> str:
        """Smarter design: accent stripes, card hierarchy, refined typography."""
        return """
        @page {
            size: letter;
            margin: 0.35in;
        }
        body {
            font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
            font-size: 9.5pt;
            line-height: 1.2;
            color: #1a1a1a;
            margin: 0;
            padding: 0;
            text-align: left;
        }
        .resume {
            padding-left: 0;
            margin: 0;
        }
        .header {
            margin-bottom: 8px;
            padding: 4px 6px 4px 4px;
            background-color: #e8f0f4;
            border-radius: 0 3px 3px 0;
        }
        .name {
            font-size: 16pt;
            font-weight: 700;
            color: #1a5276;
            margin: 0 0 1px 0;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            line-height: 1.1;
            border-bottom: 2px solid #1a5276;
            padding-bottom: 2px;
            display: inline-block;
        }
        .profile-title {
            font-size: 9pt;
            color: #555;
            margin: 2px 0 1px 0;
            font-weight: 500;
            font-style: italic;
        }
        .contact-line {
            font-size: 8.5pt;
            color: #444;
            margin: 0;
            line-height: 1.25;
        }
        .contact-line .sep {
            color: #1a5276;
            margin: 0 3px;
            font-weight: 600;
        }
        .section {
            margin-bottom: 12px;
        }
        h2 {
            font-size: 9.5pt;
            font-weight: 700;
            color: #1a5276;
            margin: 12px 0 6px 0;
            padding: 2px 0 6px 4px;
            text-transform: uppercase;
            letter-spacing: 0.6px;
            background-color: #f0f5f8;
            border-radius: 0 2px 2px 0;
            border-bottom: 2px solid #d0d8dc;
        }
        h2:first-of-type {
            margin-top: 4px;
        }
        .summary-box {
            padding: 4px 6px 4px 4px;
            border-radius: 0 3px 3px 0;
            background-color: #fafbfc;
        }
        .summary {
            text-align: left;
            margin: 0;
            font-size: 9.5pt;
            line-height: 1.22;
            word-wrap: break-word;
        }
        .experience-item {
            margin-bottom: 4px;
            padding: 3px 4px 3px 4px;
            border-radius: 0 3px 3px 0;
            background-color: #fafbfc;
        }
        .experience-item:last-child {
            margin-bottom: 0;
        }
        .exp-position {
            font-weight: bold;
            font-size: 9.5pt;
            margin: 0 0 0 0;
            color: #1a5276;
            line-height: 1.2;
        }
        .exp-company {
            font-size: 9.5pt;
            margin: 0 0 0 0;
            color: #333;
        }
        .exp-details {
            font-size: 8.5pt;
            margin: 0 0 2px 0;
            color: #555;
        }
        .exp-role {
            font-size: 8.5pt;
            margin: 0 0 2px 0;
            color: #444;
        }
        .bullets {
            margin: 2px 0 0 0;
            padding-left: 12px;
            list-style-type: none;
        }
        .bullets li {
            margin: 0;
            font-size: 9.5pt;
            line-height: 1.22;
            text-indent: -5px;
            padding-left: 5px;
            word-wrap: break-word;
            position: relative;
        }
        .bullets li:before {
            content: "\\2022 ";
            font-weight: bold;
            color: #1a5276;
        }
        .education-item {
            margin: 0 0 4px 0;
            padding: 3px 4px 3px 4px;
            border-radius: 0 3px 3px 0;
            background-color: #fafbfc;
        }
        .education-item:last-child {
            margin-bottom: 0;
        }
        .edu-degree {
            font-weight: 700;
            font-size: 9.5pt;
            margin: 0 0 0 0;
            color: #1a5276;
        }
        .edu-details {
            font-size: 8.5pt;
            margin: 0;
            color: #444;
        }
        .skills-block {
            padding: 3px 4px 3px 4px;
            border-radius: 0 3px 3px 0;
            background-color: #fafbfc;
        }
        .skill-line {
            margin: 0 0 1px 0;
            font-size: 9pt;
            line-height: 1.25;
        }
        .skill-line:last-child {
            margin-bottom: 0;
        }
        .skill-line strong {
            font-weight: 700;
            margin-right: 4px;
            color: #1a5276;
        }
        .cert-block {
            padding: 3px 4px 3px 4px;
            border-radius: 0 3px 3px 0;
            background-color: #fafbfc;
        }
        .cert-line {
            margin: 0 0 1px 0;
            font-size: 9pt;
            line-height: 1.25;
        }
        .cert-line:last-child {
            margin-bottom: 0;
        }
        .language-item {
            margin: 0 0 1px 0;
            font-size: 9pt;
        }
        strong {
            font-weight: bold;
        }
        a {
            color: #1a5276;
            text-decoration: none;
        }
        """
    
    def render_pdf(self, output_path: str, method: str = 'auto'):
        """Render PDF using the best available method."""
        if method == 'auto':
            # When running as frozen exe (e.g. PyInstaller on Windows), WeasyPrint
            # often fails (missing GTK/Cairo). Prefer ReportLab for consistent behavior.
            frozen = getattr(sys, 'frozen', False)
            if frozen and REPORTLAB_AVAILABLE:
                method = 'reportlab'
            elif WEASYPRINT_AVAILABLE:
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
            # On Windows, ReportLab (or stdio) can hit 'charmap' codec if path has non-ASCII.
            # Write to a temp file with ASCII path, then move to final path.
            if sys.platform == 'win32':
                try:
                    path_str = str(output_path)
                    path_str.encode('ascii')
                except UnicodeEncodeError:
                    fd, tmp_path = tempfile.mkstemp(suffix='.pdf')
                    try:
                        os.close(fd)
                        self.render_with_reportlab(tmp_path)
                        shutil.move(tmp_path, output_path)
                    finally:
                        if Path(tmp_path).exists():
                            try:
                                Path(tmp_path).unlink()
                            except OSError:
                                pass
                    return
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
