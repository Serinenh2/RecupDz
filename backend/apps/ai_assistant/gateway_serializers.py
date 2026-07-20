"""
Gateway Serializers — request/response validation for AI Gateway.
"""

from rest_framework import serializers


# ── Request Serializers ───────────────────────────────────────────────


class ChatRequestSerializer(serializers.Serializer):
    """Chat request payload."""
    message = serializers.CharField(
        max_length=5000,
        help_text="User message",
    )
    conversation_id = serializers.CharField(
        max_length=128,
        required=False,
        default="",
        help_text="Conversation ID for context",
    )
    session_id = serializers.CharField(
        max_length=128,
        required=False,
        default="",
        help_text="Session ID",
    )
    lang = serializers.ChoiceField(
        choices=["fr", "ar", "en"],
        default="fr",
        help_text="Response language",
    )
    entity_type = serializers.CharField(
        max_length=50,
        required=False,
        allow_null=True,
        help_text="Entity type (bsd, recuperateur, etc.)",
    )
    entity_id = serializers.CharField(
        max_length=50,
        required=False,
        allow_null=True,
        help_text="Entity ID",
    )


# ── Response Serializers ──────────────────────────────────────────────


class GatewayMetaSerializer(serializers.Serializer):
    """Metadata from the gateway."""
    request_id = serializers.CharField()
    intent = serializers.CharField(allow_blank=True)
    confidence = serializers.FloatField()
    tool_used = serializers.CharField(allow_null=True, allow_blank=True)
    tool_action = serializers.CharField(allow_blank=True)
    selection_source = serializers.CharField(allow_blank=True)
    elapsed_ms = serializers.FloatField()
    trace_id = serializers.CharField(allow_blank=True)
    cached = serializers.BooleanField()
    error = serializers.CharField(allow_null=True, allow_blank=True)


class ChatResponseSerializer(serializers.Serializer):
    """Chat response payload — mirrors GatewayResponse.to_dict()."""
    success = serializers.BooleanField()
    message = serializers.CharField()
    data = serializers.DictField(default=dict)
    followups = serializers.ListField(child=serializers.CharField(), default=list)
    meta = GatewayMetaSerializer()


class HealthResponseSerializer(serializers.Serializer):
    """Health check response."""
    ollama = serializers.DictField()
    tools = serializers.ListField(child=serializers.CharField())
    cache_stats = serializers.DictField()
    metrics = serializers.DictField()
    tracing = serializers.DictField()
    audit = serializers.DictField()


class CapabilitiesResponseSerializer(serializers.Serializer):
    """Capabilities response."""
    intents = serializers.ListField(child=serializers.DictField())
    tools = serializers.ListField(child=serializers.CharField())
    languages = serializers.ListField(child=serializers.CharField())
    version = serializers.CharField(default="2.0.0")
