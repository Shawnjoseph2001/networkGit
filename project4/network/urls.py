from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("login", views.login_view, name="login"),
    path("submit_post", views.post, name="submit_post"),
    path("logout", views.logout_view, name="logout"),
    path("register", views.register, name="register"),
    path("like_post/<str:like_post>", views.like, name="like_post"),
    path("edit/<str:edit_post>", views.edit, name="edit_post"),
    path("unlike_post/<str:like_post>", views.unlike, name="unlike_post"),
    path("follow/<str:username>", views.follow, name="follow"),
    path("unfollow/<str:username>", views.unfollow, name="unfollow"),
    path("user/<str:username>", views.user_rd, name="user_rd"),
    path("user/<str:username>/<int:page_num>", views.user, name="user"),
    path("all", views.all_rd, name="all_rd"),
    path("following", views.follow_rd, name="follow_rd"),
    path("following/<int:page_num>", views.following, name="following"),
    path("all/<int:page_num>", views.all_posts, name="all"),
    path("federation/", views.federate, name="federate"),
    path(
        "comment/<str:post_id>",
        views.comment,
        name="comment",
    ),
    path(
        "federation/comment/<str:post_id>",
        views.federated_comment,
        name="federated_comment",
    ),
    path(
        "federation/like/<str:post_id>",
        views.federated_like,
        name="federated_comment",
    ),
    path("federation/add_servers", views.add_servers, name="add_servers"),
    path("federation/delete_server", views.delete_server, name="delete_server"),
    path("federation/block_server", views.block_server, name="block_server"),
    path("federation/unblock_server", views.unblock_server, name="unblock_server"),
]
