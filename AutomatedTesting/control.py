import sys
import utils
import action
import gevent
import threading
import time
import ctypes
import inspect
import send_email as semail


def _async_raise(tid, exctype):
    """raises the exception, performs cleanup if needed"""
    utils.prt_log('', f"Stop thread ...", 0)
    tid = ctypes.c_long(tid)
    if not inspect.isclass(exctype):
        exctype = type(exctype)
    res = ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, ctypes.py_object(exctype))
    if res == 0:
        print("invalid thread id")
        # raise ValueError("invalid thread id")
    elif res != 1:
        # """if it returns a number greater than one, you're in trouble,
        # and you should call it again with exc=NULL to revert the effect"""
        ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, None)
        print("PyThreadState_SetAsyncExc failed")
        # raise SystemError("PyThreadState_SetAsyncExc failed")


def stop_thread(thread):
    _async_raise(thread.ident, SystemExit)


def get_crm_status_by_type(conn, result, resource, type):
    if result:
        if type in ['IPaddr2', 'iSCSITarget', 'portblock', 'iSCSILogicalUnit']:
            re_string = f'{resource}\s*\(ocf::heartbeat:{type}\):\s*(\w*)\s*(\w*)?'
            re_result = utils.re_search(conn, re_string, result, "groups")
            return re_result
        if type == 'FailedActions':
            re_string = "Failed Actions:\s*.*\*\s\w*\son\s(\S*)\s'(.*)'\s.*exitreason='(.*)',\s*.*"
            re_result = utils.re_search(conn, re_string, result, "group")
            return re_result
        if type == 'AllLUN':
            re_string = f'(\S+)\s*\(ocf::heartbeat:iSCSILogicalUnit\):\s*(\w*)\s*(\w*)?'
            re_result = utils.re_findall(conn, re_string, result)
            return re_result


def check_drbd_status(conn, result, resource):
    re_stand_alone = f'connection:StandAlone'
    re_string = f'{resource}\s*role:(\w+).*\s*disk:(\w+)'
    # re_peer_string = '\S+\s*role:(\w+).*\s*peer-disk:(\w+)'
    if result:
        re_stand_alone_result = utils.re_search(conn, re_stand_alone, result, "bool")
        if re_stand_alone_result:
            return 'StandAlone'
        re_result = utils.re_search(conn, re_string, result, "groups")
        return re_result


def check_drbd_no_quorum(conn, result):
    re_string = 'quorum:no'
    if result:
        re_result = utils.re_search(conn, re_string, result)
        return re_result


def check_drbd_conns_status(conn, result):
    re_string = r'([a-zA-Z0-9_-]+).*\d+\s*\|\s*[a-zA-Z]*\s*\|\s*([a-zA-Z0-9()]*)\s*\|\s*([a-zA-Z]*)\s*\|'
    if result:
        re_result = utils.re_findall(conn, re_string, result)
        return re_result


def get_dd_pid(conn, device, result):
    re_string = f'\w*\s*(\d+)\s*.*dd if=/dev/urandom of={device} oflag=direct status=progress'
    re_result = utils.re_search(conn, re_string, result, "groups")
    if re_result:
        return re_result[0]


def kill_dd(conn, device):
    dd_node = action.RWData(conn)
    result = dd_node.get_dd()
    pid = get_dd_pid(conn, device, result)
    if pid:
        dd_node.kill_dd(pid)
        utils.prt_log(conn, f"Kill dd on {utils.get_global_dict_value(conn)}.", 0)
    else:
        utils.prt_log(conn, f"dd operation had been finished.", 0)


class Connect(object):
    """
    通过ssh连接节点，生成连接对象的列表
    """
    list_vplx_ssh = []

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, '_instance'):
            Connect._instance = super().__new__(cls)
            Connect._instance.config = args[0]
            Connect.get_ssh_conn(Connect._instance)
        return Connect._instance

    def get_ssh_conn(self):
        local_ip = utils.get_host_ip()
        vplx_configs = self.config.get_vplx_configs()
        username = "root"
        for vplx_config in vplx_configs:
            if "username" in vplx_config.keys():
                if vplx_config['username'] is not None:
                    username = vplx_config['username']
            if local_ip == vplx_config['public_ip']:
                self.list_vplx_ssh.append(None)
                utils.set_global_dict_value(None, vplx_config['public_ip'])
            else:
                ssh_conn = utils.SSHConn(vplx_config['public_ip'], vplx_config['port'], username,
                                         vplx_config['password'])
                self.list_vplx_ssh.append(ssh_conn)
                utils.set_global_dict_value(ssh_conn, vplx_config['public_ip'])


class QuorumAutoTest(object):
    def __init__(self, config):
        self.config = config
        self.email = semail.Email(config)
        self.conn = Connect(self.config)
        self.vplx_configs = self.config.get_vplx_configs()
        self.node_list = [vplx_config["hostname"] for vplx_config in self.vplx_configs]
        self.skip = False

    # def ssh_conn_build(self):
    #     print("Start to build ssh connect")
    #     ssh = SSHAuthorizeNoMGN()
    #     ssh.init_cluster_no_mgn('versaplx', self.vplx_configs, self.conn.list_vplx_ssh)

    # def install_software(self):
    #     lst_update = []
    #     lst_install_spc = []
    #     lst_install_drbd = []
    #     lst_install_linstor = []
    #     for vplx_conn in self.conn.list_vplx_ssh:
    #         install_obj = action.InstallSoftware(vplx_conn)
    #         lst_update.append(gevent.spawn(install_obj.update_apt))
    #         lst_install_spc.append(gevent.spawn(install_obj.install_spc))
    #         lst_install_drbd.append(gevent.spawn(install_obj.install_drbd))
    #         lst_install_linstor.append(
    #             gevent.spawn(install_obj.install_software, "linstor-controller linstor-satellite linstor-client"))
    #     gevent.joinall(lst_update)
    #     gevent.joinall(lst_install_spc)
    #     gevent.joinall(lst_install_drbd)
    #     gevent.joinall(lst_install_linstor)

    def get_sp(self):
        sp = "sp_quorum"
        sp_list = []
        for vplx_config in self.vplx_configs:
            if "sp" in vplx_config.keys():
                sp_list.append(vplx_config["sp"])
        if len(sp_list) == 3 and len(set(sp_list)) == 1:
            self.skip = True
            sp = sp_list[0]
        return sp

    def test_drbd_quorum(self):
        if len(self.conn.list_vplx_ssh) != 3:
            utils.prt_log('', f"Please make sure there are three nodes for this test", 2)
        sp = self.get_sp()
        resource = "res_quorum"
        test_times = self.config.get_test_times()
        use_case = self.config.get_use_case()

        vtel_conn = None
        if None not in self.conn.list_vplx_ssh:
            vtel_conn = self.conn.list_vplx_ssh[0]
        self.clean_dmesg()
        # utils.prt_log(None, f"Start to install software ...", 0)
        # self.install_software()
        # TODO 可优化，使用 LINSTOR API 代码
        install_obj = action.InstallSoftware(vtel_conn)
        install_obj.update_pip()
        install_obj.install_vplx()

        self.create_linstor_resource(vtel_conn, sp, resource)

        stor_obj = action.Stor(vtel_conn)
        utils.prt_log('', f"Check DRBD quorum...", 0)
        if not stor_obj.check_drbd_quorum(resource):
            utils.prt_log(vtel_conn, f'Abnormal quorum status of {resource}', 1)
            self.get_log()
            self.delete_linstor_resource(vtel_conn, sp, resource)
            utils.prt_log('', f"Finished to collect dmesg and exit testing ...", 2)
        if not self.cycle_check_drbd_status(resource):
            self.get_log()
            self.delete_linstor_resource(vtel_conn, sp, resource)
            utils.prt_log('', f"Finished to collect dmesg and exit testing ...", 2)
        device_name = stor_obj.get_device_name(resource)
        device_list = [vplx_config["private_ip"]["device"] for vplx_config in self.vplx_configs]
        if use_case == 1:
            test_conn_list = zip(self.conn.list_vplx_ssh, self.conn.list_vplx_ssh[1:] + self.conn.list_vplx_ssh[:1])
            mode_total_test_times = 3
        if use_case == 2:
            test_conn_list = [(self.conn.list_vplx_ssh[0], self.conn.list_vplx_ssh[1]),
                              (self.conn.list_vplx_ssh[2], self.conn.list_vplx_ssh[1])]
            mode_total_test_times = 2
            device_list.pop(1)
        mode_times = 0
        total_times = mode_total_test_times * test_times
        for conn_list in test_conn_list:
            device = device_list.pop(0)
            node_a = utils.get_global_dict_value(conn_list[0])
            node_b = utils.get_global_dict_value(conn_list[1])
            stor_a = action.Stor(conn_list[0])
            stor_b = action.Stor(conn_list[1])
            ip_a = action.IpService(conn_list[0])
            dd_a = action.RWData(conn_list[0])
            dd_b = action.RWData(conn_list[1])
            mode_str = f"\nMode:({node_a}, {node_b}). Mode expect test times: {mode_total_test_times}."
            utils.prt_log('', mode_str, 0)
            for i in range(test_times):
                times = utils.get_times() + 1
                utils.set_times(times)
                utils.prt_log('',
                              f"\n{mode_str} test times: {i + 1}. Current test times: {times}. Expect test times: {total_times}.",
                              0)
                stor_a.primary_drbd(resource)
                utils.prt_log(conn_list[0], f"Primary resource on {node_a} ...", 0)
                time.sleep(3)

                thread1 = threading.Thread(target=dd_a.dd_operation,
                                           args=(device_name,), name="thread1")
                thread2 = threading.Thread(target=ip_a.down_device, args=(device,), name="thread2")
                thread3 = threading.Thread(target=dd_b.dd_operation,
                                           args=(device_name,), name="thread3")
                thread4 = threading.Thread(target=stor_a.secondary_drbd, args=(resource,), name="thread4")
                thread1.start()
                time.sleep(20)
                thread2.start()
                utils.prt_log(conn_list[0], f"Down {device} on {node_a}  ...", 0)
                thread2.join()
                time.sleep(3)
                stor_b.primary_drbd(resource)
                utils.prt_log(conn_list[1], f"Primary resource on {node_b} ...", 0)
                time.sleep(3)
                thread3.start()
                time.sleep(10)
                resource_status_result = stor_a.get_drbd_status(resource)
                if check_drbd_no_quorum(conn_list[0], resource_status_result):
                    kill_dd(conn_list[0], device_name)
                    if thread1.is_alive():
                        stop_thread(thread1)
                else:
                    utils.prt_log(conn_list[0], f"Configuration 'quorum:no' not exist ...", 0)
                    self.get_log()
                    self.email.send_autotest_mail()
                    utils.prt_log('', f"Finished to collect dmesg and exit testing ...", 2)
                thread4.start()
                utils.prt_log(conn_list[0], f"Secondary resource on {node_a} ...", 0)
                thread4.join()
                thread1.join()
                time.sleep(10)
                kill_dd(conn_list[1], device_name)
                time.sleep(5)
                if thread3.is_alive():
                    stop_thread(thread3)
                    time.sleep(5)
                thread3.join()
                ip_a.up_device(device)
                utils.prt_log(conn_list[0], f"Up {device} on {node_a}  ...", 0)
                ip_a.netplan_apply()
                time.sleep(5)
                if not self.cycle_check_drbd_status(resource):
                    self.get_log()
                    stor_b.secondary_drbd(resource)
                    self.delete_linstor_resource(vtel_conn, sp, resource)
                    self.email.send_autotest_mail()
                    utils.prt_log('', f"Finished to collect dmesg and exit testing ...", 2)
                stor_b.secondary_drbd(resource)
                utils.prt_log(conn_list[1], f"Secondary resource on {node_b} ...", 0)
                if times == mode_times * test_times + 1:
                    self.get_log()
                    mode_times = mode_times + 1
                utils.prt_log('', f"Success. Wait 3 minutes.", 0)
                time.sleep(180)

        self.delete_linstor_resource(vtel_conn, sp, resource)
        self.email.send_autotest_mail()

    def create_linstor_resource(self, conn, sp, resource):
        size = self.config.get_resource_size()
        use_case = self.config.get_use_case()

        stor_obj = action.Stor(conn)
        if not self.skip:
            utils.prt_log(conn, f"Start to create node ...", 0)
            for vplx_config in self.vplx_configs:
                stor_obj.create_node(vplx_config["hostname"], vplx_config["private_ip"]["ip"])
            utils.prt_log(conn, f"Start to create storagepool {sp} ...", 0)
            for vplx_config in self.vplx_configs:
                stor_obj.create_sp(vplx_config["hostname"], sp, vplx_config["lvm_device"])
        diskful_node_list = self.node_list[:]
        utils.prt_log(conn, f"Start to create resource {resource} ...", 0)
        if use_case == 1:
            diskless_node = diskful_node_list.pop()
            stor_obj.create_diskful_resource(diskful_node_list, sp, size, resource)
            stor_obj.create_diskless_resource(diskless_node, resource)
        if use_case == 2:
            stor_obj.create_diskful_resource(diskful_node_list, sp, size, resource)
        time.sleep(15)

    def delete_linstor_resource(self, conn, sp, resource):
        stor_obj = action.Stor(conn)
        utils.prt_log(conn, f"Start to delete resource {resource} ...", 0)
        stor_obj.delete_resource(resource)
        time.sleep(3)
        if not self.skip:
            utils.prt_log(conn, f"Start to delete storagepool {sp} ...", 0)
            for node in self.node_list:
                stor_obj.delete_sp(node, sp)
            time.sleep(3)
            utils.prt_log(conn, f"Start to delete node ...", 0)
            for node in self.node_list:
                stor_obj.delete_node(node)

    def get_log(self):
        tmp_path = "/tmp/dmesg"
        lst_get_log = []
        lst_mkdir = []
        lst_download = []
        lst_del_log = []
        log_path = self.config.get_log_path()
        utils.prt_log('', f"Start to collect dmesg file ...", 0)
        for conn in self.conn.list_vplx_ssh:
            debug_log = action.DebugLog(conn)
            lst_mkdir.append(gevent.spawn(debug_log.mkdir_log_dir, tmp_path))
            lst_get_log.append(gevent.spawn(debug_log.get_dmesg_file, tmp_path))
            lst_download.append(gevent.spawn(debug_log.download_log, tmp_path, log_path))
            lst_del_log.append(gevent.spawn(debug_log.rm_log_dir, tmp_path))
        gevent.joinall(lst_get_log)
        gevent.joinall(lst_mkdir)
        gevent.joinall(lst_download)
        gevent.joinall(lst_mkdir)
        utils.prt_log('', f"Finished to collect dmesg file ...", 0)

    def clean_dmesg(self):
        lst_clean_dmesg = []
        for conn in self.conn.list_vplx_ssh:
            debug_log = action.DebugLog(conn)
            lst_clean_dmesg.append(gevent.spawn(debug_log.clear_dmesg))
        gevent.joinall(lst_clean_dmesg)

    def check_drbd_status(self, resource):
        resource_status_list = []
        for vplx_conn in self.conn.list_vplx_ssh:
            stor_obj = action.Stor(vplx_conn)
            resource_status_result = stor_obj.get_drbd_status(resource)
            resource_status = check_drbd_status(vplx_conn, resource_status_result, resource)
            resource_status_list.append(resource_status)
        return resource_status_list

    def cycle_check_drbd_status(self, resource):
        utils.prt_log('', f"Check DRBD status...", 0)
        flag = False
        for i in range(100):
            flag = True
            resource_status_list = self.check_drbd_status(resource)
            for resource_status in resource_status_list:
                if resource_status == 'StandAlone':
                    utils.prt_log('',
                                  f'{time.strftime("%Y/%m/%d %H:%M:%S", time.localtime())} --- Connection is StandAlone',
                                  0)
                    return False
                if resource_status[1] != "UpToDate" and resource_status[1] != "Diskless":
                    status = resource_status[1]
                    time.sleep(180)
                    flag = False
            if flag is True:
                break
        if flag is False:
            utils.prt_log('', f'{time.strftime("%Y/%m/%d %H:%M:%S", time.localtime())} --- Resource status: {status}',
                          0)
        return flag


class IscsiTest(object):
    def __init__(self, config):
        self.config = config
        self.email = semail.Email(config)
        self.conn = Connect(self.config)
        self.vplx_configs = self.config.get_vplx_configs()
        self.node_list = [vplx_config["hostname"] for vplx_config in self.vplx_configs]
        self.lun_list = []

    def test_drbd_in_used(self):
        start_time = time.strftime("%Y/%m/%d %H:%M:%S", time.localtime())
        if len(self.conn.list_vplx_ssh) != 3:
            utils.prt_log('', f"Please make sure there are three nodes for this test", 2)
        test_times = self.config.get_test_times()
        device = self.config.get_device()
        target = self.config.get_target()
        resource = self.config.get_resource()
        ip_obj = action.IpService(self.conn.list_vplx_ssh[0])
        ip_node = utils.get_global_dict_value(self.conn.list_vplx_ssh[0])
        for i in range(test_times):
            i = i + 1
            utils.set_times(i)
            print(f"Number of test times --- {i}")
            if not self.check_target_lun_status(target, resource,
                                                self.conn.list_vplx_ssh[0]):
                self.collect_crm_report_file(start_time, self.conn.list_vplx_ssh[0])
                self.email.send_autotest_mail()
                utils.prt_log('', f"Finished to collect crm_report and exit testing ...", 2)
            if not self.check_drbd_status(resource):
                self.collect_crm_report_file(start_time, self.conn.list_vplx_ssh[0])
                self.email.send_autotest_mail()
                utils.prt_log('', f"Finished to collect crm_report and exit testing ...", 2)
            utils.prt_log(self.conn.list_vplx_ssh[0], f"Down {device} on {ip_node} ...", 0)
            ip_obj.down_device(device)
            time.sleep(40)
            if not self.check_target_lun_status(target, resource, self.conn.list_vplx_ssh[1]):
                ip_obj.up_device(device)
                ip_obj.netplan_apply()
                time.sleep(30)
                self.collect_crm_report_file(start_time, self.conn.list_vplx_ssh[0])
                self.email.send_autotest_mail()
                utils.prt_log('', f"Finished to collect crm_report and exit testing ...", 2)
            utils.prt_log(self.conn.list_vplx_ssh[0], f"Up {device} on {ip_node} ...", 0)
            ip_obj.up_device(device)
            ip_obj.netplan_apply()
            time.sleep(30)
            if not self.check_drbd_status(resource):
                self.collect_crm_report_file(start_time, self.conn.list_vplx_ssh[0])
                self.email.send_autotest_mail()
                utils.prt_log('', f"Finished to collect crm_report and exit testing ...", 2)
            self.restore_resource(resource)
            if i == 1:
                self.collect_crm_report_file(start_time, self.conn.list_vplx_ssh[0])
                utils.prt_log(self.conn.list_vplx_ssh[0], f"Finished to collect crm_report", 0)
            utils.prt_log('', f"Wait 2 minutes to restore the original environment", 0)
            time.sleep(120)
        self.email.send_autotest_mail()

    def check_target_lun_status(self, target, resource, conn):
        flag = True
        tips = ''
        iscsi_obj = action.Iscsi(conn)
        crm_status = iscsi_obj.get_crm_status()
        error_message = get_crm_status_by_type(conn, crm_status, None, "FailedActions")
        if error_message:
            print(error_message)
            return False
        init_target_status = get_crm_status_by_type(conn, crm_status, target, "iSCSITarget")
        if init_target_status:
            if init_target_status[0] != 'Started':
                utils.prt_log(conn, f"Target status is {init_target_status[0]}", 1)
                return False
        else:
            utils.prt_log(conn, f"Can't get status of target {target}", 1)
            return False
        all_resource_status = get_crm_status_by_type(conn, crm_status, None, "AllLUN")
        if all_resource_status:
            self.lun_list.clear()
            for status in all_resource_status:
                self.lun_list.append(status[0])
                if resource == status[0]:
                    tips = '* '
                    if not init_target_status[1] == status[2]:
                        utils.prt_log(conn, f"Target and LUN is not started on the same node", 1)
                        flag = False
                if status[1] != 'Started':
                    utils.prt_log(conn, f"{tips}{status[0]} status is {status[1]}", 1)
                    flag = False
            if not flag:
                return False
        else:
            utils.prt_log(conn, f"Can't get crm status", 1)
            return False
        return True

    def check_drbd_status(self, resource):
        flag = True
        stor_obj = action.Stor(self.conn.list_vplx_ssh[1])
        if self.lun_list:
            all_lun_string = " ".join(self.lun_list)
        else:
            all_lun_string = resource
        resource_status_result = stor_obj.get_linstor_res(all_lun_string)
        resource_status = check_drbd_conns_status(self.conn.list_vplx_ssh[1], resource_status_result)
        for status in resource_status:
            if status[1] != "Ok":
                utils.prt_log(self.conn.list_vplx_ssh[1], f"Resource {status[0]} connection is {status[1]}", 1)
                flag = False
            if status[2] != "UpToDate" and status[2] != "Diskless":
                utils.prt_log(self.conn.list_vplx_ssh[1], f"Resource {status[0]} status is {status[2]}", 1)
                flag = False
        return flag

    def restore_resource(self, resource):
        conn = self.conn.list_vplx_ssh[1]
        init_start_node = self.node_list[0]
        iscsi_obj = action.Iscsi(conn)
        iscsi_obj.ref_res()
        time.sleep(10)
        utils.prt_log(conn, f"Move {resource} back to {init_start_node} ...", 0)
        iscsi_obj.move_res(resource, init_start_node)
        time.sleep(20)
        crm_status = iscsi_obj.get_crm_status()
        resource_status = get_crm_status_by_type(conn, crm_status, resource, "iSCSILogicalUnit")
        if resource_status:
            if resource_status[0] != 'Started' or resource_status[1] != init_start_node:
                utils.prt_log(conn,
                              f"Failed to move {resource}, status:{resource_status[0]}", 1)
        else:
            utils.prt_log(conn, f"Can't get status of resource {resource}", 1)
        iscsi_obj.unmove_res(resource)

    def collect_crm_report_file(self, time, conn):
        tmp_path = "/tmp/crm_report"
        crm_log_path = self.config.get_log_path()
        debug_log = action.DebugLog(conn)
        utils.prt_log(conn, f"Start to collect crm_report...", 0)
        debug_log.get_crm_report_file(time, tmp_path)
        debug_log.download_log(tmp_path, crm_log_path)
        debug_log.rm_log_dir(tmp_path)
