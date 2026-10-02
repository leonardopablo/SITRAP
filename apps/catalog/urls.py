from django.urls import path

from apps.catalog.views import (
    CenterProductDetailView,
    CenterProductsView,
    LocationDetailView,
    LocationsView,
    ProductDetailView,
    ProductsView,
)

urlpatterns = [
    path("locations", LocationsView.as_view()),
    path("locations/<uuid:pk>", LocationDetailView.as_view()),
    path("products", ProductsView.as_view()),
    path("products/<uuid:pk>", ProductDetailView.as_view()),
    path("center-products", CenterProductsView.as_view()),
    path("center-products/<uuid:pk>", CenterProductDetailView.as_view()),
]
