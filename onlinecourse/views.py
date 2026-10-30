
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views import generic
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required

from .models import Course, Enrollment, Question, Choice, Submission

import logging

logger = logging.getLogger(__name__)


# User Registration
def registration_request(request):
    context = {}

    if request.method == 'GET':
        return render(
            request,
            'onlinecourse/user_registration_bootstrap.html',
            context
        )

    elif request.method == 'POST':
        username = request.POST['username']
        password = request.POST['psw']
        first_name = request.POST['firstname']
        last_name = request.POST['lastname']

        user_exist = User.objects.filter(
            username=username
        ).exists()

        if not user_exist:
            user = User.objects.create_user(
                username=username,
                first_name=first_name,
                last_name=last_name,
                password=password
            )

            login(request, user)
            return redirect('onlinecourse:index')

        else:
            context['message'] = "User already exists."

            return render(
                request,
                'onlinecourse/user_registration_bootstrap.html',
                context
            )


# User Login
def login_request(request):
    context = {}

    if request.method == "POST":
        username = request.POST['username']
        password = request.POST['psw']

        user = authenticate(
            username=username,
            password=password
        )

        if user is not None:
            login(request, user)
            return redirect('onlinecourse:index')

        else:
            context['message'] = "Invalid username or password."

            return render(
                request,
                'onlinecourse/user_login_bootstrap.html',
                context
            )

    else:
        return render(
            request,
            'onlinecourse/user_login_bootstrap.html',
            context
        )


# User Logout
def logout_request(request):
    logout(request)
    return redirect('onlinecourse:index')


# Check Whether User Is Enrolled
def check_if_enrolled(user, course):
    if user.is_authenticated:
        return Enrollment.objects.filter(
            user=user,
            course=course
        ).exists()

    return False


# Course List View
class CourseListView(generic.ListView):
    template_name = 'onlinecourse/course_list_bootstrap.html'
    context_object_name = 'course_list'

    def get_queryset(self):
        user = self.request.user

        courses = Course.objects.order_by(
            '-total_enrollment'
        )[:10]

        for course in courses:
            course.is_enrolled = check_if_enrolled(
                user,
                course
            )

        return courses


# Course Detail View
class CourseDetailView(generic.DetailView):
    model = Course
    template_name = 'onlinecourse/course_detail_bootstrap.html'


# Enroll in a Course
@login_required
def enroll(request, course_id):
    course = get_object_or_404(
        Course,
        pk=course_id
    )

    is_enrolled = check_if_enrolled(
        request.user,
        course
    )

    if not is_enrolled:
        Enrollment.objects.create(
            user=request.user,
            course=course,
            mode='honor'
        )

        course.total_enrollment += 1
        course.save()

    return HttpResponseRedirect(
        reverse(
            'onlinecourse:course_details',
            args=(course.id,)
        )
    )


# Submit Exam Answers
@login_required
def submit(request, course_id):

    if request.method != 'POST':
        return HttpResponseRedirect(
            reverse(
                'onlinecourse:course_details',
                args=(course_id,)
            )
        )

    course = get_object_or_404(
        Course,
        pk=course_id
    )

    # Verify user enrollment
    enrollment = get_object_or_404(
        Enrollment,
        user=request.user,
        course=course
    )

    # Create one submission for the exam
    submission = Submission.objects.create(
        enrollment=enrollment
    )

    # Extract selected answers
    selected_ids = extract_answers(request)

    # Get valid choices belonging to this course
    valid_choices = Choice.objects.filter(
        id__in=selected_ids,
        question__course=course
    )

    # Save selected choices
    submission.choices.set(valid_choices)

    # Redirect to exam result
    return HttpResponseRedirect(
        reverse(
            'onlinecourse:exam_result',
            args=(course_id, submission.id)
        )
    )


# Extract Selected Answers
def extract_answers(request):
    submitted_answers = []

    for key in request.POST:
        if key.startswith('choice'):
            try:
                choice_id = int(request.POST[key])
                submitted_answers.append(choice_id)

            except (ValueError, TypeError):
                continue

    return submitted_answers


# Display Exam Result
@login_required
def show_exam_result(request, course_id, submission_id):

    course = get_object_or_404(
        Course,
        pk=course_id
    )

    # Verify submission belongs to the current user and course
    submission = get_object_or_404(
        Submission,
        id=submission_id,
        enrollment__course=course,
        enrollment__user=request.user
    )

    # Get selected choices
    selected_choices = submission.choices.all()

    # Get all questions for this course
    questions = course.question_set.all()

    total_score = 0
    max_score = 0

    # Calculate score question by question
    for question in questions:

        max_score += question.grade

        correct_ids = set(
            question.choice_set.filter(
                is_correct=True
            ).values_list('id', flat=True)
        )

        selected_ids = set(
            selected_choices.filter(
                question=question
            ).values_list('id', flat=True)
        )

        # Award marks only for the exact correct answer set
        if correct_ids == selected_ids:
            total_score += question.grade

    # Calculate percentage
    if max_score > 0:
        score_percent = (
            total_score / max_score
        ) * 100
    else:
        score_percent = 0

    # Prepare context for exam_result_bootstrap.html
    context = {
        'course': course,
        'grade': total_score,
        'max_score': max_score,
        'score_percent': round(score_percent, 2),
        'is_passed': score_percent >= 80,
        'choices': selected_choices,
        'questions': questions,
        'selected_choice_ids': list(
            selected_choices.values_list('id', flat=True)
        ),
    }

    return render(
        request,
        'onlinecourse/exam_result_bootstrap.html',
        context
    )
