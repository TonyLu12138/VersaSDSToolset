import control


class UninstallCommands(object):
    def __init__(self, sub_parser):
        self.subp = sub_parser
        self.setup_parser()

    def setup_parser(self):
        parser_install = self.subp.add_parser(
            'uninstall',
            help='Uninstall VersaSDS software'
        )
        subp_install = parser_install.add_subparsers(dest='subargs_uninstall')

        p_linbit = subp_install.add_parser('linbit', help='uninstall software of linbit')
        p_linbit.set_defaults(func=self.uninstall_linbit)

        p_lvm2 = subp_install.add_parser('lvm2', help='uninstall lvm2')
        p_lvm2.set_defaults(func=self.uninstall_lvm2)

        p_pacemaker = subp_install.add_parser('pacemaker', help='uninstall pacemaker')
        p_pacemaker.set_defaults(func=self.uninstall_pacemaker)

        p_targetcli = subp_install.add_parser('targetcli', help='uninstall targetcli')
        p_targetcli.set_defaults(func=self.uninstall_targetcli)

        parser_install.set_defaults(func=self.uninstall_software)

    def uninstall_linbit(self, args):
        sc = control.VersaSDSSoftConsole()
        print('Uninstall DRBD')
        sc.uninstall_drbd()
        print('Uninstall LINSTOR')
        sc.uninstall_linstor()

    def uninstall_lvm2(self, args):
        sc = control.VersaSDSSoftConsole()
        print('Uninstall LVM')
        sc.uninstall_lvm2()

    def uninstall_pacemaker(self, args):
        sc = control.VersaSDSSoftConsole()
        print('Uninstall Pacemaker')
        sc.uninstall_pacemaker()

    def uninstall_targetcli(self, args):
        sc = control.VersaSDSSoftConsole()
        print('Uninstall targetcli')
        sc.uninstall_targetcli()

    def uninstall_software(self, args):
        print('* Start to uninstall software *')
        self.uninstall_lvm2(args)
        self.uninstall_linbit(args)
        self.uninstall_pacemaker(args)
        # self.uninstall_targetcli(args)
        print('* Success in uninstalling software *')
