from django.contrib import admin
from .models import PolicyHolder,Policy,PolicySubscription
# Register your models here.

admin.site.register(Policy)
admin.site.register(PolicyHolder)
admin.site.register(PolicySubscription)
