from drf_spectacular.utils import extend_schema
from rest_framework import generics, serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.access import require_admin
from apps.accounts.admin_services import create_user, reset_password, save_assignment, update_user
from apps.accounts.authentication import ReadyAccount
from apps.accounts.models import Role, RoleAssignment, User
from apps.common.errors import ErrorSerializer
from apps.common.serializers import StrictSerializer


class AdminPermission(ReadyAccount):
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        require_admin(request.user)
        return True


class UserAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "name", "is_active", "password_change_required")
        read_only_fields = fields


class CreateUserSerializer(StrictSerializer):
    id = serializers.UUIDField()
    username = serializers.CharField(max_length=150)
    name = serializers.CharField(max_length=150)
    temporary_password = serializers.CharField(
        write_only=True, trim_whitespace=False, max_length=1024
    )


class UpdateUserSerializer(StrictSerializer):
    username = serializers.CharField(max_length=150, required=False)
    name = serializers.CharField(max_length=150, required=False)
    is_active = serializers.BooleanField(required=False)


class ResetPasswordSerializer(StrictSerializer):
    temporary_password = serializers.CharField(
        write_only=True, trim_whitespace=False, max_length=1024
    )


class RoleAssignmentAdminSerializer(serializers.ModelSerializer):
    user_id = serializers.UUIDField()
    role = serializers.CharField(source="role_id")
    location_id = serializers.UUIDField(allow_null=True)

    class Meta:
        model = RoleAssignment
        fields = ("id", "user_id", "role", "scope", "location_id", "starts_at", "ends_at")
        read_only_fields = fields


class CreateAssignmentSerializer(StrictSerializer):
    id = serializers.UUIDField()
    user_id = serializers.UUIDField()
    role = serializers.ChoiceField(source="role_id", choices=Role.Code.choices)
    scope = serializers.ChoiceField(choices=RoleAssignment.Scope.choices)
    location_id = serializers.UUIDField(allow_null=True)
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField(allow_null=True, default=None)


class UpdateAssignmentSerializer(StrictSerializer):
    # Historical role/user/location cannot silently change: close and create another assignment.
    ends_at = serializers.DateTimeField(allow_null=True)


ERRORS = {401: ErrorSerializer, 403: ErrorSerializer, 409: ErrorSerializer, 422: ErrorSerializer}


class UsersView(generics.ListAPIView):
    permission_classes = [AdminPermission]
    queryset = User.objects.order_by("username", "id")
    serializer_class = UserAdminSerializer

    @extend_schema(request=CreateUserSerializer, responses={200: UserAdminSerializer, **ERRORS})
    def post(self, request):
        serializer = CreateUserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(
            UserAdminSerializer(create_user(request.user, serializer.validated_data)).data
        )


class UserDetailView(APIView):
    permission_classes = [AdminPermission]

    @extend_schema(request=UpdateUserSerializer, responses={200: UserAdminSerializer, **ERRORS})
    def patch(self, request, pk):
        serializer = UpdateUserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(
            UserAdminSerializer(update_user(request.user, pk, serializer.validated_data)).data
        )


class ResetPasswordView(APIView):
    permission_classes = [AdminPermission]

    @extend_schema(request=ResetPasswordSerializer, responses={200: UserAdminSerializer, **ERRORS})
    def post(self, request, pk):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(
            UserAdminSerializer(
                reset_password(request.user, pk, serializer.validated_data["temporary_password"])
            ).data
        )


class AssignmentsView(generics.ListAPIView):
    permission_classes = [AdminPermission]
    queryset = RoleAssignment.objects.order_by("starts_at", "id")
    serializer_class = RoleAssignmentAdminSerializer

    @extend_schema(
        request=CreateAssignmentSerializer, responses={200: RoleAssignmentAdminSerializer, **ERRORS}
    )
    def post(self, request):
        serializer = CreateAssignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(
            RoleAssignmentAdminSerializer(
                save_assignment(request.user, serializer.validated_data)
            ).data
        )


class AssignmentDetailView(APIView):
    permission_classes = [AdminPermission]

    @extend_schema(
        request=UpdateAssignmentSerializer, responses={200: RoleAssignmentAdminSerializer, **ERRORS}
    )
    def patch(self, request, pk):
        serializer = UpdateAssignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(
            RoleAssignmentAdminSerializer(
                save_assignment(request.user, serializer.validated_data, pk)
            ).data
        )
