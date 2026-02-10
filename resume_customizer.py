#!/usr/bin/env python3
"""
Resume Customizer Tool

Uses OpenAI API to customize resume content based on job descriptions.
Analyzes job requirements and tailors resume sections to match perfectly.
"""

import json
import os
import sys
import copy
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
import argparse
import re

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
        sections = self.resume_data.get('sections', [])
        logging.info("=" * 60)
        logging.info("RESUME SECTIONS RECOGNITION")
        logging.info("=" * 60)
        
        for i, section in enumerate(sections, 1):
            section_type = section.get('__t', 'Unknown')
            section_name = section.get('name', '')
            enabled = section.get('enabled', True)
            items_count = len(section.get('items', []))
            
            logging.info(f"Section {i}: {section_type}")
            if section_name:
                logging.info(f"  Name: {section_name}")
            logging.info(f"  Enabled: {enabled}")
            logging.info(f"  Items: {items_count}")
            
            # Log section-specific details
            if section_type == 'SummarySection':
                if items_count > 0:
                    summary_preview = section['items'][0].get('text', '')[:100]
                    logging.info(f"  Preview: {summary_preview}...")
            
            elif section_type == 'ExperienceSection':
                if items_count > 0:
                    positions = [item.get('position', 'N/A') for item in section.get('items', [])[:3]]
                    logging.info(f"  Positions: {', '.join(positions)}")
            
            elif section_type == 'EducationSection':
                if items_count > 0:
                    degrees = [item.get('degree', 'N/A') for item in section.get('items', [])[:3]]
                    logging.info(f"  Degrees: {', '.join(degrees)}")
            
            elif section_type == 'TechnologySection':
                if items_count > 0:
                    all_skills = []
                    for item in section.get('items', []):
                        all_skills.extend(item.get('tags', []))
                    logging.info(f"  Skills count: {len(all_skills)}")
                    logging.info(f"  Sample skills: {', '.join(all_skills[:10])}")
            
            elif section_type == 'ActivitySection':
                if items_count > 0:
                    titles = [item.get('title', 'N/A') for item in section.get('items', [])[:3]]
                    logging.info(f"  Projects/Activities: {', '.join(titles)}")
            
            elif section_type == 'LanguageSection':
                if items_count > 0:
                    languages = [item.get('name', 'N/A') for item in section.get('items', [])[:3]]
                    logging.info(f"  Languages: {', '.join(languages)}")
            
            elif section_type == 'CertificateSection':
                if items_count > 0:
                    certs = [item.get('name', 'N/A') for item in section.get('items', [])[:3]]
                    logging.info(f"  Certificates: {', '.join(certs)}")
            
            logging.info("")
        
        logging.info("=" * 60)
    
    def extract_resume_content(self) -> Dict[str, Any]:
        """Extract key content from resume for customization."""
        self.load_resume_data()
        
        header = self.resume_data.get('header', {})
        
        # Extract summary
        summary = ""
        for section in self.resume_data.get('sections', []):
            if section.get('__t') == 'SummarySection':
                if section.get('items'):
                    summary = section['items'][0].get('text', '')
                break
        
        summary = clean_text(summary)
        
        # Extract experiences
        experiences = []
        for section in self.resume_data.get('sections', []):
            if section.get('__t') == 'ExperienceSection':
                for item in section.get('items', []):
                    exp = {
                        'position': clean_text(item.get('position', '')),
                        'company': clean_text(item.get('workplace', '')),
                        'location': clean_text(item.get('location', '')),
                        'dateRange': item.get('dateRange', {}),
                        'bullets': [clean_text(bullet) for bullet in item.get('bullets', [])]
                    }
                    experiences.append(exp)
                break
        
        # Extract skills
        skills = []
        for section in self.resume_data.get('sections', []):
            if section.get('__t') == 'TechnologySection':
                for item in section.get('items', []):
                    skills.extend([clean_text(tag) for tag in item.get('tags', [])])
                break
        
        # Extract education
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
        # DEBUG: Check for emoji before cleaning
        if job_description:
            for i, char in enumerate(job_description):
                if ord(char) > 127:
                    print(f"[DEBUG] Found non-ASCII at position {i} in job_description: {repr(char)} (U+{ord(char):04X})")
                    print(f"[DEBUG] Context: {repr(job_description[max(0, i-20):i+20])}")
        
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
        
        prompt = f"""You are an expert resume writer specializing in ATS optimization. Your task is to COMPLETELY match the summary to the job description by using the exact keywords, phrases, and requirements from the job description.

Current Summary:
{clean_summary}

Job Description:
{clean_job_desc}

CRITICAL INSTRUCTIONS:
1. COMPLETELY rewrite the summary to match the job description - use the exact same keywords, technologies, and requirements mentioned in the job
2. Extract ALL key requirements from the job description (technologies, skills, responsibilities, qualifications) and incorporate them into the summary
3. Use the EXACT same terminology from the job description (e.g., if job says ".NET Core", use ".NET Core" not ".NET")
4. Highlight experience and skills that DIRECTLY match what the job is asking for
5. Make the summary sound like it was written specifically for THIS job
6. Keep the summary concise but comprehensive - aim for 3-4 sentences (80-120 words) to include key keywords and requirements
7. Be selective - include the most important technologies, skills, and achievements mentioned in the job
8. IMPORTANT: You MUST preserve the experience years exactly as "{experience_years}" if it appears in the original summary. Do NOT change the number of years of experience.
9. Keep all information truthful - only rephrase existing experience, don't invent new experience
10. Remove ALL HTML tags like <strong> - return plain text only
11. The summary must read as if the candidate is a PERFECT match for this specific job

Return ONLY the customized summary text, no explanations or additional text."""

        prompt = clean_text(prompt)
        system_message = clean_text("You are an expert resume writer specializing in ATS optimization and job matching.")
        
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt}
        ]
        
        # CRITICAL: Final cleaning pass - ensure NO emojis in messages before API call
        for msg in messages:
            # DEBUG: Check for emoji in message content
            content = msg['content']
            if content:
                for i, char in enumerate(content):
                    if ord(char) > 127:
                        print(f"[DEBUG] Found non-ASCII at position {i} in message content: {repr(char)} (U+{ord(char):04X})")
                        print(f"[DEBUG] Message role: {msg['role']}")
                        print(f"[DEBUG] Context around position {i}: {repr(content[max(0, i-20):i+20])}")
                        if i == 171:
                            print(f"[DEBUG] *** THIS IS POSITION 171 - THE PROBLEMATIC CHARACTER ***")
                            print(f"[DEBUG] Full content length: {len(content)}")
                            print(f"[DEBUG] First 200 chars: {repr(content[:200])}")
            msg['content'] = clean_text(msg['content'])
        
        # DEBUG: Check model name
        if model:
            for i, char in enumerate(model):
                if ord(char) > 127:
                    print(f"[DEBUG] Found non-ASCII at position {i} in model: {repr(char)} (U+{ord(char):04X})")
        
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
        
        prompt = f"""You are an expert resume writer specializing in ATS optimization. Your task is to make the experience bullets RICHER, MORE DETAILED, and COMPLETELY match the job description requirements.

Job Description:
{clean_job_desc}

Current Experiences:
{clean_exp_text}

CRITICAL INSTRUCTIONS:
1. For EACH experience, rewrite ALL bullet points to COMPLETELY match the job description requirements
2. Use the EXACT keywords, technologies, and phrases from the job description (e.g., if job mentions ".NET Core", "Azure", "Microservices", use those exact terms)
3. Make bullets concise but impactful - include key achievements with metrics and impact
4. Each bullet should be 1 sentence with specific details, metrics, and impact (keep it brief)
5. Extract the MOST relevant requirements from the job description and show how the experience matches them
6. Use 3-4 bullets per experience (be selective, focus on quality over quantity)
7. Quantify EVERYTHING: use numbers, percentages, dollar amounts, timeframes, team sizes, etc.
8. Focus on results, impact, and achievements that directly relate to job requirements
9. Keep all information truthful - only expand and rephrase existing achievements, don't invent new experience
10. Each bullet should demonstrate a skill or achievement mentioned in the job description
11. ABSOLUTELY CRITICAL: You MUST use the EXACT position name and company name as provided in "Current Experiences" above - DO NOT change, modify, abbreviate, or alter them in ANY way. Return them EXACTLY as they appear in the input.

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
        system_message = clean_text("You are an expert resume writer. Always return valid JSON objects.")
        
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
        job_description = clean_text(job_description)
        
        # Extract projects from resume
        projects = []
        project_section_found = False
        
        # Sections are already logged in log_all_sections() when resume is loaded
        
        for section in self.resume_data.get('sections', []):
            # Projects can be in either ProjectSection or ActivitySection
            if section.get('__t') == 'ProjectSection' or section.get('__t') == 'ActivitySection':
                project_section_found = True
                section_type = section.get('__t', 'Unknown')
                items = section.get('items', [])
                logging.info(f"  Found {section_type} with {len(items)} items (treating as projects)")
                
                if not items:
                    logging.warning("  ProjectSection exists but has no items")
                    break
                
                for item in items:
                    # Try multiple possible field names for project title
                    title = clean_text(item.get('title', '') or item.get('name', '') or item.get('projectName', ''))
                    description = clean_text(item.get('description', '') or item.get('text', ''))
                    bullets = [clean_text(bullet) for bullet in item.get('bullets', [])]
                    
                    # Log what we found for debugging
                    if not title:
                        logging.warning(f"  Project item has no title. Available keys: {list(item.keys())}")
                        logging.warning(f"  Item content: {safe_str(item)[:200]}")
                    
                    proj = {
                        'title': title,
                        'description': description,
                        'bullets': bullets
                    }
                    if proj['title']:
                        projects.append(proj)
                        logging.info(f"  Extracted project: {title[:50]}...")
                break
        
        if not project_section_found:
            logging.warning("  No ProjectSection or ActivitySection found in resume")
            return []
        elif not projects:
            logging.warning("  ProjectSection/ActivitySection found but no valid projects extracted")
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
        
        prompt = f"""You are an expert resume writer specializing in ATS optimization. Your task is to make project descriptions RICHER, MORE DETAILED, and COMPLETELY match the job description requirements.

Job Description:
{clean_job_desc}

Current Projects:
{clean_proj_text}

CRITICAL INSTRUCTIONS:
1. For EACH project, rewrite ALL bullet points and descriptions to COMPLETELY match the job description requirements
2. Use the EXACT keywords, technologies, and phrases from the job description
3. Make descriptions concise but impactful - include key achievements with metrics and impact
4. Each bullet should be 1 sentence with specific details, metrics, and impact
5. Extract the MOST relevant requirements from the job description and show how the project matches them
6. Use 3-4 bullets per project (be selective, focus on quality over quantity)
7. Quantify EVERYTHING: use numbers, percentages, dollar amounts, timeframes, team sizes, etc.
8. Focus on results, impact, and achievements that directly relate to job requirements
9. Keep all information truthful - only expand and rephrase existing achievements
10. ABSOLUTELY CRITICAL: You MUST use the EXACT project title as provided in "Current Projects" above - DO NOT change, modify, abbreviate, or alter it in ANY way.

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
        system_message = clean_text("You are an expert resume writer. Always return valid JSON objects.")
        
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
                return result['projects']
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
            raise ValueError(f"Failed to parse project customization: {content[:200]}")
    
    def prioritize_skills(self, job_description: str, model: str = "gpt-4o-mini") -> Dict[str, List[str]]:
        """Prioritize and reorganize skills based on job description."""
        job_description = clean_text(job_description)
        resume_content = self.extract_resume_content()
        
        # CRITICAL: Clean all content before building the prompt string
        clean_skills = ', '.join([clean_text(skill) for skill in resume_content['skills']])
        clean_job_desc = clean_text(job_description)
        
        prompt = f"""You are an expert resume writer specializing in ATS optimization. Your task is to create RICHER, MORE DETAILED skill sets that perfectly match the job description.

Current Skills:
{clean_skills}

Job Description:
{clean_job_desc}

CRITICAL INSTRUCTIONS:
1. Create COMPREHENSIVE skill categories that match the job requirements
2. Group skills into detailed, specific categories (e.g., "Programming Languages", "Web Frameworks", "Backend Frameworks", "Frontend Frameworks", "Cloud Platforms & Services", "DevOps & CI/CD Tools", "Databases & Data Storage", "Testing & QA Tools", "Version Control", "API & Integration", "Architecture Patterns", "Methodologies")
3. Prioritize skills mentioned in the job description - put them first in their categories
4. Include ALL relevant skills from the current list - don't omit any that could be relevant
5. Create MORE categories if needed to better organize and showcase skills
6. For each category, include as many relevant skills as possible to make the skill set richer
7. Only use skills from the current list - don't add new skills that aren't in the list
8. Make the skill organization comprehensive and impressive - show depth and breadth
9. Return results as JSON with this structure:
   {{
     "Programming Languages": ["Python", "Java", "C#", "JavaScript"],
     "Backend Frameworks": [".NET Core", "ASP.NET MVC", "Django", "Spring Boot"],
     "Frontend Frameworks": ["React", "Angular", "Vue.js"],
     "Cloud Platforms": ["AWS", "Azure", "Google Cloud"],
     "DevOps Tools": ["Docker", "Kubernetes", "Jenkins", "CI/CD"],
     "Databases": ["SQL Server", "PostgreSQL", "MongoDB", "Cosmos DB"],
     ...
   }}

Return ONLY the JSON object, no additional text."""

        prompt = clean_text(prompt)
        system_message = clean_text("You are an expert resume writer. Always return valid JSON. Create comprehensive, detailed skill categories.")
        
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
        
        logging.info("Analyzing job description...")
        logging.info("Customizing resume content...")
        
        updates = {}
        
        if customize_summary:
            logging.info("[OK] Customizing summary...")
            updates['summary'] = self.customize_summary(job_description, model)
            logging.info(f"  Summary updated: {safe_str(updates['summary'][:80])}...")
        
        if customize_experience:
            logging.info("[OK] Customizing experience bullets...")
            updates['experiences'] = self.customize_experience_bullets(job_description, model)
            logging.info(f"  Updated {len(updates['experiences'])} experience entries")
        
        if customize_projects:
            projects = self.customize_projects(job_description, model)
            if projects:
                logging.info("[OK] Customizing projects...")
                updates['projects'] = projects
                logging.info(f"  Updated {len(updates['projects'])} project entries")
            else:
                logging.info("  No projects found in resume")
        
        if customize_skills:
            logging.info("[OK] Prioritizing skills...")
            updates['skills'] = self.prioritize_skills(job_description, model)
            logging.info(f"  Organized skills into {len(updates['skills'])} categories")
        
        logging.info(f"Customization complete. Updates: {list(updates.keys())}")
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
                if section.get('__t') == 'SummarySection':
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
                if section.get('__t') == 'ExperienceSection':
                    exp_section = section
                    break
            
            if exp_section:
                updated_count = 0
                total_items = len(exp_section.get('items', []))
                
                # Create a mapping of custom experiences for easier lookup
                # Use normalized strings for matching
                custom_exp_map = {}
                for custom_exp in updates['experiences']:
                    norm_pos = normalize_for_matching(custom_exp.get('position', ''))
                    norm_comp = normalize_for_matching(custom_exp.get('company', ''))
                    key = (norm_pos, norm_comp)
                    custom_exp_map[key] = custom_exp
                
                # Update ALL experience items
                for item in exp_section.get('items', []):
                    original_position = item.get('position', '')
                    original_company = item.get('workplace', '')
                    original_dateRange = item.get('dateRange', {})
                    original_location = item.get('location', '')
                    
                    # Normalize for matching
                    norm_original_pos = normalize_for_matching(original_position)
                    norm_original_comp = normalize_for_matching(original_company)
                    item_key = (norm_original_pos, norm_original_comp)
                    
                    if item_key in custom_exp_map:
                        custom_exp = custom_exp_map[item_key]
                        item['bullets'] = custom_exp.get('bullets', [])
                        item['position'] = original_position
                        item['workplace'] = original_company
                        item['dateRange'] = original_dateRange
                        item['location'] = original_location
                        updated_count += 1
                        logging.info(f"  Matched experience: {original_position} at {original_company}")
                    else:
                        # If no exact match, try fuzzy matching with normalized strings
                        matched = False
                        best_match = None
                        best_score = 0
                        
                        for custom_exp in updates['experiences']:
                            custom_pos = normalize_for_matching(custom_exp.get('position', ''))
                            custom_comp = normalize_for_matching(custom_exp.get('company', ''))
                            
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
                            item['position'] = original_position
                            item['workplace'] = original_company
                            item['dateRange'] = original_dateRange
                            item['location'] = original_location
                            updated_count += 1
                            matched = True
                            logging.info(f"  Fuzzy matched experience: {original_position} at {original_company} (score: {best_score:.2f})")
                        
                        if not matched:
                            logging.warning(f"  Warning: No match found for experience: {original_position} at {original_company}")
                            logging.warning(f"    Normalized: '{norm_original_pos}' at '{norm_original_comp}'")
                            logging.warning(f"    Available custom experiences:")
                            for exp in updates['experiences']:
                                norm_exp_pos = normalize_for_matching(exp.get('position', ''))
                                norm_exp_comp = normalize_for_matching(exp.get('company', ''))
                                logging.warning(f"      - '{norm_exp_pos}' at '{norm_exp_comp}'")
                
                logging.info(f"  Applied updates to {updated_count} of {total_items} experience entries")
                if updated_count < total_items:
                    logging.warning(f"  WARNING: Only {updated_count} of {total_items} experiences were updated!")
            
            self.resume_data = self.updater.data
        
        if 'projects' in updates:
            proj_section = None
            for section in self.updater.data.get('sections', []):
                # Projects can be in either ProjectSection or ActivitySection
                if section.get('__t') == 'ProjectSection' or section.get('__t') == 'ActivitySection':
                    proj_section = section
                    logging.info(f"  Found {section.get('__t')} for applying project updates")
                    break
            
            if proj_section:
                updated_count = 0
                total_items = len(proj_section.get('items', []))
                
                # Create a mapping of custom projects
                custom_proj_map = {}
                for custom_proj in updates['projects']:
                    key = custom_proj.get('title', '').lower().strip()
                    custom_proj_map[key] = custom_proj
                
                # Update ALL project items
                for item in proj_section.get('items', []):
                    original_title = item.get('title', '')
                    item_key = original_title.lower().strip()
                    
                    if item_key in custom_proj_map:
                        custom_proj = custom_proj_map[item_key]
                        if 'description' in custom_proj:
                            item['description'] = custom_proj['description']
                        if 'bullets' in custom_proj:
                            item['bullets'] = custom_proj['bullets']
                        item['title'] = original_title  # Preserve original
                        updated_count += 1
                    else:
                        # Try fuzzy matching
                        matched = False
                        for custom_proj in updates['projects']:
                            custom_title = custom_proj.get('title', '').lower().strip()
                            if custom_title in original_title.lower() or original_title.lower() in custom_title:
                                if 'description' in custom_proj:
                                    item['description'] = custom_proj['description']
                                if 'bullets' in custom_proj:
                                    item['bullets'] = custom_proj['bullets']
                                item['title'] = original_title
                                updated_count += 1
                                matched = True
                                break
                        
                        if not matched:
                            logging.warning(f"  Warning: No match found for project: {original_title}")
                
                logging.info(f"  Applied updates to {updated_count} of {total_items} project entries")
                if updated_count < total_items:
                    logging.warning(f"  WARNING: Only {updated_count} of {total_items} projects were updated!")
            
            self.resume_data = self.updater.data
        
        if 'skills' in updates:
            self.updater.update_skills(updates['skills'])
            self.resume_data = self.updater.data
    
    def save_customized_resume(self, output_path: str, job_title: Optional[str] = None, render_visual: bool = False):
        """Save the customized resume."""
        if not self.resume_data:
            raise ValueError("No resume data available. Call apply_updates() first.")
        
        self.updater.data = copy.deepcopy(self.resume_data)
        
        if job_title:
            self.updater.update_header(title=job_title)
            self.resume_data = copy.deepcopy(self.updater.data)
        
        self.updater.data = copy.deepcopy(self.resume_data)
        self.updater.save_pdf(output_path, render_visual=render_visual)
        print(f"\n[OK] Customized resume saved to: {output_path}")


def read_job_description(file_path: str) -> str:
    """Read job description from file."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Job description file not found: {file_path}")
    return path.read_text(encoding='utf-8')


def main():
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
