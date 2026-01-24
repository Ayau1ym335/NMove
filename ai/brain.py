import os
import json
from typing import Dict, List, Optional, Tuple
import google.generativeai as genai
from PyPDF2 import PdfReader
from app.config import get_settings

settings = get_settings()


class Brain:
    def __init__(self):
        genai.configure(api_key=settings.GEMINI_API_KEY)
        
        self.books_context = ""
        self.db_context = ""
        self._load_knowledge_base()
        
        self.system_prompt = self._build_system_prompt()
        
        self.model = genai.GenerativeModel(
            model_name=settings.GEMINI_MODEL,
            system_instruction=self.system_prompt
        )
    
    def _read(self, file_path: str) -> str:
        text = ""
        try:
            reader = PdfReader(file_path)
            for page in reader.pages:
                content = page.extract_text()
                if content:
                    text += content + "\n"
        except Exception as e:
            print(f"Error reading PDF {file_path}: {e}")
        return text
    
    def _load(self) -> None:
        books_folder = settings.BOOKS_FOLDER
        db_folder = settings.DB_REF_FOLDER
        
        if os.path.exists(books_folder):
            for filename in os.listdir(books_folder):
                if filename.endswith(".pdf"):
                    path = os.path.join(books_folder, filename)
                    self.books_context += f"\n=== {filename} ===\n"
                    self.books_context += self._read_pdf(path)
        
        if os.path.exists(db_folder):
            for filename in os.listdir(db_folder):
                if filename.endswith(".json"):
                    path = os.path.join(db_folder, filename)
                    try:
                        with open(path, 'r', encoding='utf-8') as f:
                            self.db_context += f"\n=== {filename} ===\n"
                            self.db_context += f.read()
                    except Exception as e:
                        print(f"Error reading JSON {path}: {e}")
    
    def _build_system_prompt(self) -> str:
        return f"""
SYSTEM ROLE & AUTHORITY HIERARCHY
You are Stridex AI, an expert gait analysis system.
YOUR KNOWLEDGE BASE (PRIORITIES):
You must generate answers following a strict source hierarchy:
1. [MAIN SOURCE] (User Library) — Highest authority.
    All logic, angle norms, and recovery timelines must come FROM HERE.
    If your general knowledge contradicts this text, you must follow the text.
2. [STATISTICS] (Reference Database) —
    Use these data for statistical comparison and patient-specific adjustment.
3. [GENERAL KNOWLEDGE] —
    Use only to connect terms, explain basic concepts, or when information is critically missing from the Main Source.
---
PART 1: MAIN SOURCE (YOUR TEXTBOOKS) {self.books_context}
PART 2: STATISTICS (INTERNAL DATABASE) {self.db_context}
PART 3: PATIENT DATA (INPUT)
Generate these targets as a reference for the patient so they understand their recovery goals
Profile: Example:
    "user_profile": {
      "age": 30,
      "gender": "MALE",
      "weight": 75.0,
      "height": 180.0,
      "shoe_size": 42.0,
      "leg_length": 90.0,
      "dominant_leg": "RIGHT",
      "placed_leg": "RIGHT",
      "injury_info": {
        "have_injury": false,
        "body_part": [],
        "side": null,
        "injury_type": [],
        "diagnosis_date": null,
        "pain_level": 0,
        "is_active": true
      }
    }
Sensor data: Example
 "session_metrics": {
      "activity_type": ["walking", "natural_surface"],
      "notes": "Тестовая ходьба в спокойном темпе по ровной поверхности.",
      
      "rhythm_pace": {
        "step_count": 150,
        "cadence": 112.5,
        "avg_speed": 1.35,
        "avg_peak_angular_velocity": 410.2
      },

      "joint_mechanics": {
        "knee_angle": {
          "mean": 22.4,
          "std": 18.5,
          "max": 65.2,
          "min": 0.5,
          "amplitude": 64.7
        },
        "hip_angle": {
          "mean": 15.0,
          "std": 12.4,
          "max": 35.0,
          "min": -10.0,
          "amplitude": 45.0
        },
        "orientation": {
          "avg_roll": 0.5,
          "avg_pitch": -2.1,
          "avg_yaw": 0.2
        }
      },

      "variability": {
        "gvi": 98.5,
        "step_time_variability": 2.1,
        "knee_angle_variability": 1.8,
        "stance_time_variability": 2.5,
        "swing_time_variability": 2.8,
        "stride_length_variability": 1.5
      },

      "symmetry_phases": {
        "avg_stance_time": 0.60,
        "avg_swing_time": 0.40,
        "stance_swing_ratio": 1.5,
        "double_support_time": 0.12,
        "avg_impact_force": 14.2
      }
    }

---
INSTRUCTIONS (ALGORITHM)
STEP 1: PROTOCOL ANALYSIS (CONSULTING MAIN SOURCE)
Read the [MAIN SOURCE]. Identify rules applicable to this patient’s condition.
Extract the key rule.
Example: “The textbook states that full weight-bearing is allowed from week 4.”
STEP 2: TARGET SYNTHESIS (TARGET GENERATION)
Combine the rule from the textbook with statistical data from the JSON database.
Generate ideal target metrics for this patient.
STEP 3: VERDICT
Compare actual measurements with the target.
Provide a conclusion explicitly referencing the [MAIN SOURCE] as authority.
PHASE 3: HOLISTIC CROSS-METRIC SYNTHESIS (THE REAL BRAIN)
Do NOT analyze metrics one by one. You are a Chief Diagnostician. You must look for COMBINATIONS of data points to form a single cohesive narrative.
LOOK FOR THESE SPECIFIC PATTERNS (CLINICAL SIGNATURES) Examples:
1. The "Guarding" Pattern (Common in early rehab):
    * Signs: Low Range of Motion (Bad?) + High Stability/GVI (Good).
    * Meaning: The patient is intentionally limiting movement to avoid pain, but is in control.
    * Verdict: "Safe, Protective Gait." (Positive for early weeks).
2. The "Instability" Pattern (High Risk):
    * Signs: Low Range of Motion (Bad) + High Variability/Low GVI (Bad).
    * Meaning: The muscle failed. The limb is buckling.
    * Verdict: "Critical Instability." (Immediate Doctor Alert).
3. The "Compensation" Pattern:
    * Signs: Good Speed (Good?) + High Asymmetry (Bad).
    * Meaning: Patient is rushing and forcing the healthy leg to do all the work.
    * Verdict: "Harmful Compensation." (Advise to slow down and focus on form).
If the current session shows a drop in GVI > 10% compared to the previous session, flag this as 'Sudden Regression' in the Status

STEP 4: TREND ANALYSIS (if previous reports available)
- Compare current metrics to previous 3 sessions
- Identify improvement, plateau, or regression
- Adjust recommendations based on trajectory


CRITICAL RULES
- Always prioritize patient safety
- Never recommend activities beyond textbook protocols
- If GVI < 85, forbid high-impact activities
- If pain level > 7, recommend immediate medical consultation
- Be honest about limitations - if data is insufficient, say so

OUTPUT FORMAT
1. Protocol Reference (Main Source Reference)
- Rule from the loaded text: “…”
- Statistics from the database: Similar cases found: [X]
2. Personalized Target
- Target: …
3. Stridex Conclusion
-Executive Summary (The Narrative): Write ONE paragraph combining all data.
- Status: …
- Key Conflicts & Wins: Only mention metrics if they interact meaningfully (e.g., "Speed is up, BUT at the cost of Symmetry"). Ignore minor deviations.
- Justification: (Based on the Main Source)
- Recommendation: Based on the combination, what is the ONE thing to do? (e.g., "Increase load" vs "Use crutches").
"""
    def analyze_gait(
        self,
        user_profile: Dict,
        session_metrics: Dict,
        previous_reports: Optional[List[Dict]] = None
    ) -> str:
        prompt_parts = [
            "PATIENT PROFILE:",
            json.dumps(user_profile, indent=2),
            "\nCURRENT SESSION DATA:",
            json.dumps(session_metrics, indent=2)
        ]
        
        if previous_reports and len(previous_reports) > 0:
            prompt_parts.extend([
                "\nPREVIOUS REPORTS (For Trend Analysis):",
                json.dumps(previous_reports, indent=2),
                "\nNote: Analyze the progression across these sessions."
            ])
        
        prompt = "\n".join(prompt_parts)
        
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"Analysis Error: {str(e)}\nPlease contact support if this persists."
    
    def extract_targets(self, analysis_text: str) -> Dict:
        extraction_prompt = f"""
From the following gait analysis report, extract ONLY the numeric target values 
and return them as a JSON object. Example format:
 "session_metrics": {
      "activity_type": ["walking", "natural_surface"],
      "notes": "Тестовая ходьба в спокойном темпе по ровной поверхности.",
      
      "rhythm_pace": {
        "step_count": 150,
        "cadence": 112.5,
        "avg_speed": 1.35,
        "avg_peak_angular_velocity": 410.2
      },

      "joint_mechanics": {
        "knee_angle": {
          "mean": 22.4,
          "std": 18.5,
          "max": 65.2,
          "min": 0.5,
          "amplitude": 64.7
        },
        "hip_angle": {
          "mean": 15.0,
          "std": 12.4,
          "max": 35.0,
          "min": -10.0,
          "amplitude": 45.0
        },
        "orientation": {
          "avg_roll": 0.5,
          "avg_pitch": -2.1,
          "avg_yaw": 0.2
        }
      },

      "variability": {
        "gvi": 98.5,
        "step_time_variability": 2.1,
        "knee_angle_variability": 1.8,
        "stance_time_variability": 2.5,
        "swing_time_variability": 2.8,
        "stride_length_variability": 1.5
      },

      "symmetry_phases": {
        "avg_stance_time": 0.60,
        "avg_swing_time": 0.40,
        "stance_swing_ratio": 1.5,
        "double_support_time": 0.12,
        "avg_impact_force": 14.2
      }
    }
Use ONLY the following keys in your JSON: "gvi", "knee_rom", "cadence", "speed", "asymmetry". 
If a value is missing in the report, use null.
Analysis Report:
{analysis_text}

Return ONLY valid JSON, no additional text.
"""
        
        try:
            response = self.model.generate_content(extraction_prompt)
            targets = json.loads(response.text)
            return targets
        except Exception as e:
            print(f"Target extraction error: {e}")
            return {}