from google import genai
from google.genai import types
import json
import os
from dotenv import load_dotenv

load_dotenv(override=True)

# Initialize the NEW client
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def generate_quiz_json(topic, difficulty):
    # Map the difficulty to specific prompting instructions so the AI knows exactly what it means
    difficulty_instructions = {
        "beginner": "Focus on high-level concepts, basic definitions, and introductory knowledge. Use simple language.",
        "intermediate": "Focus on application, analysis, and standard problem-solving. Assume the user has a working knowledge of the topic.",
        "advanced": "Focus on edge cases, complex multi-step scenarios, highly technical nuances, and expert-level synthesis."
    }

    instruction = difficulty_instructions.get(difficulty, difficulty_instructions["beginner"])

    prompt = f"""
        Generate a JSON quiz with 5 questions about the topic: {topic}.
        
        CRITICAL DIFFICULTY INSTRUCTION: The target difficulty is {difficulty.upper()}  x   . 
        {instruction}
        
        Ensure the distractors (wrong answers) match this difficulty level. For advanced quizzes, the wrong answers should be common misconceptions, not obvious throwaways.
        
        CRITICAL RANDOMIZATION INSTRUCTION: You MUST randomize the position of the correct answer for every question. Do NOT always put the correct answer first. The `correct_index` must be an integer between 0 and 3, accurately reflecting the randomized position of the correct option in the array.
        
        Output valid JSON using this exact schema:
        {{
            "title": "A short, catchy title for the quiz",
            "questions": [
                {{
                    "id": 1,
                    "text": "The question text",
                    "options": ["Option A", "Option B", "Option C", "Option D"],
                    "correct_index": 0 
                }}
            ]
        }}
        """
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )
        
        quiz_data = json.loads(response.text)
        return quiz_data

    except Exception as e:
        print(f"Error generating quiz with Gemini: {e}")
        return None


def get_text_embedding(text):
    """Translates a text string into a mathematical vector."""
    try:
        result = client.models.embed_content(
            model="gemini-embedding-001",
            contents=text,
        )
        return result.embeddings[0].values
    except Exception as e:
        print(f"Error generating embedding for '{text}': {e}")
        return None

def generate_course_structure(course_title):
    prompt = f"""
        Act as an expert curriculum designer. The user wants to create a new course titled: "{course_title}".
        Generate a detailed course structure for this topic in JSON format.
        
        The JSON must strictly follow this schema:
        {{
            "description": "A comprehensive introductory description of the entire course.",
            "modules": [
                {{
                    "title": "Module 1: Introduction",
                    "lessons": [
                        "Lesson 1 topic",
                        "Lesson 2 topic"
                    ]
                }}
            ]
        }}
        Create at least 2 modules, with 2-3 lessons each, logically progressing from beginner to advanced.
    """
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"Error generating course structure: {e}")
        return None

def generate_chapter_content(lesson_title, video_summary):
    prompt = f"""
        Act as an expert teacher writing a lesson chapter.
        The lesson title is: {lesson_title}.
        A related video has this description: {video_summary}.
        
        Write an engaging, clear lesson content text (about 3 paragraphs) that covers the main concepts of {lesson_title}. Use formatting (bolding, lists) to make it easy to read. This is the assigned reading for the student for this lesson.
    """
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        return response.text
    except Exception as e:
        print(f"Error generating chapter content: {e}")
        return "Lesson content is currently unavailable."