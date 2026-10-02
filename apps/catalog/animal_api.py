from drf_spectacular.utils import extend_schema
from rest_framework import generics, serializers
from rest_framework.response import Response

from apps.accounts.access import scoped_get
from apps.catalog.animal_services import (
    add_stay,
    create_animal,
    scoped_animals,
    scoped_stays,
    update_animal,
)
from apps.catalog.models import Animal, AnimalStay
from apps.common.errors import ErrorSerializer
from apps.common.serializers import StrictSerializer


class AnimalSerializer(serializers.ModelSerializer):
    species_id = serializers.UUIDField()

    class Meta:
        model = Animal
        fields = ("id", "code", "species_id", "sex", "name", "status")


class AnimalCreate(StrictSerializer):
    id = serializers.UUIDField()
    code = serializers.CharField(max_length=32)
    species_id = serializers.UUIDField()
    sex = serializers.ChoiceField(choices=Animal.Sex.choices)
    name = serializers.CharField(max_length=100, allow_blank=True, default="")
    status = serializers.ChoiceField(choices=Animal.Status.choices, default="ACTIVO")
    stay_id = serializers.UUIDField()
    center_id = serializers.UUIDField()
    starts_on = serializers.DateField()


class AnimalUpdate(StrictSerializer):
    name = serializers.CharField(max_length=100, allow_blank=True, required=False)
    status = serializers.ChoiceField(choices=Animal.Status.choices, required=False)


class StayInput(StrictSerializer):
    id = serializers.UUIDField()
    center_id = serializers.UUIDField()
    starts_on = serializers.DateField()
    ends_on = serializers.DateField(allow_null=True, default=None)


class StaySerializer(serializers.ModelSerializer):
    center_id = serializers.UUIDField()

    class Meta:
        model = AnimalStay
        fields = ("id", "center_id", "starts_on", "ends_on")


ERRORS = {
    401: ErrorSerializer,
    403: ErrorSerializer,
    404: ErrorSerializer,
    409: ErrorSerializer,
    422: ErrorSerializer,
}


class AnimalsView(generics.ListAPIView):
    serializer_class = AnimalSerializer

    def get_queryset(self):
        return scoped_animals(self.request.user).order_by("code", "id")

    @extend_schema(request=AnimalCreate, responses={200: AnimalSerializer, **ERRORS})
    def post(self, request):
        serializer = AnimalCreate(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(
            AnimalSerializer(create_animal(request.user, serializer.validated_data)).data
        )


class AnimalDetailView(generics.RetrieveAPIView):
    serializer_class = AnimalSerializer

    def get_queryset(self):
        return scoped_animals(self.request.user)

    @extend_schema(request=AnimalUpdate, responses={200: AnimalSerializer, **ERRORS})
    def patch(self, request, pk):
        serializer = AnimalUpdate(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(
            AnimalSerializer(update_animal(request.user, pk, serializer.validated_data)).data
        )


class StaysView(generics.ListAPIView):
    serializer_class = StaySerializer

    def get_queryset(self):
        animal = scoped_get(scoped_animals(self.request.user), pk=self.kwargs["pk"])
        return scoped_stays(self.request.user, animal)

    @extend_schema(request=StayInput, responses={200: StaySerializer, **ERRORS})
    def post(self, request, pk):
        serializer = StayInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(StaySerializer(add_stay(request.user, pk, serializer.validated_data)).data)
