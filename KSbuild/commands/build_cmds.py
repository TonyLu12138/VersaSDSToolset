import control
import argparse
import sys

INSTALL_FLAG = False


class BuildCommands(object):
    def __init__(self, sub_parser):
        self.subp = sub_parser
        self.setup_parser()

    def setup_parser(self):
        parser_build = self.subp.add_parser("build", aliases=['b'],
                                            help="Configure the KBS cluster")
        parser_build.set_defaults(func=self.build_all)
        parser_build.add_argument(
            '-test',
            dest='test',
            action='store_true',
            help=argparse.SUPPRESS,
            default=False)

        subp_build = parser_build.add_subparsers(dest='subargs_build')

        p_ha = subp_build.add_parser('HA', aliases=['ha'], help='build HA')
        p_ha.set_defaults(func=self.build_ha)

        p_cluster = subp_build.add_parser('cluster', aliases=['c'], help='build cluster')
        p_cluster.set_defaults(func=self.build_cluster)
        p_cluster.add_argument(
            '-test',
            dest='test',
            action='store_true',
            help=argparse.SUPPRESS,
            default=False)

        p_ks = subp_build.add_parser('ks', help='build ks cluster')
        p_ks.set_defaults(func=self.build_ks_cluster)

        p_vtel = subp_build.add_parser('vtel', help='build VersaTEL')
        p_vtel.set_defaults(func=self.build_vtel)

    def build_all(self, args):
        self.build_ha(args)
        self.build_cluster(args)

    def build_cluster(self, args):
        self.change_sources(args)
        controller = control.KSConsole()
        print("Build cluster ...")
        print(" Set off swap")
        controller.set_swap()
        # if args.test:
        #     print('Add linbit-drbd ...')
        #     controller.install_drbd_spc()
        print(" Install software")
        controller.install_docker(args.test)
        if args.test:
            controller.replace_linbit_sources()
            controller.apt_update()
        controller.install()
        if args.test:
            controller.recovery_linbit_sources()
            controller.apt_update()
        print(' Start to synchronised time')
        controller.sync_time()
        print(" Configure LINSTOR")
        controller.create_linstor_conf_file()
        controller.add_to_linstor_cluster()
        self.build_ks_cluster(args)
        self.build_vtel(args)

    def build_ks_cluster(self, args):
        print(" Build KS cluster")
        controller = control.KSConsole()
        controller.modify_kk()
        controller.build_ks()

    def build_vtel(self, args):
        print(" Build VersaTEL")
        controller = control.KSConsole()
        controller.set_linstor_server()

    def build_ha(self, args):
        self.change_sources(args)
        print("Configure HA load balancing ...")
        controller = control.KSConsole()
        print(" Configure Keepalived ...")
        controller.install_keepalived()
        controller.modify_keepalived()
        controller.check_apiserver()
        controller.restart_keepalived()
        print(" Configure HAproxy ...")
        controller.install_haproxy()
        controller.modify_haproxy()
        controller.restart_haproxy()

    def change_sources(self, args):
        global INSTALL_FLAG
        controller = control.KSConsole()
        if not INSTALL_FLAG:
            if not args.test:
                print("Replace sources")
                controller.replace_sources()
            controller.bak_sources_files()
            print("Update apt ...")
            controller.apt_update()
        INSTALL_FLAG = True
