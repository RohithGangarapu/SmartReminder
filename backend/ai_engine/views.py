import json
import os

from django.utils import timezone
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .serializers import (
    TaskExtractionRequestSerializer,
    TaskExtractionResponseSerializer,
)


class TaskExtractionError(Exception):
    def __init__(self, message, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR):
        super().__init__(message)
        self.status_code = status_code


def _extract_task_with_groq(text):
    try:
        from openai import (
            APIConnectionError,
            APIStatusError,
            APITimeoutError,
            OpenAI,
            RateLimitError,
        )
    except ImportError as exc:
        raise TaskExtractionError(
            'OpenAI SDK is not installed. Install it with `pip install openai`.'
        ) from exc

    api_key = os.getenv('GROQ_API_KEY')
    if not api_key:
        raise TaskExtractionError('GROQ_API_KEY is not configured.')

    now = timezone.localtime(timezone.now())
    today = now.date().isoformat()
    now_iso = now.strftime('%Y-%m-%dT%H:%M')
    model = os.getenv('GROQ_TASK_MODEL', 'llama-3.1-8b-instant')

    client = OpenAI(
        api_key=api_key,
        base_url='https://api.groq.com/openai/v1',
    )
    try:
        completion = client.chat.completions.create(
            model=model,
            temperature=0,
            messages=[
                {
                    'role': 'system',
                    'content': (
                        'Extract one task from the user text. '
                        'Return only valid JSON with keys: title, datetime. '
                        'datetime must be in YYYY-MM-DDTHH:MM 24-hour format with no timezone suffix. '
                        f'Use today={today} and current_time={now_iso} to resolve relative dates like tomorrow.'
                    ),
                },
                {'role': 'user', 'content': text},
            ],
            response_format={'type': 'json_object'},
        )
    except RateLimitError as exc:
        raise TaskExtractionError(
            'Groq quota exceeded. Check plan, billing, and API key limits.',
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        ) from exc
    except (APIConnectionError, APITimeoutError) as exc:
        raise TaskExtractionError(
            'Groq service is temporarily unreachable. Please try again.',
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        ) from exc
    except APIStatusError as exc:
        raise TaskExtractionError(
            f'Groq API error: {exc.status_code}',
            status_code=status.HTTP_502_BAD_GATEWAY,
        ) from exc

    content = completion.choices[0].message.content
    if not content:
        raise TaskExtractionError('Groq returned an empty response.')

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise TaskExtractionError('Groq response was not valid JSON.') from exc

    title = parsed.get('title')
    extracted_datetime = parsed.get('datetime')
    if not title or not extracted_datetime:
        raise TaskExtractionError('Groq response is missing required fields: title, datetime.')

    return {'title': title, 'datetime': extracted_datetime}


@swagger_auto_schema(
    method='post',
    request_body=TaskExtractionRequestSerializer,
    responses={
        200: TaskExtractionResponseSerializer(),
        400: 'Bad Request',
        429: 'Quota Exceeded',
        500: 'Server Error',
        503: 'Service Unavailable',
    },
)
@api_view(['POST'])
@permission_classes([AllowAny])
def extract_task(request):
    serializer = TaskExtractionRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    text = serializer.validated_data['text'].strip()
    try:
        extracted = _extract_task_with_groq(text)
    except TaskExtractionError as exc:
        return Response({'error': str(exc)}, status=exc.status_code)

    response_serializer = TaskExtractionResponseSerializer(data=extracted)
    response_serializer.is_valid(raise_exception=True)
    return Response(response_serializer.data, status=status.HTTP_200_OK)
