import time
import sys
import utils
import action
import timeout_decorator


class Connect(object):
    """
    通过ssh连接节点，生成连接对象的列表
    """
    list_ssh = []
    list_hostname = []

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, '_instance'):
            Connect._instance = super().__new__(cls)
            Connect._instance.conf_file = utils.ConfFile()
            Connect._instance.cluster = Connect._instance.conf_file.config
            Connect.get_ssh_conn(Connect._instance)
            Connect.get_hostname_list(Connect._instance)
        return Connect._instance

    def get_ssh_conn(self):
        local_ip = utils.get_host_ip()
        for node in self.cluster['node']:
            if local_ip == node['public_ip']:
                self.list_ssh.append(None)
            else:
                ssh_conn = utils.SSHConn(node['public_ip'], node['port'], 'root', node['root_password'])
                self.list_ssh.append(ssh_conn)

    def get_hostname_list(self):
        for ssh in self.list_ssh:
            host = action.Host(ssh)
            hostname = host.get_hostname()
            self.list_hostname.append(hostname)


class PacemakerConsole(object):
    def __init__(self):
        self.conn = Connect()
        self.default_ssh = None if None in self.conn.list_ssh else self.conn.list_ssh[0]

    # TODO ssh, remove
    # def ssh_conn_build(self):
    #     ssh = SSHAuthorizeNoMGN()
    #     ssh.init_cluster_no_mgn('cluster', self.conn.cluster['node'], self.conn.list_ssh)

    # TODO ssh, remove
    # def check_ssh_authorized(self):
    #     result_lst = []
    #     cluster_hosts = [node['hostname'] for node in self.conn.cluster['node']]
    #     for ssh in self.conn.list_ssh:
    #         result = action.Host(ssh).check_ssh(cluster_hosts)
    #         result_lst.append(result)
    #     return result_lst

    def sync_time(self):
        for ssh in self.conn.list_ssh:
            action.Corosync(ssh).sync_time()

    def corosync_conf_change(self):
        cluster_name = self.conn.conf_file.get_cluster_name()
        bindnetaddr_list = self.conn.conf_file.get_bindnetaddr()
        interface = self.conn.conf_file.get_interface()
        nodelist = self.conn.conf_file.get_nodelist(self.conn.list_hostname)

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
        nodes = self.conn.list_hostname
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
        pacemaker = action.Pacemaker(self.default_ssh)
        pacemaker.modify_cluster_name(name)

    def pacmaker_conf_change(self):
        pacemaker = action.Pacemaker(self.default_ssh)
        if len(self.conn.cluster['node']) >= 3:
            pacemaker.modify_policy()
        else:
            pacemaker.modify_policy("ignore")
        pacemaker.modify_stickiness()
        pacemaker.modify_stonith_enabled()

    def check_pacemaker(self):
        # cluster_name = self.conn.cluster['cluster'] // cluster name 缺少日期，不进行判断
        pacemaker = action.Pacemaker(self.default_ssh)
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
            check_result.append(executor.check_status("drbd"))
            check_result.append(executor.check_status("linstor-controller"))
            check_result.append(executor.check_status("linstor-satellite"))
            check_result.append(executor.check_status("pacemaker"))
            check_result.append(executor.check_status("corosync"))
            if check_result == ['disabled', 'disabled', 'enabled', 'enabled', 'enabled']:
                lst.append(True)
            else:
                lst.append(False)
        return lst

    # TODO get RA from FreeNAS
    def replace_ra(self):
        other_node = []
        for ssh, hostname in zip(self.conn.list_ssh, self.conn.list_hostname):
            executor = action.RA(ssh)
            lst = []
            lst.append(executor.backup_iscsilogicalunit())
            lst.append(executor.backup_iscsitarget())
            if ssh:
                other_node.append(hostname)
        executor = action.RA(self.default_ssh)
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

    def clear_crm_res(self, node=None):
        if node:
            for ssh, hostname in zip(self.conn.list_ssh, self.conn.list_hostname):
                if node == hostname:
                    pacemaker = action.Pacemaker(ssh)
        else:
            pacemaker = action.Pacemaker(self.default_ssh)
        pacemaker.clear_crm_res()

    def clear_crm_node(self):
        for ssh, local_hostname in zip(self.conn.list_ssh, self.conn.list_hostname):
            pacemaker = action.Pacemaker(ssh)
            pacemaker.restart()
            time.sleep(2)
            for hostname in self.conn.list_hostname:
                if local_hostname != hostname:
                    pacemaker.clear_crm_node(hostname)

    def set_drbd_attr(self):
        pacemaker = action.Pacemaker(self.default_ssh)
        pacemaker.config_drbd_attr()


class LinstorConsole(object):
    def __init__(self):
        self.conn = Connect()
        self.default_ssh = None if None in self.conn.list_ssh else self.conn.list_ssh[0]

    def create_conf_file(self):
        ips = ",".join([node['private_ip'] for node in self.conn.cluster['node']])
        ip_string = f"{self.conn.cluster['vip']},{ips}"
        for ssh in self.conn.list_ssh:
            linstor = action.Linstor(ssh)
            linstor.create_conf(ip_string)
        self.start_linstor('start')

    def create_nodes(self):
        for ssh, hostname, node in zip(self.conn.list_ssh, self.conn.list_hostname, self.conn.cluster['node']):
            linstor = action.Linstor(ssh)
            linstor.create_node(hostname, node['private_ip'])

    def create_pools(self, sp):
        # 待测试 以及确定thinlv创建时用到的lvm资源的格式。
        for ssh, hostname, node in zip(self.conn.list_ssh, self.conn.list_hostname, self.conn.cluster['node']):
            linstor = action.Linstor(ssh)
            vol = node['lvm_device'].split("/")
            if len(vol) == 1:
                linstor.create_lvm_sp(hostname, node['lvm_device'], sp)
            elif len(vol) == 2:
                linstor.create_lvmthin_sp(hostname, node['lvm_device'], sp)

    def build_ha_controller(self, sp):
        """HA controller配置"""
        backup_path = self.conn.cluster['backup_path']
        ha = action.HALinstorController(self.default_ssh)
        if not ha.linstor_is_conn():
            print('LINSTOR connection refused')
            sys.exit()

        node_list = self.conn.list_hostname
        if not ha.pool_is_exist(node_list, sp):
            print(f'storage-pool：{sp} does not exist')
            sys.exit()

        ha.create_rd('linstordb')
        ha.create_vd('linstordb', '250M')

        for hostname in self.conn.list_hostname:
            ha.create_res('linstordb', hostname, sp)

        for ssh in self.conn.list_ssh:
            ha_controller = action.HALinstorController(ssh)
            if ha_controller.is_active_controller():
                ha_controller.stop_controller()
                time.sleep(3)
                ha_controller.backup_linstor(backup_path)  # 要放置备份文件的路径（文件夹）
                ha_controller.move_database(backup_path)

        ha.add_linstordb_to_pacemaker(len(self.conn.cluster['node']))
        self.set_linstor_satellite_systemd()
        self.set_controller_vip()

    def set_controller_vip(self):
        ha = action.Pacemaker(self.default_ssh)
        ha.set_vip(self.conn.cluster['vip'])
        ha.colocation_vip_controller()

    def set_linstor_satellite_systemd(self):
        for ssh in self.conn.list_ssh:
            ha_controller = action.HALinstorController(ssh)
            ha_controller.modify_satellite_service()  # linstor satellite systemd 配置

    def check_ha_controller(self, timeout=120):
        ha = action.HALinstorController(self.default_ssh)

        node_list = self.conn.list_hostname
        t_beginning = time.time()

        while True:
            if ha.check_linstor_controller(node_list):
                break
            seconds_passed = time.time() - t_beginning
            if timeout and seconds_passed > timeout:
                print("Linstor controller status error")
                return False
            time.sleep(2)

        for ssh in self.conn.list_ssh:
            ha = action.HALinstorController(ssh)
            service = action.ServiceSet(ssh)
            if service.check_status("linstor-satellite") != 'enabled':
                print('LINSTOR Satellite Service is not "enabled".')
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

    def start_linstor(self, status):
        for ssh in self.conn.list_ssh:
            handler = action.Linstor(ssh)
            handler.start_satellite(status)
        handler = action.Linstor(self.default_ssh)
        handler.start_controller(status)


class VersaSDSSoftConsole(object):
    def __init__(self):
        self.conn = Connect()

    def apt_update(self):
        for ssh in self.conn.list_ssh:
            handler = action.Host(ssh)
            handler.apt_update()

    def replace_sources(self):
        for ssh in self.conn.list_ssh:
            handler = action.Host(ssh)
            handler.replace_sources()

    def replace_linbit_sources(self):
        for ssh in self.conn.list_ssh:
            handler = action.Host(ssh)
            handler.replace_linbit_sources()

    def recovery_linbit_sources(self):
        for ssh in self.conn.list_ssh:
            handler = action.Host(ssh)
            handler.recovery_linbit_sources()

    def bak_sources_files(self):
        for ssh in self.conn.list_ssh:
            handler = action.Host(ssh)
            file_string = handler.get_sources_list()
            if file_string:
                files_list = file_string.split("\n")
                for file in files_list:
                    if file:
                        handler.bak_sources_list(file)

    # TODO: considered add this function
    def recovery_sources(self):
        print("recovery_source")

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
            result.append(service.check_status("drbd"))
            result.append(service.check_status("linstor-satellite"))
            result.append(service.check_status("linstor-controller"))
            result.append(service.check_status("pacemaker"))
            result.append(service.check_status("corosync"))
            result.append(service.check_status("rtslib-fb-targetctl"))

        for i in range(0, len(result), 7):
            yield result[i:i + 7]

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


class LVMConsole(object):
    def __init__(self):
        self.conn = Connect()

    def create_dirver_pool(self):
        pv_list = []
        for ssh, node in zip(self.conn.list_ssh, self.conn.cluster['node']):
            lvm = action.LVM(ssh)
            pv_list.append(lvm.pv_create(node['pool_disk']))
        for r, hostname in zip(pv_list, self.conn.list_hostname):
            if not r:
                print(f"{r} is not on {hostname} or it has been used")
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
