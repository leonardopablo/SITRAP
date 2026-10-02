from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics
from rest_framework.response import Response

from apps.accounts.access import require_admin
from apps.catalog.models import CenterProduct, Location, Presentation, Product, Species, Turn, Unit
from apps.catalog.serializers import (
    CenterProductInput,
    LocationInput,
    PresentationInput,
    ProductInput,
    SpeciesInput,
    TurnInput,
    UnitInput,
)
from apps.catalog.services import (
    save_catalog,
    scoped_auxiliary,
    scoped_center_products,
    scoped_locations,
    scoped_presentations,
    scoped_products,
    scoped_units,
)
from apps.common.errors import ErrorSerializer


class CatalogListView(generics.ListAPIView):
    model = None
    scope = None
    immutable = ()

    def get_queryset(self):
        return self.scope(self.request.user).order_by("pk")

    def post(self, request):
        require_admin(request.user)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        obj = save_catalog(
            request.user, self.model, serializer.validated_data, immutable=self.immutable
        )
        return Response(self.get_serializer(obj).data)


class CatalogDetailView(generics.GenericAPIView):
    model = None
    immutable = ()

    def patch(self, request, pk):
        require_admin(request.user)
        serializer = self.get_serializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        obj = save_catalog(
            request.user, self.model, serializer.validated_data, pk=pk, immutable=self.immutable
        )
        return Response(self.get_serializer(obj).data)


class LocationsView(CatalogListView):
    model = Location
    serializer_class = LocationInput
    scope = staticmethod(scoped_locations)


class LocationDetailView(CatalogDetailView):
    model = Location
    serializer_class = LocationInput
    immutable = ("code", "kind")


class ProductsView(CatalogListView):
    model = Product
    serializer_class = ProductInput
    scope = staticmethod(scoped_products)


class ProductDetailView(CatalogDetailView):
    model = Product
    serializer_class = ProductInput
    immutable = ("code", "unit_id")


class CenterProductsView(CatalogListView):
    model = CenterProduct
    serializer_class = CenterProductInput
    scope = staticmethod(scoped_center_products)


class CenterProductDetailView(CatalogDetailView):
    model = CenterProduct
    serializer_class = CenterProductInput
    immutable = ("center_id", "product_id")


# Decorate each view class separately to avoid sharing annotations on inherited methods.
for view in (LocationsView, ProductsView, CenterProductsView):
    extend_schema_view(
        post=extend_schema(
            request=view.serializer_class,
            responses={
                200: view.serializer_class,
                401: ErrorSerializer,
                403: ErrorSerializer,
                409: ErrorSerializer,
                422: ErrorSerializer,
            },
        )
    )(view)
for view in (LocationDetailView, ProductDetailView, CenterProductDetailView):
    extend_schema_view(
        patch=extend_schema(
            request=view.serializer_class,
            responses={
                200: view.serializer_class,
                401: ErrorSerializer,
                403: ErrorSerializer,
                404: ErrorSerializer,
                422: ErrorSerializer,
            },
        )
    )(view)


class UnitsView(CatalogListView):
    model = Unit
    serializer_class = UnitInput
    scope = staticmethod(scoped_units)


class UnitDetailView(CatalogDetailView):
    model = Unit
    serializer_class = UnitInput
    immutable = ("code",)


class PresentationsView(CatalogListView):
    model = Presentation
    serializer_class = PresentationInput
    scope = staticmethod(scoped_presentations)


class PresentationDetailView(CatalogDetailView):
    model = Presentation
    serializer_class = PresentationInput
    immutable = ("product_id", "content_base", "allows_fraction")


class SpeciesView(CatalogListView):
    model = Species
    serializer_class = SpeciesInput
    scope = staticmethod(lambda user: scoped_auxiliary(user, Species))


class SpeciesDetailView(CatalogDetailView):
    model = Species
    serializer_class = SpeciesInput
    immutable = ("code",)


class TurnsView(CatalogListView):
    model = Turn
    serializer_class = TurnInput
    scope = staticmethod(lambda user: scoped_auxiliary(user, Turn))


class TurnDetailView(CatalogDetailView):
    model = Turn
    serializer_class = TurnInput
    immutable = ("code",)


for view in (UnitsView, PresentationsView, SpeciesView, TurnsView):
    extend_schema_view(
        post=extend_schema(
            request=view.serializer_class,
            responses={
                200: view.serializer_class,
                401: ErrorSerializer,
                403: ErrorSerializer,
                409: ErrorSerializer,
                422: ErrorSerializer,
            },
        )
    )(view)
for view in (UnitDetailView, PresentationDetailView, SpeciesDetailView, TurnDetailView):
    extend_schema_view(
        patch=extend_schema(
            request=view.serializer_class,
            responses={
                200: view.serializer_class,
                401: ErrorSerializer,
                403: ErrorSerializer,
                404: ErrorSerializer,
                422: ErrorSerializer,
            },
        )
    )(view)
