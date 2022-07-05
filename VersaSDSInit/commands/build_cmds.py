import sys
import time
import control
import argparse
from .install_cmds import InstallCommands


class BuildCommands(object):
    def __init__(self, sub_parser):
        self.subp = sub_parser
        self.setup_parser()

    def setup_parser(self):
        parser_build = self.subp.add_parser("build", help="Configure the components of the pacemaker cluster")
        parser_build.add_argument('-sp', default='pool0')
        parser_build.set_defaults(func=self.build_all)
        parser_build.add_argument(
            '-t',
            '-test',
            dest='test',
            action='store_true',
            help=argparse.SUPPRESS,
            default=False)

        subp_build = parser_build.add_subparsers(dest='subargs_build')

        p_corosync = subp_build.add_parser('corosync', help='build corosync')
        p_corosync.set_defaults(func=self.build_corosync)

        p_pacemaker = subp_build.add_parser('pacemaker', help='build pacemaker')
        p_pacemaker.set_defaults(func=self.build_pacemaker)

        p_service = subp_build.add_parser('service', help='build service')
        p_service.set_defaults(func=self.build_service)

        p_pool = subp_build.add_parser('pool', help='build pool')
        p_pool.add_argument('-sp', default='pool0')
        p_pool.set_defaults(func=self.build_pool)

        p_controller = subp_build.add_parser('controller', help='build HA linstor-controller')
        p_controller.add_argument('-sp', default='pool0')
        p_controller.set_defaults(func=self.build_controller)

        p_drbd_attr = subp_build.add_parser('drbdattr', help='build drbd-attr')
        p_drbd_attr.set_defaults(func=self.build_drbd_attr)

        p_ra = subp_build.add_parser('ra', help='build iSCSILogicalUnit ra')
        p_ra.set_defaults(func=self.build_ra)

        p_targetcli = subp_build.add_parser('targetcli', help='build targetcli')
        p_targetcli.set_defaults(func=self.build_targetcli)

    def build_corosync(self, args):
        controller = control.PacemakerConsole()
        print('Start to synchronised time')
        controller.sync_time()
        # TODO get Corosync file from cluster node
        print('Start to set up corosync')
        controller.corosync_conf_change()
        print('Start to restart corosync')
        controller.restart_corosync()
        time.sleep(2)
        print('Check corosync, please wait')
        if all(controller.check_corosync()):
            print('Successfully configure corosync')
            print('Set up cluster name')
            controller.modify_cluster_name()
        else:
            print('Failed to configure corosync')
            sys.exit()

    def build_pacemaker(self, args):
        controller = control.PacemakerConsole()
        print('Start to set up pacemaker')
        controller.pacmaker_conf_change()
        if all(controller.check_pacemaker()):
            print('Successfully configure pacemaker')
        else:
            print('Failed to configure pacemaker')
            sys.exit()

    def build_targetcli(self, args):
        # conf and check targecli
        controller = control.PacemakerConsole()
        t_beginning = time.time()
        timeout = 30
        while True:
            controller.targetcli_conf_change()
            if all(controller.check_targetcli()):
                print('Successfully configure targetcli')
                break
            seconds_passed = time.time() - t_beginning
            if timeout and seconds_passed > timeout:
                raise TimeoutError("Failed to configure targetcli")

    def build_service(self, args):
        controller = control.PacemakerConsole()
        print('Start to set up service')
        controller.service_set()
        if all(controller.check_service()):
            print('Successfully configure service')
        else:
            print('Failed to configure service')
            sys.exit()

    # TODO get RA from FreeNAS
    def build_ra(self, args):
        controller = control.PacemakerConsole()
        print('Start to replace RA')
        controller.replace_ra()
        if all(controller.check_ra()):
            print('Successfully replace RA')
        else:
            print('Failed to replace RA')
            sys.exit()

    def build_pacemaker_cluster(self, args):
        print('* Start to build pacemaker cluster *')
        self.build_corosync(args)
        self.build_pacemaker(args)
        self.build_service(args)
        # self.build_ra(args)
        # self.build_targetcli(args)
        print('* Success *')

    def build_pool(self, args):
        controller_lvm = control.LVMConsole()
        controller_linstor = control.LinstorConsole()
        print("* Start to build pool *")
        controller_lvm.create_dirver_pool()
        print(' Success in creating PV/VG/LV')
        controller_linstor.create_conf_file()
        print(' Success in creating linstor-client.conf')
        controller_linstor.create_nodes()
        print(' Success in creating Node')
        controller_linstor.create_pools(args.sp)
        print(f' Success in creating storagepool {args.sp}')
        print('* Success *')

    def build_controller(self, args):
        controller = control.LinstorConsole()
        print('* Start to build controller *')
        print("Start to build HA controller")
        controller.build_ha_controller(args.sp)
        print('Finish configuration，checking')
        if not controller.check_ha_controller():
            print('** Fail，exit **')
            sys.exit()
        print('* Success *')

    def build_drbd_attr(self, args):
        print('* Start to build drbd_attr*')
        pcm = control.PacemakerConsole()
        pcm.set_drbd_attr()
        print('* Success *')

    def build_all(self, args):
        InstallCommands.install_software(args)
        print("1. Complete software installation\n")
        self.build_pacemaker_cluster(args)
        print("2. Complete Pacemaker cluster configuration\n")
        self.build_pool(args)
        self.build_controller(args)
        print("3. Complete HA Controller configuration\n")
