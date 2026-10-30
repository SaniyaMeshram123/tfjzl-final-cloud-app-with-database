
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

        user_exist = User.objects.filter(username=username).exists()

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

        user = authenticate(username=username, password=password)

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

        courses = Course.objects.order_by('-total_enrollment')[:10]

        for course in courses:
            course.is_enrolled = check_if_enrolled(user, course)

        return courses


# Course Detail View
class CourseDetailView(generic.DetailView):
    model = Course
    template_name = 'onlinecourse/course_details_bootstrap.html'


# Enroll in a Course
@login_required
def enroll(request, course_id):
    course = get_object_or_404(Course, pk=course_id)

    is_enrolled = check_if_enrolled(request.user, course)

    if not is_enrolled:
        Enrollment.objects.create(
            user=request.user,
            course=course,
            mode='honor'
        )

        course.total_enrollment += 1
        course.save()

    return HttpResponseRedirect(
        reverse('onlinecourse:course_details', args=(course.id,))
    )


# Submit Exam Answers
@login_required
def submit(request, course_id):

    if request.method != 'POST':
        return HttpResponseRedirect(
            reverse('onlinecourse:course_details', args=(course_id,))
        )

    course = get_object_or_404(Course, pk=course_id)

    enrollment = get_object_or_404(
        Enrollment,
        user=request.user,
        course=course
    )

    submission = Submission.objects.create(
        enrollment=enrollment
    )

    selected_ids = extract_answers(request)

    selected_choices = Choice.objects.filter(
        id__in=selected_ids,
        question__course=course
    )

    submission.choices.set(selected_choices)

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

    course = get_object_or_404(Course, pk=course_id)

    submission = get_object_or_404(
        Submission,
        id=submission_id,
        enrollment__course=course,
        enrollment__user=request.user
    )

    selected_ids = list(
        submission.choices.values_list('id', flat=True)
    )

    questions = course.question_set.all()

    total_score = 0

    for question in questions:
        if question.is_get_score(selected_ids):
            total_score += question.grade

    possible = sum(
        question.grade for question in questions
    )

    if possible > 0:
        score_percent = (total_score / possible) * 100
    else:
        score_percent = 0

    context = {
        'course': course,
        'grade': total_score,
        'questions': questions,
        'selected_ids': selected_ids,
        'possible': possible,
        'max_score': possible,
        'score_percent': round(score_percent, 2),
        'is_passed': score_percent >= 80,
        'choices': submission.choices.all(),
        'selected_choice_ids': selected_ids,
    }

    return render(
        request,
        'onlinecourse/exam_result_bootstrap.html',
        context
    )
