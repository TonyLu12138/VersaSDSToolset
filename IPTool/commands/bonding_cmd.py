import control


class BondingCommands(object):
    def __init__(self, sub_parser):
        self.subp = sub_parser
        self.setup_parser()

    def setup_parser(self):
        self.parser_bonding = self.subp.add_parser("bonding", aliases=['b', 'bond'], help="Bonding operation")
        subp_bonding = self.parser_bonding.add_subparsers()
        parser_apply = subp_bonding.add_parser('apply', help='Apply config file')
        parser_apply.add_argument('file', metavar='FILE', action='store', help='YAML file with IP config')

        parser_create = subp_bonding.add_parser('create', aliases=['c'], help='Create bonding')
        parser_create.add_argument('bonding', metavar='BONDING', action='store', help='Bonding name')
        parser_create.add_argument('-n',
                                   '--node',
                                   dest='node',
                                   action='store',
                                   help='Node (IP) for SSH connect')
        parser_create.add_argument('-p',
                                   '--password',
                                   dest='password',
                                   action='store',
                                   help='Password for SSH connect')
        parser_create.add_argument('-d',
                                   '--device',
                                   dest='device',
                                   nargs=2,
                                   action='store',
                                   required=True,
                                   help='Device name')
        parser_create.add_argument('-m',
                                   '--mode',
                                   dest='mode',
                                   action='store',
                                   choices=["balance-rr", "active-backup", "balance-xor", "broadcast", "802.3ad",
                                            "balance-tlb",
                                            "balance-alb"],
                                   required=True,
                                   help='Bonding mode')
        parser_create.add_argument('-ip',
                                   '--ip',
                                   dest='ip',
                                   action='store',
                                   required=True,
                                   help='Bonding ip')

        parser_delete = subp_bonding.add_parser('delete', aliases=['d', 'del'], help='Delete bonding')
        parser_delete.add_argument('bonding', metavar='BONDING', action='store', help='Bonding name')
        parser_delete.add_argument('-n',
                                   '--node',
                                   dest='node',
                                   action='store',
                                   help='Node (IP) for SSH connect')
        parser_delete.add_argument('-p',
                                   '--password',
                                   dest='password',
                                   action='store',
                                   help='Password for SSH connect')

        parser_modify = subp_bonding.add_parser('modify', aliases=['m', 'mod'], help='Modify bonding')
        parser_modify.add_argument('bonding', metavar='BONDING', action='store', help='Bonding name')
        parser_modify.add_argument('-n',
                                   '--node',
                                   dest='node',
                                   action='store',
                                   help='Node (IP) for SSH connect')
        parser_modify.add_argument('-p',
                                   '--password',
                                   dest='password',
                                   action='store',
                                   help='Password for SSH connect')
        parser_modify.add_argument('-m',
                                   '--mode',
                                   dest='mode',
                                   action='store',
                                   choices=["balance-rr", "active-backup", "balance-xor", "broadcast", "802.3ad",
                                            "balance-tlb", "balance-alb"],
                                   help='Bonding mode')
        parser_modify.add_argument('-ip',
                                   '--ip',
                                   dest='ip',
                                   action='store',
                                   help='Bonding IP')
        parser_modify.add_argument('-d',
                                   '--device',
                                   dest='device',
                                   nargs=2,
                                   action='store',
                                   help='Bonding device')

        parser_apply.set_defaults(func=self.apply_file)
        parser_create.set_defaults(func=self.create)
        parser_delete.set_defaults(func=self.delete)
        parser_modify.set_defaults(func=self.modify)
        self.parser_bonding.set_defaults(func=self.print_bond_help)

    def apply_file(self, args):
        bonding = control.Bonding()
        bonding.configure_bonding_by_file(args.file)

    def create(self, args):
        conn = control.get_ssh_conn(args.node, args.password)
        bonding = control.Bonding()
        bonding.create_bonding(conn, args.bonding, args.mode, args.device, args.ip)

    def delete(self, args):
        conn = control.get_ssh_conn(args.node, args.password)
        bonding = control.Bonding()
        bonding.del_bonding(conn, args.bonding)

    def modify(self, args):
        conn = control.get_ssh_conn(args.node, args.password)
        bonding = control.Bonding()
        if args.mode:
            bonding.modify_bonding_mode(conn, args.bonding, args.mode)
        if args.ip:
            bonding.modify_bonding_ip(conn, args.bonding, args.ip)
        if args.device:
            bonding.modify_bonding_slave(conn, args.bonding, args.device)
        if not any([args.mode, args.ip, args.device]):
            print("No configuration item to be modified is selected.")

    def print_bond_help(self, *args):
        self.parser_bonding.print_help()
