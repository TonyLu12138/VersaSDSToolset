# -*- coding: utf-8 -*-
import ipaddress
import sys
import re
import time

import utils
import action


def check_device(device_list, result):
    """
    @param device_list: list of device
    @param result: result for nmcli device status command
    @return: Boolean
    """
    flag = True
    for device in device_list:
        re_obj = re.search(f'{device}\s+ethernet', result)
        if not re_obj:
            print(f"{device} not exist.")
            flag = False
    return flag


def get_device_connection(device, result):
    """
    @param device: device name
    @param result: result for nmcli connection show command
    @return: UUID of connection about device
    """
    re_obj = re.search(r'(\w{8}-\w{4}-\w{4}-\w{4}-\w{12})\s+(\S+)\s+' + device, result)
    if re_obj:
        return re_obj.group(1)


def check_connection(name, result):
    """
    @param name: connection name
    @param result: result for nmcli connection show command
    @return: Boolean
    """
    re_obj = re.search(f'{name}', result)
    if re_obj:
        return re_obj.group()


def get_ip(result):
    re_obj = re.search(r'IP4.ADDRESS\[1]:\s+(\d+\.\d+\.\d+\.\d+)', result)
    if re_obj:
        return re_obj.group(1)

def get_dns(result):
    dns_list = re.findall(r'IP4.DNS\[\d+\]:\s+(\d+\.\d+\.\d+\.\d+)', result)
    return dns_list

def get_gateway(result):
    gateway_obj = re.search(r'IP4.GATEWAY:\s+(\d+\.\d+\.\d+\.\d+)', result)
    if gateway_obj:
        return gateway_obj.group(1)
    
def get_netmask(result):
    netmask_obj = re.search(r'IP4\.ADDRESS\[1\]:\s+\d+\.\d+\.\d+\.\d+\/(\d+)', result)
    if netmask_obj:
        return netmask_obj.group(1)



def get_ssh_conn(node, password):
    if utils.get_host_ip() == node or node is None:
        return None
    # ssh_conn = utils.SSHConn(host=node, username="root", password=password)
    return None


class Bonding(object):
    def __init__(self):
        self.modify_mode = False

    def configure_bonding_by_file(self, file):
        """create or modify bonding via yaml config file"""
        config = utils.ConfFile(file)
        host_config = config.get_config()
        self.modify_mode = True
        list_ssh = []
        for host in host_config:
            ssh_conn = get_ssh_conn(host["node"], host["password"])
            list_ssh.append(ssh_conn)
        for host, conn in zip(host_config, list_ssh):
            print(f'{host["node"]:-^60}')
            bonding = action.IpService(conn)
            lc_device_date = bonding.get_device_status()
            if not check_device(host["device"], lc_device_date):
                continue
            connection_detail = bonding.get_connection()
            if self.check_bonding_exist(f'vtel_{host["bond"]}', connection_detail):
                print(f'Check and modify {host["bond"]}...')
                self.modify_bonding_slave(conn, host["bond"], host["device"])
                self.modify_bonding_mode(conn, host["bond"], host["mode"])
                self.modify_bonding_ip(conn, host["bond"], host["ip"])
            else:
                print(f'Create {host["bond"]}...')
                self.create_bonding(conn, host["bond"], host["mode"], host["device"], host["ip"])

    def create_bonding(self, conn, bonding_name, mode, device_list, ip):
        """
        @param conn: ssh connection
        @param bonding_name: bond name that user input
        @param mode: bonding mode
        @param device_list: device list for bonding
        @param ip: IP for bonding
        @return: None
        Create bonding and del old configuration
        """
        connection_name = f'vtel_{bonding_name}'
        list_del = []
        bonding = action.IpService(conn)
        connection_detail = bonding.get_connection()
        if not self.modify_mode:
            if self.check_bonding_exist(connection_name, connection_detail):
                print(f"{bonding_name} already exists.")
                sys.exit()
            if not utils.check_ip(ip):
                sys.exit()
            lc_device_date = bonding.get_device_status()
            if not check_device(device_list, lc_device_date):
                sys.exit()
        for device in device_list:
            connection = get_device_connection(device, connection_detail)
            if connection:
                print(f'** {device} have old configuration ...')
                list_del.append(connection)
        print(f'Start to create {bonding_name}')
        if bonding.set_bonding(bonding_name, mode):
            bonding.modify_bond_ip(bonding_name, ip)
            if mode == "802.3ad":
                bonding.add_bond_options(bonding_name, "xmit_hash_policy=layer3+4")
                bonding.add_bond_options(bonding_name, "miimon=100")
                bonding.add_bond_options(bonding_name, "lacp_rate=fast")
        for device in device_list:
            bonding_slave = bonding.add_bond_slave(bonding_name, device)
            if bonding_slave:
                bonding.up_ip_service(bonding_slave)
            else:
                print(f' Failed to add bond slave about {device}')
        bonding.up_ip_service(connection_name)
        time.sleep(8)
        speed_detail = bonding.get_bond_ethtool(bonding_name)
        speed = self.get_speed(speed_detail)
        print(f"* {bonding_name} speed is {speed} .")
        if list_del:
            print("** Clear old configuration")
            for connection_del in list_del:
                bonding.del_connect(connection_del)

    def modify_bonding_mode(self, conn, bonding_name, mode):
        connection_name = f'vtel_{bonding_name}'
        bonding = action.IpService(conn)
        if not self.modify_mode:
            connection_detail = bonding.get_connection()
            if not self.check_bonding_exist(connection_name, connection_detail):
                print(f"{bonding_name} does not exist. Do nothing.")
                sys.exit()
        mode_detail = bonding.get_mode_detail(bonding_name)
        lc_mode = self.get_mode(mode_detail)
        if not self.check_mode(lc_mode, mode):
            print(f"Change bonding mode from {lc_mode} to {mode}.")
            if self.check_mode(lc_mode, "802.3ad"):
                bonding.delete_bond_options(bonding_name, "lacp_rate")
                bonding.delete_bond_options(bonding_name, "xmit_hash_policy")
                bonding.delete_bond_options(bonding_name, "miimon")
            bonding.modify_bonding_mode(bonding_name, mode)
            if mode == "802.3ad":
                bonding.add_bond_options(bonding_name, "xmit_hash_policy=layer3+4")
                bonding.add_bond_options(bonding_name, "miimon=100")
                bonding.add_bond_options(bonding_name, "lacp_rate=fast")
            bonding.up_ip_service(connection_name)
        else:
            if not self.modify_mode:
                print("Same bonding mode. Do nothing.")

    def modify_bonding_ip(self, conn, bonding_name, ip):
        connection_name = f'vtel_{bonding_name}'
        bonding = action.IpService(conn)
        if not self.modify_mode:
            if not utils.check_ip(ip):
                sys.exit()
            connection_detail = bonding.get_connection()
            if not self.check_bonding_exist(connection_name, connection_detail):
                print(f"{bonding_name} does not exist. Do nothing.")
                sys.exit()
        bond_detail = bonding.get_device_detail(bonding_name)
        lc_ip = get_ip(bond_detail)
        if ip == lc_ip:
            if not self.modify_mode:
                print("Same bonding IP. Do nothing.")
        else:
            print(f"Change {bonding_name} IP, {lc_ip} -> {ip}..")
            bonding.modify_bond_ip(bonding_name, ip)
            bonding.up_ip_service(connection_name)

    def modify_bonding_slave(self, conn, bonding_name, device_list):
        list_del = []
        connection_name = f'vtel_{bonding_name}'
        bonding = action.IpService(conn)
        connection_detail = bonding.get_connection()
        if not self.modify_mode:
            if not self.check_bonding_exist(connection_name, connection_detail):
                print(f"{bonding_name} does not exist. Do nothing.")
                sys.exit()
            lc_device_date = bonding.get_device_status()
            if not check_device(device_list, lc_device_date):
                sys.exit()
        slave_list = self.get_slave_via_bonding_name(bonding_name, connection_detail)
        device_slave_list = [f'vtel_{bonding_name}-slave-{i}' for i in device_list]
        # list_retain = [i for i in device_list if i in slave_list]
        list_create = [i for i in device_list if f'vtel_{bonding_name}-slave-{i}' not in slave_list]
        list_delete = [i for i in slave_list if i not in device_slave_list]
        if list_create:
            for device in list_create:
                connection = get_device_connection(device, connection_detail)
                if connection:
                    print(f'** {device} have old configuration ...')
                    list_del.append(connection)
        if list_create or list_delete:
            print(f"Change bonding salve device of {bonding_name}.")
            for delete_salve in list_delete:
                bonding.down_connect(delete_salve)
                bonding.del_connect(delete_salve)
            for device in list_create:
                bonding_slave = bonding.add_bond_slave(bonding_name, device)
                bonding.up_ip_service(bonding_slave)
            bonding.up_ip_service(connection_name)
        else:
            if not self.modify_mode:
                print("Same Device. Do nothing.")
        if list_del:
            print("** Clear old configuration")
            for connection_del in list_del:
                bonding.del_connect(connection_del)

    def del_bonding(self, conn, bonding_name):
        connection_name = f'vtel_{bonding_name}'
        bonding = action.IpService(conn)
        connection_detail = bonding.get_connection()
        if connection_detail:
            if self.check_bonding_exist(connection_name, connection_detail):
                slave_list = self.get_slave_via_bonding_name(bonding_name, connection_detail)
                if slave_list:
                    print(f"Started to delete bonding slave configuration of {bonding_name}")
                    for slave in slave_list:
                        bonding.down_connect(slave)
                        if bonding.del_connect(slave):
                            print(f" Success in deleting {slave}")
                        else:
                            print(f" Failed to delete {slave}")
                bonding.down_connect(connection_name)
                print(f"Started to delete configuration of {bonding_name}")
                if bonding.del_connect(connection_name):
                    print(f" Success in deleting {connection_name}")
                else:
                    print(f" Failed to delete {connection_name}")
            else:
                print(f"{bonding_name} not exist.")
        else:
            print("Can't get any configuration")

    def get_slave_via_bonding_name(self, bonding_name, string):
        slave_list = re.findall(f'(vtel_{bonding_name}-slave-\S*)\s+\S+\s+\S+\s+\S+', string)
        return slave_list

    def check_bonding_exist(self, name, string):
        bonding_obj = re.search(f'({name})\s+\S+\s+bond\s+\S+', string)
        if bonding_obj:
            return True

    def get_mode(self, result):
        mode_obj = re.search(r'Bonding Mode:\s+(.+)', result)
        if mode_obj:
            return mode_obj.group(1)

    def check_mode(self, local_mode, conf_mode):
        if conf_mode == 'balance-rr':
            conf_mode = "load balancing (round-robin)"
        if conf_mode in local_mode:
            return True

    def get_speed(self, result):
        re_obj = re.search(r'Speed:\s*(\S+)', result)
        if re_obj:
            return re_obj.group(1)


class NormalIP(object):
    def __init__(self):
        pass

    def create_ip(self, conn, device_list, ip, netmask, dns=None, gateway=None):
        if netmask == None:
            netmask = 24
        elif isinstance(netmask, str):
            try:
                netmask = int(netmask)
                if not 0 <= netmask <= 32:
                    print("Error: the subnet mask must be an integer from 0 to 32.")
                    sys.exit()
            except ValueError:
                print("Error: the subnet mask must be an integer from 0 to 32.")
                sys.exit()
        # print(f"DEBUG: 默认gateway: {gateway}")
        if not utils.check_ip(ip):
            sys.exit()
        if gateway is None:
            gateway = f"{'.'.join(ip.split('.')[:3])}.1"
            # print(f"DEBUG: 默认gateway修改为: {gateway}")
        elif not utils.check_ip(gateway):
            # print("Invalid gateway IP format.")
            sys.exit()
        # print(f"DEBUG: 实际gateway: {gateway}")
        
        # print(f"DEBUG: 默认DNS: {dns}")
        if dns is None:
            dns = "'114.114.114.114 8.8.8.8'"
        else:
            # print(f"DEBUG: 默认DNS修改为: {dns}")
             # 如果有逗号，则根据逗号分割成列表；如果没有逗号，则直接作为单个元素放入列表中
            dns_list = dns.split(' ') if ' ' in dns else [dns]
            for dns_ip in dns_list:
                try:
                    # print(f"cancan dns_ip: {dns_ip}")
                    ipaddress.ip_address(dns_ip)
                except ValueError:
                    # print(f"Error: The format of the DNS address '{dns_ip}' is incorrect.")
                    sys.exit()
            dns = "'"+dns+"'"
            # print(f"DEBUG: 默认DNS修改为: {dns}")
        # print(f"DEBUG: 实际DNS: {dns}")

        normal_ip = action.IpService(conn)
        lc_device_data = normal_ip.get_device_status()
        if not check_device(device_list, lc_device_data):
            sys.exit()
        device = device_list[0]
        connection_detail = normal_ip.get_connection()
        connection = get_device_connection(device, connection_detail)
        print(f"Start to set {ip} on the {device}")
        # gateway = f"{'.'.join(ip.split('.')[:3])}.1"
        normal_ip.set_ip(device, ip, gateway, dns, netmask)
        normal_ip.up_ip_service(f'vtel_{device}')
        print(f"Finish to set {ip} on the {device}")
        if connection:
            print(f"** Clear old configuration on {device}")
            normal_ip.del_connect(connection)

    def del_ip(self, conn, device_list):
        normal_ip = action.IpService(conn)
        lc_device_data = normal_ip.get_device_status()
        if not check_device(device_list, lc_device_data):
            sys.exit()
        device = device_list[0]
        print(f"Start to del IP configuration on the {device}")
        normal_ip.del_connect(f'vtel_{device}')
        connection_detail = normal_ip.get_connection()
        connection = get_device_connection(device, connection_detail)
        if connection:
            print(f"** Clear old configuration of {device}")
            normal_ip.del_connect(connection)
        print(f"Finish to del IP configuration on the {device}")

    def modify_ip(self, conn, device_list, ip, netmask, dns=None, gateway=None):
        
        #if ip:
        #    if not utils.check_ip(ip):
        #        sys.exit()
        # if gateway is None:
        #     gateway = f"{'.'.join(ip.split('.')[:3])}.1"
        # elif not utils.check_ip(gateway):
        #     print("Invalid gateway IP format.")
        #     sys.exit()

        # if dns is None:
        #     dns = "'114.114.114.114 8.8.8.8'"

        normal_ip = action.IpService(conn)
        lc_device_data = normal_ip.get_device_status()
        if not check_device(device_list, lc_device_data):
            sys.exit()
        device = device_list[0]
        connection_name = f'vtel_{device}'
        connection_detail = normal_ip.get_connection()
        if not check_connection(connection_name, connection_detail):
            print(f'IP was not set on the {device}, cannot modify.')
            sys.exit()
        ip_detail = normal_ip.get_device_detail(device)
        lc_ip = get_ip(ip_detail)
        lc_DNS = get_dns(ip_detail)
        # lc_DNS = re.search(r"'(.*?)'", str(lc_DNS)).group(1)
        lc_Gateway = get_gateway(ip_detail)
        lc_netmask = get_netmask(ip_detail)

        b_ip = False
        b_dns = False
        b_gateway = False
        b_netmask = False
        ip_ = ip
        netmask_ = netmask

        if ip is not None:
            if not utils.check_ip(ip):
                sys.exit()
            if ip == lc_ip:
                print("Same IP.")
            else:
                b_ip = True
                print(f"Change {device} IP, {lc_ip} -> {ip}.")
        elif ip is None:
            ip = lc_ip

        if netmask is not None:
            if netmask == lc_netmask:
                print("Same netmask.")
            elif isinstance(netmask, str):
                try:
                    netmask = int(netmask)
                    if not 0 <= netmask <= 32:
                        print("Error: the subnet mask must be an integer from 0 to 32.")
                        sys.exit()
                except ValueError:
                    print("Error: the subnet mask must be an integer from 0 to 32.")
                    sys.exit()
            else:
                b_netmask = True
                print(f"Change {device} Netmask, {lc_netmask} -> {netmask}.")
        elif netmask == None:
            netmask = lc_netmask

        if dns is not None:
            lc_DNS = ' '.join(sorted(lc_DNS))
            dns_ = sorted(dns.split(' '))
            dns_ = ' '.join(dns_)
            if lc_DNS == dns_:
                print("Same dns.")
            else:
                # print(f"DEBUG: 默认DNS修改为: {dns}")
                # 如果有逗号，则根据逗号分割成列表；如果没有逗号，则直接作为单个元素放入列表中
                dns_list = dns.split(' ') if ' ' in dns else [dns]
                for dns_ip in dns_list:
                    try:
                        # print(f"cancan dns_ip: {dns_ip}")
                        ipaddress.ip_address(dns_ip)
                    except ValueError:
                        print(f"Error: The format of the DNS address '{dns_ip}' is incorrect.")
                        sys.exit()
                dns = "'"+ dns +"'"
                # print(f"DEBUG: 默认DNS修改为: {dns}")
                b_dns = True
                print(f"Change {device} DNS, {lc_DNS} -> {dns}.")
            
        if gateway is not None:
            if lc_Gateway == gateway:
                print("Same gateway.")
            else:
                if not utils.check_ip(gateway):
                    print("Invalid gateway IP format.")
                    sys.exit()
                b_gateway = True
                print(f"Change {device} Gateway, {lc_Gateway} -> {gateway}.")

        if b_ip or b_dns or b_gateway or b_netmask:
            normal_ip.modify_normal_ip(device, ip, netmask, gateway, dns)
            normal_ip.up_ip_service(connection_name)
        elif not gateway and not dns and not netmask_ and not ip_:
            print("Please enter at least one content that needs to be modified!")
        else:
            print("Do nothing.") # 属于都存在，但是是重复的 就是 Do nothing. 
        