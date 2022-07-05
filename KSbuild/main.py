import argparse
import sys
import re

sys.path.append('../')
import consts

from commands import BuildCommands


class VersaKBSTools(object):
    def __init__(self):
        self.parser = argparse.ArgumentParser(prog='main')
        self.subp = self.parser.add_subparsers(metavar='', dest='subargs_init')
        self._build_cmds = BuildCommands(self.subp)
        self.setup_parser()

    def setup_parser(self):
        self.parser.add_argument('-v',
                                 '--version',
                                 dest='version',
                                 help='Show current version',
                                 action='store_true')
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


def main():
    try:
        cmd = VersaKBSTools()
        cmd.parse()
    except KeyboardInterrupt:
        sys.stderr.write("\nClient exiting (received SIGINT)\n")
    except PermissionError:
        sys.stderr.write("\nPermission denied (log file or other)\n")


if __name__ == '__main__':
    main()
