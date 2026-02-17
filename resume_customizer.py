#!/usr/bin/env python3
"""
Resume Customizer Tool

Uses OpenAI API to customize resume content based on job descriptions.
Analyzes job requirements and tailors resume sections to match perfectly.
"""

import json
import logging
import os
import sys
import copy
import shutil
import platform
from pathlib import Path
from typing import Dict, Any, List, Optional
import argparse
import re
from datetime import datetime

# Detailed debug logger (writes to resume_customizer_debug.log in script dir)
_log = logging.getLogger("resume_customizer")
def _ensure_debug_log():
    if _log.handlers:
        return
    _log.setLevel(logging.DEBUG)
    base = Path(__file__).resolve().parent
    try:
        h = logging.FileHandler(base / "resume_customizer_debug.log", encoding="utf-8")
    except Exception:
        h = logging.StreamHandler(sys.stderr)
    h.setLevel(logging.DEBUG)
    h.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    _log.addHandler(h)

try:
    from openai import OpenAI
except ImportError:
    print("Error: openai package not installed. Install with: pip install openai")
    sys.exit(1)

from pdf_resume_updater import PDFResumeUpdater


def normalize_for_matching(text):
    """Normalize text for matching by replacing special characters with ASCII equivalents."""
    if not text:
        return ""
    
    if not isinstance(text, str):
        try:
            text = str(text)
        except:
            return ""
    
    # Normalize special characters for matching
    text = text.replace('–', '-')  # En dash to hyphen
    text = text.replace('—', '-')  # Em dash to hyphen
    text = text.replace('&', 'and')  # Ampersand to 'and'
    text = text.replace('&amp;', 'and')  # HTML entity
    text = text.replace('&nbsp;', ' ')  # HTML entity
    text = re.sub(r'\s+', ' ', text)  # Normalize whitespace
    
    return text.lower().strip()


def clean_text(text):
    """Remove all emojis and non-ASCII characters from text."""
    if not text:
        return ""
    
    if not isinstance(text, str):
        try:
            text = str(text)
        except:
            return ""
    
    try:
        # Remove emojis and symbols
        text = re.sub(r'[\U0001F300-\U0001F9FF]', '', text)
        text = re.sub(r'[\U00002600-\U000027BF]', '', text)
        text = re.sub(r'[\U0001F600-\U0001F64F]', '', text)
        text = re.sub(r'[\U0001F680-\U0001F6FF]', '', text)
        text = re.sub(r'[\U0001F700-\U0001F7FF]', '', text)
        text = re.sub(r'[\U0001F800-\U0001F8FF]', '', text)
        text = re.sub(r'[\U0001F900-\U0001F9FF]', '', text)
        text = re.sub(r'[\U0001FA00-\U0001FAFF]', '', text)
        
        # Keep only printable ASCII (32-126) plus newlines and tabs
        cleaned = ''.join(char if (32 <= ord(char) <= 126) or char in '\n\t' else ' ' 
                          for char in text)
        
        # Reduce multiple spaces (but preserve newlines)
        # First, reduce multiple spaces within lines
        lines = cleaned.split('\n')
        cleaned_lines = [re.sub(r' +', ' ', line).strip() for line in lines]
        cleaned = '\n'.join(cleaned_lines)
        
        # Remove empty lines at start/end but keep internal structure
        cleaned = cleaned.strip()
        return cleaned
    except:
        # Fallback: force ASCII encoding
        try:
            return text.encode('ascii', errors='replace').decode('ascii')
        except:
            return ""


def safe_str(obj, max_len=None):
    """Convert any object to a safe ASCII string."""
    try:
        if isinstance(obj, Exception):
            s = str(obj.args[0]) if obj.args else type(obj).__name__
        else:
            s = str(obj)
    except:
        s = "(could not convert to string)"
    
    s = clean_text(s)
    if max_len and len(s) > max_len:
        s = s[:max_len] + "..."
    return s


def sanitize_windows_filename(name: str, max_length: int = 255) -> str:
    """Sanitize a filename for Windows compatibility.
    
    Removes invalid characters and reserved names.
    Handles Windows path length limits.
    """
    if not name:
        return "unnamed"
    
    # Windows invalid characters: < > : " / \ | ? *
    invalid_chars = r'[<>:"/\\|?*]'
    name = re.sub(invalid_chars, '_', name)
    
    # Remove control characters (0-31)
    name = ''.join(char for char in name if ord(char) >= 32)
    
    # Windows reserved names (case-insensitive)
    reserved_names = {
        'CON', 'PRN', 'AUX', 'NUL',
        'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
        'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
    }
    
    # Check if name (without extension) is reserved
    name_base = name.rsplit('.', 1)[0].upper()
    if name_base in reserved_names or name_base.endswith('.'):
        name = '_' + name
    
    # Remove leading/trailing spaces and dots (Windows doesn't allow these)
    name = name.strip(' .')
    
    # Limit length (Windows max filename is 255 chars, but we account for path)
    if len(name) > max_length:
        # Try to preserve extension
        if '.' in name:
            name_base, ext = name.rsplit('.', 1)
            max_base = max_length - len(ext) - 1
            name = name_base[:max_base] + '.' + ext
        else:
            name = name[:max_length]
    
    # Ensure it's not empty after sanitization
    if not name or name.strip() == '':
        name = "unnamed"
    
    return name


def sanitize_windows_path(path: Path, max_path_length: int = 240) -> Path:
    """Sanitize a full path for Windows compatibility.
    
    Windows has a 260 character path limit by default.
    We use 240 to leave room for the filename.
    """
    if platform.system() != 'Windows':
        return path
    
    # Get parts
    parts = list(path.parts)
    drive_root = (path.drive + path.root) if path.drive else None

    # Sanitize each part (do not sanitize drive+root on Windows, e.g. 'C:\')
    sanitized_parts = []
    for i, part in enumerate(parts):
        if part in ('/', '\\', ''):
            sanitized_parts.append(part)
        elif drive_root and part == drive_root:
            sanitized_parts.append(part)
        else:
            sanitized_parts.append(sanitize_windows_filename(part))
    
    # Reconstruct path
    sanitized_path = Path(*sanitized_parts)
    
    # Check total length
    path_str = str(sanitized_path)
    if len(path_str) > max_path_length:
        # Try to shorten the filename part
        if sanitized_path.is_absolute():
            # Get drive and root
            drive = sanitized_path.drive
            root = sanitized_path.root
            remaining = max_path_length - len(drive) - len(root) - 10  # Safety margin
            
            # Shorten the last part (filename)
            parts = list(sanitized_path.parts[2:])  # Skip drive and root
            if parts:
                last_part = parts[-1]
                if '.' in last_part:
                    base, ext = last_part.rsplit('.', 1)
                    max_base = remaining - len(ext) - 1 - sum(len(p) + 1 for p in parts[:-1])
                    if max_base > 10:
                        parts[-1] = base[:max_base] + '.' + ext
                    else:
                        parts[-1] = 'file.' + ext
                else:
                    max_len = remaining - sum(len(p) + 1 for p in parts[:-1])
                    if max_len > 10:
                        parts[-1] = last_part[:max_len]
                    else:
                        parts[-1] = 'file'
                
                sanitized_path = Path(drive, root, *parts)
    
    return sanitized_path


def setup_windows_console():
    """Setup Windows console for UTF-8 encoding if on Windows."""
    if platform.system() == 'Windows':
        try:
            # Set console code page to UTF-8
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleOutputCP(65001)  # UTF-8 code page
            kernel32.SetConsoleCP(65001)
        except:
            pass  # Silently fail if not in console or can't set


class ResumeCustomizer:
    """Customizes resume content based on job descriptions using OpenAI."""
    
    def __init__(self, pdf_path: str, api_key: Optional[str] = None):
        self.updater = PDFResumeUpdater(pdf_path)
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError(
                "OpenAI API key required. Set OPENAI_API_KEY environment variable "
                "or pass --api-key argument"
            )
        # CRITICAL: Clean API key to ensure no emojis
        # Make sure we have a clean copy - don't modify the original
        original_api_key = self.api_key
        clean_api_key = clean_text(original_api_key) if original_api_key else None
        if not clean_api_key:
            raise ValueError("API key is empty after cleaning")
        
        # CRITICAL: Verify API key is clean and separate from any other strings
        # Ensure it's exactly 164 characters (the expected length)
        if len(clean_api_key) != 164:
            # Log detailed error information
            error_msg = f"API key length is {len(clean_api_key)}, expected 164. Possible corruption."
            error_msg += f" Original length: {len(original_api_key) if original_api_key else 0}."
            if len(clean_api_key) > 200:
                error_msg += f" First 100 chars: {repr(clean_api_key[:100])}"
                error_msg += f" Last 100 chars: {repr(clean_api_key[-100])}"
            raise ValueError(error_msg)
        
        # Store the cleaned API key
        self.api_key = clean_api_key
        
        # CRITICAL: Initialize OpenAI client with a fresh, clean API key string
        # Make sure we're passing a clean string, not a reference that could be modified
        # Use string slicing to ensure we have a completely independent copy
        api_key_for_client = clean_api_key[:]  # Create a copy
        self.client = OpenAI(api_key=api_key_for_client)
        self.resume_data = None
        
    def load_resume_data(self):
        """Load and extract resume data."""
        if not self.resume_data:
            self.updater.extract_json_data()
            self.resume_data = self.updater.data
        else:
            self.updater.data = self.resume_data
        
        # Log all sections for recognition
        self.log_all_sections()
        
        return self.resume_data
    
    def log_all_sections(self):
        """Log all sections found in the resume for recognition."""
        # Production: No logging
        pass
    
    @staticmethod
    def _section_has_summary_items(section: Dict[str, Any]) -> bool:
        """True if section has summary-like items (items with 'text')."""
        for item in section.get('items', []):
            if item.get('text') is not None or (isinstance(item.get('text'), str) and item.get('text') != ''):
                return True
            if 'text' in item:
                return True
        return False
    
    @staticmethod
    def _section_has_experience_items(section: Dict[str, Any]) -> bool:
        """True if section has experience-like items (position/workplace or title/company + bullets)."""
        for item in section.get('items', []):
            has_role = 'position' in item or 'title' in item
            has_company = 'workplace' in item or 'company' in item
            if (has_role or has_company) and isinstance(section.get('items'), list):
                return True
        return False
    
    @staticmethod
    def _section_has_project_items(section: Dict[str, Any]) -> bool:
        """True if section has project-like items: at least one item with title/name/projectName (so Summary is excluded)."""
        for item in section.get('items', []):
            has_title = any(
                item.get(k) and str(item.get(k)).strip()
                for k in ('title', 'name', 'projectName')
            )
            if has_title:
                return True
        return False
    
    @staticmethod
    def _section_has_skill_items(section: Dict[str, Any]) -> bool:
        """True if section has skill-like items (items with 'tags')."""
        for item in section.get('items', []):
            if 'tags' in item and isinstance(item.get('tags'), list):
                return True
        return False
    
    @staticmethod
    def _normalize_project_title(raw: str) -> str:
        """Strip leading list markers / stray chars so titles render correctly in PDF."""
        if not raw or not isinstance(raw, str):
            return raw or ""
        s = raw.strip()
        s = re.sub(r'^\s*\d+\.\s*', '', s)
        s = re.sub(r'^[•\-–—]\s*', '', s)
        if len(s) > 2 and s[1] in (' ', '\t') and (
            s[0] in ('n', 'N') or (len(s) > 2 and s[2:3] and s[2].isupper())
        ):
            s = s[2:].lstrip()
        return s.strip()
    
    def extract_resume_content(self) -> Dict[str, Any]:
        """Extract key content from resume for customization."""
        self.load_resume_data()
        
        header = self.resume_data.get('header', {})
        
        # Extract summary (find section by content: items with 'text')
        summary = ""
        for section in self.resume_data.get('sections', []):
            if self._section_has_summary_items(section):
                if section.get('items'):
                    summary = section['items'][0].get('text', '')
                break
        summary = clean_text(summary)
        
        # Extract experiences (find section by content: items with position/workplace or title/company)
        experiences = []
        for section in self.resume_data.get('sections', []):
            if self._section_has_experience_items(section):
                for item in section.get('items', []):
                    pos = item.get('position', '') or item.get('title', '')
                    comp = item.get('workplace', '') or item.get('company', '')
                    exp = {
                        'position': clean_text(pos),
                        'company': clean_text(comp),
                        'location': clean_text(item.get('location', '')),
                        'dateRange': item.get('dateRange', {}),
                        'bullets': [clean_text(bullet) for bullet in item.get('bullets', [])]
                    }
                    experiences.append(exp)
                break
        
        # Extract skills (find section by content: items with 'tags')
        skills = []
        for section in self.resume_data.get('sections', []):
            if self._section_has_skill_items(section):
                for item in section.get('items', []):
                    skills.extend([clean_text(tag) for tag in item.get('tags', [])])
                break
        
        # Extract education (use __t for education; schema is stable)
        education = []
        for section in self.resume_data.get('sections', []):
            if section.get('__t') == 'EducationSection':
                for item in section.get('items', []):
                    edu = {
                        'institution': clean_text(item.get('institution', '')),
                        'degree': clean_text(item.get('degree', '')),
                        'location': clean_text(item.get('location', '')),
                        'dateRange': item.get('dateRange', {})
                    }
                    education.append(edu)
                break
        
        return {
            'name': clean_text(header.get('name', '')),
            'title': clean_text(header.get('title', '')),
            'summary': summary,
            'experiences': experiences,
            'skills': list(set(skills)),
            'education': education
        }
    
    def customize_summary(self, job_description: str, model: str = "gpt-4o-mini") -> str:
        """Customize summary section based on job description."""
        job_description = clean_text(job_description)
        resume_content = self.extract_resume_content()
        
        # Extract experience years from original summary
        original_summary = resume_content['summary']
        experience_years_match = re.search(
            r'(\d+\+?|\d+\s*years?|over\s+\d+\s*years?|\d+\+\s*years?)', 
            original_summary, re.IGNORECASE
        )
        experience_years = experience_years_match.group(0) if experience_years_match else None
        
        # CRITICAL: Clean all content before building the prompt string
        # This prevents emojis from being in the f-string which could cause encoding errors
        clean_summary = clean_text(resume_content['summary'])
        clean_job_desc = clean_text(job_description)
        
        prompt = f"""You are an expert resume writer. The resume must PERFECTLY match the job description. Your task is to rewrite the summary so it meets ALL requirements of the job description.

Current Summary:
{clean_summary}

Job Description:
{clean_job_desc}

CRITICAL - PERFECT MATCH WITH JOB:
1. The summary must meet ALL key requirements of the job (technologies, skills, responsibilities) using the EXACT same wording as the job - but do NOT downgrade the candidate's level.
2. If the job is junior or mid-level, do NOT make the summary sound junior. Always present the profile as professionally as possible: preserve the candidate's actual seniority, leadership, and scope. A senior candidate applying to a junior role should still sound senior and professional.
3. Extract requirements from the job (technologies, methodologies, role type) and address them with exact keywords - never reduce or tone down the candidate's experience level to match the job level.
4. Use the EXACT terminology from the job (e.g. ".NET Core", "Azure", "microservices"). Keep the summary concise - 3-4 sentences (80-120 words).
5. Preserve the experience years exactly as "{experience_years}" if it appears in the original summary.
6. Keep all information truthful - only rephrase existing experience; do not invent new experience. Remove ALL HTML tags - return plain text only.

Return ONLY the customized summary text, no explanations or additional text."""

        prompt = clean_text(prompt)
        system_message = clean_text("You are an expert resume writer. Match the job's requirements and keywords, but never downgrade the candidate's level (e.g. if the job is junior, keep the profile senior and professional). Always present the profile as professionally as possible.")
        
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt}
        ]
        
        # CRITICAL: Final cleaning pass - ensure NO emojis in messages before API call
        for msg in messages:
            msg['content'] = clean_text(msg['content'])
        
        clean_model = clean_text(model)
        
        response = self.client.chat.completions.create(
            model=clean_model,
            messages=messages,
            temperature=0.7,
            max_tokens=250
        )
        
        summary = clean_text(response.choices[0].message.content.strip())
        
        # Restore experience years if missing
        if experience_years:
            if not re.search(r'(\d+\+?|\d+\s*years?|over\s+\d+\s*years?|\d+\+\s*years?)', summary, re.IGNORECASE):
                summary = f"With {experience_years} of experience, {summary.lower()}"
        
        return summary
    
    def customize_experience_bullets(self, job_description: str, model: str = "gpt-4o-mini") -> List[Dict[str, Any]]:
        """Customize experience bullet points to match job description."""
        job_description = clean_text(job_description)
        resume_content = self.extract_resume_content()
        
        # Format experiences for prompt
        exp_text = ""
        for i, exp in enumerate(resume_content['experiences'], 1):
            exp_text += f"\n{i}. {exp['position']} at {exp['company']}\n"
            exp_text += f"   Current bullets:\n"
            for bullet in exp['bullets']:
                exp_text += f"   - {bullet}\n"
        
        # CRITICAL: Clean all content before building the prompt string
        clean_job_desc = clean_text(job_description)
        clean_exp_text = clean_text(exp_text)
        
        prompt = f"""You are an expert resume writer. The resume must PERFECTLY match the job description. Your task is to rewrite experience bullets so they meet ALL requirements of the job description.

Job Description:
{clean_job_desc}

Current Experiences:
{clean_exp_text}

CRITICAL - PERFECT MATCH WITH JOB:
1. The experience section must meet ALL key requirements of the job (technologies, responsibilities, qualifications) using the EXACT keywords from the job - but do NOT downgrade the candidate's level.
2. If the job is junior or mid-level, do NOT make the experience sound junior. Always present the profile as professionally as possible: keep leadership, scope, ownership, and seniority. A senior candidate's bullets should still show senior/lead-level impact (e.g. led, architected, mentored) even when applying to a junior role.
3. For EACH experience, write bullets that prove the candidate has what the job asks for - use EXACT keywords and phrases from the job. Do not tone down achievements or reduce responsibility level to match the job.
4. Make bullets concise but impactful with metrics; each bullet 1 sentence. Use 3-4 bullets per experience. Keep all information truthful - only expand and rephrase existing achievements.
5. ABSOLUTELY CRITICAL: Use the EXACT position name and company name from "Current Experiences" - DO NOT change them. Return them EXACTLY as in the input.

Return results as a JSON object with "experiences" key containing an array:
   {{
     "experiences": [
       {{
         "position": "EXACT position name from above",
         "company": "EXACT company name from above",
         "bullets": ["detailed bullet 1 with metrics and job-relevant keywords", "detailed bullet 2", "detailed bullet 3", "detailed bullet 4", "detailed bullet 5"]
       }}
     ]
   }}

Return ONLY the JSON object with "experiences" key, no additional text."""

        prompt = clean_text(prompt)
        system_message = clean_text("You are an expert resume writer. Match the job's requirements and keywords; never downgrade the candidate's level (e.g. keep senior/lead language even for junior roles). Always return valid JSON.")
        
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt}
        ]
        
        # CRITICAL: Final cleaning pass - ensure NO emojis in messages before API call
        for msg in messages:
            msg['content'] = clean_text(msg['content'])
        
        clean_model = clean_text(model)
        
        response = self.client.chat.completions.create(
            model=clean_model,
            messages=messages,
            temperature=0.7,
            response_format={"type": "json_object"},
            max_tokens=2500
        )
        
        try:
            content = response.choices[0].message.content
            content = clean_text(content)
            result = json.loads(content)
            
            if isinstance(result, dict) and 'experiences' in result:
                return result['experiences']
            elif isinstance(result, list):
                return result
            else:
                for value in result.values():
                    if isinstance(value, list):
                        return value
                return []
        except json.JSONDecodeError:
            content = clean_text(response.choices[0].message.content.strip())
            if content.startswith('['):
                return json.loads(content)
            raise ValueError(f"Failed to parse experience customization: {content[:200]}")
    
    def customize_projects(self, job_description: str, model: str = "gpt-4o-mini") -> List[Dict[str, Any]]:
        """Customize project descriptions to match job description."""
        _ensure_debug_log()
        _log.debug("customize_projects: start")
        job_description = clean_text(job_description)
        if not self.resume_data:
            _log.debug("customize_projects: resume_data was None, calling load_resume_data()")
            self.load_resume_data()
        num_sections = len(self.resume_data.get('sections', []))
        _log.debug("customize_projects: resume_data has %s sections", num_sections)

        # Extract projects from resume (use project NAME for title so API returns consistent titles)
        projects = []
        project_section_found = False
        for si, section in enumerate(self.resume_data.get('sections', [])):
            if self._section_has_project_items(section):
                project_section_found = True
                items = section.get('items', [])
                _log.debug("customize_projects: project section found at section index %s, items=%s", si, len(items))
                if not items:
                    break
                for item in items:
                    # Prefer project name (projectName/name) over role (title) for stable matching
                    project_name = clean_text(
                        item.get('projectName', '') or item.get('name', '') or item.get('title', '')
                    )
                    description = clean_text(item.get('description', '') or item.get('text', ''))
                    bullets = [clean_text(bullet) for bullet in item.get('bullets', [])]
                    proj = {'title': project_name, 'description': description, 'bullets': bullets}
                    if proj['title']:
                        projects.append(proj)
                        _log.debug("customize_projects: extracted project title=%r (desc len=%s, bullets=%s)",
                                   proj['title'][:60], len(description), len(bullets))
                break

        if not project_section_found:
            _log.debug("customize_projects: no project section found ( _section_has_project_items False for all)")
        if not projects:
            _log.debug("customize_projects: no projects extracted, returning []")
        if not project_section_found or not projects:
            return []

        # Format projects for prompt
        proj_text = ""
        for i, proj in enumerate(projects, 1):
            proj_text += f"\n{i}. {proj['title']}\n"
            if proj['description']:
                proj_text += f"   Description: {proj['description']}\n"
            if proj['bullets']:
                proj_text += f"   Current bullets:\n"
                for bullet in proj['bullets']:
                    proj_text += f"   - {bullet}\n"
        
        clean_job_desc = clean_text(job_description)
        clean_proj_text = clean_text(proj_text)
        
        prompt = f"""You are an expert resume writer. The resume must PERFECTLY match the job description. Your task is to rewrite project descriptions and bullets so they meet ALL requirements of the job description.

Job Description:
{clean_job_desc}

Current Projects:
{clean_proj_text}

CRITICAL - PERFECT MATCH WITH JOB:
1. The projects section must meet ALL key requirements of the job (technologies, outcomes) using the EXACT keywords from the job - but do NOT downgrade the candidate's level.
2. If the job is junior or mid-level, do NOT make projects sound junior. Present the profile as professionally as possible: keep scope, ownership, and impact (e.g. led, architected, delivered). Do not reduce the level of responsibility to match the job.
3. For EACH project, write description and bullets that demonstrate what the job asks for with exact keywords - without toning down the candidate's role or impact.
4. Make descriptions and bullets concise but impactful with metrics; each bullet 1 sentence. Use 3-4 bullets per project. Keep all information truthful.
5. Use the EXACT project title from "Current Projects" - DO NOT change it.

Return results as a JSON object with "projects" key containing an array:
   {{
     "projects": [
       {{
         "title": "EXACT project title from above",
         "description": "enhanced description matching job requirements",
         "bullets": ["detailed bullet 1 with metrics", "detailed bullet 2", "detailed bullet 3"]
       }}
     ]
   }}

Return ONLY the JSON object with "projects" key, no additional text."""

        prompt = clean_text(prompt)
        system_message = clean_text("You are an expert resume writer. Match the job's requirements and keywords; never downgrade the candidate's level. Present the profile as professionally as possible. Always return valid JSON.")
        
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt}
        ]
        
        for msg in messages:
            msg['content'] = clean_text(msg['content'])
        
        clean_model = clean_text(model)
        
        response = self.client.chat.completions.create(
            model=clean_model,
            messages=messages,
            temperature=0.7,
            response_format={"type": "json_object"},
            max_tokens=2000
        )
        
        try:
            content = response.choices[0].message.content
            content = clean_text(content)
            result = json.loads(content)
            if isinstance(result, dict) and 'projects' in result:
                out = result['projects']
                _log.debug("customize_projects: API returned %s projects", len(out))
                for i, p in enumerate(out):
                    _log.debug("customize_projects: API project[%s] title=%r", i, (p.get('title') or '')[:60])
                return out
            elif isinstance(result, list):
                _log.debug("customize_projects: API returned list of %s items", len(result))
                return result
            else:
                for value in result.values():
                    if isinstance(value, list):
                        _log.debug("customize_projects: API returned dict with list value len=%s", len(value))
                        return value
                _log.debug("customize_projects: API response format unexpected, keys=%s", list(result.keys()) if isinstance(result, dict) else type(result))
                return []
        except json.JSONDecodeError as e:
            raw = response.choices[0].message.content
            content = clean_text(raw.strip())[:300]
            _log.debug("customize_projects: JSONDecodeError %s; content preview=%r", e, content)
            if content.startswith('['):
                return json.loads(content)
            raise ValueError(f"Failed to parse project customization: {content[:200]}")
        except Exception as e:
            _log.debug("customize_projects: exception %s", e, exc_info=True)
            raise
    
    def prioritize_skills(self, job_description: str, model: str = "gpt-4o-mini") -> Dict[str, List[str]]:
        """Prioritize and reorganize skills based on job description."""
        job_description = clean_text(job_description)
        resume_content = self.extract_resume_content()
        
        # CRITICAL: Clean all content before building the prompt string
        clean_skills = ', '.join([clean_text(skill) for skill in resume_content['skills']])
        clean_job_desc = clean_text(job_description)
        
        prompt = f"""You are an expert resume writer specializing in ATS and AI screening. Your task is to make the resume SKILLS SECTION perfectly match the job's tech stack so the profile is detected as a strong match.

Current Skills (candidate's existing skills):
{clean_skills}

Job Description:
{clean_job_desc}

CRITICAL INSTRUCTIONS - STACK MUST MATCH JOB:
1. EXTRACT every technology, framework, tool, and platform mentioned in the job and reflect them in the skills section. USE THE EXACT SAME NAMES as in the job.
2. PRIORITIZE job-mentioned skills first in each category, then include ALL other relevant skills from the candidate's list. Do NOT remove or downgrade the candidate's skills to match a junior job - present the full professional skill set (e.g. if the candidate has architecture, leadership, or advanced tools, keep them). Match the job's stack but keep the profile as strong and professional as possible.
3. ADD missing job-required technologies when the candidate has related experience (use the exact job term). Create categories that align with the job.
4. Return results as JSON with category names as keys and arrays of skill strings as values.

Return ONLY the JSON object, no additional text."""

        prompt = clean_text(prompt)
        system_message = clean_text("You are an expert resume writer. Always return valid JSON. The skills section must match the job's tech stack exactly so ATS and AI detect the resume as a strong match.")
        
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt}
        ]
        
        # CRITICAL: Final cleaning pass - ensure NO emojis in messages before API call
        for msg in messages:
            msg['content'] = clean_text(msg['content'])
        
        clean_model = clean_text(model)
        
        response = self.client.chat.completions.create(
            model=clean_model,
            messages=messages,
            temperature=0.5,
            response_format={"type": "json_object"},
            max_tokens=2000
        )
        
        try:
            content = clean_text(response.choices[0].message.content)
            return json.loads(content)
        except json.JSONDecodeError:
            error_content = clean_text(response.choices[0].message.content)[:200]
            raise ValueError(f"Failed to parse skills prioritization: {error_content}")
    
    def customize_for_job(self, job_description: str, 
                          customize_summary: bool = True,
                          customize_experience: bool = True,
                          customize_skills: bool = True,
                          customize_projects: bool = True,
                          model: str = "gpt-4o-mini") -> Dict[str, Any]:
        """Customize entire resume for a job description."""
        job_description = clean_text(job_description)
        
        updates = {}
        
        if customize_summary:
            updates['summary'] = self.customize_summary(job_description, model)
        
        if customize_experience:
            updates['experiences'] = self.customize_experience_bullets(job_description, model)
        
        if customize_projects:
            _ensure_debug_log()
            projects = self.customize_projects(job_description, model)
            _log.debug("customize_for_job: customize_projects returned %s items", len(projects) if projects else 0)
            if projects:
                updates['projects'] = projects
            else:
                _log.debug("customize_for_job: updates['projects'] NOT set (empty list)")

        if customize_skills:
            updates['skills'] = self.prioritize_skills(job_description, model)
        
        return updates
    
    def apply_updates(self, updates: Dict[str, Any]):
        """Apply customization updates to the resume."""
        if not self.resume_data:
            self.load_resume_data()
        else:
            self.updater.data = copy.deepcopy(self.resume_data)
        
        if 'summary' in updates:
            summary_text = re.sub(r'<[^>]+>', '', updates['summary'])
            for section in self.resume_data.get('sections', []):
                if self._section_has_summary_items(section):
                    if section.get('items'):
                        # Update ALL summary items, not just the first one
                        for item in section['items']:
                            item['text'] = summary_text
                    else:
                        section['items'] = [{
                            'id': 'summary_item',
                            'record': 'SummaryItem',
                            'text': summary_text,
                            'height': 130,
                            'alignment': 'left'
                        }]
                    break
            
            self.updater.data = copy.deepcopy(self.resume_data)
        
        if 'experiences' in updates:
            exp_section = None
            for section in self.updater.data.get('sections', []):
                if self._section_has_experience_items(section):
                    exp_section = section
                    break
            
            if exp_section:
                updated_count = 0
                total_items = len(exp_section.get('items', []))
                
                # Create a mapping of custom experiences for easier lookup
                # Use normalized strings for matching
                custom_exp_map = {}
                for custom_exp in updates['experiences']:
                    norm_pos = normalize_for_matching(custom_exp.get('position', '') or custom_exp.get('title', ''))
                    norm_comp = normalize_for_matching(custom_exp.get('company', '') or custom_exp.get('workplace', ''))
                    key = (norm_pos, norm_comp)
                    custom_exp_map[key] = custom_exp
                
                # Update ALL experience items; use same keys as in PDF (position/title, workplace/company)
                for item in exp_section.get('items', []):
                    original_position = item.get('position', '') or item.get('title', '')
                    original_company = item.get('workplace', '') or item.get('company', '')
                    original_dateRange = item.get('dateRange', {})
                    original_location = item.get('location', '')
                    norm_original_pos = normalize_for_matching(original_position)
                    norm_original_comp = normalize_for_matching(original_company)
                    item_key = (norm_original_pos, norm_original_comp)
                    
                    if item_key in custom_exp_map:
                        custom_exp = custom_exp_map[item_key]
                        item['bullets'] = custom_exp.get('bullets', [])
                        if 'position' in item:
                            item['position'] = original_position
                        if 'title' in item:
                            item['title'] = original_position
                        if 'workplace' in item:
                            item['workplace'] = original_company
                        if 'company' in item:
                            item['company'] = original_company
                        item['dateRange'] = original_dateRange
                        item['location'] = original_location
                        updated_count += 1
                    else:
                        best_match = None
                        best_score = 0
                        for custom_exp in updates['experiences']:
                            custom_pos = normalize_for_matching(custom_exp.get('position', '') or custom_exp.get('title', ''))
                            custom_comp = normalize_for_matching(custom_exp.get('company', '') or custom_exp.get('workplace', ''))
                            
                            # Calculate match score based on position and company similarity
                            pos_score = 0
                            comp_score = 0
                            
                            # Position matching: check if key words match
                            # Filter out punctuation-only words (like '-', '.', etc.)
                            pos_words_orig = {w for w in norm_original_pos.split() if w and not re.match(r'^[^\w]+$', w)}
                            pos_words_custom = {w for w in custom_pos.split() if w and not re.match(r'^[^\w]+$', w)}
                            if pos_words_orig and pos_words_custom:
                                common_pos_words = pos_words_orig.intersection(pos_words_custom)
                                # Calculate score based on common words
                                pos_score = len(common_pos_words) / max(len(pos_words_orig), len(pos_words_custom))
                                # If most key words match, boost the score
                                if len(common_pos_words) >= 3:  # At least 3 common words
                                    pos_score = max(pos_score, 0.6)
                            
                            # Company matching: check if key words match
                            # Filter out punctuation-only words
                            comp_words_orig = {w for w in norm_original_comp.split() if w and not re.match(r'^[^\w]+$', w)}
                            comp_words_custom = {w for w in custom_comp.split() if w and not re.match(r'^[^\w]+$', w)}
                            if comp_words_orig and comp_words_custom:
                                common_comp_words = comp_words_orig.intersection(comp_words_custom)
                                comp_score = len(common_comp_words) / max(len(comp_words_orig), len(comp_words_custom))
                                # Company names are usually shorter, so be more lenient
                                if len(common_comp_words) >= 1:  # At least 1 common word
                                    comp_score = max(comp_score, 0.5)
                            
                            # Also try substring matching as fallback
                            if not pos_score and (custom_pos in norm_original_pos or norm_original_pos in custom_pos):
                                pos_score = 0.6
                            if not comp_score and (custom_comp in norm_original_comp or norm_original_comp in custom_comp):
                                comp_score = 0.6
                            
                            # Combined score (both position and company should match reasonably)
                            total_score = (pos_score + comp_score) / 2
                            
                            # Accept match if:
                            # 1. Position matches well (>=0.5) and company matches (>=0.3)
                            # 2. OR both match reasonably (>=0.4 each)
                            # 3. OR company matches exactly and position has good word overlap (>=0.4)
                            if (pos_score >= 0.5 and comp_score >= 0.3) or \
                               (pos_score >= 0.4 and comp_score >= 0.4) or \
                               (comp_score >= 0.8 and pos_score >= 0.4):
                                if total_score > best_score:
                                    best_score = total_score
                                    best_match = custom_exp
                        
                        if best_match:
                            item['bullets'] = best_match.get('bullets', [])
                            if 'position' in item:
                                item['position'] = original_position
                            if 'title' in item:
                                item['title'] = original_position
                            if 'workplace' in item:
                                item['workplace'] = original_company
                            if 'company' in item:
                                item['company'] = original_company
                            item['dateRange'] = original_dateRange
                            item['location'] = original_location
                            updated_count += 1
            
            self.resume_data = copy.deepcopy(self.updater.data)
        
        if 'projects' in updates:
            _ensure_debug_log()
            proj_section = None
            for si, section in enumerate(self.updater.data.get('sections', [])):
                if self._section_has_project_items(section):
                    proj_section = section
                    _log.debug("apply_updates(projects): section found at index %s", si)
                    break
            if not proj_section:
                _log.debug("apply_updates(projects): NO project section found in updater.data")

            if proj_section:
                items = proj_section.get('items', [])
                custom_list = updates['projects']
                _log.debug("apply_updates(projects): items=%s, custom_list=%s", len(items), len(custom_list))

                def set_proj_content(it, custom, title_to_set: str):
                    if custom.get('description') is not None:
                        if 'description' in it:
                            it['description'] = custom['description']
                        if 'text' in it:
                            it['text'] = custom['description']
                    if custom.get('bullets') is not None:
                        it['bullets'] = list(custom['bullets'])
                    if 'title' in it:
                        it['title'] = title_to_set
                    elif 'name' in it:
                        it['name'] = title_to_set
                    elif 'projectName' in it:
                        it['projectName'] = title_to_set

                # Apply by index (API returns same order as sent) - fixes duplicate titles and title mismatch
                for idx, item in enumerate(items):
                    original_title = item.get('title', '') or item.get('name', '') or item.get('projectName', '')
                    if not original_title:
                        _log.debug("apply_updates(projects): item[%s] skipped (no title/name/projectName)", idx)
                        continue
                    display_title = self._normalize_project_title(original_title)
                    if idx < len(custom_list):
                        set_proj_content(item, custom_list[idx], display_title)
                        _log.debug("apply_updates(projects): item[%s] applied by index, original_title=%r", idx, original_title[:50])
                    else:
                        norm_original = normalize_for_matching(original_title)
                        matched = False
                        for custom_proj in custom_list:
                            if normalize_for_matching(custom_proj.get('title', '')) == norm_original:
                                set_proj_content(item, custom_proj, display_title)
                                matched = True
                                _log.debug("apply_updates(projects): item[%s] applied by title fallback", idx)
                                break
                        if not matched:
                            _log.debug("apply_updates(projects): item[%s] NOT matched (idx >= len(custom_list) and no title match)", idx)

            self.resume_data = copy.deepcopy(self.updater.data)
        
        if 'skills' in updates:
            self.updater.update_skills(updates['skills'])
            self.resume_data = self.updater.data
    
    def save_customized_resume(self, output_path: str, job_title: Optional[str] = None, render_visual: bool = False) -> tuple:
        """Save the customized resume.
        
        Returns:
            (visual_path, visual_error): Path to visual PDF if created else None;
            error message if visual rendering failed else None.
        """
        if not self.resume_data:
            raise ValueError("No resume data available. Call apply_updates() first.")
        
        # Verify all sections are preserved
        original_section_count = len(self.resume_data.get('sections', []))
        original_section_types = [s.get('__t', 'Unknown') for s in self.resume_data.get('sections', [])]
        
        self.updater.data = copy.deepcopy(self.resume_data)
        
        if job_title:
            self.updater.update_header(title=job_title)
            self.resume_data = copy.deepcopy(self.updater.data)
        
        # Verify sections are still present after updates (production: silent check)
        final_section_count = len(self.resume_data.get('sections', []))
        
        # Ensure output path is Windows compatible
        output_path_obj = sanitize_windows_path(Path(output_path))
        output_path = str(output_path_obj)
        
        # Ensure parent directory exists
        output_path_obj.parent.mkdir(parents=True, exist_ok=True)
        
        self.updater.data = copy.deepcopy(self.resume_data)
        # Embed customized JSON into PDF (updater does not render visual)
        self.updater.save_pdf(output_path, render_visual=False)
        
        # Render visual PDF from customizer's resume_data so it always shows customized content
        visual_path = None
        visual_error = None
        if render_visual:
            visual_path = str(output_path_obj.with_suffix('.visual.pdf'))
            try:
                from pdf_renderer import PDFRenderer
                data_for_visual = copy.deepcopy(self.resume_data)
                renderer = PDFRenderer(data_for_visual)
                renderer.render_pdf(visual_path)
            except ImportError:
                visual_error = "Visual PDF not available (install weasyprint or reportlab)."
            except Exception as e:
                visual_error = str(e)
                visual_path = None
                try:
                    import traceback
                    traceback.print_exc()
                except Exception:
                    pass
        
        try:
            print(f"\n[OK] Customized resume saved to: {output_path}")
        except UnicodeEncodeError:
            print(f"\n[OK] Customized resume saved.")
        return (visual_path, visual_error)


def extract_job_title(job_description: str) -> str:
    """Extract job title from job description.
    
    Looks for common patterns like:
    - JOB TITLE: ...
    - Position: ...
    - Title: ...
    - Role: ...
    """
    if not job_description:
        return "Unknown_Job"
    
    # Clean the job description first
    job_desc = clean_text(job_description)
    
    # Try to find job title patterns
    patterns = [
        r'(?:JOB\s*TITLE|Position|Title|Role|Job Title|POSITION|TITLE|ROLE)[:\s]+([^\n]+)',
        r'^([A-Z][A-Za-z\s&]+(?:Engineer|Developer|Architect|Specialist|Manager|Analyst|Consultant|Lead|Senior|Junior)[^\n]*)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, job_desc, re.IGNORECASE | re.MULTILINE)
        if match:
            title = match.group(1).strip()
            # Clean up the title
            title = re.sub(r'[^\w\s\-&]', '', title)  # Remove special chars except - and &
            title = re.sub(r'\s+', '_', title)  # Replace spaces with underscores
            title = title[:50]  # Limit length
            if title:
                return title
    
    # Fallback: use first line or first 50 chars
    first_line = job_desc.split('\n')[0].strip()
    if first_line:
        title = re.sub(r'[^\w\s\-&]', '', first_line[:50])
        title = re.sub(r'\s+', '_', title)
        return title if title else "Unknown_Job"
    
    return "Unknown_Job"


def create_job_folder(base_dir: Optional[Path] = None) -> Path:
    """Create a folder for organizing job applications.
    
    Structure: jobs/YYYY-MM-DD_HH-MM-SS_JobTitle/
    
    Args:
        base_dir: Base directory (defaults to current working directory)
        
    Returns:
        Path to the created job folder
    """
    if base_dir is None:
        base_dir = Path.cwd()
    
    jobs_dir = base_dir / "jobs"
    jobs_dir.mkdir(exist_ok=True)
    
    # Create timestamped folder
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    job_folder = jobs_dir / f"{timestamp}_Job"
    job_folder.mkdir(exist_ok=True)
    
    return job_folder


def organize_job_files(
    job_description: str,
    resume_pdf_path: str,
    visual_pdf_path: Optional[str] = None,
    job_title: Optional[str] = None,
    model: str = "gpt-4o-mini",
    base_dir: Optional[Path] = None
) -> Dict[str, str]:
    """Organize job description and customized resume into a structured folder.
    
    NOTE: This function COPIES files to the jobs folder. The original files in the
    root directory remain untouched for quick access.
    
    Creates:
    - jobs/YYYY-MM-DD_HH-MM-SS_JobTitle/
      ├── job_description.txt
      ├── resume_customized.pdf (copy from root)
      ├── resume_customized.visual.pdf (copy from root, if provided)
      └── metadata.json
    
    Args:
        job_description: The job description text
        resume_pdf_path: Path to the customized resume PDF (in root directory)
        visual_pdf_path: Path to the visual PDF in root directory (optional)
        job_title: Job title (will be extracted if not provided)
        model: Model used for customization
        base_dir: Base directory where jobs/ folder will be created (defaults to current working directory)
        
    Returns:
        Dictionary with paths to saved files in jobs folder:
        {
            'folder': path to job folder,
            'job_description': path to job_description.txt,
            'resume': path to resume_customized.pdf (copy),
            'visual_resume': path to visual PDF copy (if provided),
            'metadata': path to metadata.json
        }
    """
    # Extract job title if not provided
    if not job_title:
        job_title = extract_job_title(job_description)
    
    # Create base folder structure
    if base_dir is None:
        base_dir = Path.cwd()
    
    jobs_dir = base_dir / "jobs"
    jobs_dir.mkdir(exist_ok=True)
    
    # Create timestamped folder with job title
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    # Sanitize job title for folder name (Windows compatible)
    safe_title = sanitize_windows_filename(job_title, max_length=50)
    safe_title = re.sub(r'\s+', '_', safe_title)
    
    job_folder = jobs_dir / f"{timestamp}_{safe_title}"
    # Sanitize full path for Windows
    job_folder = sanitize_windows_path(job_folder)
    job_folder.mkdir(parents=True, exist_ok=True)
    
    # Save job description (Windows compatible)
    job_desc_path = job_folder / "job_description.txt"
    try:
        job_desc_path.write_text(job_description, encoding='utf-8', newline='\n')
    except Exception as e:
        # Fallback: try with different encoding or path
        try:
            job_desc_path = sanitize_windows_path(job_desc_path)
            job_desc_path.write_text(job_description, encoding='utf-8', newline='\n')
        except Exception as e2:
            raise IOError(f"Failed to save job description: {e2}")
    
    # Copy resume PDF (Windows compatible)
    resume_source = Path(resume_pdf_path)
    resume_dest = job_folder / "resume_customized.pdf"
    if resume_source.exists():
        try:
            shutil.copy2(resume_source, resume_dest)
        except Exception as e:
            # Retry with sanitized path
            resume_dest = sanitize_windows_path(resume_dest)
            shutil.copy2(resume_source, resume_dest)
    
    # Copy visual PDF if provided (Windows compatible)
    visual_dest = None
    if visual_pdf_path:
        visual_source = Path(visual_pdf_path)
        visual_dest = job_folder / "resume_customized.visual.pdf"
        if visual_source.exists():
            try:
                shutil.copy2(visual_source, visual_dest)
                visual_dest = str(visual_dest)
            except Exception as e:
                # Retry with sanitized path
                visual_dest = sanitize_windows_path(visual_dest)
                shutil.copy2(visual_source, visual_dest)
                visual_dest = str(visual_dest)
    
    # Create metadata
    metadata = {
        'job_title': job_title,
        'timestamp': timestamp,
        'date': datetime.now().isoformat(),
        'model_used': model,
        'resume_source': str(resume_pdf_path),
        'visual_resume_source': str(visual_pdf_path) if visual_pdf_path else None
    }
    
    metadata_path = job_folder / "metadata.json"
    try:
        with open(metadata_path, 'w', encoding='utf-8', newline='\n') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
    except Exception as e:
        # Retry with sanitized path
        metadata_path = sanitize_windows_path(metadata_path)
        with open(metadata_path, 'w', encoding='utf-8', newline='\n') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
    
    result = {
        'folder': str(job_folder),
        'job_description': str(job_desc_path),
        'resume': str(resume_dest),
        'metadata': str(metadata_path)
    }
    
    if visual_dest:
        result['visual_resume'] = visual_dest
    
    return result


def read_job_description(file_path: str) -> str:
    """Read job description from file."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Job description file not found: {file_path}")
    return path.read_text(encoding='utf-8')


def main():
    # Setup Windows console for UTF-8 if needed
    setup_windows_console()
    
    parser = argparse.ArgumentParser(
        description='Customize resume based on job description using OpenAI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Customize resume with job description from file
  python resume_customizer.py resume.pdf --job-desc job.txt --output customized.pdf
  
  # Customize with inline job description
  python resume_customizer.py resume.pdf --job-desc-text "Job description here" --output customized.pdf
  
  # Customize only summary and skills
  python resume_customizer.py resume.pdf --job-desc job.txt \\
    --no-experience --output customized.pdf
  
  # Use specific OpenAI model
  python resume_customizer.py resume.pdf --job-desc job.txt \\
    --model gpt-4 --output customized.pdf
        """
    )
    
    parser.add_argument('pdf_path', help='Path to the PDF resume file')
    parser.add_argument('--job-desc', metavar='FILE', 
                       help='Path to file containing job description')
    parser.add_argument('--job-desc-text', metavar='TEXT',
                       help='Job description text (inline)')
    parser.add_argument('--output', '-o', required=True,
                       help='Output path for customized PDF')
    parser.add_argument('--api-key', 
                       help='OpenAI API key (or set OPENAI_API_KEY env var)')
    parser.add_argument('--model', default='gpt-4o-mini',
                       choices=['gpt-4o', 'gpt-4o-mini', 'gpt-4', 'gpt-3.5-turbo'],
                       help='OpenAI model to use (default: gpt-4o-mini)')
    parser.add_argument('--job-title', 
                       help='Update resume title to match job title')
    parser.add_argument('--render-visual', action='store_true',
                       help='Also render a new visual PDF (updates the visual content)')
    parser.add_argument('--no-summary', action='store_true',
                       help='Skip summary customization')
    parser.add_argument('--no-experience', action='store_true',
                       help='Skip experience customization')
    parser.add_argument('--no-skills', action='store_true',
                       help='Skip skills prioritization')
    
    args = parser.parse_args()
    
    # Get job description
    if args.job_desc:
        job_description = read_job_description(args.job_desc)
    elif args.job_desc_text:
        job_description = args.job_desc_text
    else:
        parser.error("Either --job-desc or --job-desc-text is required")
    
    try:
        customizer = ResumeCustomizer(args.pdf_path, api_key=args.api_key)
        
        updates = customizer.customize_for_job(
            job_description,
            customize_summary=not args.no_summary,
            customize_experience=not args.no_experience,
            customize_skills=not args.no_skills,
            model=args.model
        )
        
        print("\nApplying updates to resume...")
        customizer.apply_updates(updates)
        customizer.save_customized_resume(args.output, args.job_title, render_visual=args.render_visual)
        
        print("\n[OK] Resume customization complete!")
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
