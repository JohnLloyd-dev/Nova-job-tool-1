#!/usr/bin/env python3
"""Check if a customized PDF actually has changes."""

import sys
from pdf_resume_updater import PDFResumeUpdater

if len(sys.argv) < 2:
    print("Usage: python3 check_customization.py <original.pdf> <customized.pdf>")
    sys.exit(1)

original_path = sys.argv[1]
customized_path = sys.argv[2]

print("=" * 70)
print(f"COMPARING: {original_path} vs {customized_path}")
print("=" * 70)

original = PDFResumeUpdater(original_path)
orig_data = original.extract_json_data()

customized = PDFResumeUpdater(customized_path)
cust_data = customized.extract_json_data()

# Compare summary
orig_summary = ""
cust_summary = ""
for section in orig_data.get('sections', []):
    if section.get('__t') == 'SummarySection':
        if section.get('items'):
            orig_summary = section['items'][0].get('text', '')
            break

for section in cust_data.get('sections', []):
    if section.get('__t') == 'SummarySection':
        if section.get('items'):
            cust_summary = section['items'][0].get('text', '')
            break

print("\n[FILE] SUMMARY COMPARISON:")
print("-" * 70)
print(f"Original: {orig_summary[:150]}...")
print(f"\nCustomized: {cust_summary[:150]}...")
print(f"\nChanged: {orig_summary != cust_summary}")

# Compare experience
print("\n\n[FILE] EXPERIENCE COMPARISON (First Job, First Bullet):")
print("-" * 70)
orig_bullet = ""
cust_bullet = ""
for section in orig_data.get('sections', []):
    if section.get('__t') == 'ExperienceSection':
        if section.get('items') and section['items'][0].get('bullets'):
            orig_bullet = section['items'][0]['bullets'][0]
            break

for section in cust_data.get('sections', []):
    if section.get('__t') == 'ExperienceSection':
        if section.get('items') and section['items'][0].get('bullets'):
            cust_bullet = section['items'][0]['bullets'][0]
            break

print(f"Original: {orig_bullet[:150]}...")
print(f"\nCustomized: {cust_bullet[:150]}...")
print(f"\nChanged: {orig_bullet != cust_bullet}")

# Skills count
orig_skills = []
cust_skills = []
for section in orig_data.get('sections', []):
    if section.get('__t') == 'TechnologySection':
        for item in section.get('items', []):
            orig_skills.extend(item.get('tags', []))
        break

for section in cust_data.get('sections', []):
    if section.get('__t') == 'TechnologySection':
        for item in section.get('items', []):
            cust_skills.extend(item.get('tags', []))
        break

print("\n\n[FILE] SKILLS COMPARISON:")
print("-" * 70)
print(f"Original: {len(orig_skills)} skills")
print(f"Customized: {len(cust_skills)} skills")
print(f"Changed: {len(orig_skills) != len(cust_skills) or set(orig_skills) != set(cust_skills)}")

print("\n" + "=" * 70)
if orig_summary != cust_summary or orig_bullet != cust_bullet:
    print("✅ CUSTOMIZATION WAS APPLIED - Changes are in the PDF!")
    print("\nIf you don't see changes in PDF viewer:")
    print("  1. Close and reopen the PDF file")
    print("  2. Try a different PDF viewer (Adobe Reader, Chrome, etc.)")
    print("  3. Clear PDF viewer cache")
else:
    print("❌ NO CHANGES DETECTED - Customization may not have been applied")
print("=" * 70)
