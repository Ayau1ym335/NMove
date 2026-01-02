from tables import Exercise

async def seed_exercises():
    """
    Seed the database with initial exercises
    """
    async with AsyncSessionLocal() as session:
        exercises = [
            Exercise(
            ),
        ]

        session.add_all(exercises)
        await session.commit()