from __future__ import annotations

import logging
from typing import Iterable

import httpx
from fastapi import HTTPException, Request, Response, status


logger = logging.getLogger(__name__)

_HOP_BY_HOP_HEADERS = {
	"connection",
	"keep-alive",
	"proxy-authenticate",
	"proxy-authorization",
	"te",
	"trailers",
	"transfer-encoding",
	"upgrade",
	"content-length",
	"content-encoding",
}


def _filter_headers(headers: Iterable[tuple[str, str]]) -> dict[str, str]:
	filtered: dict[str, str] = {}
	for key, value in headers:
		lower_key = key.lower()
		if lower_key == "host" or lower_key in _HOP_BY_HOP_HEADERS:
			continue
		filtered[key] = value
	return filtered


async def proxy_request(
	request: Request,
	*,
	base_url: str,
	path: str,
	timeout: float,
) -> Response:
	url = f"{base_url.rstrip('/')}{path}"
	params = list(request.query_params.multi_items())
	body = await request.body()
	headers = _filter_headers(request.headers.items())

	try:
		async with httpx.AsyncClient(timeout=timeout) as client:
			upstream = await client.request(
				request.method,
				url,
				params=params,
				content=body,
				headers=headers,
			)
	except httpx.RequestError as exc:
		logger.warning("Gateway request failed: %s", exc)
		raise HTTPException(
			status_code=status.HTTP_502_BAD_GATEWAY,
			detail="Gateway no pudo contactar al servicio interno.",
		) from exc

	response_headers = _filter_headers(upstream.headers.items())
	media_type = upstream.headers.get("content-type")

	return Response(
		content=upstream.content,
		status_code=upstream.status_code,
		headers=response_headers,
		media_type=media_type,
	)