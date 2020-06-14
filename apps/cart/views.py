from django.shortcuts import render
from django.views.generic import View
from django.http import JsonResponse
from goods.models import GoodsSKU
from django_redis import get_redis_connection
from utils.mixin import LoginRequiredMixin

# 添加商品到购物车，详情页面不动，只有界面中购物车的记录数的会变化，且涉及到数据的变化（增删改），所以用到的是ajax的post请求
# 添加到购物车
# 1、确定前端是否传递数据，传递什么数据，什么格式
# cart_用户id: sku_id1 num1 sku_id2 num2 ....  即用的是redis中的hash数据格式
# 2、确定前端访问的方式（get  post）
# post
# 确定返回给前端的什么数据，什么格式
# 返回json数据


# ajax发起请求是在后台，在浏览器中看不到效果，所以其用户登录验证不能用LoginRequiredMixin
# /cart/add   涉及到数据的增加，所以ajax发起的是post请求，在视图中用post方法
class CartAddView(View):
    """ 在商品详情页添加商品至购物车 """
    def post(self, request):
        user = request.user
        if not user.is_authenticated:
            # 用户未登录
            return JsonResponse({'res': 0, 'errmsg': '请先登录账号'})

        # 若用户已登录
        # 获取数据  ajax通过post请求传递过来的数据
        sku_id = request.POST.get('sku_id')    # 字符串
        num = request.POST.get('num')          # 字符串

        # 数据校验
        if not all([sku_id, num]):
            return JsonResponse({'res': 1, 'errmsg': '数据不完整'})

        # 验证商品是否存在
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({'res': 2, 'errmsg': '商品信息错误'})

        # 验证商品数目
        try:
            num = int(num)
        except Exception as e:
            return JsonResponse({'res': 3, 'errmsg': '商品数量必须为有效数字'})

        # 业务处理：添加购物车记录
        conn = get_redis_connection('default')
        cart_key = 'cart_%d' % user.id
        # 先对购物车记录进行查询，如果现在要添加的商品之前添加过，那么现在就只需要将其数目在原有基础上进行累加，否则，添加新的field value
        # 如果sku_id在hash中不存在的话，hget返回none
        cart_num = conn.hget(cart_key, sku_id)
        if cart_num:     # 购物车中存在该商品记录
            num = num + int(cart_num)

        # 校验商品的库存
        if num > sku.stock:
            return JsonResponse({'res': 4, 'errmsg': '该商品数目库存不足'})
        # 购物车中不存在该商品记录，则新增记录
        conn.hset(cart_key, sku_id, num)

        # 计算用户购物车中商品的条目数
        total_num = conn.hlen(cart_key)

        # 返回应答
        return JsonResponse({'res': 5, 'total_num': total_num, 'message': '添加至购物车成功'})


class CartInfoView(LoginRequiredMixin, View):
    """购物车页面显示"""
    def get(self, request):
        """ 显示页面"""
        # 获取当前登录用户
        user = request.user
        conn = get_redis_connection('default')
        cart_key = 'cart_%d' % user.id
        # 查询出当前登录用户的购物车中的全部商品信息
        # hgetall()返回哈希名称/值对的Python字典
        sku_dict = conn.hgetall(cart_key)
        total_price = 0    # 购物车中勾选的所有商品的总金额
        total_num = 0     # 商品总件数
        skus = []        # 用于存放购物车中所有的商品
        # sku_id num  遍历出来都是字符串，所以需要转化类型
        for sku_id, num in sku_dict.items():
            # 获取商品
            sku = GoodsSKU.objects.get(id=sku_id)
            # 计算商品的小计=商品单价 * 数量
            amount = sku.price * int(num)
            # 给sku对象动态添加属性amounts，利于在模板中
            sku.amount = amount
            sku.num = int(num)    # num需要转化类型为int，否则在模板中引用{{sku.num}}输出的数据形式为 b'3'。。。
            skus.append(sku)
            # 计算购物车中所勾的总价和总件数
            total_price += amount
            total_num += int(num)

        # 组织上下文
        context = {
            'skus': skus,
            'total_price': total_price,
            'total_num': total_num,

        }

        return render(request, 'cart/cart.html', context)


# 购物车中记录更新，即在模板中增加商品的件数，需要ajax发起post请求，与后台进行交互，前端需要传递来的参数为sku_id, num
# /cart/update
class CartUpdateView(View):
    """购物车中记录更新"""
    def post(self, request):
        # 验证用户时候登录，
        user = request.user
        if not user.is_authenticated:
            # 用户未登录
            return JsonResponse({'res': 0, 'errmsg': '请先登录账号'})

        # 获取数据  ajax通过post请求传递过来的数据
        sku_id = request.POST.get('sku_id')  # 字符串
        num = request.POST.get('num')  # 字符串

        # 数据校验
        if not all([sku_id, num]):
            return JsonResponse({'res': 1, 'errmsg': '数据不完整'})

        # 验证商品是否存在
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({'res': 2, 'errmsg': '商品信息错误'})

        # 验证商品数目
        try:
            num = int(num)
        except Exception as e:
            return JsonResponse({'res': 3, 'errmsg': '商品数量必须为有效数字'})

        # 判断购物车中该商品的件数时候超过该商品的库存
        if num > sku.stock:
            return JsonResponse({'res': 4, 'errmsg': '商品库存不足'})

        # 更新redis数据库中的该用户的购物车记录
        conn = get_redis_connection('default')
        cart_key = 'cart_%d' % user.id
        conn.hset(cart_key, sku_id, num)
        return JsonResponse({'res': 5, 'message': '商品数据更新成功'})


# 购物车中记录删除，需要ajax发起post请求，前端需要传递来的参数为sku_id
class CartDeleteView(View):
    """购物车中记录删除"""
    def post(self, request):
        user = request.user
        if not user.is_authenticated:
            # 用户未登录
            return JsonResponse({'res': 0, 'errmsg': '请先登录账号'})

        # 获取数据  ajax通过post请求传递过来的数据
        sku_id = request.POST.get('sku_id')  # 字符串

        # 数据校验
        if not sku_id:
            return JsonResponse({'res': 1, 'errmsg': '数据不完整'})

        # 验证商品是否存在
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({'res': 2, 'errmsg': '商品信息错误'})

        # 删除redis数据库中的该用户的某条购物车记录
        conn = get_redis_connection('default')
        cart_key = 'cart_%d' % user.id
        conn.hdel(cart_key, sku_id)
        return JsonResponse({'res': 3, 'message': '商品删除成功'})

