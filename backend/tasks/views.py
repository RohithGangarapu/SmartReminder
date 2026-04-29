try:
    import jwt
except ImportError as exc:
    raise ImportError(
        "PyJWT is required for JWT authentication. Install it with `pip install PyJWT`."
    ) from exc

from django.conf import settings
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import Task
from .serializers import TaskSerializer

User = get_user_model()


def _get_user_from_auth_header(request):
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return None

    token = auth_header.split(' ', 1)[1].strip()
    if not token:
        return None

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
    except jwt.InvalidTokenError:
        return None

    if payload.get('type') != 'access':
        return None

    user_id = payload.get('user_id')
    if not user_id:
        return None

    try:
        return User.objects.get(id=user_id)
    except User.DoesNotExist:
        return None


def _unauthorized_response():
    return Response(
        {'error': 'Authentication credentials were not provided or are invalid.'},
        status=status.HTTP_401_UNAUTHORIZED,
    )


@swagger_auto_schema(method='get', responses={200: TaskSerializer(many=True), 401: 'Unauthorized'})
@swagger_auto_schema(method='post', request_body=TaskSerializer, responses={201: TaskSerializer(), 400: 'Bad Request', 401: 'Unauthorized'})
@api_view(['GET', 'POST'])
def tasks_collection(request):
    user = _get_user_from_auth_header(request)
    if user is None:
        return _unauthorized_response()

    if request.method == 'GET':
        tasks = Task.objects.filter(user=user).order_by('-created_at')
        serializer = TaskSerializer(tasks, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    serializer = TaskSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    serializer.save(user=user)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@swagger_auto_schema(method='put', request_body=TaskSerializer, responses={200: TaskSerializer(), 400: 'Bad Request', 401: 'Unauthorized', 404: 'Not Found'})
@swagger_auto_schema(method='delete', responses={204: 'No Content', 401: 'Unauthorized', 404: 'Not Found'})
@api_view(['PUT', 'DELETE'])
def task_detail(request, id):
    user = _get_user_from_auth_header(request)
    if user is None:
        return _unauthorized_response()

    task = get_object_or_404(Task, id=id, user=user)

    if request.method == 'PUT':
        serializer = TaskSerializer(task, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    task.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)
