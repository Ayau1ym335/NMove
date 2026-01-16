from tables import Exercises, ExerciseD, engine
from sqlalchemy.orm import AsyncSessionLocal

async def seed_exercises():
    async with AsyncSessionLocal(engine) as session:
        ex_init = [
            Exercises(
                name='Lying leg curl',
                description='This exercise is designed to develop knee flexibility and strengthen the hamstrings.It helps restore range of motion after injuries and improve blood circulation in the joint area.'
            ),
        ]

        session.add_all(ex_init)
        await session.commit()

        '''
        name = Column(String(255), nullable=False)
        description = Column(Text)
        instructions = Column(Text, comment="Пошаговая инструкция")

        # Media
        video_url = Column(String(500))
        thumbnail_url = Column(String(500))
        duration = Column(Integer, comment="Длительность (сек)")

        # Categorization
        category = Column(String(50), comment="balance/strength/flexibility/gait_training")
        target_area = Column(String(50), comment="knee/hip/ankle/general")
        difficulty = Column(SQLEnum(ExerciseD), default=ExerciseD.EASY)

        # For which issues
        addresses_issues = Column(JSON, comment='["low_cadence", "high_gvi", ...]')

        # Recommendations
        recommended_sets = Column(Integer, default=3)
        recommended_reps = Column(Integer, default=10)
        rest_time = Column(Integer, comment="Отдых между подходами (сек)")'''