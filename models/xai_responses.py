"""xAI Grok model using the Responses API with Agent Tools (x_search, web_search).

Replaces deprecated live search. Uses /v1/responses endpoint with server-side tools.
"""
from os import getenv
from typing import Any, Dict, List, Optional, Type, Union

from agno.exceptions import ModelAuthenticationError
from agno.models.message import Message
from agno.models.openai.responses import OpenAIResponses
from pydantic import BaseModel


# Server-side tools for xAI Agent Tools API (replaces deprecated live search)
XAI_SERVER_TOOLS = [
    {"type": "x_search"},
    {"type": "web_search"},
]


class XAIResponses(OpenAIResponses):
    """Grok via xAI Responses API with native x_search and web_search tools."""

    id: str = "grok-4-1-fast-reasoning"
    name: str = "XAIResponses"
    provider: str = "xAI"
    base_url: str = "https://api.x.ai/v1"
    timeout: float = 300.0  # Reasoning models can be slow

    def _get_client_params(self) -> Dict[str, Any]:
        if not self.api_key:
            self.api_key = getenv("XAI_API_KEY")
            if not self.api_key:
                raise ModelAuthenticationError(
                    message="XAI_API_KEY not set. Set the XAI_API_KEY environment variable.",
                    model_name=self.name,
                )
        params = super()._get_client_params()
        params["base_url"] = self.base_url
        params["api_key"] = self.api_key
        return params

    def get_request_params(
        self,
        messages: Optional[List[Message]] = None,
        response_format: Optional[Union[Dict, Type[BaseModel]]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        # Prepend xAI server-side tools (x_search, web_search) before agent tools
        merged_tools = list(XAI_SERVER_TOOLS)
        if tools:
            merged_tools.extend(tools)
        return super().get_request_params(
            messages=messages,
            response_format=response_format,
            tools=merged_tools,
            tool_choice=tool_choice,
        )
