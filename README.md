# Nova Job Tool - AI-Powered Resume Customizer

An intelligent resume customization tool that uses OpenAI's GPT models to tailor your resume content to match specific job descriptions. Perfect for job seekers who want to optimize their resumes for ATS (Applicant Tracking Systems) and increase their chances of landing interviews.

## Features

- 🤖 **AI-Powered Customization**: Uses OpenAI GPT models to customize resume content
- 📄 **PDF Resume Support**: Works with Enhancv-generated PDF resumes
- 🎨 **PyQt6 GUI**: User-friendly graphical interface
- ✨ **Multi-Section Customization**: 
  - Summary/Professional Summary
  - Work Experience (all entries)
  - Projects/Activities
  - Skills/Technologies
- 🔍 **Smart Matching**: Advanced word-based similarity matching for experience entries
- 📊 **Section Recognition**: Automatically recognizes all resume sections
- 🎯 **Job Description Matching**: Tailors content to match job requirements exactly

## Requirements

- Python 3.7 or higher
- OpenAI API key
- PyQt6
- WeasyPrint (for PDF rendering)
- Other dependencies (see `requirements.txt`)

## Installation

### Option 1: Using the installation script

```bash
chmod +x install_gui.sh
./install_gui.sh
```

### Option 2: Manual installation

```bash
pip install -r requirements.txt
```

## Usage

### GUI Application

1. **Launch the GUI:**
   ```bash
   ./launch_gui.sh
   ```
   Or:
   ```bash
   python3 resume_customizer_gui.py
   ```

2. **Set your OpenAI API key:**
   - Enter your API key in the GUI, or
   - Set it as an environment variable:
     ```bash
     export OPENAI_API_KEY="your-api-key-here"
     ```

3. **Load your resume PDF:**
   - Click "Browse" to select your Enhancv-generated PDF resume

4. **Enter job description:**
   - Paste the job description in the text area, or
   - Click "Load from File" to load from a text file

5. **Select customization options:**
   - ✅ Customize Summary
   - ✅ Customize Experience
   - ✅ Customize Projects
   - ✅ Prioritize Skills

6. **Choose OpenAI model:**
   - `gpt-4o-mini` (recommended, cost-effective)
   - `gpt-4o` (higher quality)
   - `gpt-4` (best quality)
   - `gpt-3.5-turbo` (fastest, lower cost)

7. **Click "Customize Resume"** and wait for the process to complete

8. **Save your customized resume:**
   - The customized PDF will be saved as `result.pdf`
   - A visual PDF will be saved as `result.visual.pdf`

### Command Line Usage

```bash
python3 resume_customizer.py \
  --pdf-path your_resume.pdf \
  --job-description "job_description.txt" \
  --api-key "your-api-key" \
  --output result.pdf
```

## Supported Resume Sections

The tool recognizes and can customize the following sections:

1. **SummarySection** - Professional summary
2. **ExperienceSection** - Work experience entries
3. **EducationSection** - Education details (preserved, not customized)
4. **TechnologySection** - Skills and technologies
5. **ActivitySection** - Projects and activities
6. **LanguageSection** - Languages
7. **CertificateSection** - Certifications

## How It Works

1. **Extracts** embedded JSON data from Enhancv PDF resumes
2. **Analyzes** the job description to identify key requirements
3. **Customizes** resume sections using OpenAI GPT models:
   - Rewrites summary to match job requirements
   - Enhances experience bullet points with relevant keywords
   - Customizes project descriptions
   - Prioritizes and reorganizes skills
4. **Preserves** important information:
   - Company names
   - Job titles
   - Dates and periods
   - Education details
5. **Renders** a new visual PDF with customized content

## Features in Detail

### Smart Experience Matching

- Handles special characters (en dash, ampersand, etc.)
- Word-based similarity matching
- Fuzzy matching for variations in job titles
- Preserves original company names and dates

### Project Detection

- Automatically detects projects in ActivitySection
- Customizes project descriptions and bullet points
- Matches projects to job requirements

### Skills Prioritization

- Reorganizes skills based on job requirements
- Groups related skills together
- Highlights most relevant technologies

## File Structure

```
.
├── resume_customizer.py          # Main customization logic
├── resume_customizer_gui.py      # PyQt6 GUI application
├── pdf_resume_updater.py         # PDF parsing and updating
├── pdf_renderer.py               # Visual PDF rendering
├── requirements.txt              # Python dependencies
├── install_gui.sh                # Installation script
├── launch_gui.sh                 # Launch script
├── README.md                     # This file
├── MarAngeloPolicarpioMarquezResume.pdf  # Example resume
└── sharesource_job.txt           # Example job description
```

## Configuration

### Environment Variables

- `OPENAI_API_KEY`: Your OpenAI API key (optional if entered in GUI)

### Settings

The GUI saves your preferences:
- Last used PDF path
- Last used API key (if saved)
- Customization options

## Troubleshooting

### API Key Issues

- Ensure your API key is exactly 164 characters
- API key should start with `sk-proj-` or `sk-`
- Check that you have sufficient API credits

### PDF Issues

- Only works with Enhancv-generated PDFs
- Ensure the PDF contains embedded JSON data in `/ecv-data` field
- Try reopening the PDF in a different viewer if changes aren't visible

### Matching Issues

- If experience entries aren't matching, check the logs for details
- The tool uses word-based matching, so slight variations should work
- Special characters are automatically normalized

## Logging

Logs are saved to `resume_customizer_gui.log` for debugging. Check this file if you encounter issues.

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## License

This project is open source and available for use.

## Acknowledgments

- Built with OpenAI GPT models
- Uses PyQt6 for the GUI
- Uses WeasyPrint for PDF rendering
- Designed for Enhancv PDF format

## Support

For issues or questions, please open an issue on GitHub.

---

**Note**: This tool requires an active OpenAI API key with sufficient credits. API usage will incur costs based on the model selected and the amount of content customized.
