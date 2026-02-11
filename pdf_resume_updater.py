#!/usr/bin/env python3
"""
PDF Resume Updater Tool

This tool can extract, analyze, and update the content of Enhancv-generated PDF resumes.
The PDF contains embedded JSON data in the /ecv-data field that stores all resume information.
"""

import json
import re
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List
import argparse


class PDFResumeUpdater:
    """Tool to update Enhancv PDF resume content."""
    
    def __init__(self, pdf_path: str):
        self.pdf_path = Path(pdf_path)
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        self.data = None
        
    def extract_json_data(self) -> Dict[str, Any]:
        """Extract embedded JSON data from PDF."""
        try:
            with open(self.pdf_path, 'rb') as f:
                content = f.read()
            
            # Find the /ecv-data field in the PDF
            # It's stored as a hex-encoded UTF-16 string
            # Try different patterns to handle various formats
            patterns = [
                rb'/ecv-data\s*<FEFF([^>]+)>',  # Standard format
                rb'/ecv-data\s*<FE\s*FF([^>]+)>',  # Space-separated FE FF
                rb'/ecv-data\s*<FE\s*FF\s*([^>]+)>',  # More spaces
            ]
            
            match = None
            for pattern in patterns:
                match = re.search(pattern, content)
                if match:
                    break
            
            if not match:
                raise ValueError("Could not find /ecv-data field in PDF")
            
            # Extract hex-encoded data
            hex_data = match.group(1)
            
            # Convert hex to bytes
            try:
                # Remove spaces and decode hex
                hex_clean = hex_data.replace(b' ', b'').replace(b'\n', b'').replace(b'\r', b'')
                # Handle both bytes and string
                if isinstance(hex_clean, bytes):
                    hex_str = hex_clean.decode('ascii', errors='ignore')
                else:
                    hex_str = str(hex_clean)
                bytes_data = bytes.fromhex(hex_str)
                
                # Decode UTF-16 (BOM FEFF indicates UTF-16BE)
                json_str = bytes_data.decode('utf-16-be')
                
                # Parse JSON
                self.data = json.loads(json_str)
                return self.data
                
            except (UnicodeDecodeError, json.JSONDecodeError) as e:
                raise ValueError(f"Failed to decode JSON data: {e}")
                
        except Exception as e:
            raise RuntimeError(f"Error extracting data from PDF: {e}")
    
    def analyze_structure(self) -> Dict[str, Any]:
        """Analyze and return the structure of the resume data."""
        if not self.data:
            self.extract_json_data()
        
        structure = {
            'header': self.data.get('header', {}),
            'sections': []
        }
        
        for section in self.data.get('sections', []):
            section_info = {
                'type': section.get('__t', 'Unknown'),
                'name': section.get('name', ''),
                'enabled': section.get('enabled', False),
                'items_count': len(section.get('items', []))
            }
            structure['sections'].append(section_info)
        
        return structure
    
    def update_header(self, **kwargs):
        """Update header information.
        
        Available fields:
        - name: Full name
        - title: Job title
        - email: Email address
        - phone: Phone number
        - location: Location
        - link: LinkedIn/profile URL
        """
        if not self.data:
            self.extract_json_data()
        
        header = self.data.setdefault('header', {})
        
        if 'name' in kwargs:
            header['name'] = kwargs['name']
        if 'title' in kwargs:
            header['title'] = kwargs['title']
        if 'email' in kwargs:
            header['email'] = kwargs['email']
        if 'phone' in kwargs:
            header['phone'] = kwargs['phone']
        if 'location' in kwargs:
            header['location'] = kwargs['location']
        if 'link' in kwargs:
            header['link'] = kwargs['link']
    
    def update_summary(self, text: str):
        """Update the summary section text."""
        if not self.data:
            self.extract_json_data()
        
        for section in self.data.get('sections', []):
            if section.get('__t') == 'SummarySection':
                if section.get('items'):
                    section['items'][0]['text'] = text
                else:
                    section['items'] = [{
                        'id': 'summary_item',
                        'record': 'SummaryItem',
                        'text': text,
                        'height': 130,
                        'alignment': 'left'
                    }]
                return
        
        # If summary section doesn't exist, create it
        self.data.setdefault('sections', []).insert(0, {
            '__t': 'SummarySection',
            'name': '',
            'record': 'SummarySection',
            'enabled': True,
            'height': 36,
            'column': 0,
            'showTitle': True,
            'items': [{
                'id': 'summary_item',
                'record': 'SummaryItem',
                'text': text,
                'height': 130,
                'alignment': 'left'
            }]
        })
    
    def add_experience(self, position: str, company: str, location: str,
                      from_month: int, from_year: int, to_month: Optional[int] = None,
                      to_year: Optional[int] = None, is_ongoing: bool = False,
                      bullets: List[str] = None):
        """Add a new experience entry."""
        if not self.data:
            self.extract_json_data()
        
        # Find or create experience section
        exp_section = None
        for section in self.data.get('sections', []):
            if section.get('__t') == 'ExperienceSection':
                exp_section = section
                break
        
        if not exp_section:
            exp_section = {
                '__t': 'ExperienceSection',
                'name': '',
                'record': 'ExperienceSection',
                'enabled': True,
                'height': 36,
                'column': 0,
                'showCompanyLogos': False,
                'timelineWidth': 136,
                'items': []
            }
            self.data.setdefault('sections', []).append(exp_section)
        
        # Create experience item
        exp_item = {
            'id': f'exp_{len(exp_section["items"])}',
            'record': 'ExperienceItem',
            'alignment': 'left',
            'position': position,
            'workplace': company,
            'location': location,
            'dateRange': {
                'record': 'DateRange',
                'fromMonth': from_month,
                'fromYear': from_year,
                'toMonth': to_month,
                'toYear': to_year,
                'isOngoing': is_ongoing,
                'ongoingText': '',
            },
            'bullets': bullets or [],
            'showBullets': True,
            'showCompany': True,
            'showDateRange': True,
            'showDescription': False,
            'showLink': False,
            'showLocation': True,
            'showTitle': True,
            'table': {
                'record': 'TableItem',
                'cols': 2,
                'rows': [['<b>Project name</b>', '<b>Description</b>'], ['', '']]
            },
            'height': 243
        }
        
        exp_section['items'].append(exp_item)
    
    def update_skills(self, skill_groups: Dict[str, List[str]]):
        """Update skills section.
        
        Args:
            skill_groups: Dictionary mapping category names to lists of skills
                Example: {'Languages': ['Python', 'Java'], 'Frameworks': ['React', 'Django']}
        """
        if not self.data:
            self.extract_json_data()
        
        # Find or create technology section
        tech_section = None
        for section in self.data.get('sections', []):
            if section.get('__t') == 'TechnologySection':
                tech_section = section
                break
        
        if not tech_section:
            tech_section = {
                '__t': 'TechnologySection',
                'name': '',
                'record': 'TechnologySection',
                'enabled': True,
                'height': 36,
                'column': 1,
                'compactMode': False,
                'surroundingBorder': False,
                'items': []
            }
            self.data.setdefault('sections', []).append(tech_section)
        
        # Update items
        tech_section['items'] = []
        for title, tags in skill_groups.items():
            tech_item = {
                'id': f'skill_{len(tech_section["items"])}',
                'record': 'TechnologyItem',
                'title': title,
                'description': '',
                'tags': tags,
                'showTitle': False,
                'height': 163
            }
            tech_section['items'].append(tech_item)
    
    def save_pdf(self, output_path: Optional[str] = None, render_visual: bool = False):
        """Save the updated data back to PDF.
        
        Args:
            output_path: Output file path
            render_visual: If True, also render a new visual PDF (requires pdf_renderer)
        """
        if not self.data:
            raise ValueError("No data to save. Extract or update data first.")
        
        output_path = output_path or self.pdf_path
        
        try:
            # Read original PDF
            with open(self.pdf_path, 'rb') as f:
                pdf_content = f.read()
            
            # Convert updated data to JSON string
            json_str = json.dumps(self.data, ensure_ascii=False)
            
            # Encode as UTF-16-BE with BOM
            json_bytes = json_str.encode('utf-16-be')
            
            # Convert to hex with FEFF BOM prefix
            hex_data = 'FEFF' + json_bytes.hex().upper()
            
            # Format hex with spaces (every 2 characters)
            hex_formatted = ' '.join(hex_data[i:i+2] for i in range(0, len(hex_data), 2))
            
            # Replace the ecv-data field
            # Try multiple patterns to handle different formats
            patterns = [
                rb'/ecv-data\s*<FEFF[^>]+>',  # Standard format
                rb'/ecv-data\s*<FE\s*FF[^>]+>',  # Space-separated FE FF
            ]
            
            replacement = f'/ecv-data <{hex_formatted}>'.encode('ascii')
            new_content = pdf_content
            
            for pattern in patterns:
                if re.search(pattern, new_content):
                    new_content = re.sub(pattern, replacement, new_content)
                    break
            else:
                # If no pattern matched, try to find and replace manually
                # Find the position of /ecv-data
                pos = new_content.find(b'/ecv-data')
                if pos != -1:
                    # Find the end of the field (next >)
                    end_pos = new_content.find(b'>', pos)
                    if end_pos != -1:
                        # Replace the entire field
                        new_content = new_content[:pos] + replacement + new_content[end_pos+1:]
                    else:
                        raise ValueError("Could not find end of /ecv-data field")
                else:
                    raise ValueError("Could not find /ecv-data field in PDF")
            
            # Write updated PDF
            with open(output_path, 'wb') as f:
                f.write(new_content)
            
            print(f"Successfully saved updated PDF to: {output_path}")
            
            # Optionally render visual PDF
            if render_visual:
                try:
                    from pdf_renderer import PDFRenderer
                    visual_path = str(Path(output_path).with_suffix('.visual.pdf'))
                    
                    summary_for_render = ""
                    for section in self.data.get('sections', []):
                        if section.get('__t') == 'SummarySection':
                            if section.get('items'):
                                summary_for_render = section['items'][0].get('text', '')
                                break
                    
                    # CRITICAL: Make a deep copy to ensure renderer gets the exact data we have
                    import copy
                    data_for_renderer = copy.deepcopy(self.data)
                    
                    # CRITICAL: Pass self.data (which should have updates) to renderer
                    renderer = PDFRenderer(data_for_renderer)
                    
                    renderer.render_pdf(visual_path)
                    print(f"✅ Rendered visual PDF to: {visual_path}")
                except ImportError:
                    print("⚠️  Visual rendering not available. Install: pip install weasyprint")
                except Exception as e:
                    print(f"⚠️  Visual rendering failed: {e}")
                    import traceback
                    traceback.print_exc()
            
        except Exception as e:
            raise RuntimeError(f"Error saving PDF: {e}")
    
    def export_json(self, output_path: str):
        """Export the resume data as JSON for inspection."""
        if not self.data:
            self.extract_json_data()
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
        
        print(f"Exported JSON data to: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description='Update content in Enhancv PDF resumes',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze PDF structure
  python pdf_resume_updater.py resume.pdf --analyze
  
  # Export JSON data
  python pdf_resume_updater.py resume.pdf --export-json data.json
  
  # Update header
  python pdf_resume_updater.py resume.pdf --update-header --name "John Doe" --email "john@example.com"
  
  # Update summary
  python pdf_resume_updater.py resume.pdf --update-summary "New summary text here"
  
  # Add experience
  python pdf_resume_updater.py resume.pdf --add-experience \\
    --position "Senior Engineer" --company "Tech Corp" --location "San Francisco, CA" \\
    --from-month 1 --from-year 2020 --to-month 12 --to-year 2023 \\
    --bullets "Led team of 5" "Improved performance by 40%"
        """
    )
    
    parser.add_argument('pdf_path', help='Path to the PDF resume file')
    parser.add_argument('--output', '-o', help='Output PDF path (default: overwrite original)')
    parser.add_argument('--analyze', action='store_true', help='Analyze and display PDF structure')
    parser.add_argument('--export-json', metavar='FILE', help='Export JSON data to file')
    
    # Header updates
    header_group = parser.add_argument_group('Header Updates')
    header_group.add_argument('--update-header', action='store_true', help='Update header information')
    header_group.add_argument('--name', help='Full name')
    header_group.add_argument('--title', help='Job title')
    header_group.add_argument('--email', help='Email address')
    header_group.add_argument('--phone', help='Phone number')
    header_group.add_argument('--location', help='Location')
    header_group.add_argument('--link', help='LinkedIn/profile URL')
    
    # Summary update
    parser.add_argument('--update-summary', metavar='TEXT', help='Update summary section')
    
    # Experience
    exp_group = parser.add_argument_group('Add Experience')
    exp_group.add_argument('--add-experience', action='store_true', help='Add new experience entry')
    exp_group.add_argument('--position', help='Job position/title')
    exp_group.add_argument('--company', help='Company name')
    exp_group.add_argument('--exp-location', dest='exp_location', help='Job location')
    exp_group.add_argument('--from-month', type=int, help='Start month (1-12)')
    exp_group.add_argument('--from-year', type=int, help='Start year')
    exp_group.add_argument('--to-month', type=int, help='End month (1-12, optional)')
    exp_group.add_argument('--to-year', type=int, help='End year (optional)')
    exp_group.add_argument('--ongoing', action='store_true', help='Mark as ongoing position')
    exp_group.add_argument('--bullets', nargs='+', help='Bullet points for experience')
    
    args = parser.parse_args()
    
    try:
        updater = PDFResumeUpdater(args.pdf_path)
        
        # Analyze structure
        if args.analyze:
            structure = updater.analyze_structure()
            print("\n=== PDF Resume Structure ===\n")
            print(f"Header:")
            header = structure['header']
            print(f"  Name: {header.get('name', 'N/A')}")
            print(f"  Title: {header.get('title', 'N/A')}")
            print(f"  Email: {header.get('email', 'N/A')}")
            print(f"  Location: {header.get('location', 'N/A')}")
            print(f"\nSections ({len(structure['sections'])}):")
            for i, section in enumerate(structure['sections'], 1):
                print(f"  {i}. {section['type']} ({section['items_count']} items)")
            return
        
        # Export JSON
        if args.export_json:
            updater.export_json(args.export_json)
            return
        
        # Extract data first
        updater.extract_json_data()
        
        # Apply updates
        updated = False
        
        if args.update_header:
            updater.update_header(
                name=args.name,
                title=args.title,
                email=args.email,
                phone=args.phone,
                location=args.location,
                link=args.link
            )
            updated = True
        
        if args.update_summary:
            updater.update_summary(args.update_summary)
            updated = True
        
        if args.add_experience:
            if not all([args.position, args.company, args.exp_location, 
                       args.from_month, args.from_year]):
                parser.error("--add-experience requires --position, --company, "
                           "--exp-location, --from-month, and --from-year")
            
            updater.add_experience(
                position=args.position,
                company=args.company,
                location=args.exp_location,
                from_month=args.from_month,
                from_year=args.from_year,
                to_month=args.to_month,
                to_year=args.to_year,
                is_ongoing=args.ongoing,
                bullets=args.bullets or []
            )
            updated = True
        
        # Save if updated
        if updated:
            updater.save_pdf(args.output)
        else:
            print("No updates specified. Use --help for usage information.")
    
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
