from typing import List, Optional
from sqlalchemy.orm import Session
from datetime import datetime
import google.generativeai as genai
from app.models.chat import ChatSession
from app.models.report import Report
from app.services.analysis import AnalysisService
from app.config import get_settings

settings = get_settings()
genai.configure(api_key=settings.GEMINI_API_KEY)


class ChatService:
    """Service for AI-powered chat about gait analysis reports"""
    
    def __init__(self, db: Session):
        self.db = db
        self.analysis_service = AnalysisService(db)
    
    def _build_chat_system_instruction(self, clinical_report_text: str) -> str:
        """Build system instruction for chat session"""
        return f"""
SYSTEM ROLE
You are Stridex AI Assistant, a helpful and empathetic medical consultant.
You are talking to the patient RIGHT NOW about their gait analysis results.

CONTEXT (THE TRUTH)
The patient has just completed a gait analysis. Here is their generated report.
You must answer all questions based ONLY on this report and established medical knowledge.

--- BEGIN CLINICAL REPORT ---
{clinical_report_text}
--- END CLINICAL REPORT ---

RULES OF ENGAGEMENT (STRICT)
1. **Consistency**: If the Report says "Knee ROM is below target", do NOT say "It's fine" 
   to be nice. Stick to the facts in the report.

2. **No New Diagnoses**: Do not invent new problems. If the user asks about something 
   not in the report (e.g., "Do I have arthritis?"), say: "I can only analyze your 
   current gait metrics. For new symptoms, please consult your doctor."

3. **Safety First**: 
   - If GVI < 85: Forbid high-impact activities (running, jumping)
   - If GVI 85-95: Allow walking, light exercises
   - If GVI > 95: Normal activities permitted
   - Always check the report's recommendations before advising activities

4. **Pain Management**: 
   - If pain level > 7: Recommend immediate medical consultation
   - If pain level 4-7: Suggest discussing with physical therapist
   - If pain level < 4: Continue current protocol

5. **Tone**: Professional, encouraging, but firm on safety. Use simple language to 
   explain technical terms.

6. **Anti-Hallucination**: If you don't know the answer or the information isn't in 
   the report, say: "I recommend showing this report to your doctor for clarification."

7. **Exercise Recommendations**: Only suggest exercises that align with the report's 
   status. Never recommend activities beyond what the protocol allows.

GOAL
Help the patient understand their gait metrics in simple terms and answer questions 
about their recovery progress.
"""
    
    def get_or_create_session(
        self,
        user_id: int,
        report_id: Optional[int] = None
    ) -> ChatSession:
        """Get active chat session or create new one"""
        
        # Try to find active session for this report
        if report_id:
            session = (
                self.db.query(ChatSession)
                .filter(
                    ChatSession.user_id == user_id,
                    ChatSession.report_id == report_id,
                    ChatSession.is_active == True
                )
                .first()
            )
            
            if session:
                return session
        
        # Create new session
        session_name = f"Chat - {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"
        new_session = ChatSession(
            user_id=user_id,
            report_id=report_id,
            session_name=session_name,
            chat_history=[],
            is_active=True
        )
        
        self.db.add(new_session)
        self.db.commit()
        self.db.refresh(new_session)
        
        return new_session
    
    def send_message(
        self,
        session_id: int,
        message: str
    ) -> str:
        """
        Send message in chat session and get AI response.
        
        Args:
            session_id: Chat session ID
            message: User's message
        
        Returns:
            AI response text
        """
        # Get session
        session = self.db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if not session:
            raise ValueError(f"Chat session {session_id} not found")
        
        # Get report context
        report_text = ""
        if session.report_id:
            try:
                report_text = self.analysis_service.get_full_analysis_text(session.report_id)
            except Exception as e:
                report_text = f"[Report data unavailable: {str(e)}]"
        
        # Build system instruction
        system_instruction = self._build_chat_system_instruction(report_text)
        
        # Get chat history
        history = session.chat_history or []
        
        # Initialize Gemini chat
        model = genai.GenerativeModel(
            model_name=settings.GEMINI_MODEL,
            system_instruction=system_instruction
        )
        
        # Convert history to Gemini format
        gemini_history = []
        for msg in history[-settings.MAX_CHAT_HISTORY:]:  # Limit history
            gemini_history.append({
                "role": msg["role"],
                "parts": [msg["content"]]
            })
        
        # Start chat with history
        chat = model.start_chat(history=gemini_history)
        
        # Send message
        try:
            response = chat.send_message(message)
            response_text = response.text
        except Exception as e:
            response_text = f"I'm having trouble processing that. Error: {str(e)}"
        
        # Update chat history
        history.append({
            "role": "user",
            "content": message,
            "timestamp": datetime.utcnow().isoformat()
        })
        history.append({
            "role": "model",
            "content": response_text,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        session.chat_history = history
        session.updated_at = datetime.utcnow()
        
        self.db.commit()
        
        return response_text
    
    def get_chat_history(self, session_id: int) -> List[dict]:
        """Get full chat history for a session"""
        session = self.db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if not session:
            raise ValueError(f"Chat session {session_id} not found")
        
        return session.chat_history or []
    
    def end_session(self, session_id: int) -> None:
        """Mark chat session as inactive"""
        session = self.db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if session:
            session.is_active = False
            self.db.commit()