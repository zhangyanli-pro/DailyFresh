from django.contrib import admin
from .models import *
from django.core.cache import cache


# 继承ModelAdmin类，重写save_model，delete_model
class BaseModelAdmin(admin.ModelAdmin):
    def save_model(self, request, obj, form, change):
        """ 当后台管理员新增或更新表中数据时调用 """
        super(BaseModelAdmin, self).save_model(request, obj, form, change)

        # 发出任务，让celery worker重新生成首页静态页
        from celery_tasks.tasks import generate_static_index_html
        generate_static_index_html.delay()

        # 更新缓存删除首页数据的原缓存，这样的话再下次查询缓存时就查不到数据而会再次重新从mysql数据库中获取新的数据并放在缓存中
        cache.delete('index_page_data')

    def delete_model(self, request, obj):
        """ 当后台管理员删除表中数据时调用 """
        super(BaseModelAdmin, self).delete_model(request, obj)

        # 发出任务，让celery worker重新生成首页静态页
        from celery_tasks.tasks import generate_static_index_html
        generate_static_index_html.delay()

        cache.delete('index_page_data')


@admin.register(GoodsType)
class GoodTypeAdmin(BaseModelAdmin):
    pass


@admin.register(IndexGoodsBanner)
class IndexGoodsBannerAdmin(BaseModelAdmin):
    pass


@admin.register(IndexTypeGoodsBanner)
class IndexTypeGoodsBannerAdmin(BaseModelAdmin):
    pass


@admin.register(IndexPromotionBanner)
class IndexPromotionBannerAdmin(BaseModelAdmin):
    pass


admin.site.register(GoodsSKU)

admin.site.register(Goods)

admin.site.register(GoodsImage)
