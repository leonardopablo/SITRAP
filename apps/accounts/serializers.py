from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.accounts.access import active_assignments, capabilities, visible_locations
from apps.accounts.models import RoleAssignment, User
from apps.catalog.models import Location
from apps.common.serializers import StrictSerializer


class AssignmentSerializer(serializers.ModelSerializer):
    role = serializers.CharField(source="role_id")
    location_id = serializers.UUIDField(allow_null=True)

    class Meta:
        model = RoleAssignment
        fields = ("id", "role", "scope", "location_id", "starts_at", "ends_at")


class LocationSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = ("id", "code", "name", "kind")


class CapabilitySerializer(serializers.Serializer):
    code = serializers.CharField()
    location_id = serializers.UUIDField(allow_null=True)


class MeSerializer(serializers.ModelSerializer):
    assignments = serializers.SerializerMethodField()
    locations = serializers.SerializerMethodField()
    capabilities = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "name",
            "password_change_required",
            "assignments",
            "locations",
            "capabilities",
        )

    @extend_schema_field(AssignmentSerializer(many=True))
    def get_assignments(self, user):
        return AssignmentSerializer(active_assignments(user), many=True).data

    @extend_schema_field(LocationSummarySerializer(many=True))
    def get_locations(self, user):
        return LocationSummarySerializer(visible_locations(user), many=True).data

    @extend_schema_field(CapabilitySerializer(many=True))
    def get_capabilities(self, user):
        return CapabilitySerializer(capabilities(user), many=True).data


class LoginSerializer(StrictSerializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=1024)


class PasswordSerializer(StrictSerializer):
    old_password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=1024)
    new_password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=1024)


class CSRFSerializer(serializers.Serializer):
    csrf_token = serializers.CharField()
