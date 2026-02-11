# Job Organization Structure

## Overview

The Resume Customizer now automatically organizes all job applications into a structured folder system. This makes it easy to find and reference job descriptions and customized resumes when preparing for interviews.

## Folder Structure

Each job application is saved in its own folder with the following structure:

```
jobs/
  └── YYYY-MM-DD_HH-MM-SS_JobTitle/
      ├── job_description.txt          # Original job description
      ├── resume_customized.pdf         # Customized resume (data PDF)
      ├── resume_customized.visual.pdf  # Visual PDF (if generated)
      └── metadata.json                 # Job metadata (title, date, model, etc.)
```

### Example

```
jobs/
  └── 2026-02-10_17-30-45_Cloud_Solutions_Architect_II/
      ├── job_description.txt
      ├── resume_customized.pdf
      ├── resume_customized.visual.pdf
      └── metadata.json
```

## File Details

### `job_description.txt`
- Contains the original, unmodified job description text
- Saved exactly as entered in the GUI
- Useful for reviewing job requirements before interviews

### `resume_customized.pdf`
- The customized resume PDF with embedded JSON data
- Contains all the tailored content (summary, experience, skills, projects)
- This is the file you should submit with your application

### `resume_customized.visual.pdf`
- Visual representation of the resume
- Generated automatically when customization completes
- Useful for previewing how the resume looks

### `metadata.json`
Contains information about the customization:
```json
{
  "job_title": "Cloud Solutions Architect II",
  "timestamp": "2026-02-10_17-30-45",
  "date": "2026-02-10T17:30:45.123456",
  "model_used": "gpt-4o-mini",
  "resume_source": "/path/to/original/resume.pdf",
  "visual_resume_source": "/path/to/visual.pdf"
}
```

## How It Works

1. **Dual Save System**: When you customize a resume, the system saves files in TWO locations:
   - **Root Directory**: Quick access files (same directory as your original resume)
     - `resume_customized.pdf` - Your customized resume
     - `resume_customized.visual.pdf` - Visual preview
   - **Jobs Folder**: Organized archive (for interview preparation)
     - Complete folder structure with all files

2. **Automatic Organization**: The system automatically:
   - Saves customized resume to root directory first (for quick access)
   - Extracts the job title from the job description
   - Creates a timestamped folder in the `jobs/` directory
   - Copies all files to the organized location (original files remain in root)

3. **Job Title Extraction**: The system looks for common patterns in job descriptions:
   - `JOB TITLE: ...`
   - `Position: ...`
   - `Title: ...`
   - `Role: ...`
   - Or uses the first line if no pattern is found

4. **Folder Naming**: Folders are named with:
   - Timestamp: `YYYY-MM-DD_HH-MM-SS`
   - Job Title: Extracted and sanitized (special characters removed)
   - Format: `YYYY-MM-DD_HH-MM-SS_JobTitle`

## Benefits

1. **Quick Access**: Latest customized resume always in root directory for immediate use
2. **Easy Reference**: All files for each job are organized in one place
3. **Interview Preparation**: Quickly find the job description and your customized resume
4. **Organization**: Chronological ordering makes it easy to track applications
5. **Metadata Tracking**: Know which model was used and when the customization was done
6. **No Data Loss**: Original files remain in root, copies are made to jobs folder

## Location

The `jobs/` folder is created in the same directory as your original resume PDF. For example:
- If your resume is at: `/path/to/resume.pdf`
- Jobs will be saved to: `/path/to/jobs/`

## Manual Access

You can manually browse the `jobs/` folder to:
- Review previous applications
- Copy resumes for new applications
- Check job descriptions before interviews
- Review customization history

## Notes

- The `jobs/` folder is created automatically on first use
- Each customization creates a new folder (even for the same job)
- **Root directory files**: Customized resume is saved in the root directory (same location as your original resume) for quick access
- **Jobs folder files**: Copies are made to the jobs folder for organization - original root files remain untouched
- You can safely delete files from either location without affecting the other
- The root directory always has your latest customized resume ready to use
