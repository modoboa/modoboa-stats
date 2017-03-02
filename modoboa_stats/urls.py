"""Stats urls."""

from django.conf.urls import url

from . import views

urlpatterns = [
    url(r"^$", views.index, name="fullindex"),
    url(r"^graphs/$", views.graphs, name="graph_list"),
    url(r"^domains/$", views.get_domain_list, name="domain_list"),
]
