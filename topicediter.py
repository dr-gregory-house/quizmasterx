import sqlite3

DATABASE_PATH = r"C:\Users\anubh\Desktop\quizmasterx\data\mcq_database.db"


def add_topics_to_questions(db_path):
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Define your topic mappings here
        topic_mappings = [
            {"start_id": 1, "end_id": 191, "topic": "History Of Medicine"},
            {"start_id": 192, "end_id": 622, "topic": "Concepts of Health and Disease"},
          
            {"start_id": 623, "end_id": 694, "topic": "Epidemiology and Vaccines"}, # Example
            {"start_id": 695, "end_id": 1320, "topic": "Screening of Disease "}, # Example
            {"start_id": 1321, "end_id": 1586, "topic": "Communicable and Non-communicable Diseases"}, # Example
            {"start_id": 1587, "end_id": 1773, "topic": "National Health Programmes"}, # Example
            {"start_id": 1774, "end_id": 1929, "topic": "Demography, Family Planning and Contraception "}, # Example
            {"start_id": 1930, "end_id": 2192, "topic": "Preventive Obstetrics, Paediatrics and Geriatrics"}, # Example
            {"start_id": 2193, "end_id": 2263, "topic": "Nutrition and Health"}, # Example
            {"start_id": 2264, "end_id": 2516, "topic": "Social Sciences and Health"}, # Example
            {"start_id": 2517, "end_id": 2680, "topic": " Environment and Health"}, # Example
            {"start_id": 2681, "end_id": 2712, "topic": "Biomedical Waste Management, Disaster Management"}, # Example
            {"start_id": 2713, "end_id": 2845, "topic": "Health Education and Communication"}, # Example
            
            {"start_id": 2846, "end_id": 2889, "topic": "Health Care in India, Health Planning and Management"}, # Example
            {"start_id": 2890, "end_id": 3125, "topic": "International Health"}, # Example
            
        ]

        for mapping in topic_mappings:
            start_id = mapping["start_id"]
            end_id = mapping["end_id"]
            topic = mapping["topic"]

            cursor.execute(
                "UPDATE questions SET topic = ? WHERE question_id BETWEEN ? AND ?",
                (topic, start_id, end_id),
            )
            print(f"Updated questions {start_id} to {end_id} with topic: {topic}")

        conn.commit()
        print("Successfully added topics to questions.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    add_topics_to_questions(DATABASE_PATH)