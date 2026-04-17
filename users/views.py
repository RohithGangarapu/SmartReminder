import datetime

try:
    import jwt
except ImportError as exc:
    raise ImportError(
        "PyJWT is required for JWT authentication. Install it with `pip install PyJWT`."
    ) from exc

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.utils import timezone
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .serializers import LoginSerializer, RegisterSerializer, UserResponseSerializer

User = get_user_model()


def _create_jwt_for_user(user):
    expiry = timezone.now() + datetime.timedelta(minutes=15)
    payload = {
        'user_id': user.id,
        'username': user.username,
        'type': 'access',
        'exp': int(expiry.timestamp()),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')


def _create_refresh_jwt_for_user(user):
    expiry = timezone.now() + datetime.timedelta(days=7)
    payload = {
        'user_id': user.id,
        'username': user.username,
        'type': 'refresh',
        'exp': int(expiry.timestamp()),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')


def _build_user_response(user, access_token, refresh_token):
    return {
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'access_token': access_token,
        'refresh_token': refresh_token,
    }


@swagger_auto_schema(
    method='post',
    request_body=RegisterSerializer,
    responses={201: UserResponseSerializer(), 400: 'Bad Request'},
)
@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    serializer = RegisterSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    username = serializer.validated_data['username']
    email = serializer.validated_data.get('email', '').strip()
    password = serializer.validated_data['password']

    user = User.objects.create_user(username=username, email=email, password=password)
    access_token = _create_jwt_for_user(user)
    refresh_token = _create_refresh_jwt_for_user(user)
    response = _build_user_response(user, access_token, refresh_token)
    return Response(response, status=status.HTTP_201_CREATED)


@swagger_auto_schema(
    method='post',
    request_body=LoginSerializer,
    responses={200: UserResponseSerializer(), 400: 'Bad Request', 401: 'Unauthorized'},
)
@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    username = serializer.validated_data.get('username', '').strip()
    email = serializer.validated_data.get('email', '').strip()
    password = serializer.validated_data['password']

    if not username and email:
        try:
            user = User.objects.get(email=email)
            username = user.username
        except User.DoesNotExist:
            return Response({'error': 'Invalid credentials.'}, status=status.HTTP_401_UNAUTHORIZED)

    user = authenticate(request, username=username, password=password)
    if user is None:
        return Response({'error': 'Invalid credentials.'}, status=status.HTTP_401_UNAUTHORIZED)

    access_token = _create_jwt_for_user(user)
    refresh_token = _create_refresh_jwt_for_user(user)
    response = _build_user_response(user, access_token, refresh_token)
    return Response(response, status=status.HTTP_200_OK)
