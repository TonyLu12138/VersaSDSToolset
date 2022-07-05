# -*- coding:utf-8 -*-
import subprocess
import os
import re
import sys


def init_global():
    global _SUDO_SRTING
    _SUDO_SRTING = ''


def set_sudo(password):
    global _SUDO_SRTING
    _SUDO_SRTING = f"echo {password} | sudo -S"


def get_sudo():
    return _SUDO_SRTING


def exec_cmd(cmd):
    """subprocess执行命令"""
    sudo_string = get_sudo()
    cmd = f"{sudo_string} {cmd}"
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    if p.returncode == 0:
        result = p.stdout
        result = result.decode() if isinstance(result, bytes) else result
        # print("result", result)
        return {"st": True, "rt": result.rstrip('\n')}
    else:
        print(f"  Failed to execute command: {cmd}")
        print("  Error message:\n", p.stderr)
        return {"st": False, "rt": p.stderr}


def get_file(path, type=None):
    """通过路径获取路径下的文件名"""
    file_list = []
    if type:
        for file in os.listdir(path):
            if os.path.splitext(file)[1] == f".{type}":
                file_list.append(file)
    else:
        return os.listdir(path)
    return file_list


def guide_check(target, default):
    flag = True
    for i in range(3):
        a = input(f"Input the value of '{target}' (default [{default}]): ")
        if a.strip() == "":
            return default
        elif a.strip() == "exit":
            sys.exit()
        else:
            if target in ["Gateway", "IP"]:
                if check_ip(a):
                    return a
                else:
                    flag = False
            if target in ["Hostname"]:
                if check_hostname(a):
                    return a
                else:
                    flag = False
            if flag:
                return a
            else:
                if i < 2:
                    print(f"Please check the format of {target}. Enter again or enter 'exit' to quit")
                else:
                    print("Three times for error input, exit the program.")
                    sys.exit()


def check_ip(ip):
    """检查IP格式"""
    re_ip = re.compile(
        r'^((2([0-4]\d|5[0-5]))|[1-9]?\d|1\d{2})(\.((2([0-4]\d|5[0-5]))|[1-9]?\d|1\d{2})){3}$')
    result = re_ip.match(ip)
    if result:
        return True


def check_hostname(name):
    """检查IP格式"""
    re_name = re.compile(r'^[a-z][a-z\d-]*[a-z\d]+$')
    result = re_name.match(name)
    if result:
        return True
    else:
        print(
            "\nAt least two letters, beginning with a letter and ending with a letter or number, which can contain letters, numbers and horizontal lines\n")
