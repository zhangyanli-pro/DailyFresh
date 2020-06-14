# 使用celery
from celery import Celery
from django.conf import settings
from django.core.mail import send_mail   # django内置的发送邮件的方法
import time
from django.template import loader


# # 在任务处理者worker的那一端的tasks.py代码中加入，用以初始化django的运行环境
import os
# import django
# os.environ.setdefault("DJANGO_SETTINGS_MODULE", "DailyFresh.settings")
# django.setup()

from goods.models import *


# 创建一个celery类的实例对象, 指定中间人使用的redis的哪个数据库（此处用的本地redis8号数据库）
app = Celery('celery_tasks.tasks', broker='redis://192.168.70.133:6379/8')


# 定义任务函数
@app.task
def send_register_active_email(to_email, username, token):
    """ 发送激活 邮件"""
    # 组织邮件信息
    subject = '天天生鲜欢迎信息'
    message = ''
    sender = settings.EMAIL_FROM
    receiver = [to_email]  # 该参数表示接收邮件的邮箱，是一个列表，可以发送给多个邮箱，这里的to_email即使获取的注册用户的email
    html_message = '<h1>%s，欢迎加入天天生鲜注册会员</h1><h4>请点击下方链接将用户激活：</h4><br/><a href="http://192.168.70.133:8000/user/active/%s">http://192.168.70.133:8000/user/active/%s</a>' % (username, token, token)
    send_mail(subject, message, sender, receiver, html_message=html_message)
    # time.sleep(10)    # 用于测试使用celery的前后效果对比


@app.task
def generate_static_index_html():
    """ 生成首页静态页面 """
    # 获取左侧菜单列表
    types = GoodsType.objects.all()

    # 获取首页轮播图图片
    goods_banners = IndexGoodsBanner.objects.all()

    # 获取活动图片
    promotion_banners = IndexPromotionBanner.objects.all().order_by('index')

    # 获取首页分类展示信息
    for type in types:
        title_goods = IndexTypeGoodsBanner.objects.filter(type=type, display_type=0).order_by('index')
        img_goods = IndexTypeGoodsBanner.objects.filter(type=type, display_type=1).order_by('index')
        # 类似于给类对象增加属性 直接用 object.sth = xxx
        type.title_goods = title_goods
        type.img_goods = img_goods

    cart_count = 0

    context = {
        'types': types,
        'goods_banners': goods_banners,
        'promotion_banners': promotion_banners,
        'cart_count': cart_count
    }

    # return render(request, 'goods/index.html', context)    这是返回一个HttpResponse对象，而我需要生成一个静态页面
    # 加载模板
    temp = loader.get_template('goods/static_index.html')
    # 渲染模板，得到渲染好的模板内容
    static_index_html = temp.render(context)

    # 文件会生成在worker所对应的项目文件中
    save_path = os.path.join(settings.BASE_DIR, 'static/index.html')
    # 生成对应的静态页面 index.html
    with open(save_path, 'w') as f:
        f.write(static_index_html)

