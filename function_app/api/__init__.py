import azure.functions as func
from azure.functions import AsgiMiddleware
from main import app as fastapi_app


async def main(req: func.HttpRequest, context: func.Context) -> func.HttpResponse:
    """Entrypoint for the Azure Function, proxies all HTTP routes to FastAPI app."""
    return await AsgiMiddleware(fastapi_app).handle_async(req, context)
