from rest_framework import serializers


class TaskExtractionRequestSerializer(serializers.Serializer):
    text = serializers.CharField(required=True, allow_blank=False)


class TaskExtractionResponseSerializer(serializers.Serializer):
    title = serializers.CharField()
    datetime = serializers.DateTimeField(format='%Y-%m-%dT%H:%M')
