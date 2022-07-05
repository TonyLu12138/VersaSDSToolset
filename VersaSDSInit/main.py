import argparse
import sys

sys.path.append('../')
import consts

from commands import (
    CheckCommands,
    InstallCommands,
    BuildCommands,
    ShowCommands,
    BackupCommands,
    ClearCommands,
    UninstallCommands
)


class VersaSDSTools(object):
    def __init__(self):
        self.parser = argparse.ArgumentParser(prog='main')
        self.subp = self.parser.add_subparsers(metavar='', dest='subargs_init')
        self._check_cmds = CheckCommands(self.subp)
        self._install_cmds = InstallCommands(self.subp)
        self._build_cmds = BuildCommands(self.subp)
        self._back_cmds = BackupCommands(self.subp)
        self._show_cmds = ShowCommands(self.subp)
        self._clear_cmds = ClearCommands(self.subp)
        self._uninstall_cmds = UninstallCommands(self.subp)
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
    # if os.geteuid() != 0:
    #     print('This program must be run as root. Aborting.')
    #     sys.exit()
    try:
        cmd = VersaSDSTools()
        cmd.parse()
    except KeyboardInterrupt:
        sys.stderr.write("\nClient exiting (received SIGINT)\n")
    except PermissionError:
        sys.stderr.write("\nPermission denied (log file or other)\n")


if __name__ == '__main__':
    main()
