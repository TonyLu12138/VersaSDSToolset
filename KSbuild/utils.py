import sys

import paramiko
import yaml
import socket
import os
import subprocess
import time
import prettytable
import logging


class SSHConn(object):

    def __init__(self, host, port=22, username=None, password=None, timeout=None):
        self._host = host
        self._port = port
        self._timeout = timeout
        self._username = username
        self._password = password
        self.SSHConnection = None
        self.ssh_connect()

    def _connect(self):
        try:
            objSSHClient = paramiko.SSHClient()
            objSSHClient.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            objSSHClient.connect(self._host, port=self._port,
                                 username=self._username,
                                 password=self._password,
                                 timeout=self._timeout)
            # time.sleep(1)
            # objSSHClient.exec_command("\x003")
            self.SSHConnection = objSSHClient
        except:
            print(f'Failed to connect host {self._host}')

    def ssh_connect(self):
        self._connect()
        if not self.SSHConnection:
            print(f'Connect retry for host {self._host}')
            self._connect()
            if not self.SSHConnection:
                sys.exit()

    def exec_cmd(self, command):
        if self.SSHConnection:
            stdin, stdout, stderr = self.SSHConnection.exec_command(command)
            data = stdout.read()
            if len(data) > 0:
                # print(data.strip())
                return data
            err = stderr.read()
            if len(err) > 0:
                # 记录一下log
                return err
            #     print('''Excute command "{}" failed on "{}" with error:
            # "{}"'''.format(command, self._host, err.strip()))


class FileEdit(object):
    def __init__(self, path):
        self.path = path
        self.data = self.read_file()

    def read_file(self):
        with open(self.path) as f:
            data = f.read()
        return data

    def replace_data(self, old, new):
        if not old in self.data:
            print('The content does not exist')
            return
        self.data = self.data.replace(old, new)
        return self.data

    def insert_data(self, content, anchor=None, type=None):
        """
        在定位字符串anchor的上面或者下面插入数据，上面和下面由type决定（under/above）
        anchor可以是多行数据，但必须完整
        :param anchor: 定位字符串
        :param type: under/above
        :return:
        """
        list_data = self.data.splitlines()
        list_add = (content + '\n').splitlines()
        pos = len(list_data)
        lst = []

        if anchor:
            if not anchor in self.data:
                return

            list_anchor = anchor.splitlines()
            len_anchor = len(list_anchor)

            for n in range(len(list_data)):
                match_num = 0
                for m in range(len_anchor):
                    if not list_anchor[m] == list_data[n + m]:
                        break
                    match_num += 1

                if match_num == len_anchor:
                    if type == 'under':
                        pos = n + len_anchor
                    else:
                        pos = n
                    break

        lst.extend(list_data[:pos])
        lst.extend(list_add)
        lst.extend(list_data[pos:])
        self.data = '\n'.join(lst)

        return self.data

    @staticmethod
    def add_data_to_head(text, data_add):
        text_list = text.splitlines()
        for i in range(len(text_list)):
            if text_list[i] != '\n':
                text_list[i] = f'{data_add}{text_list[i]}'

        return ('\n'.join(text_list))

    @staticmethod
    def remove_comma(text):
        text_list = text.splitlines()
        for i in range(len(text_list)):
            text_list[i] = text_list[i].rstrip(',')

        return ('\n'.join(text_list))


class ConfFile(object):
    def __init__(self):
        self.data = self.read_yaml()
        self.master_list = self.data['KubeKey']['master']

    def read_yaml(self, filename='./config.yaml'):
        """读YAML文件"""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                yaml_dict = yaml.safe_load(f)
            return yaml_dict
        except FileNotFoundError:
            print("Please check the file name:", filename)
        except TypeError:
            print("Error in the type of file name.")

    def update_yaml(self, data, filename='./config.yaml'):
        """更新文件内容"""
        with open(filename, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, default_flow_style=False)

    def get_master_ssh_data(self):
        ssh_list = []
        for host in self.data['host']:
            if host['name'] in self.master_list:
                ssh_list.append([host['address'], 22, 'root', host['root_password']])
        return ssh_list

    def get_worker_ssh_data(self):
        ssh_list = []
        for host in self.data['host']:
            if not host['name'] in self.master_list:
                ssh_list.append([host['address'], 22, 'root', host['root_password']])
        return ssh_list

    def get_linstor_ssh_data(self):
        ssh_list = []
        ssh_list.append(self.data["VersaSDS"]["node"]["ip"])
        ssh_list.append(22)
        ssh_list.append('root')
        ssh_list.append(self.data["VersaSDS"]["node"]["root_password"])
        return ssh_list

    def get_kk_hosts(self):
        hosts = self.data['host']
        str_all = ""
        for host in hosts:
            host.pop("root_password")
            str_host = "  - {name: %s, address: %s, internalAddress: %s, user: %s, password: %s}\n" % (
                host["name"], host["address"], host["internalAddress"], host["user"], host["password"])
            str_all += str_host
        return str_all

    def get_kk_etcd(self):
        etcds = self.data['KubeKey']['etcd']
        str_all = ""
        for etcd in etcds:
            str_etcd = f"    - {etcd}\n"
            str_all += str_etcd
        return str_all

    def get_kk_masters(self):
        masters = self.data['KubeKey']['master']
        str_all = ""
        for master in masters:
            str_master = f"    - {master}\n"
            str_all += str_master
        return str_all

    def get_kk_worker(self):
        workers = self.data['KubeKey']['worker']
        if not workers:
            return ""
        str_all = ""
        for worker in workers:
            str_worker = f"    - {worker}\n"
            str_all += str_worker
        return str_all

    def get_kk_vip(self):
        vip = self.data['KubeKey']['address']
        return f'"{vip}"'

    def get_kk_port(self):
        return self.data['KubeKey']['port']

    def get_ip(self, hostname):
        for host in self.data['host']:
            if host['name'] == hostname:
                return host['address']


class Table():
    def __init__(self):
        self.header = None
        self.data = None
        self.table = prettytable.PrettyTable()

    def add_data(self, list_data):
        self.table.add_row(list_data)

    def add_column(self, fieldname, list_column):
        self.table.add_column(fieldname, list_column)

    def print_table(self):
        self.table.field_names = self.header
        print(self.table)


def get_host_ip():
    """
    查询本机ip地址
    :return: ip
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    finally:
        s.close()

    return ip


def get_hostname():
    """
    查询本机hostname
    :return:
    """
    # local_hostname = os.popen('hostname').read()
    local_hostname = os.popen('hostname').read().strip('\n')
    return local_hostname


def exec_cmd(cmd, conn=None):
    if conn:
        result = conn.exec_cmd(cmd)
    else:
        result = subprocess.getoutput(cmd)
    result = result.decode() if isinstance(result, bytes) else result
    log_data = f'{conn._host if conn else "localhost"} - {cmd} - \n{result}'
    Log().logger.info(log_data)
    if result:
        result = result.rstrip('\n')
    return result


def exec_cmd_realtime(cmd):
    process = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    while process.poll() is None:
        line = process.stdout.readline()
        line = line.strip()
        if line:
            print(line.decode())


def run_timeout(flag, run, timeout=30):
    t_beginning = time.time()
    while True:
        run()
        if flag:
            break
        time.sleep(1)
        seconds_passed = time.time() - t_beginning
        if timeout and seconds_passed > timeout:
            raise TimeoutError()


class Log():
    def __init__(self):
        pass

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, '_instance'):
            Log._instance = super().__new__(cls)
            Log._instance.logger = logging.getLogger()
            Log._instance.logger.setLevel(logging.INFO)
            Log.set_handler(Log._instance.logger)
        return Log._instance

    @staticmethod
    def set_handler(logger):
        fh = logging.FileHandler('KSbuild.log', mode='a')
        fh.setLevel(logging.DEBUG)  # 输出到file的log等级的开关
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        fh.setFormatter(formatter)
        logger.addHandler(fh)
