from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("login", views.login_view, name="login"),
    path("submit_post", views.post, name="submit_post"),
    path("logout", views.logout_view, name="logout"),
    path("register", views.register, name="register"),
    path("like_post/<str:server_id>/<str:like_post>", views.like, name="like_post"),
    path("edit/<str:edit_post>", views.edit, name="edit_post"),
    path(
        "unlike_post/<str:server_id>/<str:like_post>", views.unlike, name="unlike_post"
    ),
    path("follow/<str:server_id>/<str:username>", views.follow, name="follow"),
    path("unfollow/<str:server_id>/<str:username>", views.unfollow, name="unfollow"),
    path("user/<str:server_id>/<str:username>", views.user, name="user"),
    path("user/<str:server_id>/<str:username>/<int:page_num>", views.user, name="user"),
    path("all", views.all_posts, name="all"),
    path("following", views.following, name="following"),
    path("following/<int:page_num>", views.following, name="following"),
    path("all/<int:page_num>", views.all_posts, name="all"),
    path("federation/get_likes", views.federated_get_likes, name="federated_get_likes"),
    path("federation/posts", views.federated_posts, name="federated_posts"),
    path(
        "comment/<str:server_id>/<str:post_id>",
        views.comment,
        name="comment",
    ),
    path(
        "federation/comment/<str:post_id>",
        views.federated_comment,
        name="federated_comment",
    ),
    path(
        "federation/unlike/<str:post_id>",
        views.federated_unlike,
        name="federated_unlike",
    ),
    path(
        "federation/like/<str:post_id>",
        views.federated_like,
        name="federated_like",
    ),
    path("federation/add_servers", views.add_servers, name="add_servers"),
    path("federation/delete_server", views.delete_server, name="delete_server"),
    path("federation/block_server", views.block_server, name="block_server"),
    path(
        "federation/block_user/<str:server_id>/<str:username>",
        views.block_user,
        name="block_user",
    ),
    path(
        "federation/unblock_user/<str:server_id>/<str:username>",
        views.unblock_user,
        name="block_user",
    ),
    path(
        "federation/user/<str:username>",
        views.federated_user,
        name="federated_user",
    ),
    path("federation/unblock_server", views.unblock_server, name="unblock_server"),
    path("federation/rss", views.RSSFeed(), name="rss"),
    path("search", views.search, name="search"),
    path("search/<str:page_num>/", views.search, name="search"),
]
