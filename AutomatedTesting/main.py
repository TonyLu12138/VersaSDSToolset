import argparse
import sys
import utils
import control
import log

sys.path.append('../')
import consts


class AutomatedTesting(object):
    def __init__(self):
        self.parser = argparse.ArgumentParser(prog='main')
        self.setup_parser()

    def setup_parser(self):
        subp = self.parser.add_subparsers(metavar='', dest='subargs_autotest')

        self.parser.add_argument('-v',
                                 '--version',
                                 dest='version',
                                 help='Show current version',
                                 action='store_true')

        parser_apply = subp.add_parser("apply", help="Apply config file of Auto Test")
        parser_apply.add_argument('file', metavar='FILE', action='store', help='YAML file with IP config')

        parser_apply.set_defaults(func=self.apply_file)

        self.parser.set_defaults(func=self.main_usage)

    def print_help(self, args):
        self.parser.print_help()

    def main_usage(self, args):
        if args.version:
            print(f'Version: {consts.VERSION}')
        else:
            self.print_help(self.parser)

    def parse(self):  # 调用入口
        args = self.parser.parse_args()
        args.func(args)

    def apply_file(self, args):
        utils._init()
        logger = log.Log()
        utils.set_logger(logger)
        config = utils.ConfFile(args.file)
        test_mode = config.get_test_mode()
        if test_mode == 'quorum':
            test_quorum = control.QuorumAutoTest(config)
            # test_quorum.ssh_conn_build()
            test_quorum.test_drbd_quorum()
        if test_mode == 'drbd_in_used':
            test_iscsi = control.IscsiTest(config)
            test_iscsi.test_drbd_in_used()


def main():
    try:
        cmd = AutomatedTesting()
        cmd.parse()
    except KeyboardInterrupt:
        sys.stderr.write("\nClient exiting (received SIGINT)\n")
    except PermissionError:
        sys.stderr.write("\nPermission denied (log file or other)\n")


if __name__ == '__main__':
    main()
