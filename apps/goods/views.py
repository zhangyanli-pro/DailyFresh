from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.generic import View
from .models import *
from django_redis import get_redis_connection
from django.core.cache import cache
from order.models import OrderGoods
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger


class IndexView(View):
    """首页"""
    def get(self, request):
        """显示首页"""
        # 尝试从缓存中获取数据
        context = cache.get('index_page_data')
        # 如果在缓存中未获取到数据，则从mysql数据库中查找数据，再设置一次缓存
        if context is None:
            # print('设置缓存')   测试是否缓存成功
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

            context = {
                'types': types,
                'goods_banners': goods_banners,
                'promotion_banners': promotion_banners,
            }

            # 设置缓存
            cache.set('index_page_data', context, 3600)

        # 获取购物车中记录总数, 如果用户未登录则显示未0，否则获取购物车记录总数
        # 与存储用户浏览记录一样，用户购物车记录的数据也是用redis存储，便于快速存取，但是这里用的redis数据类型为hash
        cart_count = 0
        user = request.user
        if user.is_authenticated:      # 不要写成user.is_authenticated()  否则报错 'bool' object is not callable
            # 用户已登录
            conn = get_redis_connection('default')
            # 设置键的格式
            cart_key = 'cart_%d' % user.id
            cart_count = conn.hlen(cart_key)

        # 组织模板的上下文
        context.update(cart_count=cart_count)

        return render(request, 'goods/index.html', context)


class DetailView(View):
    """ 详情页 """
    def get(self, request, goods_id):
        # 获取商品详情页
        try:
            # 获取详情页中展示的商品
            sku = GoodsSKU.objects.get(id=goods_id)     # 用filter过滤出来的是一个querySet对象,就可以看做是一个列表，所以尽管里面只有一个对象也需要取出来
        except GoodsSKU.DoesNotExist:
            # 商品不存在   重定向至首页
            return redirect(reverse('goods:index'))

        # 获取商品所有种类
        types = GoodsType.objects.all()

        # 获取除自身外的同类商品的不同规格的商品（例如草莓有盒装草莓和散装草莓）
        spu_skus = GoodsSKU.objects.filter(goods=sku.goods).exclude(id=goods_id)

        # 获取同种类的新品，只需要展示两个新品即可，按照创建时间进行降序排列
        new_skus = GoodsSKU.objects.filter(type=sku.type).order_by('-create_time')[:2]

        # 获取商品的评论信息
        sku_comments = OrderGoods.objects.filter(sku=sku).exclude(comment='')

        # 获取购物车中记录数
        cart_count = 0
        user = request.user
        if user.is_authenticated:  # 不要写成user.is_authenticated()  否则报错 'bool' object is not callable
            # 用户已登录
            conn = get_redis_connection('default')
            # 设置键的格式
            cart_key = 'cart_%d' % user.id
            cart_count = conn.hlen(cart_key)

            # 添加用户的历史浏览记录
            conn = get_redis_connection('default')
            history_key = 'history_%d' % user.id
            # 如果值的列表中有当前的goods_id,则移出列表中的goods_id
            conn.lrem(history_key, 0, goods_id)
            # 再将goods_id插入到列表的左侧
            conn.lpush(history_key, goods_id)
            # 只保存用户的最新浏览的5条信息
            conn.ltrim(history_key, 0, 4)

        context = {
            'types': types,
            'sku': sku,
            'spu_skus': spu_skus,
            'new_skus': new_skus,
            'sku_comments': sku_comments,
            'cart_count': cart_count
        }

        return render(request, 'goods/detail.html', context)


# url的格式： list/种类id/页码?sort=default|price|hot    ?后的参数可以同request.GET.get('sort')获取其值
class ListView(View):
    """ 列表页 """
    def get(self, request, type_id, page):
        """ 获取首页 """
        # 获取列表页需要展示的种类
        try:
            type = GoodsType.objects.get(id=type_id)
        except GoodsType.DoesNotExist:
            return redirect(reverse('goods:index'))

        # 获取商品所有种类
        types = GoodsType.objects.all()

        # 获取同种类的新品，只需要展示两个新品即可，按照创建时间进行降序排列
        new_skus = GoodsSKU.objects.filter(type=type).order_by('-create_time')[:2]

        # 获取所需展示的种类的全部商品，根据规则进行排序
        sort = request.GET.get('sort')
        if sort == 'price':     # 根据价格升序排序
            skus = GoodsSKU.objects.filter(type_id=type.id).order_by('price')
        elif sort == 'hot':     # 根据销量降序排列
            skus = GoodsSKU.objects.filter(type_id=type.id).order_by('-sales')
        else:   # 默认排序 即按照商品id升序排列
            sort = 'default'
            skus = GoodsSKU.objects.filter(type_id=type.id).order_by('id')

        # 分页
        paginator = Paginator(skus, 1)
        page = int(page)
        pages = paginator.num_pages
        try:
            page_cons = paginator.page(page)     # 返回指定页面的对象列表，比如第1页的所有内容，下标以1开始
        except PageNotAnInteger:
            # 如果请求的页数不是整数，返回第一页。
            page_cons = paginator.page(1)
        except EmptyPage:
            # 如果请求的页数不在合法的页数范围内，返回第一页。
            page_cons = paginator.page(1)

        # 进行页码控制 几种情况如下
        # 1、总页数小于5页就将全部页码显示
        # 2、如果当前页是前三页，就显示1-5页
        # 3、如果当前页是后三页，就显示后5页
        # 4、如果当前页是其他情况， 就显示当前页的前两页、当前页、当前页的后两页
        num_pages = paginator.num_pages
        if num_pages < 5:
            pages = range(1, num_pages+1)
        elif page <= 3:
            pages = range(1, 6)
        elif page >= num_pages-2:
            pages = range(num_pages-4, num_pages+1)
        else:
            pages = range(page-2, page+3)

        # 获取购物车中记录数
        cart_count = 0
        user = request.user
        if user.is_authenticated:  # 不要写成user.is_authenticated()  否则报错 'bool' object is not callable
            # 用户已登录
            conn = get_redis_connection('default')
            # 设置键的格式
            cart_key = 'cart_%d' % user.id
            cart_count = conn.hlen(cart_key)

        # 组织上下文
        context = {
            'type': type,
            'types': types,
            'new_skus': new_skus,
            'sort': sort,
            'page_cons': page_cons,
            'cart_count': cart_count,
            'pages': pages
        }

        return render(request, 'goods/list.html', context)

