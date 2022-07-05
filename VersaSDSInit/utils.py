import paramiko
import yaml
import socket
import os
import subprocess
import time
import json
import prettytable
import logging
import sys
import re


def check_ip(ip):
    """检查IP格式"""
    re_ip = re.compile(
        r'^((2([0-4]\d|5[0-5]))|[1-9]?\d|1\d{2})(\.((2([0-4]\d|5[0-5]))|[1-9]?\d|1\d{2})){3}$')
    result = re_ip.match(ip)
    if result:
        return True
    else:
        print(f"ERROR in IP format of {ip}, please check.")
        return False


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
    log_data = f'{conn._host if conn else "localhost"} - {cmd} - {result}'
    Log().logger.info(log_data)
    if result:
        result = result.rstrip('\n')
    return result


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
            print(f" Failed to connect {self._host}")

    def ssh_connect(self):
        self._connect()
        if not self.SSHConnection:
            print(f'Connect retry for {self._host}')
            self._connect()
            if not self.SSHConnection:
                sys.exit()

    def exec_cmd(self, command):
        if self.SSHConnection:
            stdin, stdout, stderr = self.SSHConnection.exec_command(command)
            data = stdout.read()
            if len(data) > 0:
                data = data.decode() if isinstance(data, bytes) else data
                return data
                # return {"st": True, "rt": data}
            err = stderr.read()
            if len(err) > 0:
                err = err.decode() if isinstance(err, bytes) else err
                return err
                # return {"st": False, "rt": err}


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

        return '\n'.join(text_list)

    @staticmethod
    def remove_comma(text):
        text_list = text.splitlines()
        for i in range(len(text_list)):
            text_list[i] = text_list[i].rstrip(',')
        return '\n'.join(text_list)


class ConfFile(object):
    def __init__(self):
        self.yaml_file = './ClusterConf.yaml'
        self.config = self.read_yaml()
        self.check_config()

    def read_yaml(self):
        """读YAML文件"""
        try:
            with open(self.yaml_file, 'r', encoding='utf-8') as f:
                yaml_dict = yaml.safe_load(f)
            return yaml_dict
        except FileNotFoundError:
            print("Please check the file name:", self.yaml_file)
        except TypeError:
            print("Error in the type of file name.")

    def update_yaml(self):
        """更新文件内容"""
        with open(self.yaml_file, 'w', encoding='utf-8') as f:
            yaml.dump(self.config, f, default_flow_style=False)

    def check_config(self):
        ip_list = []
        try:
            if not check_ip(self.config["vip"]):
                print(f'Please check the vip config of {self.config["vip"]}')
                sys.exit()
            ip_list.append('.'.join(self.config["vip"].split('.')[:3]))
            for node in self.config["node"]:
                if not check_ip(node['public_ip']):
                    print(f"Please check the ip config of {node['public_ip']}")
                    sys.exit()
                if not check_ip(node['private_ip']):
                    print(f"Please check the ip config of {node['private_ip']}")
                    sys.exit()
                if node['private_ip'] == self.config["vip"]:
                    print(
                        f"Please check the private_ip: {node['private_ip']} and vip: {self.config['vip']}, they must be the different.")
                    sys.exit()
                ip_list.append('.'.join(node['private_ip'].split('.')[:3]))
                if len(node["heartbeat_line"]) != 1 and len(node["heartbeat_line"]) != 2:
                    print(
                        f'Please check the heartbeat_line config {node["heartbeat_line"]}. The number of heartbeat_line can only be 1 or 2')
                    sys.exit()
                else:
                    for heartbeat_ip in node["heartbeat_line"]:
                        if not check_ip(heartbeat_ip):
                            print(f"Please check the ip config of {heartbeat_ip}")
                            sys.exit()
            if len(set(ip_list)) != 1:
                print(f"Please check the ip config and vip config, they must be the same network segment.")
                sys.exit()
        except KeyError as e:
            print(f"Missing configuration item {e}.")
            sys.exit()

    def get_ssh_conn_data(self):
        lst = []
        for node in self.config:
            lst.append([node['public_ip'], node['port'], 'root', node['root_password']])
        return lst

    def get_cluster_name(self):
        datetime = time.strftime('%y%m%d')
        return f"{self.config['cluster']}_{datetime}"

    def get_bindnetaddr(self):
        node = self.config['node'][0]
        ips = node['heartbeat_line']
        lst = []
        for ip in ips:
            ip_list = ip.split(".")
            lst.append(f"{'.'.join(ip_list[:3])}.0")
        return lst

    def get_interface(self):
        bindnetaddr_list = self.get_bindnetaddr()
        interface_list = []
        ringnumber = 1
        for bindnetaddr in bindnetaddr_list[1:]:
            interface = "interface {\n\tringnumber: %s\n\tbindnetaddr: %s\n\tmcastport: 5407\n\tttl: 1\n}" % (
                ringnumber, bindnetaddr)
            interface = FileEdit.add_data_to_head(interface, '\t')
            interface_list.append(interface)
            ringnumber += 1
        return "\n".join(interface_list)

    def get_nodelist(self, hostname_list):
        str_node_all = ""

        for node, hostname in zip(self.config['node'], hostname_list):
            dict_node = {}
            str_node = "node "
            index = 0
            for ip in node["heartbeat_line"]:
                dict_node.update({f"ring{index}_addr": ip})
                index += 1
            dict_node.update({'name': hostname})
            str_node += json.dumps(dict_node, indent=4, separators=(',', ': '))
            str_node = FileEdit.remove_comma(str_node)
            str_node_all += str_node + '\n'
        str_node_all = FileEdit.add_data_to_head(str_node_all, '\t')
        str_nodelist = "nodelist {\n%s\n}" % str_node_all
        return str_nodelist


class Table(object):
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


class Log(object):
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
        fh = logging.FileHandler('./VersaSDSLog.log', mode='a')
        fh.setLevel(logging.DEBUG)  # 输出到file的log等级的开关
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        fh.setFormatter(formatter)
        logger.addHandler(fh)
