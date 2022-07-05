import control
import argparse

INSTALL_FLAG = False


class InstallCommands(object):
    def __init__(self, sub_parser):
        self.subp = sub_parser
        self.setup_parser()

    def setup_parser(self):
        parser_install = self.subp.add_parser(
            'install',
            help='Install VersaSDS software'
        )
        parser_install.add_argument(
            '-t',
            '-test',
            dest='test',
            action='store_true',
            help=argparse.SUPPRESS,
            default=False)

        subp_install = parser_install.add_subparsers(dest='subargs_install')

        p_linbit = subp_install.add_parser('linbit', help='install software of linbit')
        p_linbit.add_argument(
            '-t',
            '-test',
            dest='test',
            action='store_true',
            help=argparse.SUPPRESS,
            default=False)
        p_linbit.set_defaults(func=self.install_linbit)

        p_lvm2 = subp_install.add_parser('lvm2', help='install lvm2')
        p_lvm2.add_argument(
            '-t',
            '-test',
            dest='test',
            action='store_true',
            help=argparse.SUPPRESS,
            default=False)
        p_lvm2.set_defaults(func=self.install_lvm2)

        p_pacemaker = subp_install.add_parser('pacemaker', help='install pacemaker')
        p_pacemaker.add_argument(
            '-t',
            '-test',
            dest='test',
            action='store_true',
            help=argparse.SUPPRESS,
            default=False)
        p_pacemaker.set_defaults(func=self.install_pacemaker)

        p_targetcli = subp_install.add_parser('targetcli', help='install targetcli')
        p_targetcli.add_argument(
            '-t',
            '-test',
            dest='test',
            action='store_true',
            help=argparse.SUPPRESS,
            default=False)
        p_targetcli.set_defaults(func=self.install_targetcli)

        parser_install.set_defaults(func=self.install_software)

    @classmethod
    def install_linbit(cls, args):
        cls.change_sources(args)
        sc = control.VersaSDSSoftConsole()
        # if args.test:
        #     print('Add linbit-drbd ...')
        #     result = sc.install_spc()
        #     if not all(result):
        #         print("Failed to add linbit-drbd，exit")
        #         sys.exit(1)
        if args.test:
            sc.replace_linbit_sources()
            sc.apt_update()
        print('Start install software of DRBD')
        sc.install_drbd()
        print('Start install software of LINSTOR')
        sc.install_linstor()
        if args.test:
            sc.recovery_linbit_sources()
            sc.apt_update()

    @classmethod
    def install_lvm2(cls, args):
        cls.change_sources(args)
        sc = control.VersaSDSSoftConsole()
        print('Start install software of LVM')
        sc.install_lvm2()

    @classmethod
    def install_pacemaker(cls, args):
        cls.change_sources(args)
        sc = control.VersaSDSSoftConsole()
        print('Start install software of Pacemaker')
        sc.install_pacemaker()

    @classmethod
    def install_targetcli(cls, args):
        cls.change_sources(args)
        sc = control.VersaSDSSoftConsole()
        print('Start install software of targetcli')
        sc.install_targetcli()

    @classmethod
    def install_software(cls, args):
        print('* Start install software *')
        cls.install_linbit(args)
        cls.install_lvm2(args)
        cls.install_pacemaker(args)
        # cls.install_targetcli(args)
        print('* Success in installing software *')

    @classmethod
    def change_sources(cls, args):
        global INSTALL_FLAG
        sc = control.VersaSDSSoftConsole()
        if not INSTALL_FLAG:
            if not args.test:
                sc.replace_sources()
                sc.bak_sources_files()
            print("Update apt ...")
            sc.apt_update()
        INSTALL_FLAG = True
