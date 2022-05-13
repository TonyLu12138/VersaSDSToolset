import control


class ClearCommands():
    def __init__(self, sub_parser):
        self.subp = sub_parser
        self.parser = self.setup_parser()

    def setup_parser(self):
        parser_clear = self.subp.add_parser(
            'clear',
            help='clear VersaSDS configuration'
        )
        # parser_clear.add_argument('node',nargs = '?',default = None)
        subp_clear = parser_clear.add_subparsers(dest='subargs_clear')

        p_crm = subp_clear.add_parser('crm', help='clear crm cluster resources')
        p_crm.add_argument('node', nargs='?', default=None)
        p_crm.set_defaults(func=self.clear_crm)

        p_vg = subp_clear.add_parser('vg', help='clear vg that used to create the linstordb')
        p_vg.set_defaults(func=self.clear_vg)

        p_corosync = subp_clear.add_parser('corosync', help='restore default configuration of corosync')
        p_corosync.set_defaults(func=self.clear_corosync_node_conf)

        # TODO remove args
        # p_linstordb = subp_clear.add_parser('linstordb', aliases=['ldb'], help='clear linstordb')
        # p_linstordb.set_defaults(func=self.clear_linstordb)

        parser_clear.set_defaults(func=self.clear_all)

    def clear_crm(self, args):
        sc = control.PacemakerConsole()
        print('清除 crm 集群的相关资源')
        if args.subargs_clear:
            sc.clear_crm_res(args.node)
        else:
            sc.clear_crm_res()

    def clear_corosync_node_conf(self, args):
        self.clear_corosync(args)
        self.clear_crm_node(args)

    def clear_crm_node(self, args):
        sc = control.PacemakerConsole()
        print("清除 crm 节点")
        sc.clear_crm_node()

    def clear_vg(self, args):
        sc = control.LVMConsole()
        print('清除 vg')
        sc.remove_vg()

    # TODO Unused function
    # @classmethod
    # def clear_linstordb(self):
    #     controller = control.LinstorConsole()
    #     controller.destroy_linstordb()

    def clear_corosync(self, args):
        sc = control.PacemakerConsole()
        print('恢复 corosync 配置文件')
        sc.recover_corosync_conf()

    def restart_linstor(self, args):
        sc = control.LinstorConsole()
        print('重启 linstor 集群的 controller 和 satellite')
        sc.restart_linstor()

    def clear_all(self, args):
        print('*start*')
        self.clear_crm(args)
        self.clear_vg(args)
        self.clear_corosync_node_conf(args)
        self.restart_linstor(args)
        print('*success*')
