#!/usr/bin/env python3
"""
Resume Customizer GUI Application

A PyQt6-based graphical interface for customizing resumes based on job descriptions.
Rebuilt from scratch to ensure proper separation of API key and job description.
"""

import sys
import os
import platform
from pathlib import Path
from typing import Optional
from datetime import datetime

try:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QPushButton, QTextEdit, QFileDialog, QLineEdit, QCheckBox,
        QGroupBox, QProgressBar, QMessageBox, QComboBox
    )
    from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSettings
    from PyQt6.QtGui import QFont
except ImportError:
    print("Error: PyQt6 not installed. Install with: pip install PyQt6")
    sys.exit(1)

from resume_customizer import ResumeCustomizer, clean_text, organize_job_files, sanitize_windows_filename, sanitize_windows_path, setup_windows_console


# Windows EXE compatibility: Detect if running as frozen executable
def get_base_path():
    """Get the base path for the application, handling both script and frozen EXE."""
    if getattr(sys, 'frozen', False):
        # Running as compiled executable (PyInstaller, cx_Freeze, etc.)
        if hasattr(sys, '_MEIPASS'):
            # PyInstaller
            base_path = Path(sys.executable).parent
        else:
            # cx_Freeze or other
            base_path = Path(sys.executable).parent
    else:
        # Running as script
        base_path = Path(__file__).parent
    return base_path


class CustomizationWorker(QThread):
    """Worker thread for running customization to avoid freezing UI."""
    
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)
    
    def __init__(self, pdf_path: str, job_description: str, api_key: str,
                 customize_summary: bool, customize_experience: bool,
                 customize_skills: bool, model: str, original_job_description: str = None):
        super().__init__()
        self.pdf_path = pdf_path
        self.job_description = job_description
        self.original_job_description = original_job_description or job_description
        self.api_key = api_key
        self.customize_summary = customize_summary
        self.customize_experience = customize_experience
        self.customize_skills = customize_skills
        self.model = model
    
    def run(self):
        try:
            # Clean job description
            self.job_description = clean_text(self.job_description)
            
            # Clean API key
            self.api_key = clean_text(self.api_key)
            
            # Validate API key
            if not self.api_key or len(self.api_key) != 164:
                raise ValueError(f"Invalid API key length: {len(self.api_key) if self.api_key else 0} (expected 164)")
            
            if not self.api_key.startswith('sk-'):
                raise ValueError("Invalid API key format: must start with 'sk-'")
            
            self.progress.emit("Initializing customizer...")
            customizer = ResumeCustomizer(self.pdf_path, api_key=self.api_key)
            
            self.progress.emit("Customizing resume content...")
            updates = customizer.customize_for_job(
                self.job_description,
                customize_summary=self.customize_summary,
                customize_experience=self.customize_experience,
                customize_skills=self.customize_skills,
                customize_projects=True,  # Always customize projects
                model=self.model
            )
            
            self.progress.emit("Applying updates...")
            customizer.apply_updates(updates)
            
            self.progress.emit("Customization complete!")
            self.finished.emit({
                'customizer': customizer,
                'updates': updates,
                'original_job_description': self.original_job_description,
                'model': self.model
            })
            
        except Exception as e:
            self.error.emit(str(e))


class ResumeCustomizerGUI(QMainWindow):
    """Main GUI window for Resume Customizer."""
    
    def __init__(self):
        super().__init__()
        self.settings = QSettings('ResumeCustomizer', 'App')
        self.customizer = None
        self.worker = None
        self.init_ui()
        self.load_settings()
    
    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("Resume Customizer - AI-Powered Resume Tailoring")
        self.setGeometry(100, 100, 900, 700)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)
        
        # Title
        title = QLabel("Resume Customizer")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title)
        
        subtitle = QLabel("Customize your resume to match job descriptions using AI")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: #666; margin-bottom: 10px;")
        main_layout.addWidget(subtitle)
        
        # API Key Section
        api_group = self.create_api_key_group()
        main_layout.addWidget(api_group)
        
        # File Selection Section
        file_group = self.create_file_selection_group()
        main_layout.addWidget(file_group)
        
        # Job Description Section
        job_desc_group = self.create_job_description_group()
        main_layout.addWidget(job_desc_group)
        
        # Options Section
        options_group = self.create_options_group()
        main_layout.addWidget(options_group)
        
        # Control Buttons
        button_layout = QHBoxLayout()
        self.customize_btn = QPushButton("Customize Resume")
        self.customize_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px; font-size: 14px;")
        self.customize_btn.clicked.connect(self.start_customization)
        button_layout.addWidget(self.customize_btn)
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self.cancel_customization)
        button_layout.addWidget(self.cancel_btn)
        
        main_layout.addLayout(button_layout)
        
        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)
        
        # Status Label
        self.status_label = QLabel("Ready")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.status_label)
        
        self.statusBar().showMessage("Ready")
    
    def create_api_key_group(self):
        """Create API key input group."""
        group = QGroupBox("OpenAI API Key")
        layout = QVBoxLayout()
        
        api_layout = QHBoxLayout()
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setPlaceholderText("Enter your OpenAI API key (164 characters, starts with 'sk-proj-')")
        api_layout.addWidget(self.api_key_input)
        
        load_env_btn = QPushButton("Load from Env")
        load_env_btn.clicked.connect(self.load_api_key_from_env)
        api_layout.addWidget(load_env_btn)
        
        layout.addLayout(api_layout)
        
        if os.getenv('OPENAI_API_KEY'):
            self.api_key_input.setText(os.getenv('OPENAI_API_KEY'))
            self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        
        group.setLayout(layout)
        return group
    
    def create_file_selection_group(self):
        """Create file selection group."""
        group = QGroupBox("Resume PDF File")
        layout = QVBoxLayout()
        
        file_layout = QHBoxLayout()
        self.pdf_path_input = QLineEdit()
        self.pdf_path_input.setPlaceholderText("Select resume PDF file...")
        file_layout.addWidget(self.pdf_path_input)
        
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self.browse_pdf_file)
        file_layout.addWidget(browse_btn)
        
        layout.addLayout(file_layout)
        
        output_layout = QHBoxLayout()
        self.output_path_input = QLineEdit()
        self.output_path_input.setPlaceholderText("Output file path (optional)")
        output_layout.addWidget(self.output_path_input)
        
        output_browse_btn = QPushButton("Browse")
        output_browse_btn.clicked.connect(self.browse_output_file)
        output_layout.addWidget(output_browse_btn)
        
        layout.addLayout(output_layout)
        group.setLayout(layout)
        return group
    
    def create_job_description_group(self):
        """Create job description input group."""
        group = QGroupBox("Job Description")
        layout = QVBoxLayout()
        
        file_layout = QHBoxLayout()
        load_file_btn = QPushButton("Load from File")
        load_file_btn.clicked.connect(self.load_job_description_file)
        file_layout.addWidget(load_file_btn)
        file_layout.addStretch()
        layout.addLayout(file_layout)
        
        self.job_desc_text = QTextEdit()
        # CRITICAL: Set to accept plain text only (no HTML/rich text)
        self.job_desc_text.setAcceptRichText(False)
        self.job_desc_text.setPlaceholderText(
            "Paste the job description here, or load from a file...\n\n"
            "Include:\n"
            "- Job title and requirements\n"
            "- Required skills and technologies\n"
            "- Responsibilities and qualifications"
        )
        self.job_desc_text.setMinimumHeight(150)
        layout.addWidget(self.job_desc_text)
        
        group.setLayout(layout)
        return group
    
    def create_options_group(self):
        """Create customization options group."""
        group = QGroupBox("Customization Options")
        layout = QVBoxLayout()
        
        options_layout = QHBoxLayout()
        self.summary_check = QCheckBox("Customize Summary")
        self.summary_check.setChecked(True)
        options_layout.addWidget(self.summary_check)
        
        self.experience_check = QCheckBox("Customize Experience")
        self.experience_check.setChecked(True)
        options_layout.addWidget(self.experience_check)
        
        self.skills_check = QCheckBox("Prioritize Skills")
        self.skills_check.setChecked(True)
        options_layout.addWidget(self.skills_check)
        
        layout.addLayout(options_layout)
        
        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("Model:"))
        self.model_combo = QComboBox()
        self.model_combo.addItems(["gpt-4o-mini", "gpt-4o", "gpt-4", "gpt-3.5-turbo"])
        self.model_combo.setCurrentText("gpt-4o-mini")
        model_layout.addWidget(self.model_combo)
        model_layout.addStretch()
        layout.addLayout(model_layout)
        
        group.setLayout(layout)
        return group
    
    def load_api_key_from_env(self):
        """Load API key from environment variable."""
        api_key = os.getenv('OPENAI_API_KEY')
        if api_key:
            self.api_key_input.setText(api_key)
            self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
            QMessageBox.information(self, "Success", "API key loaded from environment variable")
        else:
            QMessageBox.warning(self, "Not Found", "OPENAI_API_KEY environment variable not set")
    
    def browse_pdf_file(self):
        """Browse for PDF file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Resume PDF",
            "",
            "PDF Files (*.pdf);;All Files (*)"
        )
        if file_path:
            self.pdf_path_input.setText(file_path)
            if not self.output_path_input.text():
                base = Path(file_path).stem
                output_dir = Path(file_path).parent
                self.output_path_input.setText(str(output_dir / f"{base}_customized.pdf"))
    
    def load_job_description_file(self):
        """Load job description from file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Job Description",
            "",
            "Text Files (*.txt);;All Files (*)"
        )
        if file_path:
            try:
                # Try UTF-8 first, then fallback to latin-1
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                except UnicodeDecodeError:
                    with open(file_path, 'r', encoding='latin-1') as f:
                        content = f.read()
                
                # Clean the content and set it
                cleaned_content = clean_text(content)
                self.job_desc_text.setPlainText(cleaned_content)
                
                # Show success with file info
                file_size = len(content)
                QMessageBox.information(
                    self, 
                    "Success", 
                    f"Loaded job description from {Path(file_path).name}\n\n"
                    f"File size: {file_size} characters\n"
                    f"After cleaning: {len(cleaned_content)} characters"
                )
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load file: {e}")
    
    def browse_output_file(self):
        """Browse for output file location."""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Customized Resume",
            "",
            "PDF Files (*.pdf);;All Files (*)"
        )
        if file_path:
            if not file_path.endswith('.pdf'):
                file_path += '.pdf'
            self.output_path_input.setText(file_path)
    
    def validate_inputs(self):
        """Validate user inputs."""
        if not self.api_key_input.text().strip():
            QMessageBox.warning(self, "Missing API Key", "Please enter your OpenAI API key")
            return False
        
        if not self.pdf_path_input.text().strip():
            QMessageBox.warning(self, "Missing PDF", "Please select a resume PDF file")
            return False
        
        if not Path(self.pdf_path_input.text()).exists():
            QMessageBox.warning(self, "File Not Found", "The selected PDF file does not exist")
            return False
        
        if not self.job_desc_text.toPlainText().strip():
            QMessageBox.warning(self, "Missing Job Description", "Please enter or load a job description")
            return False
        
        if not any([self.summary_check.isChecked(), 
                   self.experience_check.isChecked(), 
                   self.skills_check.isChecked()]):
            QMessageBox.warning(self, "No Options Selected", "Please select at least one customization option")
            return False
        
        return True
    
    def start_customization(self):
        """Start the customization process."""
        if not self.validate_inputs():
            return
        
        # Disable UI
        self.customize_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.status_label.setText("Starting customization...")
        
        # CRITICAL: Extract job description from QTextEdit (multi-line text area)
        # Use toPlainText() to get plain text (no HTML formatting)
        raw_job_description = self.job_desc_text.toPlainText()
        
        # Strip whitespace
        raw_job_description = raw_job_description.strip()
        
        # Clean the job description
        cleaned_job_description = clean_text(raw_job_description)
        
        # Validate job description is not empty
        if not cleaned_job_description:
            QMessageBox.critical(
                self,
                "Job Description Error",
                "The job description is empty after cleaning. Please check the content."
            )
            self.customize_btn.setEnabled(True)
            self.cancel_btn.setEnabled(False)
            self.progress_bar.setVisible(False)
            return
        
        # CRITICAL: Extract API key from QLineEdit (single-line input)
        raw_api_key = self.api_key_input.text().strip()
        
        # Auto-fix: If API key field is too long, extract just the first 164 chars if valid
        if len(raw_api_key) > 200:
            if raw_api_key.startswith('sk-'):
                potential_key = raw_api_key[:164]
                if len(potential_key) == 164:
                    raw_api_key = potential_key
                    self.api_key_input.setText(raw_api_key)
                    QMessageBox.warning(
                        self,
                        "API Key Auto-Fixed",
                        "The API key field contained extra text. I've extracted just the API key portion.\n\nPlease verify it's correct."
                    )
                else:
                    QMessageBox.critical(
                        self,
                        "API Key Error",
                        f"The API key field contains invalid data (length: {len(raw_api_key)}).\n\n"
                        f"Please clear the 'API Key' field and enter only your OpenAI API key.\n\n"
                        f"The API key should be exactly 164 characters starting with 'sk-proj-'."
                    )
                    self.customize_btn.setEnabled(True)
                    self.cancel_btn.setEnabled(False)
                    self.progress_bar.setVisible(False)
                    return
            else:
                QMessageBox.critical(
                    self,
                    "API Key Error",
                    f"The API key field contains invalid data (length: {len(raw_api_key)}).\n\n"
                    f"Please clear the 'API Key' field and enter only your OpenAI API key.\n\n"
                    f"The API key should start with 'sk-proj-'."
                )
                self.customize_btn.setEnabled(True)
                self.cancel_btn.setEnabled(False)
                self.progress_bar.setVisible(False)
                return
        
        # Clean and validate API key
        cleaned_api_key = clean_text(raw_api_key)
        
        if not cleaned_api_key:
            QMessageBox.critical(self, "API Key Error", "API key is empty.")
            self.customize_btn.setEnabled(True)
            self.cancel_btn.setEnabled(False)
            self.progress_bar.setVisible(False)
            return
        
        if not cleaned_api_key.startswith('sk-'):
            QMessageBox.critical(
                self,
                "API Key Error",
                f"Invalid API key format. API key should start with 'sk-'.\n\n"
                f"First 20 chars: {repr(cleaned_api_key[:20])}"
            )
            self.customize_btn.setEnabled(True)
            self.cancel_btn.setEnabled(False)
            self.progress_bar.setVisible(False)
            return
        
        if len(cleaned_api_key) != 164:
            QMessageBox.critical(
                self,
                "API Key Error",
                f"Invalid API key length: {len(cleaned_api_key)} (expected 164).\n\n"
                f"Please verify the API key is correct."
            )
            self.customize_btn.setEnabled(True)
            self.cancel_btn.setEnabled(False)
            self.progress_bar.setVisible(False)
            return
        
        # Get checkbox states
        customize_summary = self.summary_check.isChecked()
        customize_experience = self.experience_check.isChecked()
        customize_skills = self.skills_check.isChecked()
        
        # Create worker with validated parameters
        self.worker = CustomizationWorker(
            pdf_path=self.pdf_path_input.text(),
            job_description=cleaned_job_description,
            api_key=cleaned_api_key,
            customize_summary=customize_summary,
            customize_experience=customize_experience,
            customize_skills=customize_skills,
            model=self.model_combo.currentText(),
            original_job_description=raw_job_description  # Store original for saving
        )
        
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.customization_complete)
        self.worker.error.connect(self.customization_error)
        
        self.worker.start()
    
    def update_progress(self, message: str):
        """Update progress message."""
        self.status_label.setText(message)
        self.statusBar().showMessage(message)
    
    def customization_complete(self, result: dict):
        """Handle successful customization."""
        self.customizer = result['customizer']
        updates = result.get('updates', {})
        original_job_description = result.get('original_job_description', '')
        model = result.get('model', 'gpt-4o-mini')
        
        self.progress_bar.setVisible(False)
        self.customize_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.status_label.setText("Customization complete! Saving files...")
        
        # Determine output path (Windows compatible)
        output_path = self.output_path_input.text().strip()
        if not output_path:
            base = Path(self.pdf_path_input.text()).stem
            output_dir = Path(self.pdf_path_input.text()).parent
            output_path = str(output_dir / f"{base}_customized.pdf")
        
        # Sanitize output path for Windows
        output_path_obj = sanitize_windows_path(Path(output_path))
        output_path = str(output_path_obj)
        
        try:
            # Step 1: Save customized resume to ROOT directory (quick access)
            visual_pdf_path, visual_error = self.customizer.save_customized_resume(
                output_path,
                render_visual=True
            )
            # Use returned path; if save_pdf failed to create visual, path may be None
            if visual_pdf_path and not Path(visual_pdf_path).exists():
                visual_pdf_path = None
            
            # Step 2: Also organize files into jobs/ folder structure (archive)
            base_dir = Path(self.pdf_path_input.text()).parent
            organized = organize_job_files(
                job_description=original_job_description,
                resume_pdf_path=output_path,
                visual_pdf_path=visual_pdf_path,
                model=model,
                base_dir=base_dir
            )
            
            # Show success message with both locations
            message = (
                f"✅ Customized resume saved to ROOT directory:\n"
                f"   {output_path}\n"
            )
            if visual_pdf_path:
                message += f"   {visual_pdf_path}\n"
            if visual_error:
                message += f"\n⚠️ Visual PDF: {visual_error}\n"
            message += (
                f"\n📁 Files also organized in JOBS folder:\n"
                f"   {organized['folder']}\n\n"
                f"Saved files in jobs folder:\n"
                f"  • Job description: {Path(organized['job_description']).name}\n"
                f"  • Resume: {Path(organized['resume']).name}\n"
            )
            if 'visual_resume' in organized:
                message += f"  • Visual resume: {Path(organized['visual_resume']).name}\n"
            message += f"  • Metadata: {Path(organized['metadata']).name}"
            
            QMessageBox.information(
                self,
                "Success",
                message
            )
            self.save_settings()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save resume: {e}")
    
    def customization_error(self, error: str):
        """Handle customization error."""
        self.progress_bar.setVisible(False)
        self.customize_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.status_label.setText("Error occurred")
        QMessageBox.critical(self, "Customization Error", f"An error occurred:\n\n{error}")
    
    def cancel_customization(self):
        """Cancel ongoing customization."""
        if self.worker and self.worker.isRunning():
            self.worker.terminate()
            self.worker.wait()
        
        self.progress_bar.setVisible(False)
        self.customize_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.status_label.setText("Cancelled")
        self.statusBar().showMessage("Ready")
    
    def save_settings(self):
        """Save application settings."""
        self.settings.setValue('api_key', self.api_key_input.text())
        self.settings.setValue('last_pdf_path', self.pdf_path_input.text())
        self.settings.setValue('model', self.model_combo.currentText())
        self.settings.setValue('customize_summary', self.summary_check.isChecked())
        self.settings.setValue('customize_experience', self.experience_check.isChecked())
        self.settings.setValue('customize_skills', self.skills_check.isChecked())
    
    def load_settings(self):
        """Load application settings."""
        api_key = self.settings.value('api_key', '')
        if api_key:
            self.api_key_input.setText(api_key)
        
        last_pdf = self.settings.value('last_pdf_path', '')
        if last_pdf and Path(last_pdf).exists():
            self.pdf_path_input.setText(last_pdf)
        
        model = self.settings.value('model', 'gpt-4o-mini')
        if model:
            index = self.model_combo.findText(model)
            if index >= 0:
                self.model_combo.setCurrentIndex(index)
        
        self.summary_check.setChecked(self.settings.value('customize_summary', True, type=bool))
        self.experience_check.setChecked(self.settings.value('customize_experience', True, type=bool))
        self.skills_check.setChecked(self.settings.value('customize_skills', True, type=bool))
    
    def closeEvent(self, event):
        """Handle window close event."""
        self.save_settings()
        if self.worker and self.worker.isRunning():
            self.worker.terminate()
            self.worker.wait()
        event.accept()


def main():
    """Main entry point."""
    # Setup Windows console for UTF-8 if needed
    setup_windows_console()
    # Force UTF-8 for print() so paths/messages with Unicode don't raise charmap errors on Windows
    if sys.platform == 'win32':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
            sys.stderr.reconfigure(encoding='utf-8')
        except (AttributeError, OSError):
            pass
    
    app = QApplication(sys.argv)
    window = ResumeCustomizerGUI()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
