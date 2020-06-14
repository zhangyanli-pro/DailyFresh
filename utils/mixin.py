# 使用封装as_view()的Mixin 实现的登录用户才能进入某页面，否则跳转至登录页面
from django.contrib.auth.decorators import login_required


class LoginRequiredMixin(object):
    @classmethod
    def as_view(cls, **initkwargs):
        # 调用父类的as_view
        view = super(LoginRequiredMixin, cls).as_view(**initkwargs)
        return login_required(view)
