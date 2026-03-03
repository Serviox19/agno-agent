"""xAI Grok model using the Responses API with x_search and web_search tools."""
from dataclasses import dataclass
from os import getenv
from typing import Any, Dict, List, Optional, Type, Union

from agno.models.openai.responses import OpenAIResponses
from agno.models.message import Message
from agno.exceptions import ModelAuthenticationError
from pydantic import BaseModel


@dataclass
class XAIResponses(OpenAIResponses):
    """Grok via xAI Responses API with native x_search and web_search tools.
    
    Requires grok-4 family models for server-side tools.
    """

    id: str = "grok-4-1-fast-reasoning"
    name: str = "XAIResponses"
    provider: str = "xAI"

    def _get_client_params(self) -> Dict[str, Any]:
        if not self.api_key:
            self.api_key = getenv("XAI_API_KEY")
            if not self.api_key:
                raise ModelAuthenticationError(
                    message="XAI_API_KEY not set. Set the XAI_API_KEY environment variable.",
                    model_name=self.name,
                )
        return {
            "api_key": self.api_key,
            "base_url": "https://api.x.ai/v1",
            "timeout": 120.0,
        }

    def get_request_params(
        self,
        messages: Optional[List[Message]] = None,
        response_format: Optional[Union[Dict, Type[BaseModel]]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        # Prepend xAI server-side tools before any agent tools
        server_tools = [{"type": "x_search"}, {"type": "web_search"}]
        merged_tools = server_tools + (tools or [])
        return super().get_request_params(
            messages=messages,
            response_format=response_format,
            tools=merged_tools,
            tool_choice=tool_choice,
        )
