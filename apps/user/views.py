from django.shortcuts import render, redirect
from django.urls import reverse   # 用于views里面反向解析
from .models import User, Address
from goods.models import GoodsSKU      # 不用管红线标注的 Unresolved reference 'GoodsSKU'
from order.models import OrderInfo, OrderGoods
import re
from django.views.generic import View   # 用于创建类视图
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer        # itsdangerous加密
from itsdangerous import SignatureExpired  # 若过期则会抛出此异常
from django.http import HttpResponse
from celery_tasks.tasks import send_register_active_email
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from utils.mixin import LoginRequiredMixin
from django_redis import get_redis_connection
from django.core.paginator import Paginator


# /user/register
class RegisterView(View):
    """ 注册 """
    def get(self, request):
        """返回注册页面"""
        return render(request, 'user/register.html')

    def post(self, request):
        """处理用户注册"""
        # 获取用户提交的数据
        username = request.POST.get('user_name')
        password = request.POST.get('pwd')
        cpasssword = request.POST.get('cpwd')
        email = request.POST.get('email')
        allow = request.POST.get('allow')

        # 数据校验，若数据有误则给注册页面返回错误信息
        # 若表单中的数据未填写完整，则返回错误信息
        if not all([username, password, cpasssword, email]):
            return render(request, 'user/register.html', {'errmsg': '信息为填写完整'})

        # 业务处理
        # 判断用户名是否已存在
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            # 用户名不存在
            user = None

        # 若新密码和再次填写的密码不一致
        if password != cpasssword:
            return render(request, 'user/register.html', {'errmsg': '两次密码不一致'})

        # 若邮箱不是正确格式
        if not re.match(r'^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
            return render(request, 'user/register.html', {'errmsg': '邮箱格式错误'})

        # 若用户未勾选“同意协议”
        if allow != 'on':
            return render(request, 'user/register.html', {'errmsg': '请勾选同意协议'})

        # 若数据都校验合格，则创建该用户并写入数据库，可以使用django认证系统自带方法create_user()创建用户对象
        user = User.objects.create_user(username, email, password)
        user.is_active = 0
        user.save()

        # 给新用户的邮箱发送激活链接以激活用户 链接为 http://127.0.0.1/user/active/(用户id加密后的字符)
        # 加密用户的身份信息，生成激活token  SECRET_KEY是settings里自动生成的django的一个秘钥  3600单位秒，即链接的有效时间是1小时
        serializer = Serializer(settings.SECRET_KEY, 3600)
        info = {'confirm': user.id}
        token = serializer.dumps(info)    # 加密之后是字节类型的，所以需要将其解码
        token = token.decode('utf8')

        # 发出任务-即给用户邮箱发送邮件，
        # from celery_tasks.tasks import send_register_active_email
        send_register_active_email.delay(email, username, token)

        # 注册成功后返回至网站首页
        return redirect(reverse('goods:index'))


class ActiveView(View):
    """ 用户激活 """
    def get(self, request, token):
        """ 点击链接所以是GET请求 """
        # 解密
        serializer = Serializer(settings.SECRET_KEY, 3600)
        try:
            info = serializer.loads(token)    # info={'confirm': user.id}
            user_id = info['confirm']

            # 根据此user_id找到该用户，将其is_active设置为1即表示用户已经激活
            user = User.objects.get(id=user_id)
            user.is_active = 1
            user.save()

            # 激活完成后返回到的登录界面
            return redirect(reverse('user:login'))
        except SignatureExpired as e:
            return HttpResponse('激活链接已过期')


# /user/login
class LoginView(View):
    """用户登录"""
    def get(self, request):
        """显示登录页面"""
        # 判断当前用户是否勾选了记住用户名，若勾选了的话，其请求的cookies里面会有’username‘,
        if 'username' in request.COOKIES:          # request.cookies 是一个字典
            username = request.COOKIES.get('username')
            checked = 'checked'
        else:
            username = ''
            checked = ''
        context = {
            'username': username,
            'checked': checked
        }
        return render(request, 'user/login.html', context)

    def post(self, request):
        """处理登录页面"""
        # 获取表单提交的数据
        username = request.POST.get('username')
        password = request.POST.get('pwd')

        # 数据校验
        if not all([username, password]):
            return render(request, 'user/login.html', {'errmsg': '信息未填写完全'})

        # 业务处理
        # 使用authenticate（）来验证用户。它使用username和password作为参数进行验证，对每个身份验证进行一一检查，
        # 如果有一个认证成功则返回一个user对象，则停止向下检查。如果后端引发PermissionDenied错误，即认证失败将返回None
        user = authenticate(username=username, password=password)
        if user:     # 若用户存在
            if user.is_active:  # 若用户已激活
                # 记录登录状态，将上述已经得到验证的用户添加到当前的会话(session)中,login()使用django的session框架将用户的
                # ID保存在session中默认session保存在项目的mysql数据库中，我要将其保存在redis的中
                login(request, user)

                # 使用封装as_view()的Mixin
                # 获取登录后所要跳转到的地址   若未登录，则会跳转至登录页面/user/login/？next=/user/
                # 默认跳转到首页     reverse('goods:index')
                next_url = request.GET.get('next', reverse('goods:index'))

                response = redirect(next_url)

                remember = request.POST.get('remember')  # 是否勾选记住用户名

                # 判断时候勾选记住用户名
                if remember == 'on':    # 勾选了，则设置cookies
                    response.set_cookie('username', username, max_age=7*24*3600)
                else:
                    response.delete_cookie('username')
                # 登录成功跳转至首页
                return response
            else:
                return render(request, 'user/login.html', {'errmsg': '当前用户未激活'})
        else:       # 若用户不存在
            return render(request, 'user/login.html', {'errmsg': '用户名或密码错误'})


# /user/logout
class LogoutView(View):
    """退出登录"""
    def get(self, request):
        """ 退出登录 """
        logout(request)    # 自动清除用户的session信息
        # 退出登录后跳转至首页
        return redirect(reverse('goods:index'))


# 凡是需要用户登录了才能进入的页面所对应的类视图，都需要继承LoginRequiredMixin而且必须写在左边，因为这样才能先继承它的里面的as_view()
# /user
class UserInfoView(LoginRequiredMixin, View):
    """ 用户中心——信息页 """
    def get(self, request):
        # django框架会把request.user直接传给模板
        user = request.user
        address = Address.objects.get_default_address(user)

        # 获取用户的浏览记录，浏览记录存储在redis中
        # from django_redis import get_redis_connection
        # 'default'就是在settings里面设置的django缓存， con就是一个StrictRedis的实例对象,使得python与redis进行交互
        conn = get_redis_connection('default')

        # 创建格式为 history_%d 的键
        history_key = 'history_%d' % user.id

        # 获取用户最近浏览的五个商品
        sku_ids = conn.lrange(history_key, 0, 4)

        # 在数据库中从上之下查询，只要在sku_ids里面就查出来，而不是按照用户浏览商品的顺序查出来
        goods_li = []
        for id in sku_ids:
            goods = GoodsSKU.objects.get(id=id)
            goods_li.append(goods)

        context = {
            'page': 'user',
            'address': address,
            'goods_li': goods_li
        }
        return render(request, 'user/user_center_info.html', context)


# /user/order
class UserOrderView(LoginRequiredMixin, View):
    """ 用户中心——订单页 """
    def get(self, request, page):
        # 获取用户的订单信息
        user = request.user
        orders = OrderInfo.objects.filter(user=user).order_by('-create_time')

        # 遍历获取订单商品的信息
        for order in orders:
            # 根据order_id查询订单商品信息
            order_skus = OrderGoods.objects.filter(order_id=order.order_id)

            # 遍历order_skus计算商品的小计
            for order_sku in order_skus:
                # 计算小计
                amount = order_sku.count*order_sku.price
                # 动态给order_sku增加属性amount,保存订单商品的小计
                order_sku.amount = amount

            # 动态给order增加属性，保存订单状态标题
            order.status_name = OrderInfo.ORDER_STATUS[order.order_status]
            # 动态给order增加属性，保存订单商品的信息
            order.order_skus = order_skus

        # 分页
        paginator = Paginator(orders, 1)

        # 获取第page页的内容
        try:
            page = int(page)
        except Exception as e:
            page = 1

        if page > paginator.num_pages:
            page = 1

        # 获取第page页的Page实例对象
        order_page = paginator.page(page)

        # todo: 进行页码的控制，页面上最多显示5个页码
        # 1.总页数小于5页，页面上显示所有页码
        # 2.如果当前页是前3页，显示1-5页
        # 3.如果当前页是后3页，显示后5页
        # 4.其他情况，显示当前页的前2页，当前页，当前页的后2页
        num_pages = paginator.num_pages
        if num_pages < 5:
            pages = range(1, num_pages + 1)
        elif page <= 3:
            pages = range(1, 6)
        elif num_pages - page <= 2:
            pages = range(num_pages - 4, num_pages + 1)
        else:
            pages = range(page - 2, page + 3)

        # 组织上下文
        context = {'order_page': order_page,
                   'pages': pages,
                   'page': 'order'}

        # 使用模板
        return render(request, 'user/user_center_order.html', context)


# /user/address
class AddressView(LoginRequiredMixin, View):
    """ 用户中心——地址页 """
    def get(self, request):
        # 获取登录用户对应的User对象
        user = request.user
        address = Address.objects.get_default_address(user)

        context = {
            'address': address,
            'page': 'address',
        }
        return render(request, 'user/user_center_site.html', context)

    def post(self, request):
        """处理用户中心地址页的表单提交"""
        # 获取数据
        receiver = request.POST.get('receiver')
        addr = request.POST.get('addr')
        zip_code = request.POST.get('zip_code')
        phone = request.POST.get('phone')

        # 校验数据
        if not all([receiver, addr, phone]):
            return render(request, 'user/user_center_site.html', {'errmsg': '收件人、地址、手机号未填写完全'})

        # 业务处理
        # 判断手机号格式是否正确
        if not re.match(r'^(13[0-9]|14[5|7]|15[0|1|2|3|5|6|7|8|9]|18[0|1|2|3|5|6|7|8|9])\d{8}$', phone):
            return render(request, 'user/user_center_site.html', {'errmsg': '手机号格式不正确'})

        user = request.user
        address = Address.objects.get_default_address(user)

        if address:
            is_default = False
        else:
            is_default = True

        # 添加新收货地址到数据库中  用create()
        new_address = Address.objects.create(
            user=user,
            receiver=receiver,
            addr=addr,
            zip_code=zip_code,
            phone=phone,
            is_default=is_default
        )

        # 添加成功后刷新地址页面
        return redirect(reverse('user:address'))
