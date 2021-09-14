import socket
import json
import hashlib
import configparser
import os
import subprocess
from conf import settings
import time
import shutil


class FTPServer:
    """处理客户端所有的交互"""

    STATUS_CODE = {
        1: '测试',
        200: 'Passed authentication!',
        201: 'Wrong username or password!',
        300: 'File does not exist!',
        301: 'File exist,and this msg include the file size!',
        302: 'This mag include msg size!',
        350: 'Dir changed!',
        351: "Dir doesn't exist",
        352: 'File is del!',
        353: 'Del file is false! ',
        355: 'Contents creat is ture!',
        356: 'Contents creat is false!',
    }
    MSG_SIZE = 1024  # 消息最长1024

    def __init__(self, management_instance):
        self.management_instance = management_instance
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind((settings.HOST, settings.PORT))
        self.sock.listen(settings.MAX_SOCKET_LISTEN)
        self.accounts = self.load_accounts()
        self.user_obj = None
        self.user_current_dir = None
        self.request = None
        self.addr = None

    def run_forever(self):
        """启动socket server"""
        print('FTP server starting on %s %s'.center(50) % (settings.HOST, settings.PORT))

        while True:
            self.request, self.addr = self.sock.accept()
            print('got a new connection from %s...' % (self.addr,))
            try:
                self.handle()
            except Exception as e:
                print('客户端发送错误，断开链接...', e)
                self.request.close()  # 清除实例

    def handle(self):
        """处理用户的所有指令交互"""
        while True:
            raw_data = self.request.recv(self.MSG_SIZE)
            print('------>', raw_data)
            if not raw_data:  # 判断消息是否为空
                print('connection %s is lost...' % (self.addr,))
                del self.request, self.addr
                break

            data = json.loads(raw_data.decode('utf-8'))
            action_type = data.get('action_type')
            if action_type:  # 指令合法检测
                if hasattr(self, '_%s' % action_type):  # 判断server有无指令
                    func = getattr(self, '_%s' % action_type)
                    func(data)

            else:
                print('不合法的指令')

    def load_accounts(self):
        """加载用户账户信息"""
        config_obj = configparser.ConfigParser()
        config_obj.read(settings.ACCOUNT_FILE)

        print(config_obj.sections())
        return config_obj

    def authenricate(self, username, password):
        """用户认证判断方法"""
        if username in self.accounts:
            _password = self.accounts[username]['password']
            md5_obj = hashlib.md5()
            md5_obj.update(password.encode())
            md5_password = md5_obj.hexdigest()
            print('password:', password, md5_password)
            if _password == md5_obj.hexdigest():
                # print('认证通过...')
                self.user_obj = self.accounts[username]
                self.user_obj['home'] = os.path.join(settings.USER_HOME_DIR, username)
                self.user_current_dir = self.user_obj['home']
                return True
            else:
                print('用户密码错误')
                return False
        else:
            print('用户名错误')
            return False

    def send_response(self, status_code, *args, **kwargs):
        """
        打包发送状态信息给客户端
        :param status_code:
        :param args:
        :param kwargs: {filename:ddd,filesize:22}
        :return:
        """
        data = kwargs
        data['status_code'] = status_code
        data['status_msg'] = self.STATUS_CODE[status_code]
        data['fill'] = ''
        bytes_data = json.dumps(data).encode()
        if len(bytes_data) < self.MSG_SIZE:
            data['fill'] = data['fill'].zfill(self.MSG_SIZE - len(bytes_data))
            bytes_data = json.dumps(data).encode()
        self.request.send(bytes_data)

    def _auth(self, data):
        """处理用户登录"""
        print('auth', data)
        if self.authenricate(data.get('username'), data.get('password')):
            print('pass auth...')

            # 1.消息内容   状态码
            # 2.json.dumps
            # 3.encode
            self.send_response(status_code=200)

        else:
            self.send_response(status_code=201)

    def _get(self, data):
        """下载文件"""
        filename = data.get('filename')
        full_path = os.path.join(self.user_obj['home'], filename)
        if os.path.isfile(full_path):
            filesize = os.stat(full_path).st_size
            self.send_response(301, file_size=filesize)
            print('ready to send file...')
            f = open(full_path, 'rb')
            for line in f:
                self.request.send(line)
            else:
                print('file send done...', full_path)
            f.close()
        else:
            self.send_response(300)

    def _ls(self, data):
        """dir"""
        cmd_obj = subprocess.Popen('dir %s' % self.user_current_dir, shell=True, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
        stdout = cmd_obj.stdout.read()
        stderr = cmd_obj.stderr.read()
        cmd_result = stdout + stderr
        if not cmd_result:
            cmd_result = 'this dir not file...'.encode('gbk')
        self.send_response(302, cmd_result_size=len(cmd_result))
        self.request.sendall(cmd_result)

    def _cd(self, data):
        """改变用户路径"""
        target_dir = data.get('target_dir')
        full_path = os.path.join(self.user_current_dir, target_dir)
        full_path = os.path.abspath(full_path)
        print(full_path)
        if os.path.isdir(full_path):  # 判断目录是否存在
            if full_path.startswith(self.user_obj['home']):  # 判断路径是否在用户家目录下
                self.user_current_dir = full_path
                relative_current_dir = self.user_current_dir.replace(self.user_obj['home'], '')
                self.send_response(350, current_dir=relative_current_dir)
            else:
                self.send_response(351)
        else:
            self.send_response(351)

    def _put(self, data):
        """上传文件
        1、拿到文件名和大小
        2、检测岑地是否有相应的文件
            有：新文件名为 文件名+时间
            没有：新文件名为文件名
        3、开始接受文件

        """
        local_file = data.get('filename')
        full_path = os.path.join(self.user_current_dir, local_file)
        if os.path.isfile(full_path):  # 文件已经存在
            filename = '%s.%s' % (full_path, time.strftime('%Y-%m-%d %H:%M', time.localtime()))
        else:
            filename = full_path
        f = open(filename, 'wb')
        total_size = data.get('file_size')
        received_size = 0
        while received_size < total_size:
            if total_size - received_size < 8192:
                data = self.request.recv(total_size - received_size)
            else:
                data = self.sock.recv(8192)
            received_size += len(data)
            f.write(data)
            print(received_size, total_size)
        else:
            print('file [%s] recv done' % local_file)
            f.close()

    def _del(self, data):
        filename = data.get('filename')
        full_path = os.path.join(self.user_current_dir, filename)
        print(full_path)
        if os.path.isfile(full_path):  # 如果删除的是文件
            os.remove(full_path)
            if os.path.isfile(full_path):
                self.send_response(353)
            else:
                self.send_response(352)
        elif os.path.isdir(full_path):  # 如果删除的是文件夹
            shutil.rmtree(full_path)
            if os.path.isdir(full_path):
                self.send_response(353)
            else:
                self.send_response(352)
        else:
            self.send_response(351)

    def _mkdir(self, data):
        filename = data.get('filename')
        full_path = os.path.join(self.user_current_dir, filename)
        print(full_path)
        if not os.path.isdir(full_path):  # 判断目录是否存在
            os.mkdir(full_path)
            if os.path.isdir(full_path):
                self.send_response(355)
            else:
                self.send_response(356)
        else:
            count = 0
            while True:
                count += 1
                path = '%s%s' % (full_path, count)
                if not os.path.isdir(path):
                    full_path = path
                    break
            os.mkdir(full_path)
            if os.path.isdir(full_path):
                self.send_response(355)
            else:
                self.send_response(356)
