"""
API Documentation — OpenAPI/Swagger schema generator.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class APIDocumentation:
    """Generate OpenAPI documentation for the AI assistant API."""

    def __init__(self, title: str = "RecupDZ AI Assistant API", version: str = "1.0.0") -> None:
        self._title = title
        self._version = version

    def generate_schema(self) -> Dict[str, Any]:
        """Generate complete OpenAPI schema."""
        return {
            "openapi": "3.0.3",
            "info": {
                "title": self._title,
                "version": self._version,
                "description": "AI-powered waste management assistant for RecupDZ",
                "contact": {"name": "RecupDZ Support"},
            },
            "servers": [
                {"url": "http://localhost:8002", "description": "Development"},
                {"url": "https://api.recupdz.dz", "description": "Production"},
            ],
            "paths": self._paths(),
            "components": self._components(),
            "tags": [
                {"name": "chat", "description": "AI Chat endpoints"},
                {"name": "conversations", "description": "Conversation management"},
                {"name": "tools", "description": "Tool execution"},
                {"name": "health", "description": "Health and monitoring"},
            ],
        }

    def _paths(self) -> Dict[str, Any]:
        return {
            "/api/assistant/chat": {
                "post": {
                    "tags": ["chat"],
                    "summary": "Send a chat message to the AI assistant",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ChatRequest"},
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Successful response",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ChatResponse"},
                                }
                            },
                        },
                        "429": {"description": "Rate limit exceeded"},
                        "503": {"description": "Service unavailable"},
                    },
                },
            },
            "/api/assistant/chat/stream": {
                "post": {
                    "tags": ["chat"],
                    "summary": "Stream a chat response (SSE)",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ChatRequest"},
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Streaming response",
                            "content": {"text/event-stream": {}},
                        },
                    },
                },
            },
            "/api/ai/health": {
                "get": {
                    "tags": ["health"],
                    "summary": "Check system health",
                    "responses": {
                        "200": {
                            "description": "Health status",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/HealthResponse"},
                                }
                            },
                        },
                    },
                },
            },
            "/api/ai/metrics": {
                "get": {
                    "tags": ["health"],
                    "summary": "Get system metrics (Prometheus format)",
                    "responses": {
                        "200": {"description": "Prometheus metrics", "content": {"text/plain": {}}},
                    },
                },
            },
            "/api/ai/tools": {
                "get": {
                    "tags": ["tools"],
                    "summary": "List available AI tools",
                    "responses": {
                        "200": {
                            "description": "Tool list",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ToolListResponse"},
                                }
                            },
                        },
                    },
                },
            },
        }

    def _components(self) -> Dict[str, Any]:
        return {
            "schemas": {
                "ChatRequest": {
                    "type": "object",
                    "required": ["message"],
                    "properties": {
                        "message": {"type": "string", "description": "User message", "maxLength": 10000},
                        "conversation_id": {"type": "string", "description": "Conversation ID for context"},
                        "stream": {"type": "boolean", "default": False},
                        "metadata": {"type": "object", "description": "Additional metadata"},
                    },
                },
                "ChatResponse": {
                    "type": "object",
                    "properties": {
                        "success": {"type": "boolean"},
                        "message": {"type": "string"},
                        "data": {
                            "type": "object",
                            "properties": {
                                "response": {"type": "string"},
                                "intent": {"type": "string"},
                                "confidence": {"type": "number"},
                                "tool_used": {"type": "string"},
                                "conversation_id": {"type": "string"},
                                "metadata": {"type": "object"},
                            },
                        },
                    },
                },
                "HealthResponse": {
                    "type": "object",
                    "properties": {
                        "status": {"type": "string", "enum": ["healthy", "degraded", "unhealthy"]},
                        "version": {"type": "string"},
                        "components": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "status": {"type": "string"},
                                    "latency_ms": {"type": "number"},
                                },
                            },
                        },
                    },
                },
                "ToolListResponse": {
                    "type": "object",
                    "properties": {
                        "tools": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "description": {"type": "string"},
                                    "parameters": {"type": "object"},
                                },
                            },
                        },
                    },
                },
                "Error": {
                    "type": "object",
                    "properties": {
                        "success": {"type": "boolean", "enum": [False]},
                        "error": {"type": "string"},
                        "code": {"type": "string"},
                    },
                },
            },
            "securitySchemes": {
                "Bearer": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT",
                }
            },
        }
