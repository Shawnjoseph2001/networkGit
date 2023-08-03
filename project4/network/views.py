import datetime
import json
import time

import requests
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import user_passes_test
from django.contrib.syndication.views import Feed
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
    ForeignUserBlocklist,
)


def superuser_check(user_check):
    return user_check.is_superuser


def index(request):
    """Redirect to the 'all_rd' route."""
    return HttpResponseRedirect(reverse("all"))


@login_required
def following(request, page_num):
    return render_index(request, "following", following_only=True, page_num=page_num)


def render_index(
    request, page_view_name, posts_contains=None, following_only=False, page_num=1
):
    """
    Fetches and displays all posts in the network, ordered by timestamp.

    This function also handles pagination and provides information about liked posts and likes.
    """
    blocked_servers = []
    if request.user.is_authenticated:
        blocked_servers = ForeignBlocklist.objects.filter(
            user=request.user
        ).values_list("server", flat=True)
    # Query all posts and handle pagination
    local_server = get_object_or_404(ForeignServer, ip="local")
    # Count likes for each post
    initial_post_list = list(Post.objects.order_by("-timestamp").values())
    post_list = []
    for i in initial_post_list:
        i["username"] = str(get_object_or_404(User, id=i["user_id"]).username)
        if (
            request.user.is_authenticated
            and (
                (
                    ForeignUserBlocklist.objects.filter(
                        user=request.user,
                        server=local_server,
                        blocked_user=i["username"],
                    ).exists()
                )
                or (
                    following_only
                    and not Follower.objects.filter(
                        following_user=request.user,
                        server=local_server,
                        followee_user=i["username"],
                    ).exists()
                )
            )
            or (posts_contains is not None and posts_contains not in str(i))
        ):
            continue
        i["server_id"] = str(local_server.id)
        i["likes"] = len(ForeignLike.objects.filter(post__id=i["id"]))
        i["comments"] = list(ForeignComment.objects.filter(post__id=i["id"]).values())
        i["server_name"] = "local"
        i["server_port"] = ""
        i["timestamp_user"] = (
            i["timestamp"]
            .astimezone(datetime.timezone.utc)
            .strftime("%b. %d, %Y, %I:%M %p")
        )
        i["timestamp"] = (
            i["timestamp"]
            .replace(tzinfo=datetime.timezone.utc)
            .strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        )
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
        post_list.append(i)
    for i in ForeignServer.objects.all():
        if i.id not in blocked_servers and i.ip != "local":
            try:
                result = requests.get(
                    "http://" + i.ip + ":" + str(i.port) + "/federation/posts",
                    timeout=5,
                    data=json.dumps(
                        {
                            "username": request.user.username,
                            "port": request.META["SERVER_PORT"],
                        }
                    ),
                )
                if result.status_code == 200:
                    json_data = json.loads(result.content)
                    append_posts = []
                    for j in json_data["posts"]:
                        j["server_name"] = str(i.ip)
                        j["server_port"] = str(i.port)
                        j["server_id"] = str(i.id)
                        if (
                            request.user.is_authenticated
                            and Follower.objects.filter(
                                following_user=request.user,
                                followee_user=j["username"],
                                server=i,
                            ).exists()
                        ):
                            j["following"] = True
                        else:
                            j["following"] = False
                        if (
                            request.user.is_authenticated
                            and (
                                ForeignUserBlocklist.objects.filter(
                                    user=request.user,
                                    server=local_server,
                                    blocked_user=j["username"],
                                ).exists()
                                or (following_only and not j["following"])
                            )
                            or (
                                posts_contains is not None
                                and posts_contains not in str(i)
                            )
                        ):
                            continue
                        append_posts.append(j)
                    post_list += append_posts
            except Exception as e:
                print(e)
                pass
    sorted_post_list = sorted(
        post_list,
        key=lambda x: int(
            time.mktime(
                datetime.datetime.strptime(
                    x["timestamp"], "%Y-%m-%dT%H:%M:%S.%fZ"
                ).utctimetuple()
            )
        ),
    )
    paginator = Paginator(sorted_post_list, 10)
    posts: Page = paginator.get_page(page_num)
    # Handle pagination
    next_page = "0"
    prev_page = "0"
    if page_num > 1:
        prev_page = reverse(page_view_name, args=(page_num - 1,))
    if page_num < paginator.num_pages:
        next_page = reverse(page_view_name, args=(page_num + 1,))

    # Render the page
    return render(
        request,
        "network/index.html",
        {
            "posts": posts,
            "next_page": next_page,
            "prev_page": prev_page,
            "server_id": str(get_object_or_404(ForeignServer, ip="local").id),
        },
    )


def all_posts(request, page_num=1):
    return render_index(request, page_view_name="all", page_num=page_num)


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
        content_str = request.POST["content"]
        if "#" in content_str:
            new_string = ""
            for i in request.POST["content"].split(" "):
                if i.startswith("#"):
                    new_string += (
                        '<a href="'
                        + reverse("search")
                        + "?q=%23"
                        + i[1:]
                        + '">'
                        + i
                        + "</a> "
                    )
                else:
                    new_string += i + " "
            content_str = new_string
        content_str = content_str.replace(
            "/!",
            '<p style="background-color: #000; color: #000;" '
            "onmouseover=\"this.style.color='#FFF';\" "
            "onmouseout=\"this.style.color='#000';\">",
        )
        content_str = content_str.replace("!/", "</p>")
        Post.objects.create(content=content_str, user=request.user)
        return HttpResponseRedirect(reverse("index"))
    else:
        return render(request, "network/post.html")


def user(request, username, server_id, page_num=1):
    """Handles requests for a specific user's posts, along with their profile info"""
    if server_id == "local":
        server = get_object_or_404(ForeignServer, ip="local")
        local_server = server
    else:
        server = get_object_or_404(ForeignServer, id=server_id)
        local_server = get_object_or_404(ForeignServer, ip="local")
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
    followers = len(Follower.objects.filter(server=server, followee_user=username))
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
        following_users = len(Follower.objects.filter(followee_user=request_user))
        # Count likes for each post
        for i in posts:
            i["likes"] = len(ForeignLike.objects.filter(post=i["id"]))
            i["username"] = request_user.username
            i["comments"] = list(
                ForeignComment.objects.filter(
                    user=username, server=server, post=i["id"]
                ).values()
            )

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
            "not_self": server != local_server or request.user.username != username,
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
            result = requests.post(
                "http://"
                + server.ip
                + ":"
                + str(server.port)
                + "/federation/like/"
                + like_post,
                timeout=5,
                data=json.dumps(
                    {
                        "username": request.user.username,
                        "port": request.META["SERVER_PORT"],
                    }
                ),
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
            result = requests.post(
                "http://"
                + server.ip
                + ":"
                + str(server.port)
                + "/federation/unlike/"
                + like_post,
                timeout=5,
                data=json.dumps(
                    {
                        "username": request.user.username,
                        "port": request.META["SERVER_PORT"],
                    }
                ),
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
        if server == get_object_or_404(ForeignServer, ip="local"):
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
                    + str(server.port)
                    + "/federation/comment/"
                    + post_id,
                    timeout=5,
                    data=json.dumps(
                        {
                            "username": request.user.username,
                            "content": request.POST["content"],
                            "port": request.META["SERVER_PORT"],
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
                ForeignServer,
                ip=request.META.get("REMOTE_ADDR"),
                port=json_data["port"],
            ),
        )
        return JsonResponse({"Comment": createdComment})
    return JsonResponse({})


@csrf_exempt
def federated_like(request, post_id):
    json_data = json.loads(request.body)
    server = get_object_or_404(
        ForeignServer, ip=request.META.get("REMOTE_ADDR"), port=json_data["port"]
    )
    if not ForeignLike.objects.filter(
        server=server,
        user=json_data["username"],
        post=get_object_or_404(Post, id=post_id),
    ).exists():
        ForeignLike.objects.create(
            server=server,
            user=json_data["username"],
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
    json_data = json.loads(request.body)
    server = get_object_or_404(
        ForeignServer, ip=request.META.get("REMOTE_ADDR"), port=json_data["port"]
    )
    if ForeignLike.objects.filter(
        server=server,
        user=json_data["username"],
        post=get_object_or_404(Post, id=post_id),
    ).exists():
        ForeignLike.objects.filter(
            server=server,
            user=json_data["username"],
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
    json_data = json.loads(request.body)
    server = get_object_or_404(
        ForeignServer, ip=request.META.get("REMOTE_ADDR"), port=json_data["port"]
    )
    post_list = list(Post.objects.all().order_by("-timestamp").values())
    for i in post_list:
        i["likes"] = len(ForeignLike.objects.filter(post__id=i["id"]))
        i["comments"] = list(ForeignComment.objects.filter(post__id=i["id"]).values())
        i["username"] = str(get_object_or_404(User, id=i["user_id"]).username)
        i["timestamp_user"] = (
            i["timestamp"]
            .astimezone(datetime.timezone.utc)
            .strftime("%b. %d, %Y, %I:%M %p")
        )
        if "username" in json_data:
            i["liked"] = ForeignLike.objects.filter(
                server=server, user=json_data["username"], post__id=i["id"]
            ).exists()
        else:
            i["liked"] = False
    return JsonResponse({"posts": post_list})


@login_required
def block_user(request, server_id, username):
    if request.user.username == username:
        return HttpResponseRedirect(reverse("index"))
    ForeignUserBlocklist.objects.get_or_create(
        server=get_object_or_404(ForeignServer, id=server_id),
        blocked_user=username,
        user=request.user,
    )
    # Unfollow blocked users
    Follower.objects.filter(
        server__id=server_id, following_user=request.user, followee_user=username
    ).delete()
    return HttpResponseRedirect(reverse("index"))


@login_required
def unblock_user(request, server_id, username):
    ForeignUserBlocklist.objects.filter(
        server__id=server_id, blocked_user=username, user=request.user
    ).delete()
    return HttpResponseRedirect(reverse("index"))


class RSSFeed(Feed):
    title = "Network RSS Feed"
    link = "/"
    description = "The RSS feed for this Federation instance."

    def items(self):
        return Post.objects.all()

    def item_title(self, item):
        return item.user.username

    def item_description(self, item):
        return item.content

    def item_link(self, item):
        return reverse("index")


def search(request, page_num=1):
    if "q" in request.GET:
        return render_index(
            request,
            "search?q=" + request.GET["q"],
            posts_contains=request.GET["q"],
            page_num=page_num,
        )
    else:
        return HttpResponseRedirect(reverse("index"))
