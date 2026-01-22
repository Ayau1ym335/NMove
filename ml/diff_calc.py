def matrix_calc(user_data, clinical_norm, personal_target):
    matrix = {}

    def calculate_diff(current, target):
        if target is None: 
            return "N/A"
        
        if abs(target) < 0.001: 
            return round(current - target, 2) 
            
        try:
            diff = (current - target) / target * 100.0
            return round(diff, 1)
        except ZeroDivisionError:
            return 0.0

    for metric, value in user_data.items():
        
        c_target = clinical_norm.get(metric)
        p_target = personal_target.get(metric)

        clinical_dev = calculate_diff(value, c_target)
        personal_trend = calculate_diff(value, p_target)

        matrix[metric] = {
            "current_value": value,
            
            "vs_clinical": {
                "target": c_target,
                "diff_percent": clinical_dev, 
                "status": "Lagging" if isinstance(clinical_dev, (int, float)) and clinical_dev < -10 else "Normal" 
            },
            
            "vs_personal": {
                "target": p_target,
                "diff_percent": personal_trend, 
                "status": "Improving" if isinstance(personal_trend, (int, float)) and personal_trend > 0 else "Regressing"
            }
        }

    return matrix


def start_doctor_chat(clinical_report_text):
    chat_system_instruction = f"""
SYSTEM ROLE
You are Stridex AI Assistant, a helpful and empathetic medical consultant.
You are talking to the patient RIGHT NOW.

CONTEXT (THE TRUTH)
The patient has just completed a gait analysis. Here is their generated report.
You must answer all questions based ONLY on this report and the medical books you know.

--- BEGIN CLINICAL REPORT ---
{clinical_report_text}
--- END CLINICAL REPORT ---

RULES OF ENGAGEMENT (STRICT)
1.  Be Consistency: If the Report says "Knee Angle is bad", do NOT say "It's okay" just to be nice. Stick to the facts in the report.
2.  No New Diagnoses: Do not invent new problems. If the user asks about something not in the report (e.g., "Do I have cancer?"), say: "I can only analyze your gait metrics."
3.  Safety First: If the user asks about running/jumping, check the GVI (Stability) in the report. If GVI < 90, forbid sports.
4.  Tone: Professional, encouraging, but firm on safety.
5.  Anti-Hallucination: If you don't know the answer, say "I recommend showing this report to your doctor."

GOAL
Explain the difficult numbers from the report in simple words.
"""

    chat_session = model.start_chat(
        history=[
            {"role": "user", "parts": [chat_system_instruction]},
            {"role": "model", "parts": ["Understood. I am ready to answer questions about this report."]}
        ]
    )

    while True:
        user_question = input("Вы: ")
        
        if user_question.lower() in ["exit", "выход", "quit"]:
            print("NMove: Выздоравливайте!")
            break
            
        try:
            response = chat_session.send_message(user_question)
            print(f"NMove: {response.text}")
        except Exception as e:
            print(f"Ошибка соединения: {e}")


