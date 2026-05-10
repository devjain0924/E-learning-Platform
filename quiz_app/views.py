from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from rest_framework import status
from django.shortcuts import render, get_object_or_404, redirect
import json
from django.http import JsonResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.views.decorators.cache import never_cache

from .models import AIQuiz, Course, StudentProfile, QuizResult, Lesson, Module
from .ai_service import generate_quiz_json

from .utils import (
    calculate_cosine_similarity,
    update_learning_vector,
    get_course_progress,
    calculate_dynamic_difficulty
)

@method_decorator(csrf_exempt, name='dispatch')
class GenerateQuizView(APIView):
    permission_classes = [IsAuthenticated] 

    def post(self, request):
        topic = request.data.get('topic')
        requested_difficulty = request.data.get('difficulty', 'auto').lower() 

        if not topic:
            return Response({"error": "Topic is required"}, status=400)

        if requested_difficulty == 'auto':
            target_difficulty = calculate_dynamic_difficulty(request.user, topic)
        else:
            valid_difficulties = ['beginner', 'intermediate', 'advanced']
            target_difficulty = requested_difficulty if requested_difficulty in valid_difficulties else 'beginner'

        data = generate_quiz_json(topic, target_difficulty) 
        
        if not data:
             return Response({"error": "AI failed"}, status=500)

        quiz = AIQuiz.objects.create(
            user=request.user,
            title=data['title'], 
            topic=topic, 
            quiz_data=data
        )
        
        return Response({
            "quiz_id": quiz.id,
            "title": quiz.title,
            "difficulty_used": target_difficulty, 
            "questions": data['questions']
        }, status=201)

@login_required(login_url='login_page')
def dashboard(request):
    user_profile, created = StudentProfile.objects.get_or_create(user=request.user)
    user_vector = user_profile.learning_vector
    
    recommended_courses = []
    
    if not user_vector:
        recommended_courses = Course.objects.all().order_by('-id')[:4]
    else:
        courses = Course.objects.all() 
        scored_courses = []
        
        for course in courses:
            if not course.course_embedding:
                continue
                
            similarity = calculate_cosine_similarity(user_vector, course.course_embedding)
            scored_courses.append((similarity, course))
        
        scored_courses.sort(key=lambda x: x[0], reverse=True)
        recommended_courses = [item[1] for item in scored_courses[:4]]
    
    for course in recommended_courses:
        course.progress_percentage = get_course_progress(request.user, course)
        
    context = {
        'recommended_courses': recommended_courses,
        'user_profile': user_profile,
    }
    
    return render(request, 'dashboard.html', context)

@csrf_exempt
@login_required(login_url='login_page') 
def save_quiz_result(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            topic = data.get('topic')
            percentage = data.get('percentage')
            
            result = QuizResult.objects.create(
                user=request.user,
                topic=topic,
                score=data.get('score'),
                total_questions=data.get('total_questions'),
                percentage=percentage
            )
            
            update_learning_vector(request.user, topic, percentage)
            
            return JsonResponse({'message': 'Result saved and AI Profile updated!'})
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
            
    return JsonResponse({'error': 'Invalid request'}, status=400)

def get_quiz_history(request):
    results = QuizResult.objects.filter(user=request.user).order_by('-date_taken').values()
    return JsonResponse(list(results), safe=False)

@never_cache
@login_required(login_url='login_page')
def course_player(request, course_slug):
    course = get_object_or_404(
        Course.objects.prefetch_related('modules__lessons'), 
        slug=course_slug
    )

    modules_list = []
    
    for module in course.modules.all():
        lessons_list = list(module.lessons.all().values(
            'id', 'title', 'video_url', 'content', 'order', 'duration'
        ))
        
        modules_list.append({
            "id": module.id,
            "title": module.title,
            "order": module.order,
            "lessons": lessons_list 
        })

    course_data = {
        "title": course.title,
        "instructor": course.instructor,
        "description": course.description,
        "modules": modules_list, 
    }

    return render(request, 'player.html', {
        'course': course,  
        'course_data': json.dumps(course_data)
    })

@csrf_exempt
@login_required(login_url='login_page')
def generate_course_api(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            title = data.get('title')
            if not title:
                return JsonResponse({'error': 'Title is required'}, status=400)
            
            from django.utils.text import slugify
            import uuid
            
            base_slug = slugify(title)
            slug = base_slug
            if Course.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{str(uuid.uuid4())[:8]}"

            course = Course.objects.create(
                title=title,
                instructor=request.user.username,
                slug=slug
            )
            
            from .course_maker import trigger_course_generation
            trigger_course_generation(course)
            
            return JsonResponse({'message': 'Course generation started! Refresh in a minute.'}, status=202)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
            
    return JsonResponse({'error': 'Invalid request'}, status=400)

def login_page(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'login.html')

def login_req(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            return redirect('dashboard')
        else:
            messages.error(request, "Invalid username or password.")
            return redirect('login_page') 

    return redirect('login_page')

def logout_view(request):
    logout(request)
    request.session.flush()
    return redirect('index')

def index(request):
    return render(request, 'index.html')

@login_required(login_url='login_page') 
def courses_list(request):
    courses = Course.objects.all()
    
    for course in courses:
        course.progress_percentage = get_course_progress(request.user, course)
    
    return render(request, 'courses.html', {'courses': courses})

def analytics(request):
    return render(request, 'analytics.html')

def settings(request):
    return render(request, 'settings.html')

def about(request):
    return render(request, 'about.html')

def contact(request):
    return render(request, 'contact.html')

def courses_home(request):
    return render(request, 'courses_home.html')

from django.utils import timezone
from datetime import timedelta

@csrf_exempt
@login_required(login_url='login_page')
def mark_lesson_complete_api(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            lesson_id = data.get('lesson_id')
            time_spent = data.get('time_spent', 0)
            
            from .models import LessonProgress
            lesson = get_object_or_404(Lesson, id=lesson_id)
            profile, _ = StudentProfile.objects.get_or_create(user=request.user)
            
            # Update Profile Activity & Streak
            today = timezone.now().date()
            if profile.last_active_date != today:
                # If they were active exactly yesterday, increment streak
                if profile.last_active_date == today - timedelta(days=1):
                    profile.streak_count += 1
                else:
                    profile.streak_count = 1  # Reset to 1 if skipped days
                profile.last_active_date = today

            profile.last_watched_lesson = lesson
            
            # Legacy logic array
            if profile.completed_lessons is None:
                profile.completed_lessons = []
            if lesson_id not in profile.completed_lessons:
                profile.completed_lessons.append(lesson_id)
                
            profile.save()
            
            # Store in relational tracking
            lp, created = LessonProgress.objects.get_or_create(user=request.user, lesson=lesson)
            lp.is_completed = True
            lp.time_spent_seconds += int(time_spent)
            lp.save()
            
            return JsonResponse({'message': 'Progress saved!', 'streak': profile.streak_count})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Invalid'}, status=400)

@login_required(login_url='login_page')
def analytics_data(request):
    import traceback
    try:
        profile, _ = StudentProfile.objects.get_or_create(user=request.user)
        completed_lesson_ids = profile.completed_lessons or []
        
        # Identify started courses
        all_lessons = list(Lesson.objects.filter(id__in=completed_lesson_ids).select_related('module__course'))
        started_courses = {l.module.course for l in all_lessons}
        
        from .models import LessonProgress
        time_spent = sum((lp.time_spent_seconds or 0) for lp in LessonProgress.objects.filter(user=request.user))
        
        overall_progress = []
        course_list = []
        for c in started_courses:
            pct = get_course_progress(request.user, c)
            overall_progress.append(pct)
            c_lessons = Lesson.objects.filter(module__course=c).count()
            c_done = len([l for l in all_lessons if l.module.course == c])
            
            course_list.append({
                'title': c.title,
                'thumbnail': c.thumbnail,
                'slug': c.slug,
                'progress': pct,
                'lessons_done': c_done,
                'total_lessons': c_lessons
            })

        avg_progress = (sum(overall_progress) / len(overall_progress)) if overall_progress else 0

        # Quizzes
        quizzes = QuizResult.objects.filter(user=request.user)
        avg_score = sum((q.percentage or 0) for q in quizzes) / len(quizzes) if quizzes else 0
        best_score = max(((q.percentage or 0) for q in quizzes), default=0)
        worst_score = min(((q.percentage or 0) for q in quizzes), default=0)
        
        quiz_history_labels = [q.date_taken.strftime("%b %d") if q.date_taken else "Unknown" for q in quizzes]
        quiz_history_data = [(q.percentage or 0) for q in quizzes]

        # Activity Heatmap
        from collections import Counter
        activity_dates = []
        for lp in LessonProgress.objects.filter(user=request.user):
            if lp.completed_at:
                activity_dates.append(lp.completed_at.strftime("%Y-%m-%d"))
        for q in quizzes:
            if q.date_taken:
                activity_dates.append(q.date_taken.strftime("%Y-%m-%d"))
                
        heatmap = dict(Counter(activity_dates))

        last_watched_title = "None"
        if profile.last_watched_lesson_id:
            try:
                last_watched_title = profile.last_watched_lesson.title
            except Exception:
                pass

        return JsonResponse({
            'summary': {
                'total_courses': len(started_courses),
                'total_lessons': len(completed_lesson_ids),
                'overall_progress': int(avg_progress),
                'time_spent': time_spent,
                'streak': profile.streak_count or 0,
                'last_watched': last_watched_title
            },
            'courses': course_list,
            'quiz_performance': {
                'avg': int(avg_score),
                'best': best_score,
                'worst': worst_score,
                'labels': quiz_history_labels,
                'data': quiz_history_data,
                'attempted': len(quizzes)
            },
            'heatmap': heatmap
        })
    except Exception as e:
        return JsonResponse({'error': str(e), 'trace': traceback.format_exc()})