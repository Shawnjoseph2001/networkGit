import datetime
import json
import time

import requests
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import user_passes_test
from django.contrib.syndication.views import Feed
from django.core import serializers
from django.core.paginator import Paginator, Page
from django.db import IntegrityError
from django.http import HttpResponseRedirect
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
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
    """Redirect to the 'all' route."""
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
        for j in i["comments"]:
            j["timestamp"] = (
                j["timestamp"]
                .astimezone(datetime.timezone.utc)
                .strftime("%b. %d, %Y, %I:%M %p")
            )
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
        reverse=True,
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
    local_server = get_object_or_404(ForeignServer, ip="local")
    if server_id == "local":
        server = local_server
    else:
        server = get_object_or_404(ForeignServer, id=server_id)
    user_following = False
    liked_posts = []
    if request.user.is_authenticated:
        followers_filter = Follower.objects.filter(
            following_user=request.user, followee_user=username, server=server
        )
        user_following = followers_filter.exists()
        liked_posts = list(
            ForeignLike.objects.filter(user=request.user).values_list(
                "post__id", flat=True
            )
        )
    followers = len(Follower.objects.filter(server=server, followee_user=username))
    if server == local_server:
        request_user = get_object_or_404(User, username=username)
        posts = list(
            Post.objects.filter(user=request_user).order_by("-timestamp").values()
        )
        following_users = len(Follower.objects.filter(followee_user=request_user))
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
                url=f"http://{server.ip}:{server.port}/federation/user/{username}",
                timeout=5,
                data=json.dumps({"port": request.META["SERVER_PORT"]}),
            )
            json_response = json.loads(result.content)
            followers += json_response["followers"]
            following_users = json_response["following_users"]
            posts = json_response["posts"]
        except Exception as e:
            print(f"Error loading user data: {e}")
            return HttpResponseRedirect(reverse("index"))
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
    if server_id == "local":
        server = get_object_or_404(ForeignServer, ip="local")
    else:
        server = get_object_or_404(ForeignServer, id=server_id)
    if server.ip == "local":
        like_post = get_object_or_404(Post, id=like_post)
        likes = ForeignLike.objects.filter(
            post=like_post, user=request.user, server=server
        )
        success = False
        if not likes.exists():
            likes.create(post=like_post, user=request.user, server=server)
            success = True
        like_count = len(ForeignLike.objects.filter(post=like_post))
        return JsonResponse({"likeCount": like_count, "success": success})
    else:
        try:
            result = requests.post(
                f"http://{server.ip}:{server.port}/federation/like/{like_post}",
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
        except requests.exceptions.Timeout:
            pass
        return JsonResponse({"success": False})


@csrf_exempt
@login_required
def unlike(request, like_post, server_id):
    """Handles unlike action for a post."""
    if server_id == "local":
        server = get_object_or_404(ForeignServer, ip="local")
    else:
        server = get_object_or_404(ForeignServer, id=server_id)
    if server.ip == "local":
        like_post = get_object_or_404(Post, id=like_post)
        likes = ForeignLike.objects.filter(
            post=like_post, user=request.user, server=server
        )
        success = False
        if likes.exists():
            likes.delete()
            success = True
        like_count = len(ForeignLike.objects.filter(post=like_post))
        return JsonResponse({"likeCount": like_count, "success": success})
    else:
        try:
            result = requests.post(
                f"http://{server.ip}:{server.port}/federation/unlike/{like_post}",
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
        except requests.exceptions.Timeout:
            pass
        return JsonResponse({"success": False})


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


@login_required
def comment(request, post_id, server_id):
    """
    Handle the creation of a comment for a given post.

    This function creates a new comment for a specific post. The comment is either created
    locally if the post is from the local server or a POST request is sent to the foreign
    server with the comment content if the post is from a foreign server.

    Parameters:
    request (WSGIRequest): The incoming HTTP request. It should be a POST request with the content of the comment.
    post_id (int): The id of the Post object that the comment is related to.
    server_id (int): The id of the ForeignServer object from which the Post originates.

    Returns:
    HttpResponseRedirect: Redirects the user to the index page regardless of request type or success of comment creation.
    """

    # Check if the request is a POST.
    if request.method == "POST":
        # Fetch the server where the post resides.
        server = get_object_or_404(ForeignServer, id=server_id)

        # If the server is local, create the comment locally.
        if server == get_object_or_404(ForeignServer, ip="local"):
            ForeignComment.objects.create(
                content=request.POST["content"],
                user=request.user,
                post=get_object_or_404(Post, id=post_id),
                server=server,
            )
        # If the server is foreign, send a POST request to create the comment.
        else:
            try:
                # Formulate the URL for the POST request.
                url = "http://{}:{}/federation/comment/{}".format(
                    server.ip, server.port, post_id
                )

                # Prepare the payload data.
                data = json.dumps(
                    {
                        "username": request.user.username,
                        "content": request.POST["content"],
                        "port": request.META["SERVER_PORT"],
                    }
                )

                # Send the POST request to the foreign server.
                requests.post(url, timeout=5, data=data)

            # Catch any timeout exceptions.
            except requests.exceptions.Timeout:
                # If the request times out, redirect to the index page.
                return HttpResponseRedirect(reverse("index"))

    # Redirect to the index page.
    return HttpResponseRedirect(reverse("index"))


@csrf_exempt
def federated_comment(request, post_id):
    """
    Handle POST requests from federated servers to create a new comment on a post.

    Parameters:
    request (WSGIRequest): The incoming HTTP request. Should be a POST request with a JSON body
    post_id (int): The id of the Post object to which the comment is to be added.

    Returns:
    JsonResponse: If request is a POST, returns a JSON object containing a serialized version of the new comment.
    HttpResponseRedirect: If request is not a POST, returns a redirect to the index page.
    """

    if request.method == "POST":
        json_data = json.loads(request.body)

        # Create a new ForeignComment in the database with the data from the payload.
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

        # Return a JSON response containing a serialized version of the new comment.
        return JsonResponse(
            {"Comment": serializers.serialize("json", (createdComment,))}
        )

    # If the request is not a POST, redirect to the index page.
    return HttpResponseRedirect(reverse("index"))


@csrf_exempt
def federated_like(request, post_id):
    """
    This function handles the "like" action for a federated post.

    Parameters:
    request (WSGIRequest): An HTTP request object that includes a body with a JSON object
    post_id (int): The ID of the post that is being liked.

    Returns:
    JsonResponse: A response containing the updated like count and the success status of the operation.
    """

    # Load the JSON data from the request body.
    json_data = json.loads(request.body)
    server = get_object_or_404(
        ForeignServer, ip=request.META.get("REMOTE_ADDR"), port=json_data["port"]
    )
    like_post = get_object_or_404(Post, id=post_id)

    success = False

    # Check if a ForeignLike object already exists for the given server, user, and post.
    if not ForeignLike.objects.filter(
        server=server, user=json_data["username"], post=like_post
    ).exists():
        # If no ForeignLike object exists, create one.
        ForeignLike.objects.create(
            server=server, user=json_data["username"], post=like_post
        )
        success = True

    # Count the total number of likes for the post.
    like_count = ForeignLike.objects.filter(post=like_post).count()

    # Return a JSON response indicating the success of the operation and the updated like count.
    return JsonResponse(
        {
            "likeCount": like_count,
            "success": success,
        }
    )


@csrf_exempt
def federated_get_likes(request):
    """
    This function retrieves all 'likes' associated with a foreign server.
    Parameters:
    request (WSGIRequest): An HTTP request object.

    Returns:
    JsonResponse: A JSON response containing the likes associated with the foreign server.
    """

    server = get_object_or_404(
        ForeignServer, ip=request.get_host(), port=request.get_port()
    )

    # Filter ForeignLike objects based on the identified server.
    likes = ForeignLike.objects.filter(server=server)

    # Return a JSON response containing the filtered 'likes'.
    return JsonResponse({"Likes": likes})


@csrf_exempt
def federated_unlike(request, post_id):
    """
    This function handles the unlike action for a federated post.
    Parameters:
    request (WSGIRequest): An HTTP request object that includes a body with a JSON object
    post_id (int): The ID of the post that is being unliked.

    Returns:
    JsonResponse: A response containing the updated like count and the success status of the operation.
    """

    # Load the JSON data from the request body.
    json_data = json.loads(request.body)

    # Get the foreign server from which the request is coming.
    # If no such server exists, raise a 404 error.
    server = get_object_or_404(
        ForeignServer, ip=request.META.get("REMOTE_ADDR"), port=json_data["port"]
    )

    # Check if a ForeignLike object exists for the given server, user, and post.
    if ForeignLike.objects.filter(
        server=server,
        user=json_data["username"],
        post=get_object_or_404(Post, id=post_id),
    ).exists():
        # If a ForeignLike object exists, delete it.
        ForeignLike.objects.filter(
            server=server,
            user=json_data["username"],
            post=get_object_or_404(Post, id=post_id),
        ).delete()

        # Return a JSON response indicating the success of the operation and the updated like count.
        return JsonResponse(
            {
                "likeCount": len(ForeignLike.objects.filter(post__id=post_id)),
                "success": True,
            }
        )

    # If no ForeignLike object exists, return a JSON response indicating the failure of the operation.
    return JsonResponse(
        {
            "likeCount": len(ForeignLike.objects.filter(post__id=post_id)),
            "success": False,
        }
    )


@login_required
def add_servers(request):
    """
    This function handles the addition of foreign Federation servers to the system by a superuser.
    The function also displays all the servers and the blocklist to the user.
    If the request method is POST and the user is a superuser, a new server will be added or retrieved if it already exists.

    Parameters:
    request (WSGIRequest): An HTTP request object.

    Returns:
    HttpResponseRedirect: A redirection to the 'add_servers' page after adding a server, if applicable.
    HttpResponse: An HTTP response containing the rendered 'network/server.html' template, otherwise.
    """

    if request.method == "POST" and request.user.is_superuser:
        # Get or create a ForeignServer object with the provided IP and port from the request.
        ForeignServer.objects.get_or_create(
            ip=request.POST["ip"], port=request.POST["port"]
        )
        # Redirect the superuser to the 'add_servers' page after adding the server.
        return HttpResponseRedirect(reverse("add_servers"))

    # If the request is not a POST request, or the user is not a superuser, render the add servers page.
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
    """
    This function allows a superuser to delete a foreign server from the system.
    The 'user_passes_test' decorator ensures that only a superuser can access this function.

    Parameters:
    request (WSGIRequest): An HTTP request object.

    Returns:
    HttpResponseRedirect: A redirection to the 'add_servers' page after deleting the server.

    """

    if request.method == "POST":
        # Delete the ForeignServer object with the provided IP and port from the request.
        ForeignServer.objects.filter(
            ip=request.POST["ip"], port=request.POST["port"]
        ).delete()

    # Redirect the superuser to the 'add_servers' page after deleting the server.
    return HttpResponseRedirect(reverse("add_servers"))


@login_required
def block_server(request):
    """
    This function handles the blocking of a foreign server for a logged-in user.

    Parameters:
    request (WSGIRequest): An HTTP request object.

    Returns:
    HttpResponseRedirect: A redirection to the 'add_servers' page after blocking the server.

    """

    if request.method == "POST":
        # Get or create a ForeignBlocklist object for the server and user from the request.
        ForeignBlocklist.objects.get_or_create(
            server=get_object_or_404(
                ForeignServer, ip=request.POST["ip"], port=request.POST["port"]
            ),
            user=request.user,
        )

    # Redirect the user to the 'add_servers' page after blocking the server.
    return HttpResponseRedirect(reverse("add_servers"))


@login_required
def unblock_server(request):
    """
    This function handles the unblocking of a foreign server for a logged-in user.
    Parameters:
    request (WSGIRequest): An HTTP request object.

    Returns:
    HttpResponseRedirect: A redirection to the 'add_servers' page after unblocking the server.

    """

    if request.method == "POST":
        server_to_delete = get_object_or_404(
            ForeignBlocklist,
            server=get_object_or_404(
                ForeignServer, ip=request.POST["ip"], port=request.POST["port"]
            ),
            user=request.user,
        )

        # Delete the retrieved ForeignBlocklist object, effectively unblocking the server.
        server_to_delete.delete()

    # Redirect the user to the 'add_servers' page after unblocking the server.
    return HttpResponseRedirect(reverse("add_servers"))


@csrf_exempt
def federated_user(request, username):
    """
    This function returns user data to a federated server.

    Parameters:
    request (WSGIRequest): An HTTP request object.
    username (str): The username of the user for whom information is requested.

    Returns:
    JsonResponse: A JsonResponse object with user information and related posts.
    """

    # Fetch the User object for the given username. If no such user exists, raise a 404 error.
    request_user = get_object_or_404(User, username=username)

    # Fetch the posts made by the requested user, ordered by timestamp.
    posts = list(Post.objects.filter(user=request_user).order_by("-timestamp").values())

    # Fetch the count of followers and following users for the requested user.
    followers = len(Follower.objects.filter(following_user=request_user))
    following_users = len(
        Follower.objects.filter(
            followee_user=username,
            server=get_object_or_404(ForeignServer, ip="local"),
        )
    )

    # Loop through each post in the post list.
    for i in posts:
        # Add 'likes' field to the post which contains the count of likes the post has received.
        i["likes"] = len(ForeignLike.objects.filter(post=i["id"]))

        # Add 'username' field to the post which contains the username of the post's author.
        i["username"] = request_user.username

    # Return a JsonResponse containing the requested user's information and related posts.
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
    """
    This function returns all of the posts on a server to any federated servers.

    Parameters:
    request (WSGIRequest): An HTTP request object.

    Returns:
    JsonResponse: A JsonResponse object with processed posts information.
    """

    # Load JSON data from the request body.
    json_data = json.loads(request.body)

    # Retrieve the ForeignServer object based on the IP address and port included in the request.
    server = get_object_or_404(
        ForeignServer, ip=request.META.get("REMOTE_ADDR"), port=json_data["port"]
    )

    # Fetch all the posts, order them by timestamp and convert the QuerySet to a list of dictionaries.
    post_list = list(Post.objects.all().order_by("-timestamp").values())

    # Loop through each post in the post list.
    for i in post_list:
        # Add 'likes' field to the post which contains the count of likes the post has received.
        i["likes"] = len(ForeignLike.objects.filter(post__id=i["id"]))

        # Add 'comments' field to the post which contains a list of comments the post has received.
        i["comments"] = list(ForeignComment.objects.filter(post__id=i["id"]).values())

        # For each comment, convert timestamp to a more readable string format.
        for j in i["comments"]:
            j["timestamp"] = (
                j["timestamp"]
                .astimezone(datetime.timezone.utc)
                .strftime("%b. %d, %Y, %I:%M %p")
            )

        # Add 'username' field to the post which contains the username of the post's author.
        i["username"] = str(get_object_or_404(User, id=i["user_id"]).username)

        # Convert timestamp of the post to a more readable string format.
        i["timestamp_user"] = (
            i["timestamp"]
            .astimezone(datetime.timezone.utc)
            .strftime("%b. %d, %Y, %I:%M %p")
        )

        # Check if the request contains the username of the originating user.
        # If so, add a 'liked' field to the post indicating whether the user has liked the post.
        # If 'username' is not present, set 'liked' as False.
        if "username" in json_data:
            i["liked"] = ForeignLike.objects.filter(
                server=server, user=json_data["username"], post__id=i["id"]
            ).exists()
        else:
            i["liked"] = False

    # Return a JsonResponse containing the post information
    return JsonResponse({"posts": post_list})


@login_required
def block_user(request, server_id, username):
    """
    This function is responsible for blocking a user.
    The user who invokes this function must be authenticated.
    A user cannot block themselves.

    Parameters:
    request (WSGIRequest): An HTTP request object.
    server_id (int): The ID of the server where the user is to be blocked.
    username (str): The username of the user to block.

    Returns:
    HttpResponseRedirect: A redirection to the index page after blocking the user.

    """

    # Check if the authenticated user is trying to block themselves.
    # If so, redirect them to the index page without performing the block operation.
    if request.user.username == username:
        return HttpResponseRedirect(reverse("index"))

    # If the user is not blocking themselves, block the specified user.
    ForeignUserBlocklist.objects.get_or_create(
        server=get_object_or_404(ForeignServer, id=server_id),
        blocked_user=username,
        user=request.user,
    )

    # Unfollow the user that has just been blocked.
    Follower.objects.filter(
        server__id=server_id, following_user=request.user, followee_user=username
    ).delete()

    # After blocking the user and unfollowing them, redirect to the index page.
    return HttpResponseRedirect(reverse("index"))


@login_required
def unblock_user(request, server_id, username):
    """
    Unblock a user
    Parameters:
    request (WSGIRequest): An HTTP request object.
    server_id (int): The ID of the server the user to unblock is on.
    username (str): The username of the user to unblock.

    Returns:
    HttpResponseRedirect: A redirection to the index page after unblocking the user.

    """

    # Delete all matching users to unblock
    ForeignUserBlocklist.objects.filter(
        server__id=server_id, blocked_user=username, user=request.user
    ).delete()

    # After unblocking the user, redirect to the index page.
    return HttpResponseRedirect(reverse("index"))


class RSSFeed(Feed):
    """
    An RSS feed for a Federation instance.

    Attributes:
    title (str): The title of the RSS feed.
    link (str): The link of the RSS feed.
    description (str): A brief description of the RSS feed.
    """

    title = "Network RSS Feed"
    link = "/"
    description = "The RSS feed for this Federation instance."

    def items(self):
        """
        Fetches all the Post objects to include in the RSS feed.

        Returns:
        QuerySet: A QuerySet of all Post objects.
        """

        return Post.objects.all()

    def item_title(self, item):
        """
        Defines the title for each item in the feed.
        In this case, the username of the author is used as the title.

        Parameters:
        item (Post): A Federation Post

        Returns:
        str: The username of the author of the post.
        """

        return item.user.username

    def item_description(self, item):
        """
        Defines the description for each item in the feed.
        In this case, the content of the post is used as the description.

        Parameters:
        item (Post): A Network Post.

        Returns:
        str: The content of the post.
        """

        return item.content

    def item_link(self, item):
        """
        Defines the link for each item in the feed.
        In this case, all items link back to the index page because posts don't have their own links

        Parameters:
        item (Post): A Post object.

        Returns:
        str: A URL for the index page.
        """

        return reverse("index")


def search(request, page_num=1):
    """
    Function to handle search requests on a web page.

    Parameters:
    request (WSGIRequest): An HTTP request object.
    page_num (int, optional): The number of the page where the search result is to be displayed. Default is 1.

    Returns:
    HttpResponse: A HTTP response. If the query parameter 'q' exists in the request,
    it returns a rendered page with the search results.
    Otherwise, it redirects to the index page.
    """
    # Check if 'q' exists in the GET parameters of the request.
    if "q" in request.GET:
        # 'q' exists. Render the index page with the search results.
        return render_index(
            request,
            "search?q=" + request.GET["q"],
            posts_contains=request.GET["q"],
            page_num=page_num,
        )
    else:
        # 'q' does not exist in the GET parameters. Redirect to the index page.
        return HttpResponseRedirect(reverse("index"))
