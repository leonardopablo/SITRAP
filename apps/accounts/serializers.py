from rest_framework import serializers

from apps.accounts.models import RoleAssignment, User
from apps.common.serializers import StrictSerializer


class AssignmentSerializer(serializers.ModelSerializer):
    role = serializers.CharField(source="role_id")
    location_id = serializers.UUIDField(allow_null=True)

    class Meta:
        model = RoleAssignment
        fields = ("id", "role", "scope", "location_id", "starts_at", "ends_at")


class MeSerializer(serializers.ModelSerializer):
    assignments = AssignmentSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = ("id", "username", "name", "password_change_required", "assignments")


class LoginSerializer(StrictSerializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=1024)


class PasswordSerializer(StrictSerializer):
    old_password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=1024)
    new_password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=1024)


class CSRFSerializer(serializers.Serializer):
    csrf_token = serializers.CharField()
