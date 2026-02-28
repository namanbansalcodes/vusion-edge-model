"""
URL configuration for detector app
"""
from django.urls import path
from . import views

app_name = 'detector'

urlpatterns = [
    path('', views.index, name='index'),
    path('api/process-frame/', views.process_frame, name='process_frame'),
    path('api/model-status/', views.model_status, name='model_status'),
]
