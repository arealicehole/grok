"""Service registry integration for Jubal ecosystem."""

import json
import asyncio
from typing import Dict, Any, Optional
import redis.asyncio as redis
from app.config import settings


class ServiceRegistry:
    """Redis-based service registry integration."""

    def __init__(self, redis_url: str = settings.redis_url):
        self.redis_url = redis_url
        self.redis_client: Optional[redis.Redis] = None
        self.service_info = {
            "service": "grok-adapter",
            "version": "1.0.0",
            "host": "grok-adapter",
            "port": settings.service_port,
            "health_endpoint": "/health",
            "capabilities": ["analyze", "extract", "summarize"],
            "features": {
                "multi_step_processing": True,
                "profile_based_analysis": True,
                "model_selection": True,
                "global_overrides": True
            },
            "supported_providers": ["local", "openrouter"],
            "available_profiles": ["business_meeting", "project_planning", "personal_notes"]
        }

    async def connect(self):
        """Connect to Redis service registry."""
        try:
            self.redis_client = redis.from_url(self.redis_url)
            await self.redis_client.ping()
            await self.register_service()
            return True
        except Exception as e:
            print(f"Failed to connect to Redis: {e}")
            return False

    async def register_service(self):
        """Register this service with the registry."""
        if self.redis_client:
            try:
                await self.redis_client.hset(
                    "jubal:services",
                    "grok-adapter",
                    json.dumps(self.service_info)
                )
                print("Service registered with Jubal registry")
            except Exception as e:
                print(f"Failed to register service: {e}")

    async def update_health_status(self, status: str = "healthy"):
        """Update service health status."""
        if self.redis_client:
            try:
                health_info = {
                    **self.service_info,
                    "status": status,
                    "last_seen": asyncio.get_event_loop().time()
                }
                await self.redis_client.hset(
                    "jubal:services",
                    "grok-adapter",
                    json.dumps(health_info)
                )
            except Exception as e:
                print(f"Failed to update health status: {e}")

    async def disconnect(self):
        """Disconnect from Redis and cleanup."""
        if self.redis_client:
            try:
                await self.redis_client.hdel("jubal:services", "grok-adapter")
                await self.redis_client.close()
            except Exception as e:
                print(f"Failed to cleanup service registry: {e}")

    async def get_services(self) -> Dict[str, Any]:
        """Get all registered services."""
        if self.redis_client:
            try:
                services = await self.redis_client.hgetall("jubal:services")
                return {k.decode(): json.loads(v.decode()) for k, v in services.items()}
            except Exception as e:
                print(f"Failed to get services: {e}")
                return {}