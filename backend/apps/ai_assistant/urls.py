"""
URL Configuration — AI Gateway endpoints.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.ai_assistant.gateway_views import chat, chat_stream, health, capabilities, metrics
from apps.ai_assistant.views import (
    AIConversationViewSet, AIMessageViewSet, AIAlertViewSet,
    KnowledgeBaseViewSet, AIRecommendationViewSet, AIDashboardViewSet
)

router = DefaultRouter()
router.register(r"conversations", AIConversationViewSet, basename="ai-conversation")
router.register(r"messages", AIMessageViewSet, basename="ai-message")
router.register(r"alerts", AIAlertViewSet, basename="ai-alert")
router.register(r"knowledge", KnowledgeBaseViewSet, basename="ai-knowledge")
router.register(r"recommendations", AIRecommendationViewSet, basename="ai-recommendation")
router.register(r"dashboard", AIDashboardViewSet, basename="ai-dashboard")

urlpatterns = [
    # Enterprise Gateway endpoints
    path("chat/", chat, name="ai-chat"),
    path("chat/stream/", chat_stream, name="ai-chat-stream"),
    path("health/", health, name="ai-health"),
    path("capabilities/", capabilities, name="ai-capabilities"),
    path("metrics/", metrics, name="ai-metrics"),
    # ViewSet endpoints
    path("", include(router.urls)),
]
