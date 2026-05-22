"""
Unpaywall API wrapper.
Queries DOIs to find legal open-access PDF copies.
"""
import httpx
from opentelemetry import trace
from obs import tracer, logger
from mcp_server.telemetry import api_failures_counter

UNPAYWALL_EMAIL = "scholar.sleuth.project@gmail.com"


async def find_open_access(doi: str) -> dict:
    """
    Query Unpaywall for open access info on a given DOI.
    Returns a dict with keys: is_oa, oa_status, pdf_url, landing_page, error.
    """
    url = f"https://api.unpaywall.org/v2/{doi}"
    params = {"email": UNPAYWALL_EMAIL}

    with tracer.start_as_current_span("unpaywall_api_call") as span:
        span.set_attribute("http.method", "GET")
        span.set_attribute("http.url", url)
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, params=params, timeout=10.0)
                span.set_attribute("http.status_code", response.status_code)
                response.raise_for_status()
                data = response.json()
            except Exception as e:
                logger.error(f"Unpaywall error for DOI {doi}: {e}")
                span.record_exception(e)
                span.set_status(trace.StatusCode.ERROR, str(e))
                api_failures_counter.add(1, {"source": "unpaywall"})
                return {"error": str(e)}

    best_loc = data.get("best_oa_location", {})
    return {
        "is_oa": data.get("is_oa", False),
        "oa_status": data.get("oa_status", "unknown"),
        "pdf_url": best_loc.get("url_for_pdf") if best_loc else None,
        "landing_page": best_loc.get("url_for_landing_page") if best_loc else None,
    }
