import azure.functions as func
from azure.functions import AsgiMiddleware
from main import app as fastapi_app


app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


@app.route(route="{*path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def all_routes(req: func.HttpRequest, context: func.Context) -> func.HttpResponse:
    return await AsgiMiddleware(fastapi_app).handle_async(req, context)
