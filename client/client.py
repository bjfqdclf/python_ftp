import optparse
import socket
import json
import os


class FTPClient:
    """FTP客户端"""
    MSG_SIZE = 1024

    def __init__(self):
        self.username = None
        self.terminal_display = None
        parser = optparse.OptionParser()
        parser.add_option("-S", "--server", dest="server", help='ftp server ip_addr')
        parser.add_option("-P", "--port", type="int", help='ftp server port')
        parser.add_option("-u", "--username", dest="username", help='username info')
        parser.add_option("-p", "--password", dest="password", help='password info')
        self.options, self.args = parser.parse_args()  # 有要求的放进options，未按要求的放进args
        print(self.options, self.args)
        self.argv_verification()

        self.make_connection()

    def argv_verification(self):
        """检查参数合法性"""
        if not self.options.server or not self.options.port:
            exit('Error:缺少 server 和 port')

    def make_connection(self):
        """建立连接"""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.options.server, self.options.port))

    def get_response(self):
        """获取服务器返回消息"""
        data = self.sock.recv(self.MSG_SIZE)
        return json.loads(data.decode())

    def auth(self):
        """用户认证"""
        # 基础环境认证
        count = 0
        while count < 3:
            username = input('username:').strip()
            if not username: continue
            password = input('password:').strip()
            cmd = {
                'action_type': 'auth',
                'username': username,
                'password': password
            }

            self.sock.send(json.dumps(cmd).encode('utf-8'))
            response = self.get_response()
            print('response:', response)
            if response.get('status_code') == 200:
                self.username = username
                self.terminal_display = '[<%s>]:' % self.username
                return True
            else:
                print(response.get('status_msg'))
            count += 1

    def intervactive(self):
        """处理FTP 的所有交互"""
        if self.auth():
            while True:
                user_input = input(self.terminal_display).strip()
                if not user_input: continue

                cmd_list = user_input.split()
                if hasattr(self, '_%s' % cmd_list[0]):
                    func = getattr(self, '_%s' % cmd_list[0])
                    func(cmd_list[1:])
                    # get file -md5

    def parameter_check(self, args, min_args=None, max_args=None, exact_args=None):
        """
        参数个数合法性检查
        :param args: 参数
        :param min_args:最小参数个数
        :param max_args: 最大参数个数
        :param exact_args: 固定参数个数
        :return: bool
        """
        if min_args:
            if len(args) < min_args:
                print('最少提供%s个参数  但是收到了%s个参数' % (min_args, len(args)))
                return False
        if max_args:
            if len(args) > max_args:
                print('最多提供%s个参数  但是收到了%s个参数' % (max_args, len(args)))
                return False
        if exact_args:
            if len(args) != exact_args:
                print('需要提供%s个参数  但是收到了%s个参数' % (exact_args, len(args)))
                return False
        return True

    def send_msg(self, action_type, **kwargs):
        """打包消息，并发送到远程"""
        msg_data = {
            'action_type': action_type,
            'fill': ''
        }
        msg_data.update(kwargs)
        bytes_msg = json.dumps(msg_data).encode()
        if self.MSG_SIZE > len(bytes_msg):
            msg_data['fill'] = msg_data['fill'].zfill(self.MSG_SIZE - len(bytes_msg))
            bytes_msg = json.dumps(msg_data).encode()
        self.sock.send(bytes_msg)

    def _ls(self, cmd_args):
        """
        查看文件列表
        :param cmd_args:
        :return:
        """
        self.send_msg(action_type='ls')
        response = self.get_response()
        print(response)
        if response.get('status_code') == 302:
            cmd_result_size = response.get('cmd_result_size')
            received_size = 0
            cmd_result = b''
            while received_size < cmd_result_size:
                if cmd_result_size - received_size < 8192:
                    data = self.sock.recv(cmd_result_size - received_size)
                else:
                    data = self.sock.recv(8192)
                cmd_result += data
                received_size += len(data)
            else:
                print(cmd_result.decode('gbk'))

    def _cd(self, cmd_args):
        """切换目录"""
        if self.parameter_check(cmd_args, exact_args=1):
            target_dir = cmd_args[0]
            self.send_msg('cd', target_dir=target_dir)
            response = self.get_response()
            print(response)
            if response.get('status_code') == 350:
                self.terminal_display = '[<%s>%s]>>:' % (self.username, response.get('current_dir'))
            else:
                pass

    def _del(self, cmd_args):
        """删除目录、文件"""
        if self.parameter_check(cmd_args, exact_args=1):
            filename = cmd_args[0]
            self.send_msg('del', filename=filename)
            response = self.get_response()
            print(response)
            if response.get('status_code') == 352:
                print('[%s]文件删除成功' % filename)
            elif response.get('status_code') == 353:
                print('[%s]文件删除失败' % filename)
            else:
                print('文件不存在')

    def _mkdir(self, cmd_args):
        """创建目录"""
        if self.parameter_check(cmd_args, exact_args=1):
            filename = cmd_args[0]
            self.send_msg('mkdir', filename=filename)
            response = self.get_response()
            print(response)
            if response.get('status_code') == 355:
                print('[%s] 目录创建成功！' % filename)
            else:
                print('目录创建失败！')

    def _get(self, cmd_args):
        """下载文件"""
        if self.parameter_check(cmd_args, min_args=1):
            filename = cmd_args[0]
            # 1.拿到文件名
            # 2、发送到远程
            # 3、等待服务器返回消息
            #   如果文件存在 拿到文件大小
            #       循环接收
            #   文件如果不存在
            #       打印错误码
            self.send_msg(action_type='get', filename=filename)
            response = self.get_response()
            if response.get('status_code') == 301:
                file_size = response.get('file_size')

                received_size = 0
                f = open(filename, 'wb')
                while received_size < file_size:
                    if file_size - received_size < 8192:
                        data = self.sock.recv(file_size - received_size)
                    else:
                        data = self.sock.recv(8192)
                    received_size += len(data)
                    f.write(data)
                    print(received_size, file_size)
                else:
                    print('----file [%s] recv done,received size[%s]----' % (filename, file_size))
                    f.close()
            else:
                print(response.get('status_msg'))

    def _put(self, cmd_args):
        """上传本地文件
        1、确定文件在服务器
        2、拿到文件+size放到消息头里发给远程
        3、打开文件，发送内容
        """
        if self.parameter_check(cmd_args, exact_args=1):
            local_file = cmd_args[0]
            if os.path.isfile(local_file):
                total_size = os.path.getsize(local_file)
                self.send_msg('put', file_size=total_size, filename=local_file)
                f = open(local_file, 'rb')
                uploaded_size = 0
                last_percent = 0
                for line in f:
                    self.sock.send(line)
                    uploaded_size += len(line)
                    current_percent = int(uploaded_size / total_size * 100)
                    if current_percent > last_percent:
                        print('#' * current_percent + '{percent}%'.format(percent=current_percent), end='\r', flush=True)
                        last_percent = current_percent
                else:
                    print('file upload done'.center(50, '='))
                    f.close()


if __name__ == '__main__':
    client = FTPClient()
    client.intervactive()  # 交互
