from django.urls import path
from rest_framework.authtoken.views import obtain_auth_token

from . import views

urlpatterns = [
    path("login/", views.LoginView.as_view(), name="api_login"),
    path("logout/", views.LogoutView.as_view(), name="api_logout"),
    path("create/", views.UserCreateView.as_view(), name="create"),
    path("signup/", views.SignupView.as_view(), name="signup"),
    path(
        "check-username/<str:username>/",
        views.CheckUsernameView.as_view(),
        name="check-username",
    ),
    path(
        "change-password/",
        views.ChangePasswordView.as_view(),
        name="change-password",
    ),
    path("profile/", views.ProfileView.as_view(), name="profile"),
    path(
        "profile/<int:user_id>/",
        views.ProfileView.as_view(),
        name="update-user",
    ),
    path("api-token-auth/", obtain_auth_token, name="api_token_auth"),
    path("users/", views.UserListView.as_view(), name="user-list"),
    path(
        "users/simple/",
        views.UserSimpleListView.as_view(),
        name="user-simple-list",
    ),
    path("groups/", views.GroupListView.as_view(), name="group-list"),
    path(
        "groups/<int:group_id>/",
        views.GroupDetailView.as_view(),
        name="group-detail",
    ),
]
