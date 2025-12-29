from rest_framework import permissions


class IsStaffOrSindico(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.user.is_staff
            or request.user.groups.filter(name="Síndicos").exists()
        )
