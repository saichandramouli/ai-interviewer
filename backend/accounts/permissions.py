from rest_framework import permissions


class IsAdminUser(permissions.BasePermission):
    """
    Custom permission to only allow admin users (is_staff or is_superuser).
    """

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.is_staff or request.user.is_superuser)
        )


class IsRecruiterUser(permissions.BasePermission):
    """
    Custom permission to only allow recruiter users (not staff and not superuser).
    Admins are strictly denied access to operational recruiter endpoints.
    """

    message = "Only recruiter accounts can access recruitment operational resources."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and not request.user.is_staff
            and not request.user.is_superuser
        )
