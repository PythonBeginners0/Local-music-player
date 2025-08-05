import re
import sys
import time
import json
import queue
import socket
import winreg
import signal
import psutil
import random
import hashlib
import filetype
import threading
from pathlib import Path
from mutagen import File
from concurrent import futures
from resources import qInitResources
from PySide6 import QtCore, QtGui, QtWidgets, QtMultimedia
from get_music_info import KuGouMusic, KuWoMusic, NetEaseMusic


# 强制关闭程序
def force_exit():
    time.sleep(3)
    print("已强制关闭程序")
    psutil.Process().terminate()


def signal_handler(*args):
    print(*args)
    main_window.close()


# def calculate_md5(file_path: Path):
#     hash_md5 = hashlib.md5()
#     with open(file_path, "rb") as f:
#     #     for data in iter(lambda: f.read(8192), b""):
#     #         hash_md5.update(data)
#         mmapped_file = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
#         hash_md5.update(mmapped_file)
#         mmapped_file.close()
#     return hash_md5.hexdigest()


def calculate_md5(file_path: Path, chunk_size=8192):
    hash_md5 = hashlib.md5()
    with open(file_path, 'rb') as file:
        file_size = file_path.stat().st_size
        if file_size < chunk_size * 5:
            hash_md5.update(file.read())
        else:
            file.seek(chunk_size)
            hash_md5.update(file.read(chunk_size))
            file.seek(file_size // 2 - chunk_size // 2)
            hash_md5.update(file.read(chunk_size))
            file.seek(-chunk_size * 2, 2)
            hash_md5.update(file.read(chunk_size))
    return hash_md5.hexdigest()


def handle_player_control_command(command: str, client_socket):
    data = json.loads(command)
    success = True
    mode = data['mode']
    try:
        if mode == 'get_status':
            content = f"播放状态:{'播放中' if main_window.player.isPlaying() else '已暂停'},播放模式:{main_window.play_mode_button.toolTip()},当前播放的内容:<{main_window.media.title} - {main_window.media.artist}>,音量:{main_window.volume_widget.value()}"
        elif mode == 'get_playlist_info':
            content = f'当前播放列表有{len(main_window.playlist.playlist)}首歌曲,播放模式:{main_window.play_mode_button.toolTip()},当前正在播放<{main_window.media.title} - {main_window.media.artist}>,列表歌曲为{";".join(f"{i[0]+1}.<{i[1].title} - {i[1].artist}>" for i in zip(range(len(main_window.playlist.playlist_random if main_window.playlist.play_mode == 1 else main_window.playlist.playlist)), (main_window.playlist.playlist_random if main_window.playlist.play_mode == 1 else main_window.playlist.playlist)))}'
        elif mode == 'play':
            main_window.player.play()
            content = f'正在播放<{main_window.media.title} - {main_window.media.artist}>'
        elif mode == 'pause':
            main_window.player.pause()
            content = f'已暂停播放<{main_window.media.title} - {main_window.media.artist}>'
        elif mode == 'next':
            main_window.playlist.next()
            content = f'已切换到下一首歌曲:<{main_window.media.title} - {main_window.media.artist}>'
        elif mode == 'previous':
            main_window.playlist.previous()
            content = f'已切换到上一首歌曲:<{main_window.media.title} - {main_window.media.artist}>'
        elif mode == 'get_volume':
            content = f'当前音量:{main_window.volume_widget.value()}'
        elif mode == 'set_volume':
            volume = int(data['args'])
            if 0 <= volume <= 100:
                main_window.audio_output.setVolume(volume / 100)
                main_window.volume_widget.setValue(volume)
                main_window.volume_button.setToolTip(f'音量:{int(main_window.audio_output.volume() * 100):.0f}')
                content = f'已将设置音量为{main_window.volume_widget.value()}'
            else:
                raise ValueError('音量设置失败,请输入0-100的数字')
        elif mode == 'get_play_mode':
            content = f'当前播放模式:{main_window.play_mode_button.toolTip()}'
        elif mode == 'set_play_mode':
            play_mode = int(data['args'])
            if 0 <= play_mode <= 2:
                main_window.playlist.play_mode = play_mode
                main_window.play_mode_changed()
                content = f'已切换播放模式为:{main_window.play_mode_button.toolTip()}'
            else:
                raise ValueError('播放模式设置失败,请输入0-2的数字')
        elif mode == 'set_media':
            music_title, music_artist, music_album = data['args']
            Multiple_ratio = (3, 2 if music_artist != '未知艺术家' else 0, 1 if music_album != '未知专辑' else 0)
            get_best_similarity = lambda n: sum(map(lambda x, y: x * y, (Similarity(music_title, n.title), Similarity(music_artist, n.artist), Similarity(music_album, n.album)), Multiple_ratio))
            media = max(main_window.playlist.playlist_random, key=get_best_similarity) if main_window.playlist.play_mode == 1 else max(main_window.playlist.playlist, key=get_best_similarity)
            main_window.playlist.set_index(media)
            content = f'已切换到歌曲:<{main_window.media.title} - {main_window.media.artist}>'
        elif mode == 'set_media_index':
            if 0 < int(data['args']) <= len(main_window.playlist.playlist):
                media: Media = main_window.playlist.playlist_random[int(data['args']) - 1] if main_window.playlist.play_mode == 1 else main_window.playlist.playlist[int(data['args']) - 1]
                main_window.playlist.set_index(media)
                content = f'已切换到歌曲:<{media.title} - {media.artist}>'
            else:
                raise ValueError('无效的索引')
        elif mode == 'sort':
            args = data['args']
            if isinstance(args, str):
                args = eval(args.replace('，', ','))
            playlist_len = len(main_window.playlist.playlist)
            if len(args) != playlist_len:
                original = [i for i in range(1, playlist_len+1)]
                for i in args[:-1]:
                    original.remove(i)
                if args[-1] == 'random':
                    random.shuffle(original)
                    args = args[:-1] + original
                elif args[-1] == 'order':
                    args = args[:-1] + original
                else:
                    raise ValueError(f'列表元素数量需为{playlist_len},而你传入的参数元素数为{len(args)},请检查参数,且输入的简化格式不对,列表最后一项只能为\'random\'或\'order\'')
            if main_window.playlist.play_mode == 1:
                playlist = main_window.playlist.playlist_random.copy()
            else:
                playlist = main_window.playlist.playlist.copy()
            playlist_widget = tuple(main_window.playlist_widget.playlist_layout.itemAt(i) for i in range(main_window.playlist_widget.playlist_layout.count()))
            main_window.playlist.play_mode = 1
            write_status('play_mode', 1)
            main_window.play_mode_button.setIcon(main_window.resource.random)
            main_window.play_mode_button.setToolTip('随机播放')
            main_window.playlist.playlist_random.clear()
            music_files = []
            for i in args:
                i = int(i) - 1
                media = playlist[i]
                music_files.append(str(media.path))
                main_window.playlist.playlist_random.append(media)
                main_window.playlist_widget.playlist_layout.addWidget(playlist_widget[i].widget())
            main_window.playlist.index = main_window.playlist.playlist_random.index(main_window.media)
            main_window.playlist_widget.isNormalShow = False
            main_window.playlist_widget.show()
            main_window.playlist_widget.isNormalShow = True
            main_window.playlist_widget.hide()
            main_window.playlist_widget.move(main_window.geometry().bottomLeft() + QtCore.QPoint(0, -main_window.playlist_widget.height()))
            write_status('files', ['playlist_random'] + music_files)
            content = f'当前播放列表有{len(main_window.playlist.playlist)}首歌曲,播放模式:{main_window.play_mode_button.toolTip()},当前正在播放<{main_window.media.title} - {main_window.media.artist}>,列表歌曲为{";".join(f"{i[0]+1}.<{i[1].title} - {i[1].artist}>" for i in zip(range(len(main_window.playlist.playlist_random)), main_window.playlist.playlist_random))}'
        else:
            content = '无效的指令'
    except Exception as e:
        success = False
        content = f'指令执行失败,错误原因<{e}>'
    client_socket.send(json.dumps({'success': success, 'result': content}).encode('utf-8'))


# 本地接口使用socket控制,主要适用于小智AI的控制
def socket_server():
    # 创建TCP socket
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # 设置端口复用
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    # 绑定IP和端口
    server_socket.bind(('127.0.0.1', 8888))
    # 开始监听
    server_socket.listen(1)
    print("服务端已启动")
    while not close_thread:
        try:
            # 接受客户端连接
            client_socket, client_address = server_socket.accept()
            try:
                while True:
                    # 接收客户端消息
                    data = client_socket.recv(8192)
                    if not data:
                        break
                    main_window.run_function.emit(lambda: handle_player_control_command(data.decode('utf-8'), client_socket))
            except ConnectionResetError:
                pass
            finally:
                client_socket.close()
        except Exception as e:
            print(f"发生错误: {e}")
            time.sleep(0.5)
    server_socket.close()


def write_status(status: str='normal', args=None):
    if cache_reading:
        return
    normal_status_dict = '{"files": {"playlist": [], "playlist_random": []}, "index": 0, "volume": 30, "play_mode": 0, "position": 0}'
    status_dict = {}
    loop = False
    try:
        status_dict = json.loads(open(status_cache_path, 'r', encoding='utf-8').read())
        if not isinstance(status_dict, dict):
            loop = True
        for i in ('files', 'index', 'volume', 'play_mode', 'position'):
            if i not in status_dict:
                loop = True
        if (not isinstance(status_dict['files'], dict) or 'playlist' not in status_dict['files'] or 'playlist_random' not in status_dict['files'] or not isinstance(status_dict['files']['playlist'], list) or not isinstance(status_dict['files']['playlist_random'], list)) and not loop:
            loop = True
    except Exception as e:
        print(e)
        loop = True
    if loop:
        status_dict = json.loads(normal_status_dict)
        with open(status_cache_path, 'w', encoding='utf-8') as file:
            json.dump(status_dict, file, ensure_ascii=False, indent=4)
    if status == 'normal':
        return
    elif status == 'files':
        status_dict['files'][args[0]] = args[1:]
    elif status == 'index':
        status_dict['index'] = args
    elif status == 'volume':
        status_dict['volume'] = args
    elif status == 'play_mode':
        status_dict['play_mode'] = args
    elif status == 'position':
        status_dict['position'] = args
    else:
        return
    # print(f'状态<{status}>更新成功<{args}>')
    try:
        with open(status_cache_path, 'w', encoding='utf-8') as file:
            json.dump(status_dict, file, ensure_ascii=False, indent=4)
    except Exception as e:
        print(e)
        with open(status_cache_path, 'w', encoding='utf-8') as file:
            json.dump(status_dict, file, ensure_ascii=False, indent=4)
    return status_dict


def get_follow_folder(folder_path: Path):
    loop = True
    while loop:
        dir_num = 0
        last_dir = None
        for i in folder_path.iterdir():
            if i.is_file() and filetype.is_audio(i):
                loop = False
                break
            elif i.is_dir():
                dir_num += 1
                if dir_num > 1:
                    loop = False
                    break
                last_dir = i
        if loop and dir_num == 1:
            folder_path = last_dir
    return folder_path


def get_music_folder():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders")
        music_folder, _ = winreg.QueryValueEx(key, "My Music")
        music_folder = get_follow_folder(Path(music_folder))
        music_folder = str(music_folder).replace('\\', '/')
        # print(QtCore.QUrl(f"file:///{music_folder}"))
        return QtCore.QUrl(f"file:///{music_folder}")
    except Exception:
        return ''


class Resource(object):
    def __init__(self):
        resource_path = Path(__file__).parent.joinpath('icons')
        self.add_line = QtGui.QPixmap(resource_path.joinpath('add-line.png'))
        self.circle_edit_outline = QtGui.QPixmap(resource_path.joinpath('circle-edit-outline.png'))
        self.delete = QtGui.QPixmap(resource_path.joinpath('delete.png'))
        self.folder_open = QtGui.QPixmap(resource_path.joinpath('folder-open.png'))
        self.music_notes = QtGui.QPixmap(resource_path.joinpath('music-notes.png'))
        self.music_app_icon = QtGui.QPixmap(resource_path.joinpath('music_app_icon.png'))
        self.no_song_cover = QtGui.QPixmap(resource_path.joinpath('no_song_cover.png'))
        self.pause_circle_outline = QtGui.QPixmap(resource_path.joinpath('pause-circle-outline.png'))
        self.play_circle_outline = QtGui.QPixmap(resource_path.joinpath('play-circle-outline.png'))
        self.play_outline = QtGui.QPixmap(resource_path.joinpath('play-outline.png'))
        self.playlist_music_outline = QtGui.QPixmap(resource_path.joinpath('playlist-music-outline.png'))
        self.random = QtGui.QPixmap(resource_path.joinpath('random.png'))
        self.repeat_once = QtGui.QPixmap(resource_path.joinpath('repeat-once.png'))
        self.repeat = QtGui.QPixmap(resource_path.joinpath('repeat.png'))
        self.skip_next_circle_outline = QtGui.QPixmap(resource_path.joinpath('skip-next-circle-outline.png'))
        self.skip_previous_circle_outline = QtGui.QPixmap(resource_path.joinpath('skip-previous-circle-outline.png'))
        self.volume_high = QtGui.QPixmap(resource_path.joinpath('volume-high.png'))
        self.volume_low = QtGui.QPixmap(resource_path.joinpath('volume-low.png'))
        self.volume_medium = QtGui.QPixmap(resource_path.joinpath('volume-medium.png'))
        self.volume_off = QtGui.QPixmap(resource_path.joinpath('volume-off.png'))
        self.window_close = QtGui.QPixmap(resource_path.joinpath('window-close.png'))
        self.window_maximize = QtGui.QPixmap(resource_path.joinpath('window-maximize.png'))
        self.window_minimize = QtGui.QPixmap(resource_path.joinpath('window-minimize.png'))
        self.window_restore = QtGui.QPixmap(resource_path.joinpath('window-restore.png'))


class Media(object):
    def __init__(self, media_path: Path):
        audio = File(media_path, easy=True)
        self.path = media_path
        self.hash_md5 = self.path.stem + '_' + calculate_md5(media_path)
        self.media_url = QtCore.QUrl.fromLocalFile(media_path)
        self.title = audio.get('title', [media_path.stem])[0]
        self.artist = audio.get('artist', ['未知艺术家'])[0]
        self.album = audio.get('album', ['未知专辑'])[0]
        self.duration = int(audio.info.length)
        self.media_info_path = media_info_cache_path.joinpath(f'{self.hash_md5}.info')
        # 特定格式的处理
        if filetype.guess(media_path).is_extension('mp3'):
            audio = File(media_path)
            self._lyrics = (lambda x: (x[0] if x else ''))(tuple(i[1].text for i in audio.tags.items() if 'USLT' in i[0] and i[1]))
        elif 'lyrics' in audio:
            self._lyrics = audio['lyrics'][0]
        else:
            self._lyrics = None
        try:
            media_info = eval(open(self.media_info_path, 'r', encoding='utf-8').read())
            if not isinstance(media_info, dict):
                media_info = {}
            if 'cover_source' not in media_info:
                media_info.update({'cover_source': 'netease'})
            if 'lyrics_source' not in media_info:
                media_info.update({'lyrics_source': 'local'})
        except Exception:
            media_info = {'cover_source': 'netease', 'lyrics_source': 'local'}
        if media_info['lyrics_source'] == 'local' and self._lyrics is None:
            media_info['lyrics_source'] = 'netease'
        self._cover_source = media_info['cover_source']
        self._lyrics_source = media_info['lyrics_source']

    @property
    def lyrics(self):
        if self._lyrics is None or not self._lyrics:
            self._lyrics = ''
            lyric_path = lyrics_cache_path.joinpath(f'{self.hash_md5}.lyric')
            if lyric_path.exists():
                with open(lyric_path, 'r', encoding='utf-8') as f:
                    self._lyrics = eval(f.read())
        return self._lyrics

    @property
    def cover_source(self):
        return self._cover_source

    @cover_source.setter
    def cover_source(self, value):
        if self._cover_source != value:
            if self.media_info_path.exists():
                try:
                    media_info = eval(open(self.media_info_path, 'r', encoding='utf-8').read())
                    if not isinstance(media_info, dict):
                        media_info = {}
                except Exception:
                    media_info = {}
                media_info.update({'cover_source': value})
            else:
                media_info = {'cover_source': value}
            open(self.media_info_path, 'w', encoding='utf-8').write(str(media_info))
            self._cover_source = value

    @property
    def lyrics_source(self):
        return self._lyrics_source

    @lyrics_source.setter
    def lyrics_source(self, value):
        if self._lyrics_source != value:
            if self.media_info_path.exists():
                try:
                    media_info = eval(open(self.media_info_path, 'r', encoding='utf-8').read())
                    if not isinstance(media_info, dict):
                        media_info = {}
                except Exception:
                    media_info = {}
                media_info.update({'lyrics_source': value})
            else:
                media_info = {'lyrics_source': value}
            open(self.media_info_path, 'w', encoding='utf-8').write(str(media_info))
            self._lyrics_source = value


def str_process(string: str):
    process_compile = {'：': ':', '、': '&', '|': '&', '/': '&'}
    for k, v in process_compile.items():
        string = string.replace(k, v)
    return string


def Similarity(str1: str, str2: str):
    m = len(str1)
    n = len(str2)

    dp = [[0 for _ in range(n + 1)] for _ in range(m + 1)]

    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if str1[i - 1] == str2[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = min(dp[i - 1][j] + 1, dp[i][j - 1] + 1, dp[i - 1][j - 1] + 1)

    return 1 - (dp[m][n] / max(len(str1), len(str2)))


def get_music_info(music: Media):
    search_info = str_process(music.title)
    music_artist = str_process(music.artist)
    music_album = str_process(music.album)
    while True:
        kuwo_results = []
        kugou_results = []
        netease_results = []
        executor.submit(KuWoMusic().get_info, search_info, music.hash_md5, data_exchange_queue)
        executor.submit(KuGouMusic().get_info, search_info, music.hash_md5, data_exchange_queue)
        executor.submit(NetEaseMusic().get_info, search_info, music.hash_md5, data_exchange_queue)
        num = 0
        while True:
            result_data = data_exchange_queue.get()
            if result_data[-1] == music.hash_md5:
                for i in result_data[1:-1]:
                    i.update({'self': result_data[0]})
                    if result_data[0].__class__.__name__ == 'KuWoMusic':
                        kuwo_results.append(i)
                    elif result_data[0].__class__.__name__ == 'KuGouMusic':
                        kugou_results.append(i)
                    elif result_data[0].__class__.__name__ == 'NetEaseMusic':
                        netease_results.append(i)
                num += 1
                if num == 3:
                    break
            else:
                data_exchange_queue.put(result_data)
                time.sleep(0.01)
        Multiple_ratio = (3, 2 if music_artist != '未知艺术家' else 0, 1 if music_album != '未知专辑' else 0)
        get_best_similarity = lambda n: sum(map(lambda x, y: x * y, (Similarity(search_info, n['name']), Similarity(music_artist, n['artist']), Similarity(music_album, n['album'])), Multiple_ratio)) - abs(music.duration - int(n['duration']))
        try:
            result = (max(netease_results, key=get_best_similarity), max(kugou_results, key=get_best_similarity), max(kuwo_results, key=get_best_similarity), music.hash_md5)
            return result
        except Exception:
            pass


class ThreadPoolExecutor(futures.ThreadPoolExecutor):
    def submit(self, fn, *args, **kwargs):
        future = super(ThreadPoolExecutor, self).submit(fn, *args, **kwargs)
        all_executor_threads.append(future)
        future.add_done_callback(lambda f: all_executor_threads.remove(f))
        return future


class MyPushButton(QtWidgets.QPushButton):
    def focusInEvent(self, event: QtGui.QFocusEvent):
        self.setCursor(QtCore.Qt.CursorShape.ArrowCursor)
        super().focusInEvent(event)


class MarqueeLabel(QtWidgets.QLabel):
    def __init__(self, *args, **kwargs):
        super(MarqueeLabel, self).__init__(*args, **kwargs)
        self.timer_id = 0
        self.loop = True
        self.x = 0
        self.text_width = 0
        self.speed = 1

    def timerEvent(self, event: QtCore.QTimerEvent):
        self.text_width = QtGui.QFontMetrics(self.font()).horizontalAdvance(self.text())
        self.x -= self.speed
        if self.x + self.text_width < 0:
            self.x = self.width()
        self.update()
        super().timerEvent(event)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        text = self.text()
        if self.text_width < self.width():
            self.loop = False
            painter.drawText(self.rect(), self.alignment(), text)
        else:
            if not self.loop:
                self.x = 0
                self.loop = True
            rect = QtCore.QRect(self.x, 0, self.text_width, self.height())
            painter.drawText(rect, self.alignment(), text)


class CustomLabel(QtWidgets.QLabel):
    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        font_metrics = painter.fontMetrics()
        text = self.text()
        width = self.width()
        if font_metrics.horizontalAdvance(text) > width:
            elided_text = font_metrics.elidedText(text, QtCore.Qt.TextElideMode.ElideRight, width)
            painter.drawText(self.rect(), self.alignment(), elided_text)
        else:
            painter.drawText(self.rect(), self.alignment(), text)


class MyMediaPlayer(QtMultimedia.QMediaPlayer):
    def setSourceFunction(self, source: QtCore.QUrl, play: bool = False):
        self.setSource(source)
        if play:
            self.play()


class MediaFrame(QtWidgets.QFrame):
    def __init__(self, media: Media, *args, **kwargs):
        super(MediaFrame, self).__init__(*args, **kwargs)
        self.setObjectName('MediaFrame')
        self.media = media
        self._parent: MyPlaylist = self.parent()
        self.resource: Resource = self._parent.resource
        self.playlist_widget: QtWidgets.QWidget = self._parent.playlist_widget
        __main_window: MainWindow = self._parent.parent()
        self.playlist: PlayList = __main_window.playlist
        self.main_layout = QtWidgets.QHBoxLayout(self)
        self.main_layout.setContentsMargins(2, 2, 2, 2)
        self.InfoLayout = QtWidgets.QHBoxLayout(self)
        self.InfoLayout.setContentsMargins(0, 0, 0, 0)
        self.cover_label = QtWidgets.QLabel(self)
        self.cover_label.setObjectName('MusicCover')
        self.isPlaying = False
        self.isNoSongCover = True
        self.scaled_size = 50
        self.cover_label.setPixmap(self.resource.no_song_cover.scaled(self.scaled_size, self.scaled_size, QtCore.Qt.AspectRatioMode.KeepAspectRatio, QtCore.Qt.TransformationMode.SmoothTransformation))
        self.cover_label.setFixedSize(self.cover_label.sizeHint())
        self.InfoLayout.addWidget(self.cover_label)
        self.info_layout = QtWidgets.QVBoxLayout(self)
        self.info_layout.setContentsMargins(0, 0, 0, 0)
        self.title = CustomLabel(media.title)
        self.title.setParent(self)
        self.title.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignBottom)
        font = QtGui.QFont('微软雅黑', 10)
        self.title.setFont(font)
        self.info_layout.addWidget(self.title)
        self.artist = CustomLabel(media.artist)
        self.artist.setParent(self)
        self.artist.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop)
        font.setPointSize(8)
        self.artist.setFont(font)
        self.info_layout.addWidget(self.artist)
        self.InfoLayout.addLayout(self.info_layout)
        self.main_layout.addLayout(self.InfoLayout, QtCore.Qt.AlignmentFlag.AlignLeft)
        self.button_frame = QtWidgets.QFrame(self)
        self.button_layout = QtWidgets.QHBoxLayout(self)
        self.button_layout.setContentsMargins(0, 0, 0, 0)
        self.play_button = QtWidgets.QPushButton(self)
        self.play_button.setIcon(self.resource.play_outline)
        self.play_button.setIconSize(QtCore.QSize(20, 20))
        self.play_button.clicked.connect(lambda: self.playlist.set_index(self.media))
        self.button_layout.addWidget(self.play_button)
        self.add_button = QtWidgets.QPushButton(self)
        self.add_button.setIcon(self.resource.add_line)
        self.add_button.setIconSize(QtCore.QSize(20, 20))
        self.add_button.clicked.connect(self.add_file_button_clicked)
        self.button_layout.addWidget(self.add_button)
        self.delete_button = QtWidgets.QPushButton(self)
        self.delete_button.setIcon(self.resource.delete)
        self.delete_button.setIconSize(QtCore.QSize(20, 20))
        self.delete_button.clicked.connect(lambda: self.playlist.delete_media(self.media, self))
        self.button_layout.addWidget(self.delete_button)
        self.button_frame.setLayout(self.button_layout)
        self.button_frame.setFixedSize(self.button_frame.sizeHint())
        self.button_frame.hide()
        self.main_layout.addWidget(self.button_frame, alignment=QtCore.Qt.AlignmentFlag.AlignRight)
        self.duration = QtWidgets.QLabel(QtCore.QTime(0, 0, 0).addSecs(media.duration).toString('hh:mm:ss'))
        self.duration.setParent(self)
        self.duration.setSizePolicy(QtWidgets.QSizePolicy.Policy.MinimumExpanding, QtWidgets.QSizePolicy.Policy.Expanding)
        font.setPointSize(10)
        self.duration.setFont(font)
        self.main_layout.addWidget(self.duration, alignment=QtCore.Qt.AlignmentFlag.AlignRight)
        self.setLayout(self.main_layout)

    def setPixmap(self, pixmap: QtGui.QPixmap):
        self.isNoSongCover = False
        self.cover_label.setPixmap(pixmap.scaled(self.scaled_size, self.scaled_size, QtCore.Qt.AspectRatioMode.KeepAspectRatio, QtCore.Qt.TransformationMode.SmoothTransformation))

    def add_file_button_clicked(self):
        main_window.playlist_widget.show_timer.stop()
        file_dialog = QtWidgets.QFileDialog(self)
        file_dialog.setFileMode(QtWidgets.QFileDialog.FileMode.ExistingFiles)
        file_dialog.setDirectoryUrl(get_music_folder())
        file_dialog.setNameFilter('音频文件 (*.mp3 *.wav *.flac)')
        if file_dialog.exec():
            for file_path in file_dialog.selectedFiles()[::-1]:
                self.playlist.add_media_from_file(Path(file_path), index=self.media)
        main_window.playlist_widget.show_timer.start()

    def resizeEvent(self, event: QtGui.QResizeEvent):
        super().resizeEvent(event)
        self.title.setMaximumWidth(self.width() - 74 - max(self.duration.width(), self.button_frame.width()))
        self.artist.setMaximumWidth(self.width() - 74 - max(self.duration.width(), self.button_frame.width()))
        # self.title.setMaximumWidth(self.width() - 74 - self.duration.width())
        # self.artist.setMaximumWidth(self.width() - 74 - self.duration.width())

    def enterEvent(self, event: QtGui.QEnterEvent):
        super().enterEvent(event)
        self._parent.setFocus()
        if not self.isPlaying:
            self.setStyleSheet('QFrame#MediaFrame{border-radius: 4px;border: 2px solid #346792;}')
            self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.button_frame.show()
        self.duration.hide()

    def leaveEvent(self, event: QtCore.QEvent):
        super().leaveEvent(event)
        self._parent.setFocus()
        if not self.isPlaying:
            self.setStyleSheet('')
            self.main_layout.setContentsMargins(2, 2, 2, 2)
        self.button_frame.hide()
        self.duration.show()


class PlayList(object):
    def __init__(self, player: MyMediaPlayer, index=0, play_mode=0, music_list=None):
        global cache_reading
        if music_list is None:
            music_list = {'playlist': [], 'playlist_random': []}
        self._index = index
        self.playlist: list[Media] = [Media(Path(i)) for i in music_list['playlist']]
        self.playlist_random: list[Media] = []
        if play_mode == 1:
            # self.playlist_random = sorted(self.playlist, key=lambda x: music_list['playlist_random'].index(str(x.path)))  # 已废用没有下边这个代码执行的快
            # for i in music_list['playlist_random']:
            #     self.playlist_random.append(self.playlist[music_list['playlist'].index(i)])  # 已废用没有下边这个代码执行的快
            index_map = {v: i for i, v in enumerate(music_list['playlist_random'])}
            self.playlist_random = sorted(self.playlist, key=lambda x: index_map[str(x.path)])
        self.player = player
        self.play_mode = play_mode
        if music_list['playlist'] or music_list['playlist_random']:
            cache_reading = True
            QtCore.QTimer.singleShot(500, self.init)
        executor.submit(self.duplicate_removal)


    # 初始化
    def init(self):
        global cache_reading
        if self.play_mode == 1:
            self.set_index(self.playlist_random[self.index])
            media_list = self.playlist_random.copy()
        else:
            self.set_index(self.playlist[self.index])
            media_list = self.playlist.copy()
        time_batch = int(5000 / len(media_list))
        times = 0
        for media in media_list[::-1]:
            times += 1
            cover_path = cover_cache_path.joinpath(media.cover_source, f'{media.hash_md5}.cover')
            if cover_path.exists():
                main_window.playlist_widget.add_media(media, cover_path, index=0, timeout=5000 - times * time_batch)
            else:
                main_window.playlist_widget.add_media(media, index=0)
        main_window.playlist_widget.isNormalShow = False
        main_window.playlist_widget.show()
        main_window.playlist_widget.isNormalShow = True
        main_window.playlist_widget.hide()
        try:
            media_frame: MediaFrame = main_window.playlist_widget.playlist_layout.itemAt(self.index).widget()
            main_window.playlist_widget.SetScrollBarValue(media_frame.frameGeometry().top())
        except:
            pass
        cache_reading = False

    def duplicate_removal(self):
        _PlayListLen = 0
        _PlayListRandomLen = 0
        while not close_thread:
            PlayListLen = len(self.playlist)
            PlayListRandomLen = len(self.playlist_random)
            if PlayListRandomLen != _PlayListRandomLen if self.play_mode == 1 else PlayListLen != _PlayListLen:
                _PlayListLen = PlayListLen
                _PlayListRandomLen = PlayListRandomLen
                if self.play_mode == 1:
                    playlist = self.playlist_random
                else:
                    playlist = self.playlist
                media_list = playlist.copy()
                playlist.clear()
                music_files = []
                hash_md5 = []
                for media in media_list:
                    if close_thread:
                        break
                    media_hash_md5 = media.hash_md5
                    if media_hash_md5 not in hash_md5:
                        hash_md5.append(media_hash_md5)
                        playlist.append(media)
                        music_files.append(str(media.path))
                if self.play_mode == 1:
                    write_status('files', ['playlist'] + [str(i.path) for i in self.playlist])
                    write_status('files', ['playlist_random'] + music_files)
                else:
                    write_status('files', ['playlist'] + music_files)
                if 'main_window' in globals():
                    main_window.run_function.emit(lambda: main_window.playlist_widget.add_file_button.setEnabled(True))
                    main_window.run_function.emit(lambda: main_window.playlist_widget.add_folder_button.setEnabled(True))
            time.sleep(0.1)

    def set_source(self, media: Media, play: bool = False):
        self.player.stop()
        main_window.media = media
        QtCore.QTimer.singleShot(1, lambda: self.player.setSourceFunction(media.media_url, play))

    def set_index(self, media: Media):
        if self.play_mode == 1:
            self.index = self.playlist_random.index(media)
        else:
            self.index = self.playlist.index(media)
        self.set_source(media, True)

    def delete_media(self, media: Media, widget: QtWidgets.QWidget):
        if self.play_mode == 1:
            index = self.playlist_random.index(media)
            self.playlist_random.remove(media)
            self.playlist.remove(media)
            if self.index >= len(self.playlist_random):
                self.index = 0
                self.set_source(self.playlist_random[0], True)
            elif self.index == index:
                self.set_source(self.playlist_random[index], True)
        else:
            index = self.playlist.index(media)
            self.playlist.remove(media)
            if self.index >= len(self.playlist):
                self.index = 0
                self.set_source(self.playlist[0], True)
            elif self.index == index:
                self.set_source(self.playlist[index], True)
        widget.parent().setFocus()
        widget.deleteLater()

    def add_media_from_file(self, media_path: Path, index: int|Media = -1):
        main_window.playlist_widget.add_folder_button.setEnabled(False)
        main_window.playlist_widget.add_file_button.setEnabled(False)
        if isinstance(index, Media):
            if self.play_mode == 1:
                index = self.playlist_random.index(index) + 1
            else:
                index = self.playlist.index(index) + 1
        if index == -1:
            if self.play_mode == 1:
                index = len(self.playlist_random)
            else:
                index = len(self.playlist)
        if media_path.is_file():
            media = Media(media_path)
            cover_path = cover_cache_path.joinpath(media.cover_source, f'{media.hash_md5}.cover')
            if cover_path.exists():
                main_window.playlist_widget.add_media(media, QtGui.QPixmap(cover_path), index=index)
            else:
                main_window.playlist_widget.add_media(media, index=index)
            if self.play_mode == 1:
                self.playlist_random.insert(index, media)
                if self.playlist:
                    index = self.playlist.index(self.playlist_random[self.index]) + 1
                else:
                    index = 0
            self.playlist.insert(index, media)
        else:
            media_path = get_follow_folder(media_path)
            media_list = [Media(i) for i in media_path.iterdir() if i.is_file() and filetype.is_audio(i)]
            if not media_list:
                main_window.playlist_widget.add_folder_button.setEnabled(True)
                main_window.playlist_widget.add_file_button.setEnabled(True)
                return
            time_batch = int(5000 / len(media_list))
            times = 0
            for media in media_list[::-1]:
                times += 1
                cover_path = cover_cache_path.joinpath(media.cover_source, f'{media.hash_md5}.cover')
                if cover_path.exists():
                    main_window.playlist_widget.add_media(media, cover_path, index=index, timeout=5000 - times * time_batch)
                else:
                    main_window.playlist_widget.add_media(media, index=index)
            if self.play_mode == 1:
                self.playlist_random[index:index] = media_list
                if self.playlist:
                    index = self.playlist.index(self.playlist_random[self.index]) + 1
                else:
                    index = 0
            self.playlist[index:index] = media_list
        if not self.player.source().path():
            if self.play_mode == 1:
                self.set_source(self.playlist_random[0])
            else:
                self.set_source(self.playlist[0])

    def play_button_clicked(self):
        if self.player.isPlaying():
            self.player.pause()
            return
        if self.play_mode == 1:
            if self.playlist_random and not self.player.isPlaying():
                if not self.player.source().path():
                    self.set_source(self.playlist_random[0])
                self.player.play()
        else:
            if self.playlist and not self.player.isPlaying():
                if not self.player.source().path():
                    self.set_source(self.playlist[0])
                self.player.play()

    def play(self):
        if self.play_mode == 1:
            if self.playlist_random:
                self.set_source(self.playlist_random[self.index], True)
        else:
            if self.playlist:
                self.set_source(self.playlist[self.index], True)

    def previous(self):
        self.index -= 1
        if self.index < 0:
            self.index = len(self.playlist) - 1
        self.play()

    def next(self):
        self.index += 1
        if self.index >= len(self.playlist):
            self.index = 0
        self.play()

    @property
    def index(self):
        return self._index

    @index.setter
    def index(self, index):
        write_status('index', index)
        self._index = index


class MyPlaylist(QtWidgets.QFrame):
    run_function = QtCore.Signal(object)
    def __init__(self, *args, **kwargs):
        super(MyPlaylist, self).__init__(*args, **kwargs)
        self.isNormalShow = True
        self._parent: MainWindow = self.parent()
        self.resource: Resource = self._parent.resource
        self.setObjectName('PlayListFrame')
        self.setStyleSheet('QFrame#PlayListFrame{background-color: #19232D;border-radius: 4px;border: 1px solid #455364;}QWidget#PlayListWidget{background-color: #19232D}')
        self.run_function.connect(lambda function: function())
        self.show_timer = QtCore.QTimer(self)
        self.show_timer.setInterval(16)
        self.show_timer.timeout.connect(self.show_hide)
        self.setMouseTracking(True)
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setContentsMargins(2, 2, 2, 2)
        self.top_frame = QtWidgets.QFrame(self)
        self.top_layout = QtWidgets.QHBoxLayout()
        self.top_layout.setContentsMargins(0, 0, 0, 0)
        self.title = QtWidgets.QLabel('播放列表')
        font = QtGui.QFont('微软雅黑', 10)
        font.setBold(True)
        font.setUnderline(True)
        self.title.setFont(font)
        self.top_layout.addWidget(self.title, QtCore.Qt.AlignmentFlag.AlignLeft)
        self.funciton_layout = QtWidgets.QHBoxLayout()
        self.add_file_button = MyPushButton(self)
        self.add_file_button.setIcon(self.resource.add_line)
        self.add_file_button.setIconSize(QtCore.QSize(20, 20))
        self.add_file_button.setFixedSize(30, 30)
        self.add_file_button.setToolTip('添加音乐')
        self.add_file_button.clicked.connect(self.add_file_button_clicked)
        self.funciton_layout.addWidget(self.add_file_button)
        self.add_folder_button = MyPushButton(self)
        self.add_folder_button.setIcon(self.resource.folder_open)
        self.add_folder_button.setIconSize(QtCore.QSize(20, 20))
        self.add_folder_button.setFixedSize(30, 30)
        self.add_folder_button.setToolTip('从文件夹中添加歌曲')
        self.add_folder_button.clicked.connect(self.add_folder_button_clicked)
        self.funciton_layout.addWidget(self.add_folder_button)
        self.delete_all_button = MyPushButton(self)
        self.delete_all_button.setIcon(self.resource.delete)
        self.delete_all_button.setIconSize(QtCore.QSize(20, 20))
        self.delete_all_button.setFixedSize(30, 30)
        self.delete_all_button.setToolTip('清空歌单')
        self.delete_all_button.clicked.connect(self.delete_all_button_clicked)
        self.funciton_layout.addWidget(self.delete_all_button)
        self.top_layout.addLayout(self.funciton_layout, QtCore.Qt.AlignmentFlag.AlignRight)
        self.top_frame.setLayout(self.top_layout)
        self.main_layout.addWidget(self.top_frame)
        self.playlist_area = QtWidgets.QScrollArea(self)
        self.playlist_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.playlist_widget = QtWidgets.QWidget(self)
        self.playlist_widget.setObjectName('PlayListWidget')
        self.playlist_layout = QtWidgets.QVBoxLayout()
        self.playlist_layout.setContentsMargins(0, 0, 0, 0)
        self.playlist_widget.setLayout(self.playlist_layout)
        self.playlist_area.setWidget(self.playlist_widget)
        self.playlist_area.setWidgetResizable(True)
        self.main_layout.addWidget(self.playlist_area)
        self.setLayout(self.main_layout)
        self.scroll_bar_animation_value = QtCore.QPropertyAnimation(self.playlist_area.verticalScrollBar(), b'value')
        self.scroll_bar_animation_value.setDuration(300)
        self.raise_()

    def SetScrollBarValue(self, value: int):
        if self.scroll_bar_animation_value.state() == QtCore.QAbstractAnimation.State.Running:
            self.scroll_bar_animation_value.stop()
        self.scroll_bar_animation_value.setStartValue(self.playlist_area.verticalScrollBar().value())
        self.scroll_bar_animation_value.setEndValue(value)
        self.scroll_bar_animation_value.start()

    def add_media(self, media: Media, pixmap: QtGui.QPixmap|Path=None, index=-1, timeout=0):
        if index == -1:
            index = self.playlist_layout.count()
        frame = MediaFrame(media, self)
        if pixmap:
            if timeout and isinstance(pixmap, Path):
                QtCore.QTimer.singleShot(timeout, lambda: frame.setPixmap(QtGui.QPixmap(pixmap)))
            else:
                frame.setPixmap(pixmap)
        self.playlist_layout.insertWidget(index, frame, alignment=QtCore.Qt.AlignmentFlag.AlignTop)
        if pixmap is None:
            playlist_executor.submit(main_window.get_music_info, media, load_cover=False, load_lyrics=False, load_playlist_cover=True)

    def show_hide(self):
        if not self.isAncestorOf(app.focusWidget()) and not self.playlist_widget.isAncestorOf(app.focusWidget()):
            main_window.play_list_button_clicked()
            self.show_timer.stop()

    def delete_all_button_clicked(self):
        while self.playlist_layout.count():
            self.playlist_layout.takeAt(0).widget().deleteLater()
        main_window.playlist.playlist.clear()
        main_window.playlist.playlist_random.clear()
        main_window.None_play()
        write_status('index', 0)
        write_status('position', 0)
        write_status('files', ['playlist'])
        write_status('files', ['playlist_random'])

    def add_file_button_clicked(self):
        self.show_timer.stop()
        file_dialog = QtWidgets.QFileDialog(self)
        file_dialog.setFileMode(QtWidgets.QFileDialog.FileMode.ExistingFiles)
        file_dialog.setDirectoryUrl(get_music_folder())
        file_dialog.setNameFilter('音频文件 (*.mp3 *.wav *.flac)')
        if file_dialog.exec():
            for file_path in file_dialog.selectedFiles():
                self._parent.playlist.add_media_from_file(Path(file_path))
        self.show_timer.start()

    def add_folder_button_clicked(self):
        self.show_timer.stop()
        folder_dialog = QtWidgets.QFileDialog(self)
        folder_dialog.setFileMode(QtWidgets.QFileDialog.FileMode.Directory)
        folder_dialog.setDirectoryUrl(get_music_folder())
        if folder_dialog.exec():
            folder_path = Path(folder_dialog.selectedFiles()[0])
            self._parent.playlist.add_media_from_file(Path(folder_path))
        self.show_timer.start()

    def showEvent(self, event: QtGui.QShowEvent):
        super().showEvent(event)
        if self.isNormalShow:
            self.setFocus()
            self.show_timer.start()


class MySlider(QtWidgets.QSlider):
    def __init__(self, *args, **kwargs):
        super(MySlider, self).__init__(*args, **kwargs)
        self.setMinimum(0)
        self.setPageStep(0)
        self.setSingleStep(0)
        self.LeftButtonPress = False

    def mousePressEvent(self, event: QtGui.QMouseEvent):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.LeftButtonPress = True
            if self.orientation() == QtCore.Qt.Orientation.Horizontal:
                value = round((event.position().x()+(pixels_per_px*8*(event.position().x() - (self.width() / 2))/self.width())) * self.maximum() / self.width())
                main_window.player.pause()
                main_window.player.setPosition(value)
            else:
                position = self.height() - event.position().y()
                value = round((position+(pixels_per_px*8*(position - (self.height() / 2))/self.height())) * self.maximum() / self.height())
                main_window.audio_output.setVolume(value / 100)
            self.setValue(value)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent):
        if self.LeftButtonPress and self.maximum() > 0:
            if self.orientation() == QtCore.Qt.Orientation.Horizontal:
                value = self.value()
                row = len(tuple(i for i in main_window.lyrics_time if i <= value)) - 1
                if row >= 0:
                    QtWidgets.QToolTip.showText(self.mapToGlobal(QtCore.QPoint(int(value/self.maximum()*self.width()), self.height() // 2)), main_window.lyrics_tuple[row][1], self)
                main_window.play_time_label.setText(QtCore.QTime(0, 0, 0).addSecs(value // 1000).toString('hh:mm:ss'))
                main_window.remain_time_label.setText(QtCore.QTime(0, 0, 0).addSecs((self.maximum() - value) // 1000).toString('hh:mm:ss'))
                if Path(main_window.player.source().path()).suffix == '.mp3':
                    if not value:
                        value += 50
                    elif value == self.maximum():
                        value -= 250
                main_window.player.setPosition(value)
            else:
                main_window.audio_output.setVolume(self.value() / 100)
                QtWidgets.QToolTip.showText(QtCore.QPoint(self.mapToGlobal(QtCore.QPoint(self.width() // 2, 0)).x(), event.globalPosition().y()), '{}%'.format(self.value()), self)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.LeftButtonPress = False
            if self.orientation() == QtCore.Qt.Orientation.Horizontal:
                main_window.player.play()
        super().mouseReleaseEvent(event)

    def focusOutEvent(self, event: QtGui.QFocusEvent):
        super().focusOutEvent(event)
        if self.orientation() == QtCore.Qt.Orientation.Vertical:
            main_window.volume_button_clicked()


class MyLabel(QtWidgets.QLabel):
    def __init__(self, *args, **kwargs):
        super(MyLabel, self).__init__(*args, **kwargs)

    def resizeEvent(self, event: QtGui.QResizeEvent):
        main_window.song_cover_label.setPixmapSize(self.geometry())
        super().resizeEvent(event)


class SongCoverLabel(QtWidgets.QLabel):
    def __init__(self, *args, **kwargs):
        super(SongCoverLabel, self).__init__(*args, **kwargs)
        self.setting_status = False
        self._parent: MainWindow = self.parent()
        self.song_cover_pixmap = QtGui.QPixmap(self._parent.resource.no_song_cover)
        self.right_button_menu = QtWidgets.QMenu(self)
        self.netease_action = QtGui.QAction('网易云音乐', self)
        self.netease_action.setObjectName('netease')
        self.netease_action.setCheckable(True)
        self.netease_action.triggered.connect(lambda: self.cover_source_changed(self.netease_action))
        self.netease_action.setChecked(True)
        self.right_button_menu.addAction(self.netease_action)
        self.kugou_action = QtGui.QAction('酷狗音乐', self)
        self.kugou_action.setObjectName('kugou')
        self.kugou_action.setCheckable(True)
        self.kugou_action.triggered.connect(lambda: self.cover_source_changed(self.kugou_action))
        self.right_button_menu.addAction(self.kugou_action)
        self.kuwo_action = QtGui.QAction('酷我音乐', self)
        self.kuwo_action.setObjectName('kuwo')
        self.kuwo_action.setCheckable(True)
        self.kuwo_action.triggered.connect(lambda: self.cover_source_changed(self.kuwo_action))
        self.right_button_menu.addAction(self.kuwo_action)

    def cover_source_changed(self, action: QtGui.QAction):
        if not self.setting_status:
            main_window.media.cover_source = action.objectName()
            main_window.playlist.playlist[main_window.playlist.index].cover_source = action.objectName()
            executor.submit(lambda: main_window.get_music_info(main_window.media, load_lyrics=False, load_playlist_cover=True))
            for i in (self.netease_action, self.kugou_action, self.kuwo_action):
                i.setChecked(False)
            action.setChecked(True)

    def set_button_status(self, source: str):
        for i in (self.netease_action, self.kugou_action, self.kuwo_action):
            i.setChecked(False)
        if source == 'netease':
            self.netease_action.setChecked(True)
        elif source == 'kugou':
            self.kugou_action.setChecked(True)
        elif source == 'kuwo':
            self.kuwo_action.setChecked(True)

    def setPixmapSize(self, geometry: QtCore.QRect):
        size = geometry.size()
        max_hidget = size.height() * 2 // 3
        scaled_size = size.width()
        if size.width() > max_hidget and max_hidget < size.width():
            scaled_size = max_hidget
        if scaled_size < main_window.min_scaled_size:
            scaled_size = main_window.min_scaled_size
        self.raise_()
        self.resize(scaled_size, scaled_size)
        self.move(geometry.bottomLeft() - QtCore.QPoint(0, scaled_size))
        self.setPixmap(self.song_cover_pixmap.scaled(scaled_size, scaled_size, QtCore.Qt.AspectRatioMode.KeepAspectRatio, QtCore.Qt.TransformationMode.SmoothTransformation))

    def contextMenuEvent(self, event: QtGui.QContextMenuEvent):
        self.setting_status = True
        self.set_button_status(main_window.media.cover_source)
        self.setting_status = False
        self.right_button_menu.exec(event.globalPos())


class LyricsScrollArea(QtWidgets.QScrollArea):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lyrics_time = 0
        self.setting_status = False
        self.setMouseTracking(True)
        self.lyrics_scrolling_timer = QtCore.QTimer(self)
        self.lyrics_scrolling_timer.setInterval(100)
        self.lyrics_scrolling_timer.timeout.connect(self.lyrics_scrolling)
        self.right_button_menu = QtWidgets.QMenu(self)
        self.local_action = QtGui.QAction('歌曲文件', self)
        self.local_action.setObjectName('local')
        self.local_action.setCheckable(True)
        self.local_action.triggered.connect(lambda: self.lyrics_source_changed(self.local_action))
        self.local_action.setChecked(True)
        self.right_button_menu.addAction(self.local_action)
        self.netease_action = QtGui.QAction('网易云音乐', self)
        self.netease_action.setObjectName('netease')
        self.netease_action.setCheckable(True)
        self.netease_action.triggered.connect(lambda: self.lyrics_source_changed(self.netease_action))
        self.right_button_menu.addAction(self.netease_action)
        self.kugou_action = QtGui.QAction('酷狗音乐', self)
        self.kugou_action.setObjectName('kugou')
        self.kugou_action.setCheckable(True)
        self.kugou_action.triggered.connect(lambda: self.lyrics_source_changed(self.kugou_action))
        self.right_button_menu.addAction(self.kugou_action)
        self.kuwo_action = QtGui.QAction('酷我音乐', self)
        self.kuwo_action.setObjectName('kuwo')
        self.kuwo_action.setCheckable(True)
        self.kuwo_action.triggered.connect(lambda: self.lyrics_source_changed(self.kuwo_action))
        self.right_button_menu.addAction(self.kuwo_action)

    def lyrics_source_changed(self, action: QtGui.QAction):
        # self.lyrics_source = action.objectName()
        if not self.setting_status:
            main_window.media.lyrics_source = action.objectName()
            main_window.playlist.playlist[main_window.playlist.index].lyrics_source = action.objectName()
            executor.submit(lambda: main_window.get_music_info(main_window.media, load_cover=False))
            for i in (self.local_action, self.netease_action, self.kugou_action, self.kuwo_action):
                i.setChecked(False)
            action.setChecked(True)

    def set_button_status(self, source: str):
        for i in (self.local_action, self.netease_action, self.kugou_action, self.kuwo_action):
            i.setChecked(False)
        if source == 'local':
            self.local_action.setChecked(True)
        elif source == 'netease':
            self.netease_action.setChecked(True)
        elif source == 'kugou':
            self.kugou_action.setChecked(True)
        elif source == 'kuwo':
            self.kuwo_action.setChecked(True)

    def lyrics_scrolling(self):
        self.lyrics_time += 1
        if self.lyrics_time >= 30:
            self.lyrics_scrolling_timer.stop()
            self.lyrics_time = 0
            main_window.lyrics_scrolling = True

    def wheelEvent(self, event: QtGui.QWheelEvent):
        self.lyrics_scrolling_timer.start()
        self.lyrics_time = 0
        main_window.lyrics_scrolling = False
        super().wheelEvent(event)

    def keyPressEvent(self, event: QtGui.QKeyEvent):
        self.lyrics_scrolling_timer.start()
        self.lyrics_time = 0
        main_window.lyrics_scrolling = False
        event.ignore()

    def contextMenuEvent(self, event: QtGui.QContextMenuEvent):
        self.local_action.setEnabled(False)
        if main_window.media.lyrics:
            self.local_action.setEnabled(True)
        self.setting_status = True
        self.set_button_status(main_window.media.lyrics_source)
        self.setting_status = False
        self.right_button_menu.exec(event.globalPos())


class MainWindow(QtWidgets.QMainWindow):
    run_function = QtCore.Signal(object)
    def __init__(self):
        super().__init__()
        self.status_info: dict[str, list|str|dict[str,list]] = eval(open(status_cache_path, "r", encoding="utf-8").read())
        self.edge = None
        self.position = self.status_info["position"]
        self.renew_position_times = 0
        self.last_row = -1
        self.music_info = dict()
        self.media: Media = None
        self.lyrics_tuple = None
        self.cursor_shape = None
        self.first_show = True
        self.lyrics_scrolling = True
        self.MouseLeftButtonPress = False
        self.MouseLeftButtonPressPos = None
        self.min_scaled_size = 0
        self._min_scaled_size = 0
        self.resource = Resource()
        self.no_song_cover_pixmap = QtGui.QPixmap(self.resource.no_song_cover)
        self.setWindowTitle('本地音乐播放器')
        self.setWindowFlags(QtCore.Qt.WindowType.Window | QtCore.Qt.WindowType.WindowMinimizeButtonHint | QtCore.Qt.WindowType.WindowMaximizeButtonHint | QtCore.Qt.WindowType.FramelessWindowHint | QtCore.Qt.WindowType.WindowMinMaxButtonsHint)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        self.player = MyMediaPlayer(self)
        self.audio_output = QtMultimedia.QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.playlist = PlayList(self.player, self.status_info["index"], self.status_info["play_mode"], self.status_info["files"])
        self.lyrics_time = []
        self.last_lyrics_label: QtWidgets.QLabel = None
        self.last_MediaFrame: MediaFrame = None
        self.renew_data_time = QtCore.QTimer()
        self.renew_data_time.setInterval(16)
        self.renew_data_time.timeout.connect(self.renew_data)
        self.setMouseTracking(True)
        self.main_widget = QtWidgets.QWidget()
        self.main_widget.setMouseTracking(True)
        self.main_layout = QtWidgets.QGridLayout()
        for i in zip(range(5), (0, 15, 15, 0, 5)):
            self.main_layout.setRowStretch(i[0], i[1])
        self.window_info_layout = QtWidgets.QHBoxLayout()
        self.window_title_label = QtWidgets.QLabel('本地音乐播放器')
        font = QtGui.QFont('微软雅黑', 10)
        font.setBold(True)
        self.window_title_label.setFont(font)
        self.window_info_layout.addWidget(self.window_title_label)
        self.main_layout.addLayout(self.window_info_layout, 0, 0, 1, 2, QtCore.Qt.AlignmentFlag.AlignLeft)
        self.window_function_layout = QtWidgets.QHBoxLayout()
        self.min_window_button = MyPushButton()
        self.min_window_button.setIconSize(QtCore.QSize(20, 20))
        self.min_window_button.setIcon(self.resource.window_minimize)
        self.window_function_layout.addWidget(self.min_window_button)
        self.max_window_button = MyPushButton()
        self.max_window_button.setIconSize(QtCore.QSize(20, 20))
        self.max_window_button.setIcon(self.resource.window_maximize)
        self.window_function_layout.addWidget(self.max_window_button)
        self.close_window_button = MyPushButton()
        self.close_window_button.setIconSize(QtCore.QSize(20, 20))
        self.close_window_button.setIcon(self.resource.window_close)
        self.window_function_layout.addWidget(self.close_window_button)
        self.main_layout.addLayout(self.window_function_layout, 0, 2, 1, 1, QtCore.Qt.AlignmentFlag.AlignRight)
        self.song_cover_label = SongCoverLabel(self)
        self.song_cover_label.raise_()
        self.song_cover_label_ = MyLabel(self)
        self.song_cover_label_.lower()
        self.main_layout.addWidget(self.song_cover_label_, 1, 0, 2, 1)
        self.lyrics_area = LyricsScrollArea()
        self.lyrics_area.setWidgetResizable(True)
        self.lyrics_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.lyrics_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.lyrics_widget = QtWidgets.QWidget()
        self.lyrics_widget.setMouseTracking(True)
        self.lyrics_layout = QtWidgets.QVBoxLayout()
        self.lyrics_widget.setLayout(self.lyrics_layout)
        self.lyrics_area.setWidget(self.lyrics_widget)
        self.main_layout.addWidget(self.lyrics_area, 1, 1, 2, 2)
        self.play_progress_layout = QtWidgets.QHBoxLayout()
        self.play_time_label = QtWidgets.QLabel('00:00:00')
        self.play_progress_layout.addWidget(self.play_time_label)
        self.play_progress = MySlider()
        self.play_progress.setOrientation(QtCore.Qt.Orientation.Horizontal)
        self.play_progress_layout.addWidget(self.play_progress)
        self.remain_time_label = QtWidgets.QLabel('00:00:00')
        self.play_progress_layout.addWidget(self.remain_time_label)
        self.main_layout.addLayout(self.play_progress_layout, 3, 0, 1, 3)
        self.song_info_layout = QtWidgets.QVBoxLayout()
        self.song_title_label = MarqueeLabel('歌曲标题')
        font = QtGui.QFont('微软雅黑', 14)
        self.song_title_label.setFont(font)
        self.song_info_layout.addWidget(self.song_title_label)
        self.song_artist_label = MarqueeLabel('歌手名称')
        font.setPointSize(12)
        self.song_artist_label.setFont(font)
        self.song_info_layout.addWidget(self.song_artist_label)
        self.main_layout.addLayout(self.song_info_layout, 4, 0, 1, 1, QtCore.Qt.AlignmentFlag.AlignLeft)
        self.control_layout = QtWidgets.QHBoxLayout()
        self.prev_button = MyPushButton()
        self.prev_button.setIconSize(QtCore.QSize(50, 50))
        self.prev_button.setIcon(self.resource.skip_previous_circle_outline)
        self.control_layout.addWidget(self.prev_button)
        self.play_button = MyPushButton()
        self.play_button.setIconSize(QtCore.QSize(50, 50))
        self.play_button.setIcon(self.resource.play_circle_outline)
        self.control_layout.addWidget(self.play_button)
        self.next_button = MyPushButton()
        self.next_button.setIconSize(QtCore.QSize(50, 50))
        self.next_button.setIcon(self.resource.skip_next_circle_outline)
        self.control_layout.addWidget(self.next_button)
        self.main_layout.addLayout(self.control_layout, 4, 1, 1, 1, QtCore.Qt.AlignmentFlag.AlignCenter)
        self.function_layout = QtWidgets.QHBoxLayout()
        self.play_mode_button = MyPushButton()
        self.play_mode_button.setIconSize(QtCore.QSize(30, 30))
        # self.play_mode_button.setIcon(self.resource.repeat)
        self.function_layout.addWidget(self.play_mode_button)
        self.volume_button = MyPushButton()
        self.volume_button.setIconSize(QtCore.QSize(30, 30))
        self.volume_button.setIcon(self.resource.volume_medium)
        self.function_layout.addWidget(self.volume_button)
        self.play_list_button = MyPushButton()
        self.play_list_button.setIconSize(QtCore.QSize(30, 30))
        self.play_list_button.setIcon(self.resource.playlist_music_outline)
        self.function_layout.addWidget(self.play_list_button)
        self.main_layout.addLayout(self.function_layout, 4, 2, 1, 1, QtCore.Qt.AlignmentFlag.AlignRight)
        self.main_widget.setLayout(self.main_layout)
        self.setCentralWidget(self.main_widget)
        self.volume_widget = MySlider()
        self.volume_widget.setParent(self)
        self.volume_widget.raise_()
        self.volume_widget.setOrientation(QtCore.Qt.Orientation.Vertical)
        self.volume_widget.setMinimum(0)
        self.volume_widget.setMaximum(100)
        self.volume_widget.setMaximumWidth(self.volume_widget.sizeHint().width())
        self.volume_widget.setValue(self.status_info['volume'])
        # self.volume_widget.valueChanged.connect(lambda value: (self.audio_output.setVolume(value / 100), self.volume_button.setIcon(self.resource.volume_high if value > 60 else self.resource.volume_medium if value > 30 else self.resource.volume_low)))
        self.volume_widget.hide()
        self.volume_animation_pos = QtCore.QPropertyAnimation(self.volume_widget, b'pos')
        self.volume_animation_pos.setDuration(300)
        self.volume_animation_size = QtCore.QPropertyAnimation(self.volume_widget, b'size')
        self.volume_animation_size.setDuration(300)
        self.playlist_widget = MyPlaylist(self)
        self.playlist_widget.hide()
        self.playlist_animation_pos = QtCore.QPropertyAnimation(self.playlist_widget, b'pos')
        self.playlist_animation_pos.setDuration(300)
        self.playlist_animation_size = QtCore.QPropertyAnimation(self.playlist_widget, b'size')
        self.playlist_animation_size.setDuration(300)
        self.scroll_bar_animation_value = QtCore.QPropertyAnimation(self.lyrics_area.verticalScrollBar(), b'value')
        self.scroll_bar_animation_value.setDuration(300)
        self.run_function.connect(lambda function: function())
        self.prev_button.clicked.connect(self.playlist.previous)
        self.play_button.clicked.connect(self.playlist.play_button_clicked)
        self.next_button.clicked.connect(self.playlist.next)
        self.play_mode_button.clicked.connect(self.play_mode_button_clicked)
        self.volume_button.clicked.connect(self.volume_button_clicked)
        self.play_list_button.clicked.connect(self.play_list_button_clicked)
        self.min_window_button.clicked.connect(self.showMinimized)
        self.max_window_button.clicked.connect(self.max_window_button_clicked)
        self.close_window_button.clicked.connect(lambda: (self.close, app.quit()))
        self.audio_output.volumeChanged.connect(self.volume_changed)
        self.player.mediaStatusChanged.connect(self.media_status_changed)
        self.player.playingChanged.connect(self.play_status_changed)
        self.player.durationChanged.connect(lambda duration: ((self.play_progress.setMaximum(duration), self.remain_time_label.setText(QtCore.QTime(0, 0, 0).addSecs(duration // 1000).toString('hh:mm:ss'))) if duration else None))
        self.player.sourceChanged.connect(self.play_source_changed)
        self.min_window_button.setToolTip('最小化')
        self.max_window_button.setToolTip('最大化')
        self.close_window_button.setToolTip('关闭')
        self.prev_button.setToolTip('上一首')
        self.play_button.setToolTip('播放/暂停')
        self.next_button.setToolTip('下一首')
        # self.play_mode_button.setToolTip('循环播放')
        if not self.playlist.play_mode:
            self.play_mode_button.setIcon(self.resource.repeat)
            self.play_mode_button.setToolTip('循环播放')
        elif self.playlist.play_mode == 1:
            self.play_mode_button.setIcon(self.resource.random)
            self.play_mode_button.setToolTip('随机播放')
        elif self.playlist.play_mode == 2:
            self.play_mode_button.setIcon(self.resource.repeat_once)
            self.play_mode_button.setToolTip('单曲循环')
        self.audio_output.setVolume(self.status_info["volume"]/100)
        self.volume_button.setToolTip(f'音量:{int(self.audio_output.volume() * 100):.0f}')
        self.play_list_button.setToolTip('播放列表')
        self.adjustSize()
        self.load_lyrics(((0, '歌曲歌词'),))
        if len(sys.argv) == 2:
            if Path(sys.argv[1]).exists():
                QtCore.QTimer.singleShot(500, lambda: self.playlist.add_media_from_file(Path(sys.argv[1])))

    def renew_data(self):
        try:
            if self.position:
                self.player.setPosition(self.position)
                self.position = 0
            position = self.player.position()
            self.renew_position_times += 1
            if self.renew_position_times >= 15:
                self.renew_position_times = 0
                self.status_info = write_status("position", position)
            self.play_progress.setValue(position)
            self.play_time_label.setText(QtCore.QTime(0, 0, 0).addSecs(position // 1000).toString('hh:mm:ss'))
            self.remain_time_label.setText(QtCore.QTime(0, 0, 0).addSecs((self.play_progress.maximum() - position) // 1000).toString('hh:mm:ss'))
            row = len(tuple(i for i in self.lyrics_time if i <= position)) - 1
            if -1 < row:
                if row != self.last_row:
                    self.last_row = row
                    try:
                        font = self.last_lyrics_label.font()
                        font.setBold(False)
                        font.setPointSize(12)
                        self.last_lyrics_label.setFont(font)
                    except:
                        pass
                    self.last_lyrics_label = self.lyrics_layout.itemAt(row).widget()
                    font = self.last_lyrics_label.font()
                    font.setBold(True)
                    font.setPointSize(14)
                    self.last_lyrics_label.setFont(font)
                if self.lyrics_scrolling and self.last_lyrics_label:
                    try:
                        frame_geometry = self.last_lyrics_label.frameGeometry()
                        value = (frame_geometry.top() + frame_geometry.height() / 2) - self.lyrics_area.viewport().height() / 2
                        if self.renew_data_time.isActive():
                            if not self.scroll_bar_animation_value.endValue() or abs(value - self.scroll_bar_animation_value.endValue()) > 0.5:
                                self.lyrics_scrolling_animation(value)
                        else:
                            self.lyrics_area.verticalScrollBar().setValue(value)
                    except:
                        pass
        except Exception as e:
            with open(status_cache_path, 'w', encoding='utf-8') as file:
                json.dump(self.status_info, file, ensure_ascii=False, indent=4)
            print(e)
            self.close()

    def lyrics_scrolling_animation(self, value):
        if self.scroll_bar_animation_value.state() == QtCore.QAbstractAnimation.State.Running:
            self.scroll_bar_animation_value.stop()
        self.scroll_bar_animation_value.setStartValue(self.lyrics_area.verticalScrollBar().value())
        self.scroll_bar_animation_value.setEndValue(value)
        self.scroll_bar_animation_value.start()

    def load_lyrics(self, lyrics: str| tuple[tuple[int, str],...]):
        self.last_row = -1
        self.last_lyrics_label = None
        self.lyrics_area.verticalScrollBar().setValue(0)
        while self.lyrics_layout.count():
            self.lyrics_layout.takeAt(0).widget().deleteLater()
        if isinstance(lyrics, str):
            time_compile = re.compile(r'\[(\d*:?\d+:\d+\.*\d*)] *')
            self.lyrics_tuple = tuple(sorted(((QtCore.QTime(0, 0, 0).msecsTo(QtCore.QTime.fromString(time_compile.findall(i)[0], 'mm:ss.zz')), time_compile.sub('', i)) for i in lyrics.split('\n') if i), key=lambda x: x[0]))
        elif isinstance(lyrics, tuple):
            self.lyrics_tuple = lyrics
        self.lyrics_time.clear()
        font = QtGui.QFont('微软雅黑', 12)
        for i in self.lyrics_tuple:
            self.lyrics_time.append(i[0])
            label = QtWidgets.QLabel(i[1])
            label.setWordWrap(True)
            label.setMouseTracking(True)
            label.setFont(font)
            label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            self.lyrics_layout.addWidget(label)

    def play_mode_changed(self):
        write_status("play_mode", self.playlist.play_mode)
        if not self.playlist.play_mode:
            self.play_mode_button.setIcon(self.resource.repeat)
            self.play_mode_button.setToolTip('循环播放')
        elif self.playlist.play_mode == 1:
            self.play_mode_button.setIcon(self.resource.random)
            self.play_mode_button.setToolTip('随机播放')
            self.playlist.playlist_random = self.playlist.playlist.copy()
            random.shuffle(self.playlist.playlist_random)
            write_status('files', ['playlist_random'] + [str(i.path) for i in self.playlist.playlist_random])
            if self.playlist.playlist_random:
                self.playlist.index = self.playlist.playlist_random.index(self.media)
            playlist_widget = tuple(self.playlist_widget.playlist_layout.itemAt(i) for i in range(self.playlist_widget.playlist_layout.count()))
            for i in self.playlist.playlist_random:
                self.playlist_widget.playlist_layout.addWidget(playlist_widget[self.playlist.playlist.index(i)].widget())
            self.playlist_widget.move(self.geometry().bottomLeft() + QtCore.QPoint(0, -self.playlist_widget.height()))
            self.playlist_widget.isNormalShow = False
            self.playlist_widget.show()
            self.playlist_widget.isNormalShow = True
            self.playlist_widget.hide()
            try:
                media_frame: MediaFrame = self.playlist_widget.playlist_layout.itemAt(self.playlist.index).widget()
                self.playlist_widget.SetScrollBarValue(media_frame.frameGeometry().top())
            except:
                pass
        elif self.playlist.play_mode == 2:
            self.play_mode_button.setIcon(self.resource.repeat_once)
            self.play_mode_button.setToolTip('单曲循环')
            if self.playlist.playlist:
                self.playlist.index = self.playlist.playlist.index(self.media)
            playlist_widget = tuple(self.playlist_widget.playlist_layout.itemAt(i) for i in range(self.playlist_widget.playlist_layout.count()))
            for i in self.playlist.playlist:
                self.playlist_widget.playlist_layout.addWidget(playlist_widget[self.playlist.playlist_random.index(i)].widget())
            self.playlist_widget.move(self.geometry().bottomLeft() + QtCore.QPoint(0, -self.playlist_widget.height()))
            self.playlist_widget.isNormalShow = False
            self.playlist_widget.show()
            self.playlist_widget.isNormalShow = True
            self.playlist_widget.hide()
            try:
                media_frame: MediaFrame = self.playlist_widget.playlist_layout.itemAt(self.playlist.index).widget()
                self.playlist_widget.SetScrollBarValue(media_frame.frameGeometry().top())
            except:
                pass

    def play_mode_button_clicked(self):
        self.playlist.play_mode += 1
        if self.playlist.play_mode == 3:
            self.playlist.play_mode = 0
        self.play_mode_changed()

    def get_music_info(self, media: Media, load_cover=True, load_lyrics=True, load_playlist_cover=False):
        if load_lyrics:
            executor.submit(self.load_lyrics_thread, media)
        if load_cover:
            executor.submit(self.load_cover_thread, media)
        cover_path = cover_cache_path.joinpath(media.cover_source, f'{media.hash_md5}.cover')
        lyrics_path = lyrics_cache_path.joinpath(media.lyrics_source, f'{media.hash_md5}.lyric')
        # if not cover_path.exists() or (load_cover and (not cover_path.exists() or cover_path.stat().st_size == 0)) or (load_lyrics and (((not lyrics_path.exists()) and self.media.lyrics_source != 'local') or (False if self.media.lyrics_source == 'local' else (lyrics_path.stat().st_size == 0)))):
        if (load_playlist_cover and not cover_path.exists()) or (load_cover and (not cover_path.exists() or cover_path.stat().st_size == 0)) or (load_lyrics and (((not lyrics_path.exists()) and media.lyrics_source != 'local') or (False if media.lyrics_source == 'local' else (lyrics_path.stat().st_size == 0)))):
            for i in ('netease', 'kugou', 'kuwo'):
                cover_cache_path.joinpath(i).mkdir(exist_ok=True, parents=True)
                lyrics_cache_path.joinpath(i).mkdir(exist_ok=True, parents=True)
            if media.hash_md5 in self.music_info and time.perf_counter() - self.music_info[media.hash_md5][1] < 300:
                while self.music_info[media.hash_md5][0] is None:
                    time.sleep(0.1)
                music_info = self.music_info[media.hash_md5][0]
            else:
                try:
                    self.music_info.update({media.hash_md5: (None, time.perf_counter())})
                    music_info = get_music_info(media)
                    self.music_info.update({media.hash_md5: (music_info, time.perf_counter())})
                except Exception as e:
                    print(e)
                    return
            cover_music_info = music_info[('netease', 'kugou', 'kuwo').index(media.cover_source)]
            if media.lyrics_source == 'local':
                lyrics_music_info = None
            else:
                lyrics_music_info = music_info[('netease', 'kugou', 'kuwo').index(media.lyrics_source)]
            if (not cover_path.exists() or cover_path.stat().st_size == 0) and (load_cover or load_playlist_cover):
                cover = cover_music_info['self'].get_cover(cover_music_info['pic'])
                with open(cover_path, 'wb') as f:
                    f.write(cover)
                    f.flush()
            if (not lyrics_path.exists() or lyrics_path.stat().st_size == 0) and lyrics_music_info and load_lyrics:
                lyrics = lyrics_music_info['self'].get_lyrics(lyrics_music_info['id'])
                with open(lyrics_path, 'w', encoding='utf-8') as f:
                    f.write(str(lyrics))
                    f.flush()
        if load_playlist_cover:
            executor.submit(lambda: self.load_playlist_cover_thread(media))
            # threading.Thread(target=lambda: self.load_playlist_cover_thread(media), daemon=True).start()

    def load_lyrics_thread(self, media: Media):
        def function():
            while self.lyrics_layout.count():
                self.lyrics_layout.takeAt(0).widget().deleteLater()
            self.lyrics_time.clear()
            self.lyrics_time.append(0)
            label = QtWidgets.QLabel('正在获取歌词...')
            label.setWordWrap(True)
            label.setFont(QtGui.QFont('微软雅黑', 12))
            label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            self.lyrics_layout.addWidget(label)

        if self.media.lyrics_source == 'local':
            self.run_function.emit(lambda: self.load_lyrics(self.media.lyrics))
            return
        lyrics_path = lyrics_cache_path.joinpath(self.media.lyrics_source, f'{media.hash_md5}.lyric')
        self.run_function.emit(function)
        lyrics = None
        num = 0
        while not lyrics_path.exists():
            if num > 30:
                lyrics = ((0, '未获取到歌词'),)
                break
            if self.media.hash_md5 != media.hash_md5:
                return
            num += 1
            time.sleep(0.1)
        if lyrics is None:
            with open(lyrics_path, 'r', encoding='utf-8') as f:
                lyrics = eval(f.read())
            if not lyrics:
                lyrics = ((0, '纯音乐,请欣赏'),)
        self.run_function.emit(lambda: self.load_lyrics(lyrics))

    def load_cover_thread(self, media: Media):
        def function():
            geometry = self.song_cover_label_.geometry()
            self.song_cover_label.setPixmapSize(geometry)

        self.song_cover_label.song_cover_pixmap = self.no_song_cover_pixmap
        self.run_function.emit(function)
        cover_path = cover_cache_path.joinpath(self.media.cover_source, f'{media.hash_md5}.cover')
        num = 0
        while not cover_path.exists():
            if self.media.hash_md5 != media.hash_md5 or num > 50:
                return
            num += 1
            time.sleep(0.1)
        cover = QtGui.QPixmap(cover_path)
        self.song_cover_label.song_cover_pixmap = cover
        self.run_function.emit(function)

    def load_playlist_cover_thread(self, media: Media):
        def function():
            media_frame: MediaFrame = self.playlist_widget.playlist_layout.itemAt((self.playlist.playlist_random.index if self.playlist.play_mode == 1 else self.playlist.playlist.index)(media)).widget()
            media_frame.setPixmap(QtGui.QPixmap(cover_path))

        cover_path = cover_cache_path.joinpath(media.cover_source, f'{media.hash_md5}.cover')
        num = 0
        while not cover_path.exists():
            if num > 30:
                print(f'<{media.path.stem}>未获取到封面,{cover_path}')
                return
            num += 1
            time.sleep(0.1)
        self.run_function.emit(function)

    def None_play(self):
        self.player.stop()
        self.song_cover_label.song_cover_pixmap = self.no_song_cover_pixmap
        self.song_cover_label.setPixmapSize(self.song_cover_label_.geometry())
        while self.lyrics_layout.count():
            self.lyrics_layout.takeAt(0).widget().deleteLater()
        self.lyrics_time.clear()
        self.load_lyrics(((0, '歌曲歌词'),))
        self.play_progress.setValue(0)
        self.play_progress.setMaximum(0)
        self.play_time_label.setText('00:00:00')
        self.remain_time_label.setText('00:00:00')
        self.song_title_label.setText('歌曲标题')
        self.song_title_label.x = 0
        self.song_artist_label.setText('歌手名称')
        self.song_artist_label.x = 0
        self.player.setSource(QtCore.QUrl())

    def play_source_changed(self):
        if not self.player.source().path():
            return
        try:
            media_frame: MediaFrame = self.playlist_widget.playlist_layout.itemAt(self.playlist.index).widget()
            self.playlist_widget.SetScrollBarValue(media_frame.frameGeometry().top())
        except:
            pass
        self.lyrics_area.set_button_status(self.media.lyrics_source)
        self.play_progress.setValue(0)
        self.play_time_label.setText('00:00:00')
        self.song_title_label.setText(self.media.title)
        self.song_title_label.x = 0
        self.song_artist_label.setText(self.media.artist)
        self.song_artist_label.x = 0
        try:
            if self.last_MediaFrame:
                self.last_MediaFrame.isPlaying = False
                self.last_MediaFrame.setStyleSheet('')
                self.last_MediaFrame.main_layout.setContentsMargins(2, 2, 2, 2)
        except:
            pass
        try:
            media_frame: MediaFrame = self.playlist_widget.playlist_layout.itemAt((self.playlist.playlist_random.index if self.playlist.play_mode == 1 else self.playlist.playlist.index)(self.media)).widget()
            self.last_MediaFrame = media_frame
            media_frame.isPlaying = True
            media_frame.setStyleSheet('QFrame#MediaFrame{border-radius: 4px;border: 2px solid #55aa00;}')
            media_frame.main_layout.setContentsMargins(0, 0, 0, 0)
            executor.submit(self.get_music_info, self.media, load_playlist_cover=media_frame.isNoSongCover)
        except:
            executor.submit(self.get_music_info, self.media)

    def media_status_changed(self, status: QtMultimedia.QMediaPlayer.MediaStatus):
        if status == QtMultimedia.QMediaPlayer.MediaStatus.EndOfMedia:
            if self.playlist.play_mode == 2:
                self.playlist.play()
            else:
                self.playlist.next()

    def play_status_changed(self, status: bool):
        if status:
            self.renew_data_time.start()
            self.song_title_label.timer_id = self.song_title_label.startTimer(20)
            self.song_artist_label.timer_id = self.song_artist_label.startTimer(20)
            self.play_button.setIcon(self.resource.pause_circle_outline)
        else:
            self.renew_data_time.stop()
            self.song_title_label.killTimer(self.song_title_label.timer_id)
            self.song_artist_label.killTimer(self.song_artist_label.timer_id)
            self.play_button.setIcon(self.resource.play_circle_outline)

    def volume_changed(self, value: float):
        self.volume_button.setToolTip(f'音量:{value * 100:.0f}')
        write_status('volume', int(value*100))
        if value > 0.59:
            self.volume_button.setIcon(self.resource.volume_high)
        elif value > 0.29:
            self.volume_button.setIcon(self.resource.volume_medium)
        elif value >= 0.01:
            self.volume_button.setIcon(self.resource.volume_low)
        else:
            QtCore.QTimer.singleShot(50, lambda: (self.volume_button.setIcon(self.resource.volume_off)))

    def max_window_button_clicked(self):
        if self.isMaximized():
            self.showNormal()
            self.max_window_button.setIcon(self.resource.window_maximize)
        else:
            self.showMaximized()
            self.max_window_button.setIcon(self.resource.window_restore)

    def volume_button_clicked(self):
        self.volume_button.setEnabled(False)
        self.play_list_button.setEnabled(False)
        if self.volume_widget.isHidden():
            self.volume_animation_pos.setDirection(QtCore.QAbstractAnimation.Direction.Forward)
            self.volume_animation_size.setDirection(QtCore.QAbstractAnimation.Direction.Forward)
            pos = self.volume_button.mapToGlobal(QtCore.QPoint(0, 0)) - self.mapToGlobal(QtCore.QPoint(0, 0))
            pos.setX(pos.x() + (self.volume_button.width() - self.volume_widget.width()) // 2)
            self.volume_animation_pos.setStartValue(pos)
            self.volume_animation_size.setStartValue(QtCore.QSize(self.volume_widget.width(), 0))
            self.volume_animation_pos.setEndValue(QtCore.QPoint(pos.x(), pos.y() - self.volume_widget.maximumHeight()))
            self.volume_animation_size.setEndValue(QtCore.QSize(self.volume_widget.width(), self.volume_widget.maximumHeight()))
            self.volume_animation_size.start()
            self.volume_widget.show()
            self.volume_animation_pos.start()
            QtCore.QTimer.singleShot(self.volume_animation_pos.duration(), lambda: self.volume_widget.setFocus())
        else:
            self.setFocus()
            self.volume_animation_pos.setDirection(QtCore.QAbstractAnimation.Direction.Backward)
            self.volume_animation_size.setDirection(QtCore.QAbstractAnimation.Direction.Backward)
            self.volume_animation_pos.start()
            self.volume_animation_size.start()
            QtCore.QTimer.singleShot(self.volume_animation_pos.duration(), self.volume_widget.hide)
        QtCore.QTimer.singleShot(self.volume_animation_pos.duration(), lambda: (self.volume_button.setEnabled(True), self.play_list_button.setEnabled(True)))

    def play_list_button_clicked(self):
        self.play_list_button.setEnabled(False)
        self.volume_button.setEnabled(False)
        if self.playlist_widget.isHidden():
            self.playlist_animation_pos.setDirection(QtCore.QAbstractAnimation.Direction.Forward)
            self.playlist_animation_size.setDirection(QtCore.QAbstractAnimation.Direction.Forward)
            pos = self.play_list_button.mapToGlobal(QtCore.QPoint(0, 0)) - self.mapToGlobal(QtCore.QPoint(0, 0))
            pos.setX(pos.x() + self.play_list_button.width() - self.playlist_widget.width())
            self.playlist_animation_pos.setStartValue(pos)
            self.playlist_animation_size.setStartValue(QtCore.QSize(self.playlist_widget.width(), 0))
            self.playlist_animation_pos.setEndValue(QtCore.QPoint(pos.x(), pos.y() - self.playlist_widget.maximumHeight()))
            self.playlist_animation_size.setEndValue(QtCore.QSize(self.playlist_widget.width(), self.playlist_widget.maximumHeight()))
            self.playlist_animation_size.start()
            self.playlist_widget.show()
            self.playlist_animation_pos.start()
            QtCore.QTimer.singleShot(self.playlist_animation_pos.duration(), lambda: self.playlist_widget.setFocus())
        else:
            self.setFocus()
            self.playlist_animation_pos.setDirection(QtCore.QAbstractAnimation.Direction.Backward)
            self.playlist_animation_size.setDirection(QtCore.QAbstractAnimation.Direction.Backward)
            self.playlist_animation_pos.start()
            self.playlist_animation_size.start()
            QtCore.QTimer.singleShot(self.playlist_animation_pos.duration(), self.playlist_widget.hide)
        QtCore.QTimer.singleShot(self.playlist_animation_pos.duration(), lambda: (self.play_list_button.setEnabled(True), self.volume_button.setEnabled(True)))

    def is_on_edge(self, event):
        margin = 10
        rect = self.rect()
        pos = event.position()
        if pos.x() < margin and pos.y() < margin:
            self.edge = QtCore.Qt.Edge.LeftEdge | QtCore.Qt.Edge.TopEdge
            self.cursor_shape = QtCore.Qt.CursorShape.SizeFDiagCursor
            return True
        elif pos.x() > rect.width() - margin and pos.y() > rect.height() - margin:
            self.edge = QtCore.Qt.Edge.RightEdge | QtCore.Qt.Edge.BottomEdge
            self.cursor_shape = QtCore.Qt.CursorShape.SizeFDiagCursor
            return True
        elif pos.x() < margin and pos.y() > rect.height() - margin:
            self.edge = QtCore.Qt.Edge.LeftEdge | QtCore.Qt.Edge.BottomEdge
            self.cursor_shape = QtCore.Qt.CursorShape.SizeBDiagCursor
            return True
        elif pos.x() > rect.width() - margin and pos.y() < margin:
            self.edge = QtCore.Qt.Edge.RightEdge | QtCore.Qt.Edge.TopEdge
            self.cursor_shape = QtCore.Qt.CursorShape.SizeBDiagCursor
            return True
        elif pos.x() < margin:
            self.edge = QtCore.Qt.Edge.LeftEdge
            self.cursor_shape = QtCore.Qt.CursorShape.SizeHorCursor
            return True
        elif pos.x() > rect.width() - margin:
            self.edge = QtCore.Qt.Edge.RightEdge
            self.cursor_shape = QtCore.Qt.CursorShape.SizeHorCursor
            return True
        elif pos.y() < margin:
            self.edge = QtCore.Qt.Edge.TopEdge
            self.cursor_shape = QtCore.Qt.CursorShape.SizeVerCursor
            return True
        elif pos.y() > rect.height() - margin:
            self.edge = QtCore.Qt.Edge.BottomEdge
            self.cursor_shape = QtCore.Qt.CursorShape.SizeVerCursor
            return True
        return False

    def mousePressEvent(self, event):
        self.main_widget.setFocus()
        if event.button() == QtCore.Qt.MouseButton.RightButton:
            self.MouseLeftButtonPress = False
        if event.button() == QtCore.Qt.MouseButton.LeftButton and not self.isFullScreen():
            if self.is_on_edge(event):
                self.renew_data_time.stop()
                self.song_title_label.killTimer(self.song_title_label.timer_id)
                self.song_artist_label.killTimer(self.song_artist_label.timer_id)
                self.windowHandle().startSystemResize(self.edge)
            else:
                self.MouseLeftButtonPress = True
                self.MouseLeftButtonPressPos = event.globalPosition() - self.mapToGlobal(QtCore.QPoint(0, 0))
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not self.isMaximized():
            if self.is_on_edge(event):
                self.setCursor(self.cursor_shape)
            else:
                self.setCursor(QtCore.Qt.CursorShape.ArrowCursor)
            if self.MouseLeftButtonPress:
                position = (event.globalPosition() - self.MouseLeftButtonPressPos).toPoint()
                if position.x() < 0:
                    position.setX(0)
                if position.y() < 0:
                    position.setY(0)
                if position.x() > self.screen().size().width() - self.width():
                    position.setX(self.screen().size().width() - self.width())
                if position.y() > self.screen().size().height() - self.height():
                    position.setY(self.screen().size().height() - self.height())
                self.move(position)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            if not self.isMaximized() and self.player.isPlaying() and not self.renew_data_time.isActive():
                self.renew_data_time.start()
                self.song_title_label.timer_id = self.song_title_label.startTimer(20)
                self.song_artist_label.timer_id = self.song_artist_label.startTimer(20)
            self.MouseLeftButtonPress = False
        super().mouseReleaseEvent(event)

    def resizeEvent(self, event: QtGui.QResizeEvent):
        size = event.size()
        x, y = size.width() // 3, size.height() // 3
        if not self.min_scaled_size:
            if self._min_scaled_size != x:
                self._min_scaled_size = x
            else:
                self.min_scaled_size = x
            geometry = self.song_cover_label_.geometry()
            self.song_cover_label_.setMinimumSize(x, x)
            self.song_cover_label.setPixmapSize(QtCore.QRect(geometry.x(), geometry.y(), x, x))
            self.song_title_label.setMinimumWidth(x)
            self.song_artist_label.setMinimumWidth(x)
            self.windowHandle().requestActivate()
        else:
            self.renew_data()
        self.playlist_widget.setFixedWidth(int(size.width() / 3.5 * 2))
        self.volume_widget.setMaximumHeight(y)
        self.playlist_widget.setMaximumHeight(y * 2)
        super().resizeEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        if self.isMaximized():
            painter.fillRect(self.rect(), painter.background())
        else:
            path = QtGui.QPainterPath()
            path.addRoundedRect(self.rect(), 15, 15)
            painter.fillPath(path, painter.background())

    def closeEvent(self, event):
        global close_thread
        super().closeEvent(event)
        close_thread = True
        print(all_executor_threads)
        for i in all_executor_threads:
            if i.running():
                pass
            else:
                i.cancel()
        print(all_executor_threads)
        print(threading.active_count())
        print(threading.enumerate())
        executor.shutdown(wait=False)
        app.quit()
        threading.Thread(target=force_exit, daemon=True).start()


__file__ = Path(sys.argv[0]).resolve()
data_exchange_queue = queue.Queue(maxsize=100)
cpu_count = psutil.cpu_count()
executor = ThreadPoolExecutor(max_workers=cpu_count//2)
playlist_executor = ThreadPoolExecutor(max_workers=(cpu_count//2 if cpu_count//2 > 4 else 4))  # 如果卡顿就用下边这个
# playlist_executor = ThreadPoolExecutor(max_workers=4)
all_executor_threads: list[futures.Future] = []
close_thread = False
cache_reading = False
status_cache_path = Path(__file__).parent.joinpath('status.cache')
write_status('normal')
media_info_cache_path = Path(__file__).parent.joinpath('media_info')
cover_cache_path = Path(__file__).parent.joinpath('cover')
lyrics_cache_path = Path(__file__).parent.joinpath('lyrics')
media_info_cache_path.mkdir(exist_ok=True, parents=True)
cover_cache_path.mkdir(exist_ok=True, parents=True)
lyrics_cache_path.mkdir(exist_ok=True, parents=True)
app = QtWidgets.QApplication(sys.argv)
app.setWindowIcon(Resource().music_app_icon)
app.setStyleSheet(open('style.txt', 'r', encoding='utf-8').read())
qInitResources()
translator = QtCore.QTranslator()
translator.load('qt_zh_CN.qm')
app.installTranslator(translator)
pixels_per_px = app.primaryScreen().devicePixelRatio() ** 2
main_window = MainWindow()
signal.signal(signal.SIGINT, signal_handler)
main_window.setWindowIcon(Resource().music_app_icon)
main_window.show()
threading.Thread(target=socket_server, daemon=True).start()
sys.exit(app.exec())
