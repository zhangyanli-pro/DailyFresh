from django.urls import path, re_path
from .views import IndexView, DetailView, ListView

urlpatterns = [
    path('index/', IndexView.as_view(), name='index'),
    re_path(r'detail/(?P<goods_id>\d+)/', DetailView.as_view(), name='detail'),
    re_path(r'list/(?P<type_id>\d+)/(?P<page>\d+)/', ListView.as_view(), name='list')
]

