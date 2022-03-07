import time
import sys

from ssh_authorized import SSHAuthorizeNoMGN
import utils
import action
import timeout_decorator


class Connect():
    """
    通过ssh连接节点，生成连接对象的列表
    """
    list_ssh = []

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, '_instance'):
            Connect._instance = super().__new__(cls)
            Connect._instance.conf_file = utils.ConfFile()
            Connect._instance.cluster = Connect._instance.conf_file.cluster
            Connect.get_ssh_conn(Connect._instance)
        return Connect._instance

    def get_ssh_conn(self):
        ssh = SSHAuthorizeNoMGN()
        local_ip = utils.get_host_ip()
        for node in self.cluster['node']:
            if local_ip == node['public_ip']:
                self.list_ssh.append(None)
            else:
                self.list_ssh.append(ssh.make_connect(node['public_ip'], node['port'], 'root', node['root_password']))


class PacemakerConsole():
    def __init__(self):
        self.conn = Connect()

    def modify_hostname(self):
        hosts_file = []
        for node in self.conn.cluster['node']:
            hosts_file.append({'ip': node['public_ip'], 'hostname': node['hostname']})
        for ssh, node in zip(self.conn.list_ssh, self.conn.cluster['node']):
            executor = action.Host(ssh)
            executor.modify_hostname(node['hostname'])
            executor.modify_hostsfile('127.0.1.1', node['hostname'])
            for host in hosts_file:
                executor.modify_hostsfile(host['ip'], host['hostname'])

    def ssh_conn_build(self):
        ssh = SSHAuthorizeNoMGN()
        ssh.init_cluster_no_mgn('cluster', self.conn.cluster['node'], self.conn.list_ssh)

    def check_hostname(self):
        result_lst = []
        for ssh, node in zip(self.conn.list_ssh, self.conn.cluster['node']):
            result = action.Host(ssh).check_hostname(node['hostname'])
            result_lst.append(result)
        return result_lst

    def check_ssh_authorized(self):
        result_lst = []
        cluster_hosts = [node['hostname'] for node in self.conn.cluster['node']]
        for ssh in self.conn.list_ssh:
            result = action.Host(ssh).check_ssh(cluster_hosts)
            result_lst.append(result)
        return result_lst

    def sync_time(self):
        for ssh in self.conn.list_ssh:
            action.Corosync(ssh).sync_time()

    def corosync_conf_change(self):
        cluster_name = self.conn.conf_file.get_cluster_name()
        bindnetaddr_list = self.conn.conf_file.get_bindnetaddr()
        interface = self.conn.conf_file.get_inferface()
        nodelist = self.conn.conf_file.get_nodelist()

        for ssh in self.conn.list_ssh:
            action.Corosync(ssh).change_corosync_conf(
                cluster_name,
                bindnetaddr_list,
                interface,
                nodelist
            )

    def restart_corosync(self):
        try:
            for ssh in self.conn.list_ssh:
                action.Corosync(ssh).restart_corosync()
        except timeout_decorator.timeout_decorator.TimeoutError:
            print('Restarting corosync service timed out')
            sys.exit()

    def check_corosync(self):
        nodes = [node['hostname'] for node in self.conn.cluster['node']]
        lst_ring_status = []
        lst_cluster_status = []
        lst = []
        times = 3
        for ssh, node in zip(self.conn.list_ssh, self.conn.cluster['node']):
            corosync = action.Corosync(ssh)
            lst_ring_status.append(corosync.check_ring_status(node))
            lst_cluster_status.append(corosync.check_corosync_status(nodes))

        while not all(lst_cluster_status) and times > 0:
            time.sleep(5)
            lst_cluster_status = []
            for ssh, node in zip(self.conn.list_ssh, self.conn.cluster['node']):
                corosync = action.Corosync(ssh)
                lst_cluster_status.append(corosync.check_corosync_status(nodes))
            times -= 1

        for x, y in zip(lst_ring_status, lst_cluster_status):
            if x and y:
                lst.append(True)
            else:
                lst.append(False)

        return lst

    def recover_corosync_conf(self):
        self.modify_cluster_name("debian")
        for ssh in self.conn.list_ssh:
            corosync = action.Corosync(ssh)
            corosync.recover_conf()
            corosync.restart_corosync()

    def modify_cluster_name(self, name=None):
        if not name:
            name = self.conn.conf_file.get_cluster_name()
        pacemaker = action.Pacemaker()
        pacemaker.modify_cluster_name(name)

    def pacmaker_conf_change(self):
        pacemaker = action.Pacemaker()
        pacemaker.modify_policy()
        pacemaker.modify_stickiness()
        pacemaker.modify_stonith_enabled()

    def check_pacemaker(self):
        # cluster_name = self.conn.cluster['cluster'] // cluster name 缺少日期，不进行判断
        pacemaker = action.Pacemaker()
        if pacemaker.check_crm_conf():
            return [True] * len(self.conn.list_ssh)
        else:
            return [False] * len(self.conn.list_ssh)

    def targetcli_conf_change(self):
        for ssh in self.conn.list_ssh:
            targetcli = action.TargetCLI(ssh)
            targetcli.set_auto_add_default_portal()
            targetcli.set_auto_add_mapped_luns()
            targetcli.set_auto_enable_tpgt()

    def check_targetcli(self):
        result_lst = []
        for ssh in self.conn.list_ssh:
            targetcli = action.TargetCLI(ssh)
            result_lst.append(targetcli.check_targetcli_conf())
        return result_lst

    def service_set(self):
        for ssh in self.conn.list_ssh:
            executor = action.ServiceSet(ssh)
            executor.set_disable_drbd()
            executor.set_disable_linstor_controller()
            executor.set_disable_targetctl()
            executor.set_enable_linstor_satellite()
            executor.set_enable_pacemaker()
            executor.set_enable_corosync()

    def check_service(self):
        lst = []
        for ssh in self.conn.list_ssh:
            check_result = []
            executor = action.ServiceSet(ssh)
            check_result.append(executor.check_drbd())
            check_result.append(executor.check_linstor_controller())
            check_result.append(executor.check_linstor_satellite())
            check_result.append(executor.check_pacemaker())
            check_result.append(executor.check_corosync())
            if check_result == ['disable', 'disable', 'enable', 'enable', 'enable']:
                lst.append(True)
            else:
                lst.append(False)
        return lst

    def replace_ra(self):
        other_node = []
        for ssh, node in zip(self.conn.list_ssh, self.conn.cluster['node']):
            executor = action.RA(ssh)
            lst = []
            lst.append(executor.backup_iscsilogicalunit())
            lst.append(executor.backup_iscsitarget())
            if ssh:
                other_node.append(node['hostname'])

        executor = action.RA()
        executor.cp_ra()
        executor.rename_ra()
        for node in other_node:
            executor.scp_ra(node)

    def check_ra(self):
        lst = []

        for ssh in self.conn.list_ssh:
            check_result = []
            executor = action.RA(ssh)
            check_result.append(executor.check_ra_target())
            check_result.append(executor.check_ra_logicalunit())
            if all(check_result):
                lst.append(True)
            else:
                lst.append(False)

        return lst

    def set_ip_on_device(self):
        lst_set = []
        for ssh, node in zip(self.conn.list_ssh, self.conn.cluster['node']):
            ip_service = action.IpService(ssh)
            lst_set.append(ip_service.set_ip(node['private_ip']['device'], node['private_ip']['ip'],
                                             node['private_ip']['gateway']))
        self.up_ip_service()
        print("Finish to set ip")

    def modify_ip_on_device(self):
        lst_modify = []
        for ssh, node in zip(self.conn.list_ssh, self.conn.cluster['node']):
            ip_service = action.IpService(ssh)
            lst_modify.append(ip_service.modify_ip(node['private_ip']['device'], node['private_ip']['ip'],
                                                   node['private_ip']['gateway']))
        self.up_ip_service()
        print("Finish to modify ip")

    def up_ip_service(self):
        lst_up = []
        for ssh, node in zip(self.conn.list_ssh, self.conn.cluster['node']):
            ip_service = action.IpService(ssh)
            lst_up.append(ip_service.up_ip_service(node['private_ip']['device']))

    def clear_crm_res(self, node=None):
        if node:
            for ssh, n in zip(self.conn.list_ssh, self.conn.cluster['node']):
                if node == n['hostname']:
                    pacemaker = action.Pacemaker(ssh)
        else:
            pacemaker = action.Pacemaker()
        pacemaker.clear_crm_res()

    def clear_crm_node(self):
        for ssh, local_node in zip(self.conn.list_ssh, self.conn.cluster['node']):
            pacemaker = action.Pacemaker(ssh)
            pacemaker.restart()
            time.sleep(2)
            for node in self.conn.cluster['node']:
                if local_node['hostname'] != node['hostname']:
                    pacemaker.clear_crm_node(node['hostname'])


class LinstorConsole():
    def __init__(self):
        self.conn = Connect()

    def create_conf_file(self):
        ips = ",".join([node['public_ip'] for node in self.conn.cluster['node']])
        for ssh in self.conn.list_ssh:
            linstor = action.Linstor(ssh)
            linstor.create_conf(ips)

        if self.conn.list_ssh:
            action.Linstor(self.conn.list_ssh[0]).restart_controller()

    def create_nodes(self):
        for ssh, node in zip(self.conn.list_ssh, self.conn.cluster['node']):
            linstor = action.Linstor(ssh)
            linstor.create_node(node['hostname'], node['public_ip'])

    def create_pools(self, sp):
        # 待测试 以及确定thinlv创建时用到的lvm资源的格式。
        for ssh, node in zip(self.conn.list_ssh, self.conn.cluster['node']):
            linstor = action.Linstor(ssh)
            vol = node['lvm_device'].split("/")
            if len(vol) == 1:
                linstor.create_lvm_sp(node['hostname'], node['lvm_device'], sp)
            elif len(vol) == 2:
                linstor.create_lvmthin_sp(node['hostname'], node['lvm_device'], sp)

    # HA controller配置
    def build_ha_controller(self, sp):
        backup_path = self.conn.cluster['backup_path']
        ha = action.HALinstorController()
        if not ha.linstor_is_conn():
            print('LINSTOR connection refused')
            sys.exit()

        node_list = [node['hostname'] for node in self.conn.cluster['node']]
        if not ha.pool_is_exist(node_list, sp):
            print(f'storage-pool：{sp} does not exist')
            sys.exit()

        ha.create_rd('linstordb')
        ha.create_vd('linstordb', '250M')

        for node in self.conn.cluster['node']:
            ha.create_res('linstordb', node['hostname'], sp)

        for ssh in self.conn.list_ssh:
            ha = action.HALinstorController(ssh)
            if ha.is_active_controller():
                ha.stop_controller()
                ha.backup_linstor(backup_path)  # 要放置备份文件的路径（文件夹）
                ha.move_database(backup_path)
                ha.add_linstordb_to_pacemaker(len(self.conn.cluster['node']))
            ha.modify_satellite_service()  # linstor satellite systemd 配置

    def check_ha_controller(self, timeout=30):
        ha = action.HALinstorController()
        node_list = [node['hostname'] for node in self.conn.cluster['node']]
        t_beginning = time.time()

        while True:
            if ha.check_linstor_controller(node_list):
                break
            seconds_passed = time.time() - t_beginning
            if timeout and seconds_passed > timeout:
                print("Linstor controller status error")
                return False
            time.sleep(1)

        for ssh in self.conn.list_ssh:
            ha = action.HALinstorController(ssh)
            service = action.ServiceSet(ssh)
            if service.check_linstor_satellite() != 'enable':
                print('LINSTOR Satellite Service is not "enable".')
                return False
            if not ha.check_satellite_settings():
                print("File linstor-satellite.service modification failed")
                return False

        return True

    def backup_linstordb(self, timeout=30):
        linstordb_path = '/var/lib/linstor'
        if self.conn.cluster['backup_path'].endswith('/'):
            backup_path = f"{self.conn.cluster['backup_path']}backup_{time.strftime('%Y%m%d%H%M')}"
        else:
            backup_path = f"{self.conn.cluster['backup_path']}/backup_{time.strftime('%Y%m%d%H%M')}"

        t_beginning = time.time()
        while True:
            for ssh in self.conn.list_ssh:
                ha = action.HALinstorController(ssh)
                if ha.is_active_controller():
                    if ha.check_linstor_file(linstordb_path):
                        ha.backup_linstor(backup_path)
                if ha.check_linstor_file(f'{backup_path}/linstor'):
                    return True
            seconds_passed = time.time() - t_beginning
            if timeout and seconds_passed > timeout:
                return False
            time.sleep(1)

    # TODO Unused function
    # def destroy_linstordb(self):
    #     ha = action.HALinstorController()
    #     if not ha.linstor_is_conn():
    #         print('LINSTOR connection refused')
    #         sys.exit()
    #
    #     for ssh in self.conn.list_ssh:
    #         ha = action.HALinstorController(ssh)
    #         list_lv = ha.get_linstordb_lv()
    #         ha.umount_lv(list_lv)
    #         ha.secondary_drbd('linstordb')
    #         ha.delete_rd('linstordb') # 一般只需在一个节点上执行一次
    #         ha.remove_lv(list_lv)

    def clear_linstor_conf(self):
        for ssh in self.conn.list_ssh:
            handler = action.Linstor(ssh)
            handler.clear()

    def restart_linstor(self):
        for ssh in self.conn.list_ssh:
            handler = action.Linstor(ssh)
            handler.restart_satellite()

        handler = action.Linstor()
        handler.restart_controller()


class VersaSDSSoftConsole():
    def __init__(self):
        self.conn = Connect()

    def apt_update(self):
        for ssh in self.conn.list_ssh:
            handler = action.DRBD(ssh)
            handler.apt_update()

    def install_spc(self):
        result_lst = []
        for ssh in self.conn.list_ssh:
            handler = action.DRBD(ssh)
            result_lst.append(handler.install_spc())
        return result_lst

    def install_drbd(self):
        for ssh in self.conn.list_ssh:
            handler = action.DRBD(ssh)
            handler.install_drbd()

    def uninstall_drbd(self):
        result_lst = []
        for ssh in self.conn.list_ssh:
            handler = action.DRBD(ssh)
            handler.uninstall()
            result_lst.append(handler.uninstall())
        return result_lst

    def install_linstor(self):
        for ssh in self.conn.list_ssh:
            handler = action.Linstor(ssh)
            handler.install()

    def uninstall_linstor(self):
        for ssh in self.conn.list_ssh:
            handler = action.Linstor(ssh)
            handler.uninstall()

    def install_lvm2(self):
        for ssh in self.conn.list_ssh:
            handler = action.LVM(ssh)
            handler.install()

    def uninstall_lvm2(self):
        for ssh in self.conn.list_ssh:
            handler = action.LVM(ssh)
            handler.uninstall()

    def install_pacemaker(self):
        for ssh in self.conn.list_ssh:
            handler = action.Pacemaker(ssh)
            handler.install()

    def uninstall_pacemaker(self):
        for ssh in self.conn.list_ssh:
            handler = action.Pacemaker(ssh)
            handler.uninstall()

    def install_targetcli(self):
        for ssh in self.conn.list_ssh:
            handler = action.TargetCLI(ssh)
            handler.install()

    def uninstall_targetcli(self):
        for ssh in self.conn.list_ssh:
            handler = action.TargetCLI(ssh)
            handler.uninstall()

    def get_all_service_status(self):
        result = []
        for ssh in self.conn.list_ssh:
            service = action.ServiceSet(ssh)
            host = action.Host(ssh)
            result.append(host.get_hostname())
            result.append(service.check_pacemaker())
            result.append(service.check_corosync())
            result.append(service.check_linstor_satellite())
            result.append(service.check_drbd())
            result.append(service.check_linstor_controller())

        for i in range(0, len(result), 6):
            yield result[i:i + 6]

    def get_version(self, *args):
        """
        参数输入要获取版本信息的软件，支持sysos，syskernel，drbd，linstor，targetcli，pacemaker，corosync
        返回数据的顺序与参数顺序一致
        :param args:
        :return:
        """
        result = []
        for ssh in self.conn.list_ssh:
            host = action.Host(ssh)
            result.append(host.get_hostname())
            for soft in args:
                if soft == 'sysos':
                    result.append(host.get_sys_version())
                elif soft == 'syskernel':
                    result.append(host.get_kernel_version())
                elif soft == 'drbd':
                    drbd = action.DRBD(ssh)
                    result.append(drbd.get_version())
                elif soft == 'linstor':
                    linstor = action.Linstor(ssh)
                    result.append(linstor.get_version())
                elif soft == 'targetcli':
                    targetcli = action.TargetCLI(ssh)
                    result.append(targetcli.get_version())
                elif soft == 'pacemaker':
                    pacemaker = action.Pacemaker(ssh)
                    result.append(pacemaker.get_version())
                elif soft == 'corosync':
                    corosync = action.Corosync(ssh)
                    result.append(corosync.get_version())

        for i in range(0, len(result), len(args) + 1):
            yield result[i:i + len(args) + 1]


class LVMConsole():
    def __init__(self):
        self.conn = Connect()

    def create_dirver_pool(self):
        pv_list = []
        for ssh, node in zip(self.conn.list_ssh, self.conn.cluster['node']):
            lvm = action.LVM(ssh)
            pv_list.append(lvm.pv_create(node['pool_disk']))
        for r, node in zip(pv_list, self.conn.cluster['node']):
            if not r:
                print(f"{node['pool_disk']} is not on {node['hostname']} or it has been used")
                sys.exit()

        for ssh, node in zip(self.conn.list_ssh, self.conn.cluster['node']):
            lvm = action.LVM(ssh)
            vol = node['lvm_device'].split("/")
            if len(vol) == 1:
                vg = vol[0]
                lvm.vg_create(vg, node['pool_disk'])
            elif len(vol) == 2:
                vg, lv = vol
                lvm.vg_create(vg, node['pool_disk'])
                lvm.thinpool_create(vg, lv)

    def remove_vg(self):
        for ssh, node in zip(self.conn.list_ssh, self.conn.cluster['node']):
            lvm = action.LVM(ssh)
            vol = node['lvm_device'].split("/")
            vg = vol[0]
            result = lvm.remove_vg(vg)
            if result:
                print(result)
