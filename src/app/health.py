from django.http import JsonResponse


def health(request):
    """Health check endpoint for readiness monitoring.

    Retorna 200 e um JSON simples quando a aplicação está no ar.
    """
    return JsonResponse({"status": "ok"}, status=200)
