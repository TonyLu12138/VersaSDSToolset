import time

import gevent
from gevent import monkey
import os
import sys
import utils
import action

# 协程相关的补丁
monkey.patch_all()

timeout = gevent.Timeout(60)


class KSBConnect(object):
    """
    通过ssh连接节点，生成连接对象的列表
    """
    list_master_ssh = []
    list_worker_ssh = []

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, '_instance'):
            KSBConnect._instance = super().__new__(cls)
            KSBConnect._instance.conf_file = utils.ConfFile()
            KSBConnect._instance.data = KSBConnect._instance.conf_file.data
            KSBConnect.get_master_ssh(KSBConnect._instance)
            KSBConnect.get_worker_ssh(KSBConnect._instance)
            KSBConnect._instance.linstor_ssh = KSBConnect.get_linstor_ssh(KSBConnect._instance)
            KSBConnect._instance.list_all_ssh = KSBConnect.get_all_ssh(KSBConnect._instance)
        return KSBConnect._instance

    def get_master_ssh(self):
        local_ip = utils.get_host_ip()
        for node in self.conf_file.get_master_ssh_data():
            if local_ip == node[0]:
                self.list_master_ssh.append(None)
            else:
                ssh = utils.SSHConn(node[0], node[1], node[2], node[3])
                self.list_master_ssh.append(ssh)

    def get_worker_ssh(self):
        local_ip = utils.get_host_ip()
        for node in self.conf_file.get_worker_ssh_data():
            if local_ip == node[0]:
                self.list_worker_ssh.append(None)
            else:
                ssh = utils.SSHConn(node[0], node[1], node[2], node[3])
                self.list_worker_ssh.append(ssh)

    def get_linstor_ssh(self):
        node = self.conf_file.get_linstor_ssh_data()
        ssh = utils.SSHConn(node[0], node[1], node[2], node[3])
        return ssh

    def get_all_ssh(self):
        all_ssh = set(self.list_master_ssh).union(set(self.list_worker_ssh))
        return list(all_ssh)


class KSConsole(object):
    def __init__(self):
        self.conn = KSBConnect()
        self.default_ssh = None if None in self.conn.list_master_ssh else self.conn.list_master_ssh[0]

    def install_haproxy(self):
        lst = []
        for ssh in self.conn.list_master_ssh:
            handler = action.HAproxy(ssh)
            lst.append(gevent.spawn(handler.install))
        gevent.joinall(lst)

    def install_keepalived(self):
        lst = []
        for ssh in self.conn.list_master_ssh:
            handler = action.Keepalived(ssh)
            lst.append(gevent.spawn(handler.install))
        gevent.joinall(lst)

    def install_docker(self, flag):
        lst = []
        for ssh in self.conn.list_all_ssh:
            handler = action.VersaKBS(ssh)
            lst.append(gevent.spawn(handler.install_docker, flag))
        gevent.joinall(lst)

    def install(self):
        for ssh in self.conn.list_all_ssh:
            handler = action.VersaKBS(ssh)
            handler.install()
        for ssh in self.conn.list_all_ssh:
            handler = action.VersaSDS(ssh)
            handler.install()
        handler = action.VersaKBS(self.default_ssh)
        handler.install_kk()

    def sync_time(self):
        for ssh in self.conn.list_all_ssh:
            handler = action.VersaSDS(ssh)
            handler.sync_time()

    def modify_haproxy(self):
        lst = []
        if not os.path.exists("./sample-haproxy.cfg"):
            print("haproxy.cfg 文件不存在，退出")
            sys.exit()
        data = ""
        haproxy = action.HAproxy(self.default_ssh)
        for server in self.conn.data['HAproxy']['server']:
            ip = self.conn.conf_file.get_ip(server['name'])
            data += haproxy.get_server(server['name'], ip, server['port'])

        for ssh in self.conn.list_master_ssh:
            handler = action.HAproxy(ssh)
            lst.append(gevent.spawn(handler.modify_cfg, "/etc/haproxy/haproxy.cfg", data))
        gevent.joinall(lst)

    def modify_keepalived(self):
        lst = []
        if not os.path.exists("./sample-keepalived.conf"):
            print("keepalived.conf 文件不存在，退出")
            sys.exit()

        router_id = self.conn.data['Keepalived']['router_id']
        virtual_router_id = self.conn.data['Keepalived']['virtual_router_id']
        virtual_ipaddress = self.conn.data['Keepalived']['virtual_ipaddress']

        for ssh, master in zip(self.conn.list_master_ssh, self.conn.conf_file.master_list):
            unicast_peer_list = []
            interface = ""
            priority = ""
            unicast_src_ip = ""
            handler = action.Keepalived(ssh)
            for host in self.conn.data['Keepalived']['host']:
                if master == host['name']:
                    unicast_src_ip = self.conn.conf_file.get_ip(host['name'])
                    interface = host['interface']
                    priority = host['priority']
                else:
                    unicast_peer_list.append(self.conn.conf_file.get_ip(host['name']))

            if not all([interface, priority, unicast_src_ip]):
                print("配置文件master节点的数据不一致")
                sys.exit()

            lst.append(gevent.spawn(handler.modify_conf,
                                    "/etc/keepalived/keepalived.conf",
                                    router_id,
                                    interface,
                                    virtual_router_id,
                                    priority,
                                    unicast_src_ip,
                                    unicast_peer_list,
                                    virtual_ipaddress
                                    ))
        gevent.joinall(lst)

    def modify_kk(self):
        handler = action.VersaKBS(self.default_ssh)
        confile = utils.ConfFile()
        hosts = confile.get_kk_hosts()
        etcd = confile.get_kk_etcd()
        master = confile.get_kk_masters()
        worker = confile.get_kk_worker()
        kk_vip = confile.get_kk_vip()
        port = confile.get_kk_port()
        if len(self.conn.data['Keepalived']['host']) > 1:
            handler.modify_config(hosts, etcd, master, worker, kk_vip, port)
        else:
            handler.modify_config(hosts, etcd, master, worker, kk_vip, port, True)

    def build_ks(self):
        handler = action.VersaKBS(self.default_ssh)
        handler.build()

    def install_drbd_spc(self):
        for ssh in self.conn.list_all_ssh:
            handler = action.VersaSDS(ssh)
            handler.install_drbd_spc()

    def restart_haproxy(self):
        lst = []
        for ssh in self.conn.list_master_ssh:
            handler = action.HAproxy(ssh)
            lst.append(gevent.spawn(handler.restart))
        gevent.joinall(lst)

    def check_apiserver(self):
        lst = []
        for ssh in self.conn.list_master_ssh:
            handler = action.Keepalived(ssh)
            lst.append(gevent.spawn(handler.set_check_apiserver_sh))
        gevent.joinall(lst)

    def restart_keepalived(self):
        lst = []
        for ssh in self.conn.list_master_ssh:
            handler = action.Keepalived(ssh)
            lst.append(gevent.spawn(handler.restart))
        gevent.joinall(lst)

    def set_swap(self):
        lst = []
        for ssh in self.conn.list_master_ssh:
            handler = action.SystemOperation(ssh)
            lst.append(gevent.spawn(handler.off_swap))
            lst.append(gevent.spawn(handler.modify_fstab))
        gevent.joinall(lst)

    def create_linstor_conf_file(self):
        vip = self.conn.data['VersaSDS']['vip']
        for ssh in self.conn.list_all_ssh:
            handler = action.VersaSDS(ssh)
            handler.create_conf(vip)
            handler.start_satellite()

    def add_to_linstor_cluster(self):
        handler = action.VersaSDS(self.conn.linstor_ssh)
        for node in self.conn.data['host']:
            handler.create_node(node["name"], node["private_ip"])

    def set_linstor_server(self):
        vip = self.conn.data["VersaSDS"]["vip"]
        handler = action.VersaSDS(self.default_ssh)
        handler.connect_linstor_cluster(vip)
        time.sleep(5)
        handler.set_console_image(self.conn.data["ImageVersion"]["console"])
        handler.set_server_image(self.conn.data["ImageVersion"]["server"])
        time.sleep(5)
        handler.set_linstor_csi(vip)

    def replace_sources(self):
        for ssh in self.conn.list_all_ssh:
            handler = action.SystemOperation(ssh)
            handler.replace_sources()

    def replace_linbit_sources(self):
        for ssh in self.conn.list_all_ssh:
            handler = action.SystemOperation(ssh)
            handler.replace_linbit_sources()

    def recovery_linbit_sources(self):
        for ssh in self.conn.list_all_ssh:
            handler = action.SystemOperation(ssh)
            handler.recovery_linbit_sources()

    def bak_sources_files(self):
        for ssh in self.conn.list_all_ssh:
            handler = action.SystemOperation(ssh)
            file_string = handler.get_sources_list()
            if file_string:
                files_list = file_string.split("\n")
                for file in files_list:
                    if file:
                        handler.bak_sources_list(file)

    def apt_update(self):
        for ssh in self.conn.list_all_ssh:
            handler = action.SystemOperation(ssh)
            handler.apt_update()
