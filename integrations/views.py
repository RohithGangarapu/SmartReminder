import datetime
import hashlib
import hmac
import json
import os
import urllib.error
import urllib.parse
import urllib.request

try:
    import jwt
except ImportError as exc:
    raise ImportError(
        "PyJWT is required for JWT authentication. Install it with `pip install PyJWT`."
    ) from exc

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.http import HttpResponse
from django.utils import timezone
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from tasks.models import Task

from .models import (
    GmailIntegration,
    GmailSyncedMessage,
    GoogleCalendarTaskSync,
    WhatsAppIntegration,
    WhatsAppSyncedMessage,
)
from .serializers import (
    GmailConnectRequestSerializer,
    GmailConnectResponseSerializer,
    GmailFetchResponseSerializer,
    GoogleCalendarSyncRequestSerializer,
    GoogleCalendarSyncResponseSerializer,
    WhatsAppConnectRequestSerializer,
    WhatsAppConnectResponseSerializer,
    WhatsAppFetchResponseSerializer,
)

User = get_user_model()

NON_ACTIONABLE_KEYWORDS = [
    'unsubscribe',
    'sponsored',
    'promotion',
    'promotions',
    'sale',
    'offer',
    'discount',
    'coupon',
    'newsletter',
    'digest',
    'new arrivals',
    'deal',
    'black friday',
    'cyber monday',
    'shop now',
    'recommended for you',
    'you might like',
]


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


def _json_request(url, method='GET', payload=None, headers=None):
    req_headers = {'Content-Type': 'application/json'}
    if headers:
        req_headers.update(headers)

    data = None
    if payload is not None:
        data = json.dumps(payload).encode('utf-8')

    req = urllib.request.Request(url=url, method=method, data=data, headers=req_headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode('utf-8')
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode('utf-8', errors='ignore')
        detail = error_body or str(exc)
        raise ValueError(f'HTTP {exc.code}: {detail}') from exc
    except urllib.error.URLError as exc:
        raise ValueError(f'Network error: {exc.reason}') from exc


def _build_gmail_headers(access_token):
    return {'Authorization': f'Bearer {access_token}'}


def _has_calendar_scope(scope_value):
    if not scope_value:
        return False
    scopes = set(scope_value.split())
    return (
        'https://www.googleapis.com/auth/calendar' in scopes
        or 'https://www.googleapis.com/auth/calendar.events' in scopes
    )


def _build_google_calendar_headers(access_token):
    return {'Authorization': f'Bearer {access_token}'}


def _build_google_calendar_event_payload(task):
    duration_minutes = int(os.getenv('GOOGLE_CALENDAR_EVENT_DURATION_MINUTES', '30'))
    event_end = task.datetime + datetime.timedelta(minutes=max(duration_minutes, 5))
    tz_name = timezone.get_current_timezone_name()
    return {
        'summary': task.title,
        'description': task.description or '',
        'start': {
            'dateTime': task.datetime.isoformat(),
            'timeZone': tz_name,
        },
        'end': {
            'dateTime': event_end.isoformat(),
            'timeZone': tz_name,
        },
        'reminders': {'useDefault': True},
        'extendedProperties': {
            'private': {
                'smartreminder_task_id': str(task.id),
                'smartreminder_source': task.source,
            }
        },
    }


def _create_calendar_event(access_token, task, calendar_id='primary'):
    payload = _build_google_calendar_event_payload(task)
    safe_calendar_id = urllib.parse.quote(calendar_id, safe='')
    url = f'https://www.googleapis.com/calendar/v3/calendars/{safe_calendar_id}/events'
    return _json_request(
        url,
        method='POST',
        payload=payload,
        headers=_build_google_calendar_headers(access_token),
    )


def _update_calendar_event(access_token, calendar_id, event_id, task):
    payload = _build_google_calendar_event_payload(task)
    safe_calendar_id = urllib.parse.quote(calendar_id, safe='')
    safe_event_id = urllib.parse.quote(event_id, safe='')
    url = (
        f'https://www.googleapis.com/calendar/v3/calendars/{safe_calendar_id}/events/'
        f'{safe_event_id}'
    )
    return _json_request(
        url,
        method='PUT',
        payload=payload,
        headers=_build_google_calendar_headers(access_token),
    )


def _exchange_oauth_code_for_tokens(authorization_code, redirect_uri):
    client_id = os.getenv('GMAIL_CLIENT_ID')
    client_secret = os.getenv('GMAIL_CLIENT_SECRET')

    if not client_id or not client_secret:
        raise ValueError('GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET must be configured.')

    token_payload = {
        'code': authorization_code,
        'client_id': client_id,
        'client_secret': client_secret,
        'redirect_uri': redirect_uri,
        'grant_type': 'authorization_code',
    }
    token_data = _json_request(
        'https://oauth2.googleapis.com/token',
        method='POST',
        payload=token_payload,
    )

    access_token = token_data.get('access_token')
    refresh_token = token_data.get('refresh_token')
    expires_in = token_data.get('expires_in')
    scope = token_data.get('scope', '')

    if not access_token or not refresh_token:
        raise ValueError(
            'Google token response is missing access_token/refresh_token. '
            'Ensure offline access and consent prompt are enabled in OAuth flow.'
        )

    token_expiry = None
    if expires_in:
        token_expiry = timezone.now() + datetime.timedelta(seconds=int(expires_in))

    return {
        'access_token': access_token,
        'refresh_token': refresh_token,
        'token_expiry': token_expiry,
        'scope': scope,
    }


def _refresh_access_token(integration):
    client_id = os.getenv('GMAIL_CLIENT_ID')
    client_secret = os.getenv('GMAIL_CLIENT_SECRET')
    if not client_id or not client_secret:
        raise ValueError('GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET must be configured.')

    token_payload = {
        'client_id': client_id,
        'client_secret': client_secret,
        'refresh_token': integration.refresh_token,
        'grant_type': 'refresh_token',
    }
    token_data = _json_request(
        'https://oauth2.googleapis.com/token',
        method='POST',
        payload=token_payload,
    )

    access_token = token_data.get('access_token')
    expires_in = token_data.get('expires_in')
    if not access_token:
        raise ValueError('Google token refresh did not return access_token.')

    integration.access_token = access_token
    if expires_in:
        integration.token_expiry = timezone.now() + datetime.timedelta(seconds=int(expires_in))
    integration.save(update_fields=['access_token', 'token_expiry', 'updated_at'])


def _ensure_valid_access_token(integration):
    if integration.token_expiry is None:
        return integration.access_token

    remaining = (integration.token_expiry - timezone.now()).total_seconds()
    if remaining > 60:
        return integration.access_token

    _refresh_access_token(integration)
    integration.refresh_from_db(fields=['access_token', 'token_expiry'])
    return integration.access_token


def _get_gmail_profile(access_token):
    return _json_request(
        'https://gmail.googleapis.com/gmail/v1/users/me/profile',
        headers=_build_gmail_headers(access_token),
    )


def _list_gmail_messages(access_token, max_results):
    query = os.getenv(
        'GMAIL_FETCH_QUERY',
        'newer_than:7d -category:promotions -category:social',
    )
    encoded_q = urllib.parse.quote(query)
    url = (
        'https://gmail.googleapis.com/gmail/v1/users/me/messages'
        f'?maxResults={max_results}&q={encoded_q}'
    )
    data = _json_request(url, headers=_build_gmail_headers(access_token))
    return data.get('messages', [])


def _get_message_metadata(access_token, message_id):
    url = (
        'https://gmail.googleapis.com/gmail/v1/users/me/messages/'
        f'{message_id}?format=metadata&metadataHeaders=Subject&metadataHeaders=Date'
    )
    return _json_request(url, headers=_build_gmail_headers(access_token))


def _extract_header_value(message, name):
    payload = message.get('payload', {})
    headers = payload.get('headers', [])
    for header in headers:
        if header.get('name', '').lower() == name.lower():
            return header.get('value', '')
    return ''


def _parse_task_datetime(value):
    dt = datetime.datetime.strptime(value, '%Y-%m-%dT%H:%M')
    if timezone.is_naive(dt):
        return timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def _looks_non_actionable_email(subject, snippet):
    text = f'{subject} {snippet}'.lower()
    for keyword in NON_ACTIONABLE_KEYWORDS:
        if keyword in text:
            return True
    return False


def _extract_email_task_strict(subject, snippet):
    try:
        from openai import (
            APIConnectionError,
            APIStatusError,
            APITimeoutError,
            OpenAI,
            RateLimitError,
        )
    except ImportError as exc:
        raise ValueError(
            'OpenAI SDK is not installed. Install it with `pip install openai`.'
        ) from exc

    api_key = os.getenv('GROQ_API_KEY')
    if not api_key:
        raise ValueError('GROQ_API_KEY is not configured.')

    model = os.getenv(
        'GROQ_EMAIL_TASK_MODEL',
        os.getenv('GROQ_TASK_MODEL', 'llama-3.1-8b-instant'),
    )
    now = timezone.localtime(timezone.now())
    today = now.date().isoformat()
    now_iso = now.strftime('%Y-%m-%dT%H:%M')

    client = OpenAI(
        api_key=api_key,
        base_url='https://api.groq.com/openai/v1',
    )
    try:
        completion = client.chat.completions.create(
            model=model,
            temperature=0,
            response_format={'type': 'json_object'},
            messages=[
                {
                    'role': 'system',
                    'content': (
                        'You are a strict email-to-task gatekeeper. '
                        'Create tasks ONLY for concrete, necessary, user-actionable commitments '
                        'with a clear or inferable reminder time. '
                        'ALWAYS reject marketing/sponsored/promotional/newsletter/subscription/social digest/'
                        'content recommendations/general updates/receipts without required user action. '
                        'If uncertain, reject. '
                        'Return JSON only with keys: should_create_task, title, datetime, reason. '
                        'should_create_task must be boolean. '
                        'If false, set title and datetime to null. '
                        'If true, datetime must be YYYY-MM-DDTHH:MM (24h, no timezone suffix). '
                        f'Use today={today} and current_time={now_iso} for relative dates.'
                    ),
                },
                {
                    'role': 'user',
                    'content': (
                        f'Email subject: {subject}\n'
                        f'Email snippet: {snippet}\n'
                        'Decide if this should become a task.'
                    ),
                },
            ],
        )
    except RateLimitError as exc:
        raise ValueError('Groq quota exceeded while classifying email.') from exc
    except (APIConnectionError, APITimeoutError) as exc:
        raise ValueError('Groq service is temporarily unreachable.') from exc
    except APIStatusError as exc:
        raise ValueError(f'Groq API error: {exc.status_code}') from exc

    content = completion.choices[0].message.content
    if not content:
        raise ValueError('Groq returned empty strict-classification response.')

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError('Groq strict-classification response was not valid JSON.') from exc

    should_create = parsed.get('should_create_task')
    if should_create is not True:
        return {
            'should_create_task': False,
            'reason': str(parsed.get('reason', 'Non-actionable email')).strip(),
        }

    title = parsed.get('title')
    task_datetime = parsed.get('datetime')
    if not title or not task_datetime:
        raise ValueError('Groq marked email actionable but missed title/datetime.')

    return {
        'should_create_task': True,
        'title': str(title).strip(),
        'datetime': str(task_datetime).strip(),
        'reason': str(parsed.get('reason', '')).strip(),
    }


def _validate_whatsapp_signature(request):
    app_secret = os.getenv('WHATSAPP_APP_SECRET')
    if not app_secret:
        return True

    signature = request.headers.get('X-Hub-Signature-256', '')
    if not signature:
        return False

    expected = 'sha256=' + hmac.new(
        app_secret.encode('utf-8'),
        request.body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(signature, expected)


def _extract_whatsapp_task_strict(message_text):
    try:
        from openai import (
            APIConnectionError,
            APIStatusError,
            APITimeoutError,
            OpenAI,
            RateLimitError,
        )
    except ImportError as exc:
        raise ValueError(
            'OpenAI SDK is not installed. Install it with `pip install openai`.'
        ) from exc

    api_key = os.getenv('GROQ_API_KEY')
    if not api_key:
        raise ValueError('GROQ_API_KEY is not configured.')

    model = os.getenv(
        'GROQ_WHATSAPP_TASK_MODEL',
        os.getenv('GROQ_TASK_MODEL', 'llama-3.1-8b-instant'),
    )
    now = timezone.localtime(timezone.now())
    today = now.date().isoformat()
    now_iso = now.strftime('%Y-%m-%dT%H:%M')

    client = OpenAI(
        api_key=api_key,
        base_url='https://api.groq.com/openai/v1',
    )

    try:
        completion = client.chat.completions.create(
            model=model,
            temperature=0,
            response_format={'type': 'json_object'},
            messages=[
                {
                    'role': 'system',
                    'content': (
                        'You are a strict WhatsApp-message-to-task gatekeeper. '
                        'Create tasks ONLY for clear user-actionable commitments with a clear or '
                        'inferable reminder time. If uncertain, reject. '
                        'Return JSON only with keys: should_create_task, title, datetime, reason. '
                        'should_create_task must be boolean. '
                        'If false, set title and datetime to null. '
                        'If true, datetime must be YYYY-MM-DDTHH:MM (24h, no timezone suffix). '
                        f'Use today={today} and current_time={now_iso} for relative dates.'
                    ),
                },
                {
                    'role': 'user',
                    'content': (
                        f'WhatsApp message: {message_text}\n'
                        'Decide if this should become a task.'
                    ),
                },
            ],
        )
    except RateLimitError as exc:
        raise ValueError('Groq quota exceeded while classifying WhatsApp message.') from exc
    except (APIConnectionError, APITimeoutError) as exc:
        raise ValueError('Groq service is temporarily unreachable.') from exc
    except APIStatusError as exc:
        raise ValueError(f'Groq API error: {exc.status_code}') from exc

    content = completion.choices[0].message.content
    if not content:
        raise ValueError('Groq returned empty strict-classification response.')

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError('Groq strict-classification response was not valid JSON.') from exc

    should_create = parsed.get('should_create_task')
    if should_create is not True:
        return {
            'should_create_task': False,
            'reason': str(parsed.get('reason', 'Non-actionable WhatsApp message')).strip(),
        }

    title = parsed.get('title')
    task_datetime = parsed.get('datetime')
    if not title or not task_datetime:
        raise ValueError('Groq marked WhatsApp message actionable but missed title/datetime.')

    return {
        'should_create_task': True,
        'title': str(title).strip(),
        'datetime': str(task_datetime).strip(),
        'reason': str(parsed.get('reason', '')).strip(),
    }


@swagger_auto_schema(
    method='post',
    request_body=GmailConnectRequestSerializer,
    responses={
        200: GmailConnectResponseSerializer(),
        400: 'Bad Request',
        401: 'Unauthorized',
        502: 'Google API Error',
    },
)
@api_view(['POST'])
def gmail_connect(request):
    user = _get_user_from_auth_header(request)
    if user is None:
        return _unauthorized_response()

    serializer = GmailConnectRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    authorization_code = serializer.validated_data['authorization_code']
    redirect_uri = serializer.validated_data['redirect_uri']

    try:
        token_data = _exchange_oauth_code_for_tokens(authorization_code, redirect_uri)
        profile = _get_gmail_profile(token_data['access_token'])
    except ValueError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

    gmail_email = profile.get('emailAddress')
    if not gmail_email:
        return Response(
            {'error': 'Could not resolve Gmail account email from profile.'},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    integration, _created = GmailIntegration.objects.update_or_create(
        user=user,
        defaults={
            'gmail_email': gmail_email,
            'access_token': token_data['access_token'],
            'refresh_token': token_data['refresh_token'],
            'token_expiry': token_data['token_expiry'],
            'scope': token_data['scope'],
        },
    )

    response_payload = {
        'connected': True,
        'gmail_email': integration.gmail_email,
        'token_expiry': integration.token_expiry,
        'scope': integration.scope,
    }
    return Response(response_payload, status=status.HTTP_200_OK)


@swagger_auto_schema(
    method='get',
    responses={
        200: GmailFetchResponseSerializer(),
        401: 'Unauthorized',
        404: 'Gmail Not Connected',
        502: 'Google API Error',
    },
)
@api_view(['GET'])
def gmail_fetch(request):
    user = _get_user_from_auth_header(request)
    if user is None:
        return _unauthorized_response()

    try:
        integration = GmailIntegration.objects.get(user=user)
    except GmailIntegration.DoesNotExist:
        return Response(
            {'error': 'Gmail is not connected. Call /api/integrations/gmail/connect first.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    max_results_raw = request.query_params.get('max_results', '10')
    try:
        max_results = min(max(int(max_results_raw), 1), 50)
    except ValueError:
        return Response(
            {'error': 'max_results must be an integer between 1 and 50.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        access_token = _ensure_valid_access_token(integration)
        messages = _list_gmail_messages(access_token, max_results=max_results)
    except ValueError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

    fetched = len(messages)
    created = 0
    skipped = 0
    failed = 0
    created_tasks = []

    for entry in messages:
        message_id = entry.get('id')
        subject = ''
        snippet = ''
        if not message_id:
            skipped += 1
            continue

        if GmailSyncedMessage.objects.filter(user=user, gmail_message_id=message_id).exists():
            skipped += 1
            continue

        try:
            metadata = _get_message_metadata(access_token, message_id)
            subject = _extract_header_value(metadata, 'Subject')
            snippet = metadata.get('snippet', '')

            if _looks_non_actionable_email(subject, snippet):
                skipped += 1
                GmailSyncedMessage.objects.create(
                    user=user,
                    integration=integration,
                    gmail_message_id=message_id,
                    subject=subject,
                    snippet=snippet,
                    extraction_status=GmailSyncedMessage.STATUS_SKIPPED,
                    error_message='Skipped by strict keyword filter (non-actionable/promotional).',
                )
                continue

            extracted = _extract_email_task_strict(subject, snippet)
            if not extracted.get('should_create_task'):
                skipped += 1
                GmailSyncedMessage.objects.create(
                    user=user,
                    integration=integration,
                    gmail_message_id=message_id,
                    subject=subject,
                    snippet=snippet,
                    extraction_status=GmailSyncedMessage.STATUS_SKIPPED,
                    error_message=extracted.get('reason', 'Skipped by strict AI relevance filter.'),
                )
                continue

            task_datetime = _parse_task_datetime(extracted['datetime'])

            task = Task.objects.create(
                user=user,
                title=extracted['title'],
                description=f'From Gmail: {subject}'.strip(),
                datetime=task_datetime,
                source='gmail',
                status='pending',
            )

            GmailSyncedMessage.objects.create(
                user=user,
                integration=integration,
                gmail_message_id=message_id,
                subject=subject,
                snippet=snippet,
                task=task,
                extraction_status=GmailSyncedMessage.STATUS_CREATED,
            )

            created += 1
            created_tasks.append(
                {
                    'id': task.id,
                    'title': task.title,
                    'datetime': task.datetime.isoformat(),
                    'source': task.source,
                }
            )
        except IntegrityError:
            skipped += 1
        except ValueError as exc:
            failed += 1
            GmailSyncedMessage.objects.create(
                user=user,
                integration=integration,
                gmail_message_id=message_id,
                subject=subject,
                snippet=snippet,
                extraction_status=GmailSyncedMessage.STATUS_FAILED,
                error_message=str(exc),
            )

    response_payload = {
        'fetched': fetched,
        'created': created,
        'skipped': skipped,
        'failed': failed,
        'tasks': created_tasks,
    }
    return Response(response_payload, status=status.HTTP_200_OK)


@swagger_auto_schema(
    method='post',
    request_body=WhatsAppConnectRequestSerializer,
    responses={
        200: WhatsAppConnectResponseSerializer(),
        401: 'Unauthorized',
        409: 'Phone number already connected by another user',
    },
)
@api_view(['POST'])
def whatsapp_connect(request):
    user = _get_user_from_auth_header(request)
    if user is None:
        return _unauthorized_response()

    serializer = WhatsAppConnectRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    phone_number_id = serializer.validated_data['phone_number_id']
    business_phone_number = serializer.validated_data.get('business_phone_number', '')

    try:
        integration, _created = WhatsAppIntegration.objects.update_or_create(
            user=user,
            defaults={
                'phone_number_id': phone_number_id,
                'business_phone_number': business_phone_number,
            },
        )
    except IntegrityError:
        return Response(
            {'error': 'This phone_number_id is already connected with another user.'},
            status=status.HTTP_409_CONFLICT,
        )

    return Response(
        {
            'connected': True,
            'phone_number_id': integration.phone_number_id,
            'business_phone_number': integration.business_phone_number,
        },
        status=status.HTTP_200_OK,
    )


def _extract_whatsapp_text(message):
    msg_type = message.get('type', '')
    if msg_type == 'text':
        return message.get('text', {}).get('body', ''), msg_type
    return '', msg_type


@swagger_auto_schema(
    method='get',
    responses={
        200: 'Webhook verified',
        403: 'Verification failed',
    },
)
@swagger_auto_schema(
    method='post',
    responses={
        200: 'Webhook accepted',
        401: 'Invalid webhook signature',
    },
)
@api_view(['GET', 'POST'])
def whatsapp_webhook(request):
    if request.method == 'GET':
        mode = request.query_params.get('hub.mode')
        verify_token = request.query_params.get('hub.verify_token')
        challenge = request.query_params.get('hub.challenge')
        expected_token = os.getenv('WHATSAPP_VERIFY_TOKEN', '')

        if mode == 'subscribe' and verify_token and verify_token == expected_token:
            return HttpResponse(challenge or '', status=200, content_type='text/plain')
        return Response({'error': 'Webhook verification failed.'}, status=status.HTTP_403_FORBIDDEN)

    if not _validate_whatsapp_signature(request):
        return Response({'error': 'Invalid webhook signature.'}, status=status.HTTP_401_UNAUTHORIZED)

    payload = request.data if isinstance(request.data, dict) else {}
    entries = payload.get('entry', [])
    if not isinstance(entries, list):
        return Response({'status': 'ignored'}, status=status.HTTP_200_OK)

    for entry in entries:
        changes = entry.get('changes', [])
        if not isinstance(changes, list):
            continue

        for change in changes:
            if change.get('field') != 'messages':
                continue

            value = change.get('value', {})
            metadata = value.get('metadata', {})
            phone_number_id = metadata.get('phone_number_id')
            if not phone_number_id:
                continue

            try:
                integration = WhatsAppIntegration.objects.get(phone_number_id=phone_number_id)
            except WhatsAppIntegration.DoesNotExist:
                continue

            messages = value.get('messages', [])
            if not isinstance(messages, list):
                continue

            for message in messages:
                message_id = message.get('id')
                if not message_id:
                    continue

                if WhatsAppSyncedMessage.objects.filter(
                    user=integration.user,
                    whatsapp_message_id=message_id,
                ).exists():
                    continue

                from_number = str(message.get('from', '')).strip()
                text_body, message_type = _extract_whatsapp_text(message)

                if message_type != 'text' or not text_body.strip():
                    WhatsAppSyncedMessage.objects.create(
                        user=integration.user,
                        integration=integration,
                        whatsapp_message_id=message_id,
                        from_number=from_number,
                        message_type=message_type,
                        text_body=text_body,
                        raw_payload=message,
                        extraction_status=WhatsAppSyncedMessage.STATUS_SKIPPED,
                        error_message='Unsupported or empty message type for task extraction.',
                    )
                    continue

                try:
                    extracted = _extract_whatsapp_task_strict(text_body)
                    if not extracted.get('should_create_task'):
                        WhatsAppSyncedMessage.objects.create(
                            user=integration.user,
                            integration=integration,
                            whatsapp_message_id=message_id,
                            from_number=from_number,
                            message_type=message_type,
                            text_body=text_body,
                            raw_payload=message,
                            extraction_status=WhatsAppSyncedMessage.STATUS_SKIPPED,
                            error_message=extracted.get(
                                'reason',
                                'Skipped by strict AI relevance filter.',
                            ),
                        )
                        continue

                    task_datetime = _parse_task_datetime(extracted['datetime'])
                    task = Task.objects.create(
                        user=integration.user,
                        title=extracted['title'],
                        description=f'From WhatsApp {from_number}: {text_body}'.strip(),
                        datetime=task_datetime,
                        source='whatsapp',
                        status='pending',
                    )

                    WhatsAppSyncedMessage.objects.create(
                        user=integration.user,
                        integration=integration,
                        whatsapp_message_id=message_id,
                        from_number=from_number,
                        message_type=message_type,
                        text_body=text_body,
                        raw_payload=message,
                        task=task,
                        extraction_status=WhatsAppSyncedMessage.STATUS_CREATED,
                    )
                except ValueError as exc:
                    WhatsAppSyncedMessage.objects.create(
                        user=integration.user,
                        integration=integration,
                        whatsapp_message_id=message_id,
                        from_number=from_number,
                        message_type=message_type,
                        text_body=text_body,
                        raw_payload=message,
                        extraction_status=WhatsAppSyncedMessage.STATUS_FAILED,
                        error_message=str(exc),
                    )
                except IntegrityError:
                    continue

    return Response({'status': 'received'}, status=status.HTTP_200_OK)


@swagger_auto_schema(
    method='get',
    responses={
        200: WhatsAppFetchResponseSerializer(),
        401: 'Unauthorized',
        404: 'WhatsApp Not Connected',
    },
)
@api_view(['GET'])
def whatsapp_fetch(request):
    user = _get_user_from_auth_header(request)
    if user is None:
        return _unauthorized_response()

    try:
        WhatsAppIntegration.objects.get(user=user)
    except WhatsAppIntegration.DoesNotExist:
        return Response(
            {'error': 'WhatsApp is not connected. Call /api/integrations/whatsapp/connect first.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    limit_raw = request.query_params.get('limit', '20')
    try:
        limit = min(max(int(limit_raw), 1), 100)
    except ValueError:
        return Response(
            {'error': 'limit must be an integer between 1 and 100.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    rows = list(
        WhatsAppSyncedMessage.objects.filter(user=user)
        .select_related('task')
        .order_by('-received_at')[:limit]
    )

    created = 0
    skipped = 0
    failed = 0
    tasks = []
    messages = []
    task_ids = set()

    for row in rows:
        if row.extraction_status == WhatsAppSyncedMessage.STATUS_CREATED:
            created += 1
        elif row.extraction_status == WhatsAppSyncedMessage.STATUS_FAILED:
            failed += 1
        else:
            skipped += 1

        messages.append(
            {
                'id': row.whatsapp_message_id,
                'from': row.from_number,
                'type': row.message_type,
                'text': row.text_body,
                'status': row.extraction_status,
                'error': row.error_message,
                'received_at': row.received_at.isoformat(),
            }
        )

        if row.task_id and row.task_id not in task_ids:
            task_ids.add(row.task_id)
            tasks.append(
                {
                    'id': row.task.id,
                    'title': row.task.title,
                    'datetime': row.task.datetime.isoformat(),
                    'source': row.task.source,
                }
            )

    return Response(
        {
            'fetched': len(rows),
            'created': created,
            'skipped': skipped,
            'failed': failed,
            'tasks': tasks,
            'messages': messages,
        },
        status=status.HTTP_200_OK,
    )


@swagger_auto_schema(
    method='post',
    request_body=GoogleCalendarSyncRequestSerializer,
    responses={
        200: GoogleCalendarSyncResponseSerializer(),
        400: 'Bad Request',
        401: 'Unauthorized',
        404: 'Gmail Not Connected',
        502: 'Google API Error',
    },
)
@api_view(['POST'])
def google_calendar_sync_tasks(request):
    user = _get_user_from_auth_header(request)
    if user is None:
        return _unauthorized_response()

    try:
        integration = GmailIntegration.objects.get(user=user)
    except GmailIntegration.DoesNotExist:
        return Response(
            {'error': 'Gmail is not connected. Connect Gmail before syncing calendar.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not _has_calendar_scope(integration.scope):
        return Response(
            {
                'error': (
                    'Google Calendar scope is missing. Reconnect Gmail with '
                    '`https://www.googleapis.com/auth/calendar.events` scope.'
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    serializer = GoogleCalendarSyncRequestSerializer(data=request.data or {})
    serializer.is_valid(raise_exception=True)
    task_ids = serializer.validated_data.get('task_ids', [])

    tasks_qs = Task.objects.filter(user=user).order_by('datetime', 'id')
    if task_ids:
        tasks_qs = tasks_qs.filter(id__in=task_ids)

    tasks = list(tasks_qs)
    if not tasks:
        return Response(
            {'total': 0, 'synced': 0, 'failed': 0, 'results': []},
            status=status.HTTP_200_OK,
        )

    try:
        access_token = _ensure_valid_access_token(integration)
    except ValueError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

    synced = 0
    failed = 0
    results = []

    for task in tasks:
        sync_record = GoogleCalendarTaskSync.objects.filter(user=user, task=task).first()
        try:
            if sync_record:
                calendar_data = _update_calendar_event(
                    access_token,
                    sync_record.calendar_id,
                    sync_record.calendar_event_id,
                    task,
                )
                event_id = calendar_data.get('id', sync_record.calendar_event_id)
                sync_record.calendar_event_id = event_id
                sync_record.status = GoogleCalendarTaskSync.STATUS_SYNCED
                sync_record.error_message = ''
                sync_record.save(
                    update_fields=[
                        'calendar_event_id',
                        'status',
                        'error_message',
                        'synced_at',
                    ]
                )
            else:
                calendar_data = _create_calendar_event(access_token, task)
                event_id = calendar_data.get('id')
                if not event_id:
                    raise ValueError('Google Calendar response missing event id.')
                GoogleCalendarTaskSync.objects.create(
                    user=user,
                    integration=integration,
                    task=task,
                    calendar_id='primary',
                    calendar_event_id=event_id,
                    status=GoogleCalendarTaskSync.STATUS_SYNCED,
                )

            synced += 1
            results.append(
                {
                    'task_id': task.id,
                    'title': task.title,
                    'status': 'synced',
                }
            )
        except ValueError as exc:
            failed += 1
            error_text = str(exc)
            if sync_record:
                sync_record.status = GoogleCalendarTaskSync.STATUS_FAILED
                sync_record.error_message = error_text
                sync_record.save(update_fields=['status', 'error_message', 'synced_at'])

            results.append(
                {
                    'task_id': task.id,
                    'title': task.title,
                    'status': 'failed',
                    'error': error_text,
                }
            )

    return Response(
        {
            'total': len(tasks),
            'synced': synced,
            'failed': failed,
            'results': results,
        },
        status=status.HTTP_200_OK,
    )
