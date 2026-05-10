from django.contrib import admin
from .models import (
    StudentProfile, 
    Course, 
    Module, 
    Lesson,
    AIQuiz, 
    QuizResult
)

# ==========================================
# 1. AI & USER PROFILES
# ==========================================

@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'get_vector_preview')
    search_fields = ('user__username',)

    def get_vector_preview(self, obj):
        # Shows a truncated version of the learning vector in the admin list
        return str(obj.learning_vector)[:50] + "..." if obj.learning_vector else "[]"
    get_vector_preview.short_description = 'Learning Vector'

# ==========================================
# 2. COURSE ARCHITECTURE
# ==========================================

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('title', 'instructor', 'slug')
    search_fields = ('title', 'instructor')
    # Automatically fills the slug field as you type the title
    prepopulated_fields = {'slug': ('title',)} 
    
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        # Import here to avoid circular dependencies
        from .course_maker import trigger_course_generation
        trigger_course_generation(obj) 

@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'order')
    list_filter = ('course',) # Adds a sidebar to filter modules by course
    search_fields = ('title', 'course__title')
    ordering = ('course', 'order')


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ('title', 'module', 'get_course', 'order')
    list_filter = ('module__course',) # Filter lessons by course
    search_fields = ('title', 'module__title')
    ordering = ('module__course', 'module__order', 'order')

    def get_course(self, obj):
        return obj.module.course.title
    get_course.short_description = 'Course'

# ==========================================
# 3. PROGRESS & QUIZZES
# ==========================================

# @admin.register(LessonProgress)
# class LessonProgressAdmin(admin.ModelAdmin):
#     list_display = ('user', 'lesson', 'is_completed', 'completed_at')
#     list_filter = ('is_completed', 'completed_at')
#     search_fields = ('user__username', 'lesson__title')
    

@admin.register(AIQuiz)
class AIQuizAdmin(admin.ModelAdmin):
    list_display = ('title', 'topic', 'created_at')
    list_filter = ('topic', 'created_at')
    search_fields = ('title', 'topic')

@admin.register(QuizResult)
class QuizResultAdmin(admin.ModelAdmin):
    list_display = ('user', 'topic', 'score', 'total_questions', 'percentage', 'date_taken')
    list_filter = ('topic', 'date_taken')
    search_fields = ('user__username', 'topic')