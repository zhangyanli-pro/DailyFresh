from django.core.files.storage import Storage
from fdfs_client.client import *
from django.conf import settings


class FDFSStorage(Storage):
    """fast df文件存储类"""

    def __init__(self, client_conf=None, base_url=None):
        """初始化"""
        if client_conf is None:
            client_conf = settings.FDFS_CLIENT_CONF
        self.client_conf = client_conf

        if base_url is None:
            base_url = settings.FDFS_URL
        self.base_url = base_url

    def _open(self, name, mode='rb'):
        """打开文件时使用"""
        pass

    def _save(self, name, content):
        """保存文件时使用"""
        # name: 你选择上传的文件的名字
        # content：包含你上传文件内容的File对象

        # 创建一个Fdfs_client对象
        # 创建client实例对象的时候不能直接传入配置文件的地址字符串,否则报错.
        # 错误代码:TypeError: type object argument after ** must be a mapping, not str
        # 通过模块内get_tracker_conf函数, 获取配置文件后传入.
        trackers = get_tracker_conf(self.client_conf)
        client = Fdfs_client(trackers)

        # 上传文件到fast dfs系统中
        # content.read() 可以从File的实例对象content中 读取 文件内容
        # upload_by_buffer返回内容为 字典。格式如下 注释部分
        res = client.upload_by_buffer(content.read())

        # res就是下面的dict类型数据
        # dict
        # {
        #     'Group name': group_name,
        #     'Remote file_id': remote_file_id,
        #     'Status': 'Upload successed.',
        #     'Local file name': '',
        #     'Uploaded size': upload_size,
        #     'Storage IP': storage_ip
        # }

        if res.get('Status') != 'Upload successed.':
            # 上传失败
            raise Exception('上传文件到FDFS失败')

        # 上传成功，则返回文件的ID,将其存储在数据库表中
        filename = res.get('Remote file_id')

        # 只能返回str类型, filename为bytes类型(需要转换类型，不然会报错)
        return filename.decode()

    # django在调用_save之前，会先调用_exists
    # _exists 根据 文件的name，判断 文件 是否存在于 文件系统中。存在：返回True，不存在：返回False
    def exists(self, name):
        """django判断文件名是否可用"""
        # 因为 文件是存储在 fastdfs文件系统中的，所以 对于django来说：不存在 文件名不可用 的情况
        return False

    def url(self, name):
        """返回访问文件name所需的url路径"""
        # django调用url方法时，所传递的 name参数：数据库 表中所存的 文件名字符串(即是，fastdfs中存储文件时 使用的文件名)
        return self.base_url + name
