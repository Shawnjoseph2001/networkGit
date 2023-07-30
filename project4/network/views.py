import json

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, Page
from django.db import IntegrityError
from django.http import HttpResponseRedirect
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .models import (
    User,
    Follower,
    Like,
    Post,
    Comment,
    ForeignLike,
    ForeignComment,
    ForeignServer,
    ForeignBlocklist,
)

from django.contrib.auth.decorators import user_passes_test


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
    # Query all users that the current user is following
    follow_query = Follower.objects.filter(followee_user=request.user)

    # Extract relevant information from the follow query
    following_users = list(follow_query.values_list("following_user", flat=True))
    following_user_usernames = list(
        follow_query.values_list("following_user__username", flat=True)
    )

    # Query all posts that the current user liked
    liked_posts = list(
        Like.objects.filter(user=request.user).values_list("post__id", flat=True)
    )

    # Create a dictionary with post id as key and number of likes as value
    likes = {}
    comments = {}
    for i in Post.objects.all():
        likes[i.id] = len(Like.objects.filter(post=i))
        comments[i.id] = Comment.objects.filter(post=i)

    # Query posts from following users
    following_posts = list(
        Post.objects.filter(user__in=following_users).order_by("-timestamp")
    )

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
            "posts": paginator.get_page(page_num),
            "next_page": next_page,
            "prev_page": prev_page,
            "following_users": following_user_usernames,
            "likes": likes,
            "liked_posts": liked_posts,
            "comments": comments,
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
    liked_posts = []
    if request.user.is_authenticated:
        following_users = list(
            Follower.objects.filter(followee_user=request.user).values_list(
                "following_user__username", flat=True
            )
        )
        liked_posts = list(
            Like.objects.filter(user=request.user).values_list("post__id", flat=True)
        )

    # Query all posts and handle pagination
    paginator = Paginator(list(Post.objects.all().order_by("-timestamp")), 10)
    posts: Page = paginator.get_page(page_num)

    likes = {}
    comments = {}
    page_links = []
    for i in range(paginator.num_pages):
        page_links.append((i, reverse("following", args=(i,))))

    # Count likes for each post
    for i in Post.objects.all():
        likes[i.id] = len(Like.objects.filter(post=i))
        comments[i.id] = Comment.objects.filter(post=i)

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
            "page_links": page_links,
            "following_users": following_users,
            "likes": likes,
            "liked_posts": liked_posts,
            "comments": comments,
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


def user(request, username, page_num):
    """Handles requests for a specific user's posts, along with their profile info"""
    # Fetch the requested user or return 404 if not found
    request_user = get_object_or_404(User, username=username)
    # Fetch the posts made by the requested user, ordered by timestamp
    posts = Post.objects.filter(user=request_user).order_by("-timestamp")
    # Fetch the count of followers and following users
    followers = len(Follower.objects.filter(following_user=request_user))
    following_users = len(Follower.objects.filter(followee_user=request_user))
    # Initialize variables for authenticated users
    user_following = False
    liked_posts = []
    likes = {}
    # Count likes for each post
    for i in Post.objects.all():
        likes[i.id] = len(Like.objects.filter(post=i))
    if request.user.is_authenticated:
        user_following = Follower.objects.filter(
            following_user=request.user, followee_user=request_user
        ).exists()
        liked_posts = list(
            Like.objects.filter(user=request.user).values_list("post__id", flat=True)
        )
    # Handle pagination
    next_page = "0"
    prev_page = "0"
    paginator = Paginator(posts, 10)
    if page_num > 1:
        prev_page = reverse(
            "user",
            args=(
                username,
                page_num - 1,
            ),
        )
    if page_num < paginator.num_pages:
        next_page = reverse(
            "user",
            args=(
                username,
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
            "likes": likes,
            "liked_posts": liked_posts,
        },
    )


@csrf_exempt
@login_required
def like(request, like_post):
    """Handles like action for a post."""
    like_post = get_object_or_404(Post, id=like_post)
    if len(Like.objects.filter(post=like_post, user=request.user)) == 0:
        Like.objects.create(post=like_post, user=request.user)
        return JsonResponse(
            data={
                "likeCount": len(Like.objects.filter(post=like_post)),
                "success": True,
            },
            status=200,
        )
    return JsonResponse(
        data={"likeCount": len(Like.objects.filter(post=like_post)), "success": False},
        status=200,
    )


@csrf_exempt
@login_required
def unlike(request, like_post):
    """Handles unlike action for a post."""
    like_post = get_object_or_404(Post, id=like_post)
    like_to_delete = get_object_or_404(Like, user=request.user, post=like_post)
    like_to_delete.delete()
    return JsonResponse(
        data={"likeCount": len(Like.objects.filter(post=like_post)), "success": True},
        status=200,
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
def follow(request, username):
    """Allows the current user to follow another user."""
    follow_user = get_object_or_404(User, username=username)
    if (
        len(
            Follower.objects.filter(
                following_user=follow_user, followee_user=request.user
            )
        )
        == 0
    ):
        Follower.objects.create(following_user=follow_user, followee_user=request.user)
    return HttpResponseRedirect(reverse("index"))


@login_required
def unfollow(request, username):
    """Allows the current user to unfollow another user."""
    follow_user = get_object_or_404(User, username=username)
    follower_to_delete = get_object_or_404(
        Follower, following_user=follow_user, followee_user=request.user
    )
    follower_to_delete.delete()
    return HttpResponseRedirect(reverse("index"))


def user_rd(request, username):
    """User redirect"""
    return redirect("user", username=username, page_num=1)


@login_required
def comment(request, post_id):
    """Create post comment"""
    if request.method == "POST":
        Comment.objects.create(
            content=request.POST["content"],
            user=request.user,
            post=get_object_or_404(Post, id=post_id),
        )
    return HttpResponseRedirect(reverse("index"))


def federate(request):
    if request.method == "POST":
        server = request.get_host()
        port = request.get_port()
        ForeignServer.objects.get_or_create(ip=server, port=port)
        return JsonResponse({"Success": True})


def federated_comment(request, post_id):
    if request.method == "POST":
        server = request.get_host()
        port = request.get_port()
        json_data = json.loads(request.body)
        createdComment = ForeignComment.objects.create(
            content=json_data["content"],
            user=request.user,
            post=get_object_or_404(Post, id=post_id),
            server=get_object_or_404(
                ForeignServer, server=request.get_host(), port=request.get_host()
            ),
        )
        return JsonResponse({"Comment": createdComment})


@csrf_exempt
def federated_like(request, post_id):
    if request.method == "POST":
        json_data = json.loads(request.body)
        server = get_object_or_404(
            ForeignServer, ip=request.get_host(), port=request.get_port()
        )
        ForeignLike.objects.create(
            server=server,
            username=json_data["username"],
            post=get_object_or_404(Post, id=post_id),
        )
        return JsonResponse({"Like": "Success"})


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
