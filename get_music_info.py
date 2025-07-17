import io
import re
import json
import time
import queue
import random
import hashlib
import certifi
import requests
import warnings
from PIL import Image
from urllib import parse
from PySide6 import QtCore
warnings.filterwarnings('ignore')


def resize_image(binary_data):
    # 打开图片
    image = Image.open(io.BytesIO(binary_data))
    # 判断图片像素值是否超标
    width, height = image.size
    pixels = width * height
    if pixels > 1000000:
        # 缩小图片
        resized_image = image.resize((1000, 1000))
        # 创建字节流对象
        byte_io = io.BytesIO()
        # 以原有格式保存到字节流中
        resized_image.save(byte_io, format=image.format)
        # 获取二进制数据
        binary_data = byte_io.getvalue()
        byte_io.close()
    image.close()
    return binary_data


def request(url: str, data=None, headers=None, cookies=None, method='GET', **kwargs):
    """
    :param url: URL for the new :class:`Request` object.
    :param data: (optional) Dictionary, list of tuples, bytes, or file-like
    :param headers: (optional) Dictionary of HTTP Headers to send with the :class:`Request`.
    :param cookies: (optional) Dict or CookieJar object to send with the :class:`Request`.
    :param method: method for the new :class:`Request` object: ``GET``, ``OPTIONS``, ``HEAD``, ``POST``, ``PUT``, ``PATCH``, or ``DELETE``.
    :return: :class:`Response <Response>` object
    :rtype: requests.Response
    """
    while True:
        try:
            response = requests.request(method, url, data=data, headers=headers, cookies=cookies, timeout=3, verify=certifi.where(), **kwargs)
            if response.status_code == 200:
                return response
            else:
                print(f'<{url}>请求失败，状态码：{response.status_code}')
        except requests.exceptions.RequestException as e:
            print(f'<{url}>请求失败，错误信息：{e}')
        time.sleep(0.5)



def str_process(string: str):
    process_compile = {"&amp;": "&", "&lt;": "<", "&gt;": ">", "&lrm;": "*", "&rlm;": "*", "&nbsp;": " ", '：': ':', '、': '&', '|': '&', '/': '&'}
    for k, v in process_compile.items():
        string = string.replace(k, v)
    return string


# # 此方法无法正常使用
# import base64
# import binascii
# from Cryptodome.Cipher import AES
#
#
# def generate_random_bytes(size):
#     system_random = random.SystemRandom()
#     return system_random.getrandbits(size * 8).to_bytes(size, 'big')
#
#
# def aes(text, key):
#     pad = 16 - len(text) % 16
#     text = text + bytearray([pad] * pad)
#     encryptor = AES.new(key, 2, b"0102030405060708")
#     ciphertext = encryptor.encrypt(text)
#     return base64.b64encode(ciphertext)
#
#
# def rsa(text, pubkey, modulus):
#     text = text[::-1]
#     rs = pow(int(binascii.hexlify(text), 16), int(pubkey, 16), int(modulus, 16))
#     return format(rs, "x").zfill(256)
#
#
# def create_key(size):
#     return binascii.hexlify(generate_random_bytes(size))[:16]
#
#
# class NetEaseMusic(object):
#     def __init__(self):
#         self.MODULUS = (
#             "00e0b509f6259df8642dbc35662901477df22677ec152b5ff68ace615bb7"
#             "b725152b3ab17a876aea8a5aa76d2e417629ec4ee341f56135fccf695280"
#             "104e0312ecbda92557c93870114af6c9d05c4f7f0c3685b7a46bee255932"
#             "575cce10b424d813cfe4875d3e82047b97ddef52741d546b8e289dc6935b"
#             "3ece0462db0a22b8e7"
#         )
#         self.PUBKEY = "010001"
#         self.NONCE = b"0CoJUm6Qyw8W8jud"
#         self.userAgent = [
#             "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/59.0.3071.115 Safari/537.36",
#             "Mozilla/5.0 (iPhone; CPU iPhone OS 9_1 like Mac OS X) AppleWebKit/601.1.46 (KHTML, like Gecko) Version/9.0 Mobile/13B143 Safari/601.1",
#             "Mozilla/5.0 (iPhone; CPU iPhone OS 9_1 like Mac OS X) AppleWebKit/601.1.46 (KHTML, like Gecko) Version/9.0 Mobile/13B143 Safari/601.1",
#             "Mozilla/5.0 (Linux; Android 5.0; SM-G900P Build/LRX21T) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/59.0.3071.115 Mobile Safari/537.36",
#             "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/59.0.3071.115 Mobile Safari/537.36",
#             "Mozilla/5.0 (Linux; Android 5.1.1; Nexus 6 Build/LYZ28E) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/59.0.3071.115 Mobile Safari/537.36",
#             "Mozilla/5.0 (iPhone; CPU iPhone OS 10_3_2 like Mac OS X) AppleWebKit/603.2.4 (KHTML, like Gecko) Mobile/14F89;GameHelper",
#             "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_5) AppleWebKit/603.2.4 (KHTML, like Gecko) Version/10.1.1 Safari/603.2.4",
#             "Mozilla/5.0 (iPhone; CPU iPhone OS 10_0 like Mac OS X) AppleWebKit/602.1.38 (KHTML, like Gecko) Version/10.0 Mobile/14A300 Safari/602.1",
#             "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.103 Safari/537.36",
#             "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.12; rv:46.0) Gecko/20100101 Firefox/46.0",
#             "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:46.0) Gecko/20100101 Firefox/46.0",
#             "Mozilla/4.0 (compatible; MSIE 7.0; Windows NT 6.0)",
#             "Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 6.0; Trident/4.0)",
#             "Mozilla/5.0 (compatible; MSIE 9.0; Windows NT 6.1; Trident/5.0)",
#             "Mozilla/5.0 (compatible; MSIE 10.0; Windows NT 6.2; Win64; x64; Trident/6.0)",
#             "Mozilla/5.0 (Windows NT 6.3; Win64, x64; Trident/7.0; rv:11.0) like Gecko",
#             "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/42.0.2311.135 Safari/537.36 Edge/13.10586",
#             "Mozilla/5.0 (iPad; CPU OS 10_0 like Mac OS X) AppleWebKit/602.1.38 (KHTML, like Gecko) Version/10.0 Mobile/14A300 Safari/602.1"
#         ]
#         musicU = 'e4ace7b13afdd88161175bda1c091445ad6bc398f36fb0f0315f1fa0787d4fbce7c70899629a7e58dcb329764b52b00341049cea1c6bb9b6'
#         self.CookiesList = [
#             # 'os=pc; osver=Microsoft-Windows-10-Professional-build-10586-64bit; appver=2.0.3.131777; channel=netease; __remember_me=true',
#             'MUSIC_U=' + musicU + '; buildver=1506310743; resolution=1920x1080; mobilename=MI5; osver=7.0.1; channel=coolapk; os=android; appver=4.2.0',
#             'osver=%E7%89%88%E6%9C%AC%2010.13.3%EF%BC%88%E7%89%88%E5%8F%B7%2017D47%EF%BC%89; os=osx; appver=1.5.9; MUSIC_U=' +
#             musicU + '; channel=netease;'
#         ]
#         self.headers = {
#             'User-Agent': random.choice(self.userAgent),
#             'cookie': random.choice(self.CookiesList),
#             'referer': 'https://music.163.com'
#         }
#
#     def encrypted_request(self, text):
#         text = str(text)
#         data = text.encode("utf-8")
#         secret = create_key(16)
#         params = aes(aes(data, self.NONCE), secret)
#         encseckey = rsa(secret, self.PUBKEY, self.MODULUS)
#         return {"params": params, "encSecKey": encseckey}
#
#     def send(self, url, param):
#         return request(url=url, data=self.encrypted_request(param), headers=self.headers, method='POST').json()
#
#     def search(self, text: str, number=10):
#         url = "https://music.163.com/weapi/cloudsearch/get/web"
#         param = '{"hlpretag":"<span class=\\"s-fc7\\">","hlposttag":"</span>","s":"' + text + '","type":"1","offset":"0","total":"true","limit":"' + str(number) + '","csrf_token":""}'
#         return self.send(url, param)
#
#     def get_info(self, search_info: str, hash_sha256: str, data_exchange_queue: queue.Queue):
#         music_list = self.search(search_info)['result']['songs']
#         music_info = (self,) + tuple({'name': str_process(music['name']), 'artist': '&'.join(i['name'] for i in music['ar']), 'album': str_process(music['al']['name']), 'id': music['id'], 'duration': music['dt'] // 1000, 'pic': music['al']['picUrl']} for music in music_list) + (hash_sha256,)
#         data_exchange_queue.put(music_info)
#
#     def get_lyrics(self, song_id):
#         url = "https://music.163.com/weapi/song/lyric"
#         param = '{"id":"' + str(song_id) + '","lv":-1,"tv":-1,"csrf_token":""}'
#         time_compile = re.compile(r'\[(\d*:?\d+:\d+\.*\d*)] *')
#         lyrics = self.send(url, param)['lrc']['lyric']
#         lyrics_tuple = tuple(sorted(((QtCore.QTime(0, 0, 0).msecsTo(QtCore.QTime.fromString(time_compile.findall(i)[0], 'mm:ss.zz')), time_compile.sub('', i)) for i in lyrics.split('\n') if i), key=lambda x: x[0]))
#         return lyrics_tuple
#
#     def get_cover(self, cover_url: str):
#         cover_response = request(cover_url, method='GET')
#         return resize_image(cover_response.content)


class NetEaseMusic(object):
    def __init__(self):
        self.userAgent = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.45 Safari/537.36"
        ]
        musicU = 'e4ace7b13afdd88161175bda1c091445ad6bc398f36fb0f0315f1fa0787d4fbce7c70899629a7e58dcb329764b52b00341049cea1c6bb9b6'
        self.CookiesList = [
            # 'os=pc; osver=Microsoft-Windows-10-Professional-build-10586-64bit; appver=2.0.3.131777; channel=netease; __remember_me=true',
            'MUSIC_U=' + musicU + '; buildver=1506310743; resolution=1920x1080; mobilename=MI5; osver=7.0.1; channel=coolapk; os=android; appver=4.2.0',
            'osver=%E7%89%88%E6%9C%AC%2010.13.3%EF%BC%88%E7%89%88%E5%8F%B7%2017D47%EF%BC%89; os=osx; appver=1.5.9; MUSIC_U=' +
            musicU + '; channel=netease;'
        ]
        self.headers = {
            'User-Agent': random.choice(self.userAgent),
            'cookie': random.choice(self.CookiesList),
            'Referer': 'http://music.163.com',
            'Host': 'music.163.com',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': '*/*',
            'Accept-Language': 'zh-CN,zh;q=0.8,gl;q=0.6,zh-TW;q=0.4',
            'Connection': 'keep-alive'
        }

    def _search(self, key, type_=1, page=0, limit=30):
        """
        搜索 type_:
        1: 单曲, 10: 专辑, 100: 歌手, 1000: 歌单, 1002: 用户
        1004: MV, 1006: 歌词, 1009: 电台, 1014: 视频
        """
        url = "https://music.163.com/api/cloudsearch/pc"
        data = {
            "s": key,
            "type": type_,
            "limit": limit,
            "offset": limit * page,
            "total": True
        }
        response = request(url=url, data=data, headers=self.headers, method='POST')
        return response.json()

    def search(self, text: str, number=10):
        return self._search(text, "1", 0, number)

    def get_info(self, search_info: str, hash_sha256: str, data_exchange_queue: queue.Queue):
        music_list = self.search(search_info)['result']['songs']
        music_info = (self,) + tuple({'name': str_process(music['name']), 'artist': '&'.join(i['name'] for i in music['ar']), 'album': str_process(music['al']['name']), 'id': music['id'], 'duration': music['dt'] // 1000, 'pic': music['al']['picUrl']} for music in music_list) + (hash_sha256,)
        data_exchange_queue.put(music_info)

    def get_lyrics(self, song_id):
        """使用您已有的歌词解析逻辑"""
        url = 'https://music.163.com/api/song/lyric'
        time_compile = re.compile(r'\[(\d*:?\d+:\d+\.*\d*)] *')
        lyrics = request(url=url, data={"id": song_id, "lv": -1, "kv": -1, "tv": -1, }, headers=self.headers, method='POST').json()['lrc']['lyric']
        lyrics_tuple = tuple(sorted(((QtCore.QTime(0, 0, 0).msecsTo(QtCore.QTime.fromString(time_compile.findall(i)[0], 'mm:ss.zz')), time_compile.sub('', i)) for i in lyrics.split('\n') if i), key=lambda x: x[0]))
        return lyrics_tuple

    def get_cover(self, cover_url: str):
        """使用您已有的封面处理逻辑"""
        cover_response = request(url=cover_url, method='GET')
        return resize_image(cover_response.content)


def generate_signature(params, secret_key):
    sorted_params = sorted(params.items())
    base_string = ''.join(f"{k}={v}" for k, v in sorted_params)
    base_string = secret_key + base_string + secret_key
    new_md5 = hashlib.md5()
    new_md5.update(base_string.encode('utf-8'))
    return new_md5.hexdigest()


class KuGouMusic(object):
    def __init__(self):
        self.cookie_dict = {}
        self.secret_key = "NVPh5oo715z5DIWAeQlhMDsWXXQV4hwt"
        self.headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/71.0.3578.98 Safari/537.36'}

    def get_cookie(self):
        cookie = 'kg_mid=68aa6f0242d4192a2a9e2b91e44c226d; kg_dfid=4DoTYZ0DYq9M3ctVHp0cBghm; kg_dfid_collect=d41d8cd98f00b204e9800998ecf8427e; Hm_lvt_aedee6983d4cfc62f509129360d6bb3d=1618922741,1618923483; Hm_lpvt_aedee6983d4cfc62f509129360d6bb3d=1618924198'.split('; ')
        self.cookie_dict.clear()
        for co in cookie:
            co_list = co.split('=')
            self.cookie_dict[co_list[0]] = co_list[1]

    def get_html(self, url):
        # 加一个cookie
        cookie = 'kg_mid=68aa6f0242d4192a2a9e2b91e44c226d; kg_dfid=4DoTYZ0DYq9M3ctVHp0cBghm; kg_dfid_collect=d41d8cd98f00b204e9800998ecf8427e; Hm_lvt_aedee6983d4cfc62f509129360d6bb3d=1618922741,1618923483; Hm_lpvt_aedee6983d4cfc62f509129360d6bb3d=1618924198'.split('; ')
        cookie_dict = {}
        for co in cookie:
            co_list = co.split('=')
            cookie_dict[co_list[0]] = co_list[1]
        try:
            response = request(url, headers=self.headers, cookies=cookie_dict, method='GET')
            response.raise_for_status()
            response.encoding = 'utf-8'
            return response.text
        except Exception as err:
            print(err)
            return '请求异常'

    def get_search_url(self, keyword: str):
        k = int(round(time.time() * 1000))
        params = {
            'appid': '1014',
            'bitrate': '0',
            'callback': 'callback123',
            'clienttime': k,
            'clientver': '1000',
            'dfid': '-',
            'filter': '10',
            'inputtype': '0',
            'iscorrection': '1',
            'isfuzzy': '0',
            'keyword': keyword,
            'mid': k,
            'page': '1',
            'pagesize': '10',
            'platform': 'WebFilter',
            'privilege_filter': '0',
            'srcappid': '2919',
            'token': '',
            'userid': '0',
            'uuid': k,
        }
        signature = generate_signature(params, self.secret_key)
        keyword = parse.quote(keyword)
        params['keyword'] = keyword
        params['signature'] = signature
        url = "https://complexsearch.kugou.com/v2/search/song?{0}".format('&'.join('='.join(map(str, i)) for i in params.items()))
        return url

    # 电脑端网页歌词获取(已失效)
    # def get_lyrics_url(self, song_id: str):
    #     k = int(round(time.time() * 1000))
    #     params = {
    #         "srcappid": "2919",
    #         "clientver": "20000",
    #         "clienttime": k,
    #         "mid": k,
    #         "uuid": k,
    #         "dfid": "-",
    #         "appid": "1014",
    #         "platid": "4",
    #         "encode_album_audio_id": song_id,
    #         "token": "",
    #         "userid": "0"
    #     }
    #     signature = generate_signature(params, self.secret_key)
    #     params['signature'] = signature
    #     url = "https://wwwapi.kugou.com/play/songinfo?{0}".format('&'.join('='.join(map(str, i)) for i in params.items()))
    #     return url

    # 手机浏览器网页歌词获取
    # def get_lyrics_url(self, song_title, song_hash: str, song_length: int):
    def get_lyrics_url(self, song_hash: str):
        k = int(round(time.time() * 1000))
        # params = {
        #     'keyword': song_title,
        #     'hash': song_hash,
        #     'timelength': song_length,
        #     'srcappid': '2919',
        #     'clientver': '20000',
        #     'clienttime': k,
        #     'mid': '-',
        #     'uuid': '-',
        #     'dfid': '-'
        # }
        params = {
            'keyword': '',
            'hash': song_hash,
            'timelength': '0',
            'srcappid': '2919',
            'clientver': '20000',
            'clienttime': k,
            'mid': '-',
            'uuid': '-',
            'dfid': '-'
        }
        signature = generate_signature(params, self.secret_key)
        params['signature'] = signature
        url = "https://m3ws.kugou.com/api/v1/krc/get_lyrics?{0}".format('&'.join('='.join(map(str, i)) for i in params.items()))
        return url

    def get_info(self, search_info: str, hash_sha256: str, data_exchange_queue: queue.Queue):
        search_url = self.get_search_url(search_info)
        text = self.get_html(search_url)
        song_list = json.loads(text[12:-2])['data']['lists']
        music_info = (self,) + tuple({'name': str_process(info['SongName']), 'artist': str_process(info['SingerName']), 'album': str_process(info['AlbumName']), 'id': info['FileHash'], 'duration': info['Duration'], 'pic': info['Image']} for info in song_list) + (hash_sha256,)
        # music_info = (self,) + tuple({'name': str_process(info['SongName']), 'artist': str_process(info['SingerName']), 'album': str_process(info['AlbumName']), 'id': info['EMixSongID'], 'duration': info['Duration'], 'pic': info['Image']} for info in song_list) + (hash_sha256,)
        data_exchange_queue.put(music_info)

    def get_lyrics(self, song_id: str):
        lyrics_url = self.get_lyrics_url(song_id)
        lyrics_info = request(url=lyrics_url, headers=self.headers, method='GET').json()
        # lyrics = lyrics_info['data']['lyrics']
        lyrics = lyrics_info['data']['lrc']
        if '\r\n' in lyrics:
            lyrics = lyrics.split('\r\n')
        if '\n' in lyrics:
            lyrics = lyrics.split('\n')
        time_compile = re.compile(r'\[(\d*:?\d+:\d+\.*\d*)] *')
        lyrics = tuple(sorted(((QtCore.QTime(0, 0, 0).msecsTo(QtCore.QTime.fromString(time_compile.findall(i)[0], 'mm:ss.zz')), time_compile.sub('', i)) for i in lyrics if time_compile.search(i)), key=lambda x: x[0]))
        return lyrics

    def get_cover(self, cover_url: str):
        cover_url = cover_url.replace('{size}/', '')
        cover_response = request(url=cover_url, headers=self.headers, method='GET')
        return resize_image(cover_response.content)


class KuWoMusic(object):
    def __init__(self):
        self.headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                                      'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/71.0.3578.98 Safari/537.36',
                        'Cookie': '_ga=GA1.2.136730414.1610802835; _gid=GA1.2.80092114.1621072767; Hm_lvt_cdb524f'
                                  '42f0ce19b169a8071123a4797=1621072767; Hm_lpvt_cdb524f42f0ce19b169a8071123a4797'
                                  '=1621073279; _gat=1; kw_token=C713RK6IJ8J',
                        'csrf': 'C713RK6IJ8J',
                        'Host': 'www.kuwo.cn',
                        'Referer': ''}

    def get_html(self, url, search_key=None, mid=None):
        if 'mid' not in url:
            self.headers['Referer'] = 'http://www.kuwo.cn/search/list?key=' + search_key
        else:
            self.headers['Referer'] = 'http://www.kuwo.cn/play_detail/{}'.format(mid)
            del self.headers['csrf']
        try:
            response = request(url=url, headers=self.headers, method='GET')
            response.raise_for_status()
            response.encoding = 'utf-8'
            return response.text
        except Exception as err:
            print(err)
            return '请求异常'

    def get_info(self, search_info: str, hash_sha256: str, data_exchange_queue: queue.Queue):
        search_key = parse.quote(search_info)
        search_url = 'https://www.kuwo.cn/search/searchMusicBykeyWord?vipver=1&client=kt&ft=music&encoding=utf8&rformat=json&pn=0&rn=10&all={}'.format(search_key)
        text = self.get_html(search_url, search_key)
        song_list = json.loads(text.replace('\'', '"'))['abslist']
        pic_compile = re.compile(r'^\d+')
        music_info = (self,) + tuple({'name': str_process(info['NAME']), 'artist': str_process(info['ARTIST']), 'album': str_process(info['ALBUM']), 'id': info['DC_TARGETID'], 'duration': info['DURATION'], 'pic': pic_compile.sub('', info['web_albumpic_short'], 1)} for info in song_list) + (hash_sha256,)
        data_exchange_queue.put(music_info)

    def get_lyrics(self, song_id: str):
        lyrics_url = 'https://www.kuwo.cn/openapi/v1/www/lyric/getlyric?musicId={}'.format(song_id)
        lyrics_info = request(url=lyrics_url, headers=self.headers, method='GET').json()
        lyrics = tuple(sorted(((int(float(i['time']) * 1000), i['lineLyric']) for i in lyrics_info['data']['lrclist']), key=lambda x: x[0]))
        return lyrics

    def get_cover(self, cover_url: str):
        cover_url = 'https://img2.kuwo.cn/star/albumcover/500{}'.format(cover_url)
        headers = self.headers.copy()
        headers['Host'] = 'img2.kuwo.cn'
        cover_response = request(url=cover_url, headers=headers, method='GET')
        return resize_image(cover_response.content)


# 测试示例
# if __name__ == '__main__':
#     import threading
#     queue_ = queue.Queue(maxsize=100)
#     threading.Thread(target=NetEaseMusic().get_info, args=('生来倔强', '0', queue_), daemon=True).start()
#     threading.Thread(target=KuGouMusic().get_info, args=('生来倔强', '0', queue_), daemon=True).start()
#     threading.Thread(target=KuWoMusic().get_info, args=('生来倔强', '0', queue_), daemon=True).start()
#     for _ in range(3):
#         print(queue_.get())
#     print(KuGouMusic().get_lyrics('22EA4CECB925BC0F2F54F48E9A81A167'))
