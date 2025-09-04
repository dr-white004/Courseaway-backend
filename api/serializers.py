from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import User, Course, Enrollment, CourseContent, StudentProgress

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)
    admin_secret = serializers.CharField(write_only=True, required=False, allow_blank=True)
    
    class Meta:
        model = User
        fields = ('id', 'email', 'password', 'first_name', 'last_name', 'role', 
                 'date_of_birth', 'phone_number', 'address', 'admin_secret')
        extra_kwargs = {
            'password': {'write_only': True},
            'role': {'read_only': True}
        }
    
    def validate(self, data):
        # Check if admin secret is provided and correct
        admin_secret = data.get('admin_secret')
        if admin_secret:
            from django.conf import settings
            if admin_secret == settings.ADMIN_REGISTRATION_SECRET:
                # Secret is correct - mark this as an admin registration
                data['is_admin'] = True
            else:
                raise serializers.ValidationError(
                    {'admin_secret': 'Invalid admin registration secret code'}
                )
        
        return data
    
    def create(self, validated_data):
        # Check if this is an admin registration
        is_admin = validated_data.pop('is_admin', False)
        
        # Remove admin_secret from validated_data before creating user
        validated_data.pop('admin_secret', None)
        
        # Set role based on whether admin secret was provided and correct
        validated_data['role'] = 'admin' if is_admin else 'student'
        
        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            role=validated_data['role'],
            date_of_birth=validated_data.get('date_of_birth'),
            phone_number=validated_data.get('phone_number', ''),
            address=validated_data.get('address', '')
        )
        return user

class UserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    
    def validate(self, data):
        email = data.get('email')
        password = data.get('password')
        
        if email and password:
            user = authenticate(request=self.context.get('request'), 
                               email=email, password=password)
            if not user:
                raise serializers.ValidationError('Invalid credentials')
        else:
            raise serializers.ValidationError('Must include email and password')
        
        data['user'] = user
        return data

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'email', 'first_name', 'last_name', 'role', 
                 'date_of_birth', 'phone_number', 'address')
        read_only_fields = ('id', 'email', 'role')

class CourseSerializer(serializers.ModelSerializer):
    instructor_name = serializers.CharField(source='instructor.get_full_name', read_only=True)
    
    class Meta:
        model = Course
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at')

class EnrollmentSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.get_full_name', read_only=True)
    course_title = serializers.CharField(source='course.title', read_only=True)
    
    class Meta:
        model = Enrollment
        fields = '__all__'
        read_only_fields = ('id', 'enrolled_at')

class CourseContentSerializer(serializers.ModelSerializer):
    class Meta:
        model = CourseContent
        fields = '__all__'
        read_only_fields = ('id', 'created_at')

class StudentProgressSerializer(serializers.ModelSerializer):
    content_title = serializers.CharField(source='content.title', read_only=True)
    
    class Meta:
        model = StudentProgress
        fields = '__all__'
        read_only_fields = ('id',)

class EnrollmentWithProgressSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.get_full_name', read_only=True)
    course_title = serializers.CharField(source='course.title', read_only=True)
    progress_details = StudentProgressSerializer(source='progress', many=True, read_only=True)
    
    class Meta:
        model = Enrollment
        fields = '__all__'