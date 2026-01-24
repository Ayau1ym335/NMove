from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from app.data.tables import Report, Users
from app.routers.schemas import ReportCreate
from ai.brain import Brain
from ai.diff_calc import matrix_calc
from app.config import get_settings

settings = get_settings()

class Analysis:
    def __init__(self, db: Session):
        self.db = db
        self.brain = Brain()
    
    def get_user_previous_reports(self, user_id: int, limit: int = 3) -> List[Dict]:
        """
        Retrieve user's previous reports for trend analysis.
        
        Args:
            user_id: User ID
            limit: Number of previous reports to retrieve
        
        Returns:
            List of report summaries
        """
        reports = (
            self.db.query(Report)
            .filter(Report.user_id == user_id)
            .order_by(Report.created_at.desc())
            .limit(limit)
            .all()
        )
        
        # Convert to simplified format for AI context
        report_summaries = []
        for r in reports:
            report_summaries.append({
                "date": r.created_at.isoformat(),
                "gvi_score": r.gvi_score,
                "overall_score": r.overall_score,
                "status": r.status,
                "key_metrics": {
                    "rhythm_pace": r.rhythm_pace,
                    "joint_mechanics": r.joint_mechanics,
                    "variability": r.variability
                }
            })
        
        return report_summaries
    
    def generate_report(self, report_data: ReportCreate) -> Report:
        """
        Generate comprehensive gait analysis report.
        
        This is the main analysis pipeline:
        1. Fetch user profile
        2. Get previous reports (for trend analysis)
        3. Run AI analysis (StridexBrain)
        4. Calculate comparison matrix
        5. Identify gait patterns
        6. Store results in database
        """
        # 1. Fetch user
        user = self.db.query(User).filter(User.id == report_data.user_id).first()
        if not user:
            raise ValueError(f"User {report_data.user_id} not found")
        
        # 2. Get previous reports
        previous_reports = self.get_user_previous_reports(
            user.id,
            limit=settings.CONTEXT_WINDOW_SIZE
        )
        
        # 3. Prepare user profile for AI
        user_profile = {
            "age": user.age,
            "gender": user.gender,
            "weight": user.weight,
            "height": user.height,
            "dominant_leg": user.dominant_leg,
            "placed_leg": user.placed_leg,
            "injury_info": user.injury_info
        }
        
        # 4. Run AI analysis
        session_metrics = report_data.session_metrics.model_dump()
        
        ai_analysis = self.brain.analyze_gait(
            user_profile=user_profile,
            session_metrics=session_metrics,
            previous_reports=previous_reports
        )
        
        # 5. Extract personalized targets from AI analysis
        personalized_targets = self.brain.extract_targets(ai_analysis)
        
        # 6. Calculate comparison matrix
        user_current_data = {
            "gvi": session_metrics["variability"]["gvi"],
            "cadence": session_metrics["rhythm_pace"]["cadence"],
            "knee_amplitude": session_metrics["joint_mechanics"]["knee_angle"]["amplitude"],
            "step_time_variability": session_metrics["variability"]["step_time_variability"],
            "stance_swing_ratio": session_metrics["symmetry_phases"]["stance_swing_ratio"]
        }
        
        # Clinical norms (these could also come from the reference database)
        clinical_norms = {
            "gvi": 100.0,
            "cadence": 110.0,
            "knee_amplitude": 60.0,
            "step_time_variability": 2.0,
            "stance_swing_ratio": 1.5
        }
        
        matrix = matrix_calc(
            user_data=user_current_data,
            clinical_norm=clinical_norms,
            personal_target=personalized_targets
        )
        
        # 7. Identify gait pattern
        gvi = session_metrics["variability"]["gvi"]
        pattern = identify_gait_pattern(matrix, gvi)
        
        # 8. Determine status
        if pattern["severity"] == "Critical":
            status = "Critical"
        elif pattern["severity"] == "Medium":
            status = "Warning"
        else:
            status = "Safe"
        
        # 9. Calculate overall score (weighted average)
        gvi_weight = 0.4
        rom_weight = 0.3
        symmetry_weight = 0.3
        
        gvi_normalized = min(gvi / 100.0, 1.0)
        rom_normalized = min(user_current_data["knee_amplitude"] / 60.0, 1.0)
        symmetry_score = max(0, 1.0 - abs(1.5 - user_current_data["stance_swing_ratio"]) / 1.5)
        
        overall_score = (
            gvi_weight * gvi_normalized +
            rom_weight * rom_normalized +
            symmetry_weight * symmetry_score
        ) * 100
        
        # 10. Create report record
        new_report = Report(
            user_id=user.id,
            activity_type=session_metrics.get("activity_type"),
            notes=session_metrics.get("notes"),
            rhythm_pace=session_metrics["rhythm_pace"],
            joint_mechanics=session_metrics["joint_mechanics"],
            variability=session_metrics["variability"],
            symmetry_phases=session_metrics["symmetry_phases"],
            protocol_reference=ai_analysis[:500],  # Store first 500 chars
            personalized_target=personalized_targets,
            analysis_matrix=matrix,
            clinical_narrative=pattern["description"],
            status=status,
            recommendations=pattern["verdict"],
            overall_score=round(overall_score, 1),
            gvi_score=gvi
        )
        
        self.db.add(new_report)
        self.db.commit()
        self.db.refresh(new_report)
        
        return new_report
    
    def get_full_analysis_text(self, report_id: int) -> str:
        """
        Get the full AI analysis text for a report.
        This regenerates the analysis for chat context.
        """
        report = self.db.query(Report).filter(Report.id == report_id).first()
        if not report:
            raise ValueError(f"Report {report_id} not found")
        
        user = report.user
        
        # Reconstruct the analysis
        user_profile = {
            "age": user.age,
            "gender": user.gender,
            "injury_info": user.injury_info
        }
        
        session_metrics = {
            "rhythm_pace": report.rhythm_pace,
            "joint_mechanics": report.joint_mechanics,
            "variability": report.variability,
            "symmetry_phases": report.symmetry_phases
        }
        
        return self.brain.analyze_gait(user_profile, session_metrics)