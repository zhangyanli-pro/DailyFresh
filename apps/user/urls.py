from django.urls import path, re_path
from .views import RegisterView, ActiveView, LoginView, LogoutView, UserInfoView, UserOrderView, AddressView

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),   # 注册
    re_path(r'^active/(?P<token>.*)$', ActiveView.as_view(), name='active'),  # 激活用户
    path('login/', LoginView.as_view(), name='login'),    # 登录
    path('logout/', LogoutView.as_view(), name='logout'),     # 退出登录
    path('', UserInfoView.as_view(), name='user'),             # 用户中心信息页
    re_path(r'order/(?P<page>\d+)', UserOrderView.as_view(), name='order'),        # 用户中心订单页
    path('address/', AddressView.as_view(), name='address'),     # 用户中心地址页
]
