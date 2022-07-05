# -*- coding: utf-8 -*-
import argparse
import sys

sys.path.append('../')
import consts
from commands import (
    BondingCommands,
    NormalIPCommands
)


class IPTool(object):
    def __init__(self):
        self.parser = argparse.ArgumentParser(prog='main')
        self.subp = self.parser.add_subparsers(metavar='', dest='subargs_ip_setting')
        self._bonding_cmd = BondingCommands(self.subp)
        self._normal_cmd = NormalIPCommands(self.subp)
        self.setup_parser()

    def setup_parser(self):

        self.parser.add_argument('-v',
                                 '--version',
                                 dest='version',
                                 help='Show current version',
                                 action='store_true')
        self.parser.set_defaults(func=self.main_usage)

    def main_usage(self, args):
        if args.version:
            print(f'Version: {consts.VERSION}')
        else:
            self.parser.print_help()

    def parse(self):  # 调用入口
        args = self.parser.parse_args()
        args.func(args)


def main():
    try:
        cmd = IPTool()
        cmd.parse()
    except KeyboardInterrupt:
        sys.stderr.write("\nClient exiting (received SIGINT)\n")
    except PermissionError:
        sys.stderr.write("\nPermission denied (log file or other)\n")


if __name__ == '__main__':
    main()
