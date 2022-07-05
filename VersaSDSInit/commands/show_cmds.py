import control
import utils


class ShowCommands(object):
    def __init__(self, sub_parser):
        self.subp = sub_parser
        self.setup_parser()

    def setup_parser(self):
        parser_show = self.subp.add_parser(
            'status',
            aliases=['st'],
            help='Display the information of cluster/node system service and software'
        )
        parser_show.add_argument('node', nargs='?', default=None)
        parser_show.set_defaults(func=self.show_status)

    def show_status(self, args):
        controller = control.VersaSDSSoftConsole()

        iter_service_status = controller.get_all_service_status()
        table_status = utils.Table()
        table_status.header = ['node', 'drbd', 'linstor-satellite', 'linstor-controller',
                               'pacemaker', 'corosync', 'rtslib-fb-targetctl']
        for i in iter_service_status:
            if args.node:
                if args.node == i[0]:
                    table_status.add_data(i)
                    break
            else:
                table_status.add_data(i)

        iter_version = controller.get_version('sysos', 'syskernel', 'drbd', 'linstor', 'targetcli', 'pacemaker')
        table_version = utils.Table()
        table_version.header = ['node', 'os_system', 'kernel', 'drbd_kernel_version', 'linstor', 'targetcli',
                                'pacemaker']
        for i in iter_version:
            if args.node:
                if args.node == i[0]:
                    table_version.add_data(i)
                    break
            else:
                table_version.add_data(i)

        table_status.print_table()
        table_version.print_table()

    # 检查pacemaker集群的部署情况，暂时不使用show_status
    # TODO remove
    # def show_pacemaker_cluster(self, args):
    #     controller = control.PacemakerConsole()
    #     conf = utils.ConfFile()
    #     l_node = [i['hostname'] for i in conf.cluster['node']]
    #     l_corosync = ['T' if i else 'F' for i in controller.check_corosync()]
    #     l_packmaker = ['T' if i else 'F' for i in controller.check_packmaker()]
    #     l_targetcli = ['T' if i else 'F' for i in controller.check_targetcli()]
    #     l_service = ['T' if i else 'F' for i in controller.check_service()]
    #
    #     table = utils.Table()
    #     table.header = ['node', 'corosync', 'pacemaker', 'targetcli', 'service']
    #     for i in range(len(l_node)):
    #         table.add_data(
    #             [l_node[i], l_corosync[i], l_packmaker[i], l_targetcli[i], l_service[i]])
    #
    #     table.print_table()
    #     print()
