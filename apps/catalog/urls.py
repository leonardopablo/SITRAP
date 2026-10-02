from django.urls import path

from apps.catalog.views import (
    CenterProductDetailView,
    CenterProductsView,
    LocationDetailView,
    LocationsView,
    PresentationDetailView,
    PresentationsView,
    ProductDetailView,
    ProductsView,
    SpeciesDetailView,
    SpeciesView,
    TurnDetailView,
    TurnsView,
    UnitDetailView,
    UnitsView,
)

urlpatterns = [
    path("locations", LocationsView.as_view()),
    path("locations/<uuid:pk>", LocationDetailView.as_view()),
    path("products", ProductsView.as_view()),
    path("products/<uuid:pk>", ProductDetailView.as_view()),
    path("center-products", CenterProductsView.as_view()),
    path("center-products/<uuid:pk>", CenterProductDetailView.as_view()),
]

urlpatterns += [
    path("units", UnitsView.as_view()),
    path("units/<str:pk>", UnitDetailView.as_view()),
    path("presentations", PresentationsView.as_view()),
    path("presentations/<uuid:pk>", PresentationDetailView.as_view()),
    path("species", SpeciesView.as_view()),
    path("species/<uuid:pk>", SpeciesDetailView.as_view()),
    path("turns", TurnsView.as_view()),
    path("turns/<uuid:pk>", TurnDetailView.as_view()),
]
