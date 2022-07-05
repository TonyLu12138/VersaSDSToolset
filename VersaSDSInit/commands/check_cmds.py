import control
import utils


class CheckCommands(object):
    def __init__(self, sub_parser):
        self.subp = sub_parser
        self.setup_parser()

    def setup_parser(self):
        parser_check = self.subp.add_parser(
            'check',
            aliases=['ck'],
            help='Check the consistency of the software version'
        )
        parser_check.set_defaults(func=self.check_version)

    def check_version(self, args):
        controller = control.VersaSDSSoftConsole()
        iter_version = controller.get_version('drbd', 'linstor', 'targetcli', 'pacemaker', 'corosync')

        dict_all = {'node': [], 'drbd': [], 'linstor': [], 'targetcli': [], 'pacemaker': [], 'corosync': []}
        for i in iter_version:
            dict_all['node'].append(i[0])
            dict_all['drbd'].append(i[1])
            dict_all['linstor'].append(i[2])
            dict_all['targetcli'].append(i[3])
            dict_all['pacemaker'].append(i[4])
            dict_all['corosync'].append(i[5])

        flag = []
        diff_version = []
        for k, v in dict_all.items():
            if len(set(v)) == 1 and v[0] is not None:
                flag.append([k, True])
            else:
                flag.append([k, False])
                diff_version.append([k, v])

        flag.pop(0)

        table_soft_check = utils.Table()
        table_soft_check.header = ['software', 'result']
        for i in flag:
            table_soft_check.add_data(i)

        table_soft_check.print_table()

        if len(diff_version) > 1:
            table_version = utils.Table()
            table_version.header = []
            for i in diff_version:
                table_version.header.append(i[0])
                table_version.add_column(i[0], i[1])
            table_version.print_table()
