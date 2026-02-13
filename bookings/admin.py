from django.contrib import admin
from .models import Pitch, Booking, Payment

# تأكد إن كل سطر من دول مكتوب مرة واحدة بس في الملف كله
admin.site.register(Pitch)
admin.site.register(Booking)
admin.site.register(Payment)
