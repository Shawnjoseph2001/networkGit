import json

import requests
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import user_passes_test
from django.core.paginator import Paginator, Page
from django.db import IntegrityError
from django.http import HttpResponseRedirect
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt

from .models import (
    User,
    Follower,
    Post,
    ForeignLike,
    ForeignComment,
    ForeignServer,
    ForeignBlocklist,
)


def superuser_check(user_check):
    return user_check.is_superuser


def index(request):
    """Redirect to the 'all_rd' route."""
    return HttpResponseRedirect(reverse("all_rd"))


@login_required
def following(request, page_num):
    """
    Fetches and displays posts from users the current user is following.

    The function handles pagination and also provides information about liked posts and likes.
    """
    blocked_servers = []
    local_server = get_object_or_404(ForeignServer, ip="local")
    if request.user.is_authenticated:
        blocked_servers = ForeignBlocklist.objects.filter(
            user=request.user
        ).values_list("server", flat=True)
    # Query all users that the current user is following
    follow_query = Follower.objects.filter(following_user=request.user)

    # Extract relevant information from the follow query
    following_users = list(follow_query.values_list("following_user", flat=True))

    # Query posts from local following users
    following_posts = list(
        Post.objects.filter(user__in=following_users).order_by("-timestamp").values()
    )
    for i in following_posts:
        i["server_id"] = str(local_server.id)
        i["likes"] = len(ForeignLike.objects.filter(post__id=i["id"]))
        i["comments"] = list(ForeignComment.objects.filter(post__id=i["id"]).values())
        i["username"] = str(get_object_or_404(User, id=i["user_id"]).username)
        i["server_name"] = "local"
        i["server_port"] = ""
    foreign_posts = []
    for i in ForeignServer.objects.all():
        if i not in blocked_servers and i.ip != "local":
            try:
                result = requests.get(
                    "http://" + i.ip + ":" + str(i.port) + "/federation/posts",
                    timeout=5,
                )
                if result.status_code == 200:
                    json_data = json.loads(result.content)
                    for j in json_data["posts"]:
                        j["server_name"] = str(i.ip)
                        j["server_port"] = str(i.port)
                        j["server_id"] = str(i.id)
                foreign_posts += json_data["posts"]
            except:
                pass
    for i in foreign_posts:
        if Follower.objects.filter(
            following_user=request.user,
            followee_user=i["username"],
            server_id=i["server_id"],
        ).exists():
            following_posts.append(i)

    # Handle pagination
    paginator = Paginator(following_posts, 10)
    next_page = "0"
    prev_page = "0"
    if page_num > 1:
        prev_page = reverse("following", args=(page_num - 1,))
    if page_num < paginator.num_pages:
        next_page = reverse("following", args=(page_num + 1,))

    # Render the page
    return render(
        request,
        "network/index.html",
        {
            "posts": following_posts,
            "next_page": next_page,
            "prev_page": prev_page,
            "following_users": following_users,
            "server_id": str(get_object_or_404(ForeignServer, ip="local").id),
        },
    )


def all_rd(request):
    """Redirect to the first page of the 'all_rd' route."""
    return HttpResponseRedirect(reverse("all_rd") + "/1")


def follow_rd(request):
    """Redirect to the first page of the 'following' route."""
    return HttpResponseRedirect(reverse("following") + "/1")


def all_posts(request, page_num):
    """
    Fetches and displays all posts in the network, ordered by timestamp.

    This function also handles pagination and provides information about liked posts and likes.
    """
    following_users = []
    blocked_servers = []
    if request.user.is_authenticated:
        following_users = list(
            Follower.objects.filter(followee_user=request.user.username)
            .values_list("followee_user", flat=True)
            .values()
        )
        blocked_servers = ForeignBlocklist.objects.filter(
            user=request.user
        ).values_list("server", flat=True)

    # Query all posts and handle pagination
    local_server = get_object_or_404(ForeignServer, ip="local")
    # Count likes for each post
    post_list = list(Post.objects.all().order_by("-timestamp").values())
    for i in post_list:
        i["server_id"] = str(local_server.id)
        i["likes"] = len(ForeignLike.objects.filter(post__id=i["id"]))
        i["comments"] = list(ForeignComment.objects.filter(post__id=i["id"]).values())
        i["username"] = str(get_object_or_404(User, id=i["user_id"]).username)
        i["server_name"] = "local"
        i["server_port"] = ""
        i["liked"] = ForeignLike.objects.filter(
            user=request.user, server=local_server, post__id=i["id"]
        ).exists()
        if request.user.is_authenticated:
            i["following"] = Follower.objects.filter(
                following_user=request.user,
                followee_user=i["username"],
                server=local_server,
            ).exists()
        else:
            i["following"] = False
    for i in ForeignServer.objects.all():
        if i not in blocked_servers and i.ip != "local":
            try:
                result = requests.get(
                    "http://" + i.ip + ":" + str(i.port) + "/federation/posts",
                    timeout=5,
                )
                if result.status_code == 200:
                    json_data = json.loads(result.content)
                    for j in json_data["posts"]:
                        j["server_name"] = str(i.ip)
                        j["server_port"] = str(i.port)
                        j["server_id"] = str(i.id)
                        j["following"] = Follower.objects.filter(
                            following_user=request.user,
                            followee_user=j["username"],
                            server=i,
                        ).exists()
                        j["liked"] = ForeignLike.objects.filter(
                            user=request.user, server=i, post__id=j["id"]
                        ).exists()
                    post_list += json_data["posts"]
            except:
                pass

    paginator = Paginator(post_list, 10)
    posts: Page = paginator.get_page(page_num)

    # Handle pagination
    next_page = "0"
    prev_page = "0"
    if page_num > 1:
        prev_page = reverse("all", args=(page_num - 1,))
    if page_num < paginator.num_pages:
        next_page = reverse("all", args=(page_num + 1,))

    # Render the page
    return render(
        request,
        "network/index.html",
        {
            "posts": posts,
            "next_page": next_page,
            "prev_page": prev_page,
            "following_users": following_users,
            "server_id": str(get_object_or_404(ForeignServer, ip="local").id),
        },
    )


def login_view(request):
    if request.method == "POST":
        # Attempt to sign user in
        username = request.POST["username"]
        password = request.POST["password"]
        user = authenticate(request, username=username, password=password)

        # Check if authentication successful
        if user is not None:
            login(request, user)
            return HttpResponseRedirect(reverse("index"))
        else:
            return render(
                request,
                "network/login.html",
                {"message": "Invalid username and/or password."},
            )
    else:
        return render(request, "network/login.html")


def logout_view(request):
    logout(request)
    return HttpResponseRedirect(reverse("index"))


def register(request):
    if request.method == "POST":
        username = request.POST["username"]
        email = request.POST["email"]

        # Ensure password matches confirmation
        password = request.POST["password"]
        confirmation = request.POST["confirmation"]
        if password != confirmation:
            return render(
                request, "network/register.html", {"message": "Passwords must match."}
            )

        # Attempt to create new user
        try:
            user = User.objects.create_user(username, email, password)
            user.save()
        except IntegrityError:
            return render(
                request, "network/register.html", {"message": "Username already taken."}
            )
        login(request, user)
        return HttpResponseRedirect(reverse("index"))
    else:
        return render(request, "network/register.html")


@login_required
def post(request):
    """
    Creates a new post associated with the current user and redirects to the index page.
    """
    if request.method == "POST":
        Post.objects.create(content=request.POST["content"], user=request.user)
        return HttpResponseRedirect(reverse("index"))
    else:
        return render(request, "network/post.html")


def user(request, username, server_id, page_num):
    """Handles requests for a specific user's posts, along with their profile info"""
    print()
    server = get_object_or_404(ForeignServer, id=server_id)
    # Initialize variables for authenticated users
    user_following = False
    liked_posts = []
    if request.user.is_authenticated:
        user_following = Follower.objects.filter(
            following_user=request.user,
            followee_user=username,
            server=server,
        ).exists()
        liked_posts = list(
            ForeignLike.objects.filter(user=request.user).values_list(
                "post__id", flat=True
            )
        )
    followers = len(
        Follower.objects.filter(server__id=server_id, followee_user=username)
    )
    following_users: int
    posts: list
    if server.ip == "local":
        # TODO: Add block button
        # Fetch the requested user or return 404 if not found
        request_user = get_object_or_404(User, username=username)
        # Fetch the posts made by the requested user, ordered by timestamp
        posts = list(
            Post.objects.filter(user=request_user).order_by("-timestamp").values()
        )
        # Fetch the count of local followers and following users
        # The server is only aware of followers local to the host and dest servers
        followers += len(Follower.objects.filter(following_user=request_user))
        following_users = len(Follower.objects.filter(followee_user=request_user))
        # Count likes for each post
        for i in posts:
            i["likes"] = len(ForeignLike.objects.filter(post=i["id"]))
            i["username"] = request_user.username
    else:
        try:
            result = requests.get(
                url="http://"
                + server.ip
                + ":"
                + str(server.port)
                + "/federation/user/"
                + username,
                timeout=5,
                data=json.dumps({"port": request.META["SERVER_PORT"]}),
            )
            json_response = json.loads(result.content)
            followers += json_response["followers"]
            following_users = json_response["following_users"]
            posts = json_response["posts"]
        except:
            return HttpResponseRedirect(reverse("index"))
    # Handle pagination
    next_page = "0"
    prev_page = "0"
    paginator = Paginator(posts, 10)
    if page_num > 1:
        prev_page = reverse(
            "user",
            args=(
                username,
                server_id,
                page_num - 1,
            ),
        )
    if page_num < paginator.num_pages:
        next_page = reverse(
            "user",
            args=(
                username,
                server_id,
                page_num + 1,
            ),
        )
    # Render the profile page
    return render(
        request,
        "network/profile.html",
        {
            "posts": paginator.get_page(page_num),
            "username": username,
            "next_page": next_page,
            "prev_page": prev_page,
            "followers": followers,
            "following": following_users,
            "user_following": user_following,
            "liked_posts": liked_posts,
            "server_id": server_id,
            "local_server": server.ip == "local",
        },
    )


@csrf_exempt
@login_required
def like(request, like_post, server_id):
    """Handles like action for a post."""
    server = get_object_or_404(ForeignServer, id=server_id)
    if server.ip == "local":
        like_post = get_object_or_404(Post, id=like_post)
        if not ForeignLike.objects.filter(
            post=like_post, user=request.user, server=server
        ).exists():
            ForeignLike.objects.create(post=like_post, user=request.user, server=server)
            return JsonResponse(
                {
                    "likeCount": len(ForeignLike.objects.filter(post=like_post)),
                    "success": True,
                }
            )
        return JsonResponse(
            data={
                "likeCount": len(ForeignLike.objects.filter(post=like_post)),
                "success": False,
            }
        )
    else:
        try:
            result = requests.get(
                "http://"
                + server.ip
                + ":"
                + str(server.port)
                + "/federation/like/"
                + like_post,
                timeout=5,
            )
            if result.status_code == 200:
                return JsonResponse(json.loads(result.content))
            else:
                return JsonResponse(
                    {
                        "success": False,
                    }
                )
        except requests.exceptions.Timeout:
            return JsonResponse(
                {
                    "success": False,
                }
            )


@csrf_exempt
@login_required
def unlike(request, like_post, server_id):
    """Handles unlike action for a post."""
    server = get_object_or_404(ForeignServer, id=server_id)
    if server.ip == "local":
        like_post = get_object_or_404(Post, id=like_post)
        if ForeignLike.objects.filter(
            post=like_post, user=request.user, server=server
        ).exists():
            ForeignLike.objects.filter(
                post=like_post, user=request.user, server=server
            ).delete()
            return JsonResponse(
                {
                    "likeCount": len(ForeignLike.objects.filter(post=like_post)),
                    "success": True,
                }
            )
        return JsonResponse(
            data={
                "likeCount": len(ForeignLike.objects.filter(post=like_post)),
                "success": False,
            }
        )
    else:
        try:
            result = requests.get(
                "http://"
                + server.ip
                + ":"
                + str(server.port)
                + "/federation/unlike/"
                + like_post,
                timeout=5,
            )
            if result.status_code == 200:
                return JsonResponse(json.loads(result.content))
            else:
                return JsonResponse(
                    {
                        "success": False,
                    }
                )
        except requests.exceptions.Timeout:
            return JsonResponse(
                {
                    "success": False,
                }
            )


@csrf_exempt
@login_required
def edit(request, edit_post):
    """Handles editing a post by the current authenticated user."""
    edit_post = get_object_or_404(Post, id=edit_post)
    if request.method == "POST" and request.user == edit_post.user:
        json_data = json.loads(request.body)
        edit_post.content = json_data["content"]
        edit_post.save()
    return JsonResponse({"content": edit_post.content})


@login_required
def follow(request, username, server_id):
    """Allows the current user to follow another user."""
    Follower.objects.get_or_create(
        following_user=request.user,
        followee_user=username,
        server=get_object_or_404(ForeignServer, id=server_id),
    )
    return HttpResponseRedirect(reverse("index"))


@login_required
def unfollow(request, username, server_id):
    """Allows the current user to unfollow another user."""
    follower_to_delete = get_object_or_404(
        Follower,
        following_user=request.user,
        followee_user=username,
        server=get_object_or_404(ForeignServer, id=server_id),
    )
    follower_to_delete.delete()
    return HttpResponseRedirect(reverse("index"))


def user_rd(request, username, server_id):
    """User redirect"""
    return redirect(
        "user",
        username=username,
        server_id=server_id,
        page_num=1,
    )


@login_required
def comment(request, post_id, server_id):
    """Create post comment"""
    if request.method == "POST":
        server = get_object_or_404(ForeignServer, id=server_id)
        if server_id == "local":
            ForeignComment.objects.create(
                content=request.POST["content"],
                user=request.user,
                post=get_object_or_404(Post, id=post_id),
                server=server,
            )
        else:
            try:
                requests.post(
                    "http://"
                    + server.ip
                    + ":"
                    + server.port
                    + "/federation/comment/"
                    + post_id,
                    timeout=5,
                    data=json.dumps(
                        {
                            "username": request.user.username,
                            "content": request.POST["content"],
                        }
                    ),
                )
            except requests.exceptions.Timeout:
                return HttpResponseRedirect(reverse("index"))
    return HttpResponseRedirect(reverse("index"))


@csrf_exempt
def federated_comment(request, post_id):
    if request.method == "POST":
        json_data = json.loads(request.body)
        createdComment = ForeignComment.objects.create(
            content=json_data["content"],
            user=json_data["username"],
            post=get_object_or_404(Post, id=post_id),
            server=get_object_or_404(
                ForeignServer, server=request.get_host(), port=json_data["port"]
            ),
        )
        return JsonResponse({"Comment": createdComment})
    return JsonResponse({})


@csrf_exempt
def federated_like(request, post_id):
    if request.method == "POST":
        json_data = json.loads(request.body)
        server = get_object_or_404(
            ForeignServer, ip=request.get_host(), port=json_data["port"]
        )
        if ForeignLike.objects.filter(
            server=server,
            username=json_data["username"],
            post=get_object_or_404(Post, id=post_id),
        ).exists():
            ForeignLike.objects.create(
                server=server,
                username=json_data["username"],
                post=get_object_or_404(Post, id=post_id),
            )
            return JsonResponse(
                {
                    "likeCount": len(ForeignLike.objects.filter(post__id=post_id)),
                    "success": True,
                }
            )
        return JsonResponse(
            {
                "likeCount": len(ForeignLike.objects.filter(post__id=post_id)),
                "success": False,
            }
        )


@csrf_exempt
def federated_get_likes(request):
    server = get_object_or_404(
        ForeignServer, ip=request.get_host(), port=request.get_port()
    )
    likes = ForeignLike.objects.filter(server=server)
    return JsonResponse({"Likes": likes})


@csrf_exempt
def federated_unlike(request, post_id):
    if request.method == "POST":
        json_data = json.loads(request.body)
        server = get_object_or_404(
            ForeignServer, ip=request.get_host(), port=json_data["port"]
        )
        if not ForeignLike.objects.filter(
            server=server,
            username=json_data["username"],
            post=get_object_or_404(Post, id=post_id),
        ).exists():
            ForeignLike.objects.filter(
                server=server,
                username=json_data["username"],
                post=get_object_or_404(Post, id=post_id),
            ).delete()
            return JsonResponse(
                {
                    "likeCount": len(ForeignLike.objects.filter(post__id=post_id)),
                    "success": True,
                }
            )
        return JsonResponse(
            {
                "likeCount": len(ForeignLike.objects.filter(post__id=post_id)),
                "success": False,
            }
        )


@login_required
def add_servers(request):
    if request.method == "POST" and request.user.is_superuser:
        ForeignServer.objects.get_or_create(
            ip=request.POST["ip"], port=request.POST["port"]
        )
        return HttpResponseRedirect(reverse("add_servers"))
    return render(
        request,
        "network/server.html",
        {
            "servers": ForeignServer.objects.all(),
            "blocklist": ForeignBlocklist.objects.filter(user=request.user).values_list(
                "server", flat=True
            ),
            "server_id": get_object_or_404(ForeignServer, ip="local").id,
        },
    )


@user_passes_test(superuser_check)
def delete_server(request):
    if request.method == "POST":
        ForeignServer.objects.filter(
            ip=request.POST["ip"], port=request.POST["port"]
        ).delete()
    return HttpResponseRedirect(reverse("add_servers"))


@login_required
def block_server(request):
    if request.method == "POST":
        ForeignBlocklist.objects.get_or_create(
            server=get_object_or_404(
                ForeignServer, ip=request.POST["ip"], port=request.POST["port"]
            ),
            user=request.user,
        )
    return HttpResponseRedirect(reverse("add_servers"))


@login_required
def unblock_server(request):
    if request.method == "POST":
        server_to_delete = get_object_or_404(
            ForeignBlocklist,
            server=get_object_or_404(
                ForeignServer, ip=request.POST["ip"], port=request.POST["port"]
            ),
            user=request.user,
        )
        server_to_delete.delete()
    return HttpResponseRedirect(reverse("add_servers"))


@csrf_exempt
def federated_user(request, username):
    user = get_object_or_404(User, username=username)
    request_user = get_object_or_404(User, username=username)
    # Fetch the posts made by the requested user, ordered by timestamp
    posts = list(Post.objects.filter(user=request_user).order_by("-timestamp").values())
    # Fetch the count of local followers and following users
    followers = len(Follower.objects.filter(following_user=request_user))
    following_users = len(Follower.objects.filter(followee_user=request_user))
    # Count likes for each post
    for i in posts:
        i["likes"] = len(ForeignLike.objects.filter(post=i["id"]))
        i["username"] = request_user.username
    return JsonResponse(
        {
            "username": username,
            "posts": posts,
            "followers": followers,
            "following_users": following_users,
        }
    )


@csrf_exempt
def federated_posts(request):
    post_list = list(Post.objects.all().order_by("-timestamp").values())
    for i in post_list:
        i["likes"] = len(ForeignLike.objects.filter(post__id=i["id"]))
        i["comments"] = list(ForeignComment.objects.filter(post__id=i["id"]).values())
        i["username"] = str(get_object_or_404(User, id=i["user_id"]).username)
    return JsonResponse({"posts": post_list})
