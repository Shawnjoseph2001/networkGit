import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    pass


class Post(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)


class ForeignServer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ip = models.TextField()
    port = models.PositiveBigIntegerField(default=8000)
    block = models.BooleanField(default=False)


class Follower(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    following_user = models.ForeignKey(
        User, related_name="following_user", on_delete=models.CASCADE
    )
    followee_user = models.TextField()
    server = models.ForeignKey(ForeignServer, on_delete=models.CASCADE)


class ForeignLike(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    server = models.ForeignKey(ForeignServer, on_delete=models.CASCADE)
    user = models.TextField()
    post = models.ForeignKey(Post, on_delete=models.CASCADE)


class ForeignComment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    user = models.TextField()
    post = models.ForeignKey(Post, on_delete=models.CASCADE)
    server = models.ForeignKey(ForeignServer, on_delete=models.CASCADE)


class Blocklist(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    blockedUser = models.TextField()
    server = models.ForeignKey(ForeignServer, on_delete=models.CASCADE)


class ForeignBlocklist(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    server = models.ForeignKey(ForeignServer, on_delete=models.CASCADE)


class ForeignUserBlocklist(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    server = models.ForeignKey(ForeignServer, on_delete=models.CASCADE)
    blocked_user = models.TextField()
