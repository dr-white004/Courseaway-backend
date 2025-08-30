from rest_framework import status, viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Count, Avg
from django.shortcuts import get_object_or_404

from .models import User, Course, Enrollment, CourseContent, StudentProgress
from .serializers import (
    UserRegistrationSerializer, UserLoginSerializer, UserSerializer,
    CourseSerializer, EnrollmentSerializer, CourseContentSerializer,
    StudentProgressSerializer, EnrollmentWithProgressSerializer
)
from .permissions import IsAdmin, IsStudent, IsAdminOrReadOnly, IsOwnerOrAdmin

class AuthViewSet(viewsets.GenericViewSet):
    permission_classes = [AllowAny]
    
    @action(detail=False, methods=['post'])
    def register(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            # Allow admin registration with secret code
            data = serializer.validated_data.copy()
            
            # If user is trying to register as admin
            if 'admin_secret' in request.data and request.data['admin_secret']:
                from django.conf import settings
                if request.data['admin_secret'] == settings.ADMIN_REGISTRATION_SECRET:
                    data['role'] = 'admin'
                else:
                    return Response(
                        {'error': 'Invalid admin registration secret'}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            user = serializer.save()
            refresh = RefreshToken.for_user(user)
            return Response({
                'user': UserSerializer(user).data,
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def login(self, request):
        serializer = UserLoginSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            user = serializer.validated_data['user']
            refresh = RefreshToken.for_user(user)
            return Response({
                'user': UserSerializer(user).data,
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAdmin]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    search_fields = ['email', 'first_name', 'last_name']
    
    def get_queryset(self):
        if self.request.user.role == 'admin':
            return User.objects.all()
        return User.objects.filter(id=self.request.user.id)
    
    def get_permissions(self):
        if self.action in ['retrieve', 'update', 'partial_update']:
            return [IsOwnerOrAdmin()]
        return [IsAdmin()]

class CourseViewSet(viewsets.ModelViewSet):
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['instructor', 'is_active']
    search_fields = ['title', 'description']
    
    @action(detail=True, methods=['get'])
    def enrollments(self, request, pk=None):
        course = self.get_object()
        enrollments = Enrollment.objects.filter(course=course)
        serializer = EnrollmentSerializer(enrollments, many=True)
        return Response(serializer.data)

class EnrollmentViewSet(viewsets.ModelViewSet):
    queryset = Enrollment.objects.all()
    serializer_class = EnrollmentSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['student', 'course', 'status']
    
    def get_queryset(self):
        if self.request.user.role == 'admin':
            return Enrollment.objects.all()
        return Enrollment.objects.filter(student=self.request.user)
    
    def create(self, request, *args, **kwargs):
        # Students can only enroll themselves
        if 'student' in request.data and request.data['student'] != request.user.id:
            if request.user.role != 'admin':
                return Response({'error': 'You can only enroll yourself'}, 
                              status=status.HTTP_403_FORBIDDEN)
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Check if enrollment already exists
        student_id = serializer.validated_data['student'].id
        course_id = serializer.validated_data['course'].id
        if Enrollment.objects.filter(student_id=student_id, course_id=course_id).exists():
            return Response({'error': 'Already enrolled in this course'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
    
    @action(detail=True, methods=['put'])
    def update_progress(self, request, pk=None):
        enrollment = self.get_object()
        
        # Check permissions
        if not (request.user.role == 'admin' or enrollment.student == request.user):
            return Response({'error': 'Permission denied'}, 
                          status=status.HTTP_403_FORBIDDEN)
        
        completion_percentage = request.data.get('completion_percentage')
        grade = request.data.get('grade')
        
        if completion_percentage is not None:
            try:
                completion_percentage = float(completion_percentage)
                if completion_percentage < 0 or completion_percentage > 100:
                    return Response({'error': 'Completion percentage must be between 0 and 100'}, 
                                  status=status.HTTP_400_BAD_REQUEST)
                enrollment.completion_percentage = completion_percentage
            except (ValueError, TypeError):
                return Response({'error': 'Invalid completion percentage'}, 
                              status=status.HTTP_400_BAD_REQUEST)
        
        if grade is not None:
            try:
                grade = float(grade)
                if grade < 0 or grade > 100:
                    return Response({'error': 'Grade must be between 0 and 100'}, 
                                  status=status.HTTP_400_BAD_REQUEST)
                enrollment.grade = grade
            except (ValueError, TypeError):
                return Response({'error': 'Invalid grade'}, 
                              status=status.HTTP_400_BAD_REQUEST)
        
        enrollment.save()
        return Response(EnrollmentSerializer(enrollment).data)
    
    @action(detail=False, methods=['get'])
    def student_enrollments(self, request):
        student_id = request.query_params.get('student_id')
        
        if student_id and request.user.role == 'admin':
            enrollments = Enrollment.objects.filter(student_id=student_id)
        else:
            enrollments = Enrollment.objects.filter(student=request.user)
        
        serializer = EnrollmentWithProgressSerializer(enrollments, many=True)
        return Response(serializer.data)
    

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        enrollment = self.get_object()
        
        # Check if user is the course instructor or admin
        if not (request.user.role == 'admin' or enrollment.course.instructor == request.user):
            return Response({'error': 'Permission denied'}, 
                          status=status.HTTP_403_FORBIDDEN)
        
        enrollment.status = 'approved'
        enrollment.save()
        
        return Response(EnrollmentSerializer(enrollment).data)
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        enrollment = self.get_object()
        
        # Check if user is the course instructor or admin
        if not (request.user.role == 'admin' or enrollment.course.instructor == request.user):
            return Response({'error': 'Permission denied'}, 
                          status=status.HTTP_403_FORBIDDEN)
        
        enrollment.status = 'rejected'
        enrollment.save()
        
        return Response(EnrollmentSerializer(enrollment).data)
    
    @action(detail=False, methods=['get'])
    def pending_approvals(self, request):
        # Only instructors and admins can see pending approvals
        if not (request.user.role == 'admin'):
            return Response({'error': 'Permission denied'}, 
                          status=status.HTTP_403_FORBIDDEN)
        
        # Get courses taught by this instructor
        courses = Course.objects.filter(instructor=request.user)
        enrollments = Enrollment.objects.filter(
            course__in=courses, 
            status='pending'
        )
        
        serializer = EnrollmentSerializer(enrollments, many=True)
        return Response(serializer.data)

class CourseContentViewSet(viewsets.ModelViewSet):
    queryset = CourseContent.objects.all()
    serializer_class = CourseContentSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['course', 'content_type', 'is_active']
    
    def get_queryset(self):
        queryset = CourseContent.objects.all()
        
        # Admins can see all content
        if self.request.user.role == 'admin':
            return queryset
        
        # Instructors can see content for their courses
        if self.request.user.role == 'admin':  # Using admin role for instructors
            return queryset.filter(course__instructor=self.request.user)
        
        # Students can only see content for approved enrollments
        return queryset.filter(
            course__enrollment__student=self.request.user,
            course__enrollment__status='approved',
            is_active=True
        )

class StudentProgressViewSet(viewsets.ModelViewSet):
    queryset = StudentProgress.objects.all()
    serializer_class = StudentProgressSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
    
    def get_queryset(self):
        if self.request.user.role == 'admin':
            return StudentProgress.objects.all()
        
        return StudentProgress.objects.filter(
            enrollment__student=self.request.user,
            enrollment__status='approved'
        )
    
    def create(self, request, *args, **kwargs):
        enrollment_id = request.data.get('enrollment')
        content_id = request.data.get('content')
        
        # Check if enrollment is approved
        try:
            enrollment = Enrollment.objects.get(id=enrollment_id)
            if enrollment.status != 'approved':
                return Response(
                    {'error': 'Enrollment not approved'}, 
                    status=status.HTTP_403_FORBIDDEN
                )
        except Enrollment.DoesNotExist:
            return Response(
                {'error': 'Enrollment not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if progress already exists
        if StudentProgress.objects.filter(enrollment_id=enrollment_id, content_id=content_id).exists():
            return Response({'error': 'Progress already recorded for this content'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        return super().create(request, *args, **kwargs)
    
    @action(detail=False, methods=['get'])
    def course_progress(self, request):
        course_id = request.query_params.get('course_id')
        student_id = request.query_params.get('student_id')
        
        if not course_id:
            return Response({'error': 'course_id parameter is required'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        # Admin can view any student's progress, students can only view their own
        if student_id and request.user.role == 'admin':
            enrollments = Enrollment.objects.filter(course_id=course_id, student_id=student_id)
        else:
            enrollments = Enrollment.objects.filter(course_id=course_id, student=request.user)
        
        if not enrollments.exists():
            return Response({'error': 'No enrollment found for this course'}, 
                          status=status.HTTP_404_NOT_FOUND)
        
        enrollment = enrollments.first()
        progress = StudentProgress.objects.filter(enrollment=enrollment)
        
        # Calculate overall progress
        total_contents = CourseContent.objects.filter(course_id=course_id, is_active=True).count()
        completed_contents = progress.filter(is_completed=True).count()
        
        overall_progress = {
            'total_contents': total_contents,
            'completed_contents': completed_contents,
            'completion_percentage': (completed_contents / total_contents * 100) if total_contents > 0 else 0
        }
        
        serializer = self.get_serializer(progress, many=True)
        return Response({
            'overall_progress': overall_progress,
            'detailed_progress': serializer.data
        })
