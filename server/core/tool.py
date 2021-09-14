from core import main


class ManagementTool(object):
    """
    对用户输入的指令解析并处理相应的模块
    """

    def __init__(self, sys_argv):
        self.sys_argv = sys_argv
        print(self.sys_argv)
        self.verify_argv()

    def verify_argv(self):
        """"验证指令合法性"""
        if len(self.sys_argv) < 2:
            self.help_msg()
        cmd = self.sys_argv[1]
        if not hasattr(self, cmd):
            print('指令不合法')
            self.help_msg()

    def help_msg(self):
        msg = '''
        start       start FTP server
        stop        stop FTP server
        restart     restart FTP server
        createuser  username    create a ftp user
        
        '''
        exit(msg)

    def execute(self):
        """
        解析并执行指令
        :return:
        """
        cmd = self.sys_argv[1]
        func = getattr(self, cmd)
        func()

    def start(self):
        """start FTP server"""
        server = main.FTPServer(self)
        server.run_forever()

    def creteuser(self):
        pass
