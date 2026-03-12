from django.conf import settings


def user_pitches(request):
    ctx = {"support_whatsapp": getattr(settings, "SUPPORT_WHATSAPP", "")}
    if request.user.is_authenticated:
        ctx["has_pitches"] = request.user.owned_pitches.exists()
    else:
        ctx["has_pitches"] = False
    return ctx
