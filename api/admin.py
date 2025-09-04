from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Course, Enrollment, CourseContent, StudentProgress

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('email', 'first_name', 'last_name', 'role', 'is_active', 'is_staff')
    list_filter = ('role', 'is_active', 'is_staff')
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('email',)
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'date_of_birth', 'phone_number', 'address')}),
        ('Permissions', {'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important Dates', {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'first_name', 'last_name', 'role'),
        }),
    )

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('title', 'instructor', 'start_date', 'end_date', 'is_active')
    list_filter = ('is_active', 'start_date', 'end_date')
    search_fields = ('title', 'description')
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Filter the instructor field to only show admin users
        if db_field.name == "instructor":
            kwargs["queryset"] = User.objects.filter(role='admin')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ('student', 'course', 'status', 'completion_percentage', 'grade', 'enrolled_at')
    list_filter = ('status', 'enrolled_at')
    search_fields = ('student__email', 'course__title')
    raw_id_fields = ('student', 'course')

@admin.register(CourseContent)
class CourseContentAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'content_type', 'order', 'is_active')
    list_filter = ('content_type', 'is_active')
    search_fields = ('title', 'course__title')
    raw_id_fields = ('course',)

@admin.register(StudentProgress)
class StudentProgressAdmin(admin.ModelAdmin):
    list_display = ('enrollment', 'content', 'is_completed', 'score', 'completed_at')
    list_filter = ('is_completed', 'completed_at')
    search_fields = ('enrollment__student__email', 'content__title')
    raw_id_fields = ('enrollment', 'content')