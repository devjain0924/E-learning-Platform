import threading
import logging
import json
from .models import Course, Module, Lesson, AIQuiz
from .ai_service import generate_course_structure, generate_chapter_content, generate_quiz_json, get_text_embedding
from .youtube_service import search_youtube_video

logger = logging.getLogger(__name__)

def generate_full_course_task(course_id):
    try:
        course = Course.objects.get(id=course_id)
        logger.info(f"Starting course generation for: {course.title}")
        
        # 1. Structure
        structure = generate_course_structure(course.title)
        if not structure:
            logger.error(f"Failed to generate structure for {course.title}")
            return
            
        course.description = structure.get('description', f"An automated AI-generated course about {course.title}.")
        
        # Calculate embedding so it shows in recommendations
        embedding = get_text_embedding(course.title + " " + course.description)
        if embedding:
            course.course_embedding = embedding
            
        course.save()
        
        # 2. Modules & Lessons
        module_order = 1
        for mod_data in structure.get('modules', []):
            module = Module.objects.create(
                course=course,
                title=mod_data.get('title', f"Module {module_order}"),
                order=module_order
            )
            module_order += 1
            
            lesson_order = 1
            for lesson_title in mod_data.get('lessons', []):
                # Search video via YouTube Data API
                search_query = f"{course.title} {lesson_title}"
                video_data = search_youtube_video(search_query)
                
                content = ""
                video_url = ""
                duration = ""
                
                if video_data:
                    video_url = video_data['url']
                    duration = video_data['duration']
                    content = generate_chapter_content(lesson_title, video_data['summary'])
                else:
                    content = generate_chapter_content(lesson_title, "Educational tutorial concepts")
                
                lesson = Lesson.objects.create(
                    module=module,
                    title=lesson_title,
                    video_url=video_url,
                    duration=duration,
                    content=content,
                    order=lesson_order
                )
                lesson_order += 1
                
                # Generate a quick AIQuiz for this lesson
                quiz_data = generate_quiz_json(topic=f"{course.title}: {lesson_title}", difficulty="beginner")
                if quiz_data:
                    AIQuiz.objects.create(
                        user=None,
                        title=f"Quiz: {lesson_title}",
                        topic=lesson_title,
                        quiz_data=quiz_data
                    )
        
        logger.info(f"Successfully generated full course: {course.title}")

    except Exception as e:
        logger.error(f"Error in course generation task: {e}")

def trigger_course_generation(course_obj):
    # Only triggered if course has no modules yet
    if not course_obj.modules.exists() and course_obj.title:
        thread = threading.Thread(target=generate_full_course_task, args=(course_obj.id,))
        thread.daemon = True
        thread.start()
