from django.contrib import admin
from accounts.models import User, RecruiterInvitation


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('email', 'first_name', 'last_name', 'is_staff', 'is_superuser', 'is_active', 'date_joined')
    search_fields = ('email', 'first_name', 'last_name')
    list_filter = ('is_staff', 'is_superuser', 'is_active')


@admin.register(RecruiterInvitation)
class RecruiterInvitationAdmin(admin.ModelAdmin):
    list_display = ('email', 'status', 'created_by', 'created_at', 'expires_at', 'used_at', 'is_revoked')
    search_fields = ('email', 'created_by__email')
    list_filter = ('is_revoked',)
    readonly_fields = ('token_hash', 'created_at', 'used_at')
