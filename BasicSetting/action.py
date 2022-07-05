# -*- coding:utf-8 -*-
import utils


class InstallSoftware(object):

    def update_apt(self):
        """更新apt"""
        cmd = f"apt update -y"
        result = utils.exec_cmd(cmd)
        if result["st"]:
            return True

    def install_software(self, name):
        """根据软件名安装对应软件"""
        cmd = f"apt install {name} -y"
        result = utils.exec_cmd(cmd)
        if result["st"]:
            return True


class NetworkManagerService(object):

    def modify_renderer(self):
        netplan_file = utils.get_file("/etc/netplan", "yaml")
        cmd = f"sed -i 's/renderer: networkd/renderer: NetworkManager/g;/ethernets/,$d' /etc/netplan/{netplan_file[0]}"
        result = utils.exec_cmd(cmd)
        if result["st"]:
            return True

    def modify_config(self):
        cmd = f"sed -i 's/^managed=false/#managed=false\\nmanaged=true/g' /etc/NetworkManager/NetworkManager.conf"
        result = utils.exec_cmd(cmd)
        if result["st"]:
            return True

    def netplan_apply(self):
        cmd = f"netplan apply"
        result = utils.exec_cmd(cmd)
        if result["st"]:
            return True

    def restart_network_manager(self):
        cmd = f"systemctl restart network-manager.service"
        result = utils.exec_cmd(cmd)
        if result["st"]:
            return True


class SystemService(object):

    def oprt_ssh_service(self, status):
        """启动、停止、重启openssh服务"""
        cmd = f"/etc/init.d/ssh {status}"
        result = utils.exec_cmd(cmd)
        if result["st"]:
            return True

    def modify_hostname(self, hostname):
        cmd = f'hostnamectl set-hostname {hostname}'
        result = utils.exec_cmd(cmd)
        if result["st"]:
            return True

    def modify_hostsfile(self, ip, hostname):
        cmd = f"sed -i 's/{ip}.*/{ip}\t{hostname}/g' /etc/hosts"
        result = utils.exec_cmd(cmd)
        if result["st"]:
            return True

    def get_hostname(self):
        cmd = "hostname"
        result = utils.exec_cmd(cmd)
        if result["st"]:
            return result["rt"]


class IpService(object):

    def set_local_ip(self, device, ip, gateway, netmask=24):
        """设置连接的IP地址"""
        connection_name = 'vtel_' + device
        cmd = f"nmcli connection add con-name {connection_name} type ethernet ifname {device} ipv4.addresses {ip}/{netmask} ipv4.gateway {gateway} ipv4.dns '114.114.114.114 8.8.8.8' ipv4.method manual ipv6.method ignore"
        result = utils.exec_cmd(cmd)
        if result["st"]:
            return True

    def up_local_ip_service(self, device):
        """启用设置的IP"""
        connection_name = 'vtel_' + device
        cmd = f"nmcli connection up id {connection_name}"
        result = utils.exec_cmd(cmd)
        if result["st"]:
            return True

    def get_connection(self):
        """get all the connection,return a string"""
        cmd = f"nmcli connection show"
        result = utils.exec_cmd(cmd)
        if result:
            return result["rt"]

    def del_connect(self, name):
        cmd = f"nmcli connection delete {name}"
        result = utils.exec_cmd(cmd)
        if result:
            if result["st"]:
                return True
        return False


class RootConfig(object):

    def set_root_password(self, new_password):
        """设置root用户密码"""
        cmd = f"su root | echo root:{new_password} | sudo -S chpasswd"
        result = utils.exec_cmd(cmd)
        if result["st"]:
            return True

    def set_root_permit_login(self):
        """允许以root用户登录"""
        cmd = f"sed -i 's/PermitRootLogin prohibit-password/#PermitRootLogin prohibit-password\\nPermitRootLogin yes/g' /etc/ssh/sshd_config"
        result = utils.exec_cmd(cmd)
        if result["st"]:
            return True
