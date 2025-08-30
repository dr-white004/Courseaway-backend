from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'auth', views.AuthViewSet, basename='auth')
router.register(r'users', views.UserViewSet, basename='user')
router.register(r'courses', views.CourseViewSet, basename='course')
router.register(r'enrollments', views.EnrollmentViewSet, basename='enrollment')
router.register(r'contents', views.CourseContentViewSet, basename='content')
router.register(r'progress', views.StudentProgressViewSet, basename='progress')

urlpatterns = [
    path('', include(router.urls)),
]