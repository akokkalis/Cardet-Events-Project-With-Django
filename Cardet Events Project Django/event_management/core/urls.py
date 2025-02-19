from django.urls import path
from .views import (
    login_view,
    logout_view,
    event_list,
    event_create,
    event_edit,
    event_delete,
    event_detail,
)

urlpatterns = [
    path("", login_view, name="home"),
    path("login/", login_view, name="login"),
    path("logout/", logout_view, name="logout"),
    path("events/", event_list, name="event_list"),
    path("events/new/", event_create, name="event_create"),
    path("events/edit/<int:event_id>/", event_edit, name="event_edit"),
    path("delete/<int:event_id>/", event_delete, name="event_delete"),
    path("events/<int:event_id>/", event_detail, name="event_detail"),
]
