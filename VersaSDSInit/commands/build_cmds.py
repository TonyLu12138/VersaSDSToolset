import sys
import time

import action
import control
from .install_cmds import InstallCommands


class BuildCommands():
    def __init__(self, sub_parser):
        self.subp = sub_parser
        self.setup_parser()

    def setup_parser(self):
        parser_build = self.subp.add_parser("build", help="Configure the components of the pacemaker cluster")
        parser_build.add_argument('-sp', default='pool0')
        parser_build.set_defaults(func=self.build_all)

        subp_build = parser_build.add_subparsers(dest='subargs_build')

        p_ip = subp_build.add_parser('ip', help='set up ip')
        p_ip.set_defaults(func=self.build_ip)

        p_hostname = subp_build.add_parser('hostname', help='modify hostname')
        p_hostname.set_defaults(func=self.build_hostname)

        p_ssh = subp_build.add_parser('ssh', help='build ssh connetc')
        p_ssh.set_defaults(func=self.build_ssh)

        p_corosync = subp_build.add_parser('corosync', help='build corosync')
        p_corosync.set_defaults(func=self.build_corosync)

        p_pacemaker = subp_build.add_parser('pacemaker', help='build pacemaker')
        p_pacemaker.set_defaults(func=self.build_pacemaker)

        p_targetcli = subp_build.add_parser('targetcli', help='build targetcli')
        p_targetcli.set_defaults(func=self.build_targetcli)

        p_service = subp_build.add_parser('service', help='build service')
        p_service.set_defaults(func=self.build_service)

        p_ra = subp_build.add_parser('ra', help='build ra')
        p_ra.set_defaults(func=self.build_ra)

        p_pool = subp_build.add_parser('pool', help='build pool')
        p_pool.add_argument('-sp', default='pool0')
        p_pool.set_defaults(func=self.build_pool)

        p_controller = subp_build.add_parser('controller', help='build HA linstor-controller')
        p_controller.add_argument('-sp', default='pool0')
        p_controller.set_defaults(func=self.build_controller)

        p_drbd_attr = subp_build.add_parser('drbdattr', help='build drbd-attr')
        p_drbd_attr.set_defaults(func=self.build_drbd_attr)

    def build_ip(self, args):
        controller = control.PacemakerConsole()
        print('start to set private ip')
        controller.set_ip_on_device()

    def build_hostname(self, args):
        controller = control.PacemakerConsole()
        print('start to modify hostname')
        controller.modify_hostname()

    def build_ssh(self, args):
        controller = control.PacemakerConsole()
        print('start to build ssh connect')
        controller.ssh_conn_build()  # ssh免密授权

    def build_corosync(self, args):
        controller = control.PacemakerConsole()
        print('start to synchronised time')
        controller.sync_time()
        print('start to set up corosync')
        controller.corosync_conf_change()
        print('start to restart corosync')
        controller.restart_corosync()
        print('check corosync, please wait')
        if all(controller.check_corosync()):
            print('successfully configure corosync')
            print('set up cluster name')
            controller.modify_cluster_name()
        else:
            print('failed to configure corosync')
            sys.exit()

    def build_pacemaker(self, args):
        controller = control.PacemakerConsole()
        print('start to set up pacemaker')
        controller.pacmaker_conf_change()
        if all(controller.check_pacemaker()):
            print('successfully configure pacemaker')
        else:
            print('failed to configure pacemaker')
            sys.exit()

    def build_targetcli(self, args):
        # conf and check targecli
        controller = control.PacemakerConsole()
        t_beginning = time.time()
        timeout = 30
        while True:
            controller.targetcli_conf_change()
            if all(controller.check_targetcli()):
                print('successfully configure targetcli')
                break
            seconds_passed = time.time() - t_beginning
            if timeout and seconds_passed > timeout:
                raise TimeoutError("failed to configure targetcli")

    def build_service(self, args):
        controller = control.PacemakerConsole()
        print('start to set up service')
        controller.service_set()
        if all(controller.check_service()):
            print('successfully configure service')
        else:
            print('failed to configure service')
            sys.exit()

    def build_ra(self, args):
        controller = control.PacemakerConsole()
        print('start to replace RA')
        controller.replace_ra()
        if all(controller.check_ra()):
            print('successfully replace RA')
        else:
            print('failed to replace RA')
            sys.exit()

    def build_pacemaker_cluster(self, args):
        print('*start*')
        self.build_ip(args)
        self.build_hostname(args)
        self.build_ssh(args)
        self.build_corosync(args)
        self.build_pacemaker(args)
        self.build_targetcli(args)
        self.build_service(args)
        self.build_ra(args)
        print('*success*')

    def build_pool(self, args):
        controller_lvm = control.LVMConsole()
        controller_linstor = control.LinstorConsole()
        print("*start")
        controller_lvm.create_dirver_pool()
        print('创建PV/VG/LV成功')
        controller_linstor.create_conf_file()
        controller_linstor.create_nodes()
        print('创建节点成功')
        if args.sp:
            controller_linstor.create_pools(args.sp)
        else:
            controller_linstor.create_pools()
        print('*success*')

    def build_controller(self, args):
        controller = control.LinstorConsole()
        print('*start*')
        print("start to build HA controller")
        if args.sp:
            controller.build_ha_controller(args.sp)
        else:
            controller.build_ha_controller()
        print('Finish configuration，checking')
        if not controller.check_ha_controller():
            print('Fail，exit')
            sys.exit()
        print('*success*')

    def build_drbd_attr(self, args):
        print('*start*')
        pcm = action.Pacemaker()
        pcm.config_drbd_attr()
        print('*success*')

    def build_all(self, args):
        controller_lvm = control.LVMConsole()
        controller_linstor = control.LinstorConsole()

        InstallCommands.install_software(args)
        print("1. 安装软件完成")
        self.build_pacemaker_cluster(args)
        print("2. 配置pacemaker集群完成")
        controller_lvm.create_dirver_pool()
        print('创建PV/VG/LV成功')
        controller_linstor.create_conf_file()
        controller_linstor.create_nodes()
        print('创建节点成功')
        controller_linstor.create_pools('pool0')
        print('创建存储池pool0成功')
        self.build_controller(args)
        print("3. HA Controller配置完成")
        self.build_drbd_attr(args)
        print("4. drbd-attr 配置完成")
